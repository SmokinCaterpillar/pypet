"""Module containing wrappers for multiprocessing"""

__author__ = 'Robert Meyer'

try:
    from thread import error as ThreadError
except ImportError:
    # Python 3 Syntax
    from threading import ThreadError
try:
    import queue
except ImportError:
    import Queue as queue
try:
    import cPickle as pickle
except ImportError:
    import pickle
try:
    import zmq
except ImportError:
    zmq = None

from collections import deque
import copy as cp
import gc
import sys
from threading import ThreadError
import time
import os
import socket

import pypet.pypetconstants as pypetconstants
from pypet.pypetlogging import HasLogger
from pypet.utils.decorators import retry


class MultiprocWrapper(object):
    """Abstract class definition of a Wrapper.

    Note that only storing is required, loading is optional.

    ABSTRACT: Needs to be defined in subclass

    """
    @property
    def is_open(self):
        """ Normally the file is opened and closed after each insertion.

        However, the storage service may provide to keep the store open and signals
        this via this property.

        """
        return False

    @property
    def multiproc_safe(self):
        """This wrapper guarantees multiprocessing safety"""
        return True

    def store(self, *args, **kwargs):
        raise NotImplementedError('Implement this!')


class LockerServer(HasLogger):

    PING = 'PING'
    PONG = 'PONG'
    DONE = 'DONE'
    LOCK = 'LOCK'
    RELEASE_ERROR = 'RELEASE_ERROR'
    MSG_ERROR = 'MSG_ERROR'
    UNLOCK = 'UNLOCK'
    UNLOCKED = 'UNLOCKED'
    GO = 'GO'
    WAIT = 'WAIT'
    DELIMITER = ':'
    DEFAULT_LOCK = '_DEFAULT_'
    CLOSE = 'CLOSE'

    def __init__(self, url="tcp://*:7777"):
        self._locks = {}
        self._url = url
        self._set_logger()

    def _lock(self, name, id_):
        if name not in self._locks:
            self._locks[name] = id_
            return self.GO
        else:
            return self.WAIT

    def _unlock(self, name, id_):
        locker_id = self._locks[name]
        if locker_id != id_:
            response = (self.RELEASE_ERROR + self.DELIMITER +
                        'Lock was acquired by `%s` and not by `%s`.' % (locker_id, id_))
            self._logger.error(response)
            return response
        else:
            del self._locks[name]
            return self.UNLOCKED

    def run(self):
        """Runs Server"""
        try:
            self._logger.info('Starting Lock Server')
            context = zmq.Context()
            socket_ = context.socket(zmq.REP)
            socket_.bind(self._url)
            while True:

                msg = socket_.recv_string()
                name = None
                id_ = None
                if self.DELIMITER in msg:
                    msg, name, id_ = msg.split(self.DELIMITER)
                if msg == self.DONE:
                    socket_.send_string(self.CLOSE + self.DELIMITER + 'Closing Lock Server')
                    self._logger.info('Closing Lock Server')
                    break
                elif msg == self.LOCK:
                    if name is None or id_ is None:
                        response = (self.MSG_ERROR + self.DELIMITER +
                                    'Please provide name and id for locking')
                        self._logger.error(response)
                    else:
                        response = self._lock(name, id_)
                    socket_.send_string(response)
                elif msg == self.UNLOCK:
                    if name is None or id_ is None:
                        response = (self.MSG_ERROR + self.DELIMITER +
                                    'Please provide name and id for unlocking')
                        self._logger.error(response)
                    else:
                        response = self._unlock(name, id_)
                    socket_.send_string(response)
                elif msg == self.PING:
                    socket_.send_string(self.PONG)
                else:
                    response = self.MSG_ERROR + self.DELIMITER + 'MSG `%s` not understood' % msg
                    self._logger.error(response)
                    socket_.send_string(response)
        except Exception:
            self._logger.exception('Crashed Lock Server!')
            raise


class LockerClient(object):
    """ Implements a Lock by requesting from LockServer"""

    SLEEP = 0.01

    def __init__(self, url="tcp://localhost:7777", lock_name=LockerServer.DEFAULT_LOCK):
        self.lock_name = lock_name
        self.url = url
        self._context = None
        self._socket = None
        self.id = None

    def __getstate__(self):
        result_dict = self.__dict__.copy()
        # Do not pickle zmq data
        result_dict['_context'] = None
        result_dict['_socket'] = None
        return result_dict

    def start(self):
        """Starts connection to server.

        Makes ping-pong test as well

        """
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.REQ)
        self._socket.connect(self.url)
        self.test_ping()
        # create a unique id
        self.id = socket.getfqdn().replace(LockerServer.DELIMITER, '-') + '__' + str(os.getpid())

    def send_done(self):
        """Notifies the Server to shutown"""
        if self._socket is None:
            self.start()
        self._socket.send_string(LockerServer.DONE)
        self._socket.recv_string()  # Final receiving of closing

    def test_ping(self):
        """Connection test"""
        self._socket.send_string(LockerServer.PING)
        response = self._socket.recv_string()
        if response != LockerServer.PONG:
            raise RuntimeError('Connection Error to LockServer')

    def finalize(self):
        """Closes socket"""
        if self._socket is not None:
            self._socket.close()
            self._socket = None
            self._context = None

    def acquire(self):
        """Acquires lock and returns `True`

        Blocks until lock is available.

        """
        if self._context is None:
            self.start()
        request = (LockerServer.LOCK + LockerServer.DELIMITER +
                   self.lock_name + LockerServer.DELIMITER + self.id)
        while True:
            self._socket.send_string(request)
            response = self._socket.recv_string()
            if response == LockerServer.GO:
                return True
            elif response == LockerServer.WAIT:
                time.sleep(self.SLEEP)
            else:
                raise RuntimeError('Response `%s` not understood' % response)

    def release(self):
        """Releases lock"""
        request = (LockerServer.UNLOCK + LockerServer.DELIMITER +
                   self.lock_name + LockerServer.DELIMITER + self.id)
        self._socket.send_string(request)
        response = self._socket.recv_string()
        if response != LockerServer.UNLOCKED:
            raise RuntimeError('Could not release lock `%s` (`%s`) '
                               'because of `%s`!' % (self.lock_name, self.id, response))


class QueueStorageServiceSender(MultiprocWrapper, HasLogger):
    """ For multiprocessing with :const:`~pypet.pypetconstants.WRAP_MODE_QUEUE`, replaces the
        original storage service.

        All storage requests are send over a queue to the process running the
        :class:`~pypet.storageservice.QueueStorageServiceWriter`.

        Does not support loading of data!

    """

    def __init__(self, storage_queue=None):
        self.queue = storage_queue
        self.pickle_queue = True
        self._set_logger()

    def __getstate__(self):
        result = super(QueueStorageServiceSender, self).__getstate__()
        if not self.pickle_queue:
            result['queue'] = None
        return result

    def load(self, *args, **kwargs):
        raise NotImplementedError('Queue wrapping does not support loading. If you want to '
                                  'load data in a multiprocessing environment, use the Lock '
                                  'wrapping.')

    @retry(9, Exception, 0.01, 'pypet.retry')
    def _put_on_queue(self, to_put):
        """Puts data on queue"""
        old = self.pickle_queue
        self.pickle_queue = False
        try:
            self.queue.put(to_put, block=True)
        finally:
            self.pickle_queue = old

    def store(self, *args, **kwargs):
        """Puts data to store on queue.

        Note that the queue will no longer be pickled if the Sender is pickled.

        """
        self._put_on_queue(('STORE', args, kwargs))

    def send_done(self):
        """Signals the writer that it can stop listening to the queue"""
        self._put_on_queue(('DONE', [], {}))


class LockAcquisition(HasLogger):
    """Abstract class to allow lock acquisition and release.

    Assumes that implementing classes have a ``lock``, ``is_locked`` and
    ``is_open`` attribute.

    Requires a ``_logger`` for error messaging.

    """
    @retry(9, TypeError, 0.01, 'pypet.retry')
    def acquire_lock(self):
        if not self.is_locked:
            self.is_locked = self.lock.acquire()

    @retry(9, TypeError, 0.01, 'pypet.retry')
    def release_lock(self):
        if self.is_locked and not self.is_open:
            try:
                self.lock.release()
            except (ValueError, ThreadError):
                self._logger.exception('Could not release lock, '
                                       'probably has been released already!')
            self.is_locked = False


class PipeStorageServiceSender(MultiprocWrapper, LockAcquisition):
    def __init__(self, storage_connection=None, lock=None):
        self.conn = storage_connection
        self.lock = lock
        self.is_locked = False
        self._set_logger()

    def __getstate__(self):
        # result = super(PipeStorageServiceSender, self).__getstate__()
        result = self.__dict__.copy()
        result['conn'] = None
        result['lock'] = None
        return result

    def load(self, *args, **kwargs):
        raise NotImplementedError('Pipe wrapping does not support loading. If you want to '
                                  'load data in a multiprocessing environment, use the Lock '
                                  'wrapping.')

    @retry(9, Exception, 0.01, 'pypet.retry')
    def _put_on_pipe(self, to_put):
        """Puts data on queue"""
        self.acquire_lock()
        self._send_chunks(to_put)
        self.release_lock()

    def _make_chunk_iterator(self, to_chunk, chunksize):
        return (to_chunk[i:i + chunksize] for i in range(0, len(to_chunk), chunksize))

    def _send_chunks(self, to_put):
        put_dump = pickle.dumps(to_put)
        data_size = sys.getsizeof(put_dump)
        nchunks = data_size / 20000000.   # chunks with size 20 MB
        chunksize = int(len(put_dump) / nchunks)
        chunk_iterator = self._make_chunk_iterator(put_dump, chunksize)
        for chunk in chunk_iterator:
            # print('S: sending False')
            self.conn.send(False)
            # print('S: sent False')
            # print('S: sending chunk')
            self.conn.send_bytes(chunk)
            # print('S: sent chunk %s' % chunk[0:10])
            # print('S: recv signal')
            self.conn.recv() # wait for signal that message was received
            # print('S: read signal')
        # print('S: sending True')
        self.conn.send(True)
        # print('S: sent True')
        # print('S: recving last signal')
        self.conn.recv() # wait for signal that message was received
        # print('S: read last signal')
        # print('S; DONE SENDING data')

    def store(self, *args, **kwargs):
        """Puts data to store on queue.

        Note that the queue will no longer be pickled if the Sender is pickled.

        """
        self._put_on_pipe(('STORE', args, kwargs))

    def send_done(self):
        """Signals the writer that it can stop listening to the queue"""
        self._put_on_pipe(('DONE', [], {}))


class StorageServiceDataHandler(HasLogger):
    """Class that can store data via a storage service, needs to be sub-classed to receive data"""

    def __init__(self, storage_service, gc_interval=None):
        self._storage_service = storage_service
        self._trajectory_name = ''
        self.gc_interval = gc_interval
        self.operation_counter = 0
        self._set_logger()

    def __repr__(self):
        return '<%s wrapping Storage Service %s>' % (self.__class__.__name__,
                                                     repr(self._storage_service))

    def _open_file(self):
        self._storage_service.store(pypetconstants.OPEN_FILE, None,
                                    trajectory_name=self._trajectory_name)
        self._logger.info('Opened the hdf5 file.')

    def _close_file(self):
        self._storage_service.store(pypetconstants.CLOSE_FILE, None)
        self._logger.info('Closed the hdf5 file.')

    def _check_and_collect_garbage(self):
        if self.gc_interval and self.operation_counter % self.gc_interval == 0:
            collected = gc.collect()
            self._logger.debug('Garbage Collection: Found %d unreachable items.' % collected)
        self.operation_counter += 1

    def _handle_data(self, msg, args, kwargs):
        """Handles data and returns `True` or `False` if everything is done."""
        stop = False
        try:
            if msg == 'DONE':
                stop = True
            elif msg == 'STORE':
                if 'msg' in kwargs:
                    store_msg = kwargs.pop('msg')
                else:
                    store_msg = args[0]
                    args = args[1:]
                if 'stuff_to_store' in kwargs:
                    stuff_to_store = kwargs.pop('stuff_to_store')
                else:
                    stuff_to_store = args[0]
                    args = args[1:]
                trajectory_name = kwargs['trajectory_name']
                if self._trajectory_name != trajectory_name:
                    if self._storage_service.is_open:
                        self._close_file()
                    self._trajectory_name = trajectory_name
                    self._open_file()
                self._storage_service.store(store_msg, stuff_to_store, *args, **kwargs)
                self._storage_service.store(pypetconstants.FLUSH, None)
                self._check_and_collect_garbage()
            else:
                raise RuntimeError('You queued something that was not '
                                   'intended to be queued. I did not understand message '
                                   '`%s`.' % msg)
        except Exception:
            self._logger.exception('ERROR occurred during storing!')
            time.sleep(0.01)
            pass  # We don't want to kill the queue process in case of an error

        return stop

    def run(self):
        """Starts listening to the queue."""
        try:
            while True:
                msg, args, kwargs = self._receive_data()
                stop = self._handle_data(msg, args, kwargs)
                if stop:
                    break
        finally:
            if self._storage_service.is_open:
                self._close_file()
            self._trajectory_name = ''

    def _receive_data(self):
        raise NotImplementedError('Implement this!')


class QueueStorageServiceWriter(StorageServiceDataHandler):
    """Wrapper class that listens to the queue and stores queue items via the storage service."""

    def __init__(self, storage_service, storage_queue, gc_interval=None):
        super(QueueStorageServiceWriter, self).__init__(storage_service, gc_interval=gc_interval)
        self.queue = storage_queue

    @retry(9, Exception, 0.01, 'pypet.retry')
    def _receive_data(self):
        """Gets data from queue"""
        result = self.queue.get(block=True)
        if hasattr(self.queue, 'task_done'):
            self.queue.task_done()
        return result


class PipeStorageServiceWriter(StorageServiceDataHandler):
    """Wrapper class that listens to the queue and stores queue items via the storage service."""

    def __init__(self, storage_service, storage_connection, max_buffer_size=10, gc_interval=None):
        super(PipeStorageServiceWriter, self).__init__(storage_service, gc_interval=gc_interval)
        self.conn = storage_connection
        if max_buffer_size == 0:
            # no maximum buffer size
            max_buffer_size = float('inf')
        self.max_size = max_buffer_size
        self._buffer = deque()
        self._set_logger()

    def _read_chunks(self):
        chunks = []
        stop = False
        while not stop:
            # print('W: recving stop')
            stop = self.conn.recv()
            # print('W: read stop = %s' % str(stop))
            if not stop:
                # print('W: recving chunk')
                chunk = self.conn.recv_bytes()
                chunks.append(chunk)
                # print('W: read chunk')
            # print('W: sending True')
            self.conn.send(True)
            # print('W: sent True')
        # print('W: reconstructing data')
        to_load = b''.join(chunks)
        del chunks  # free unnecessary memory
        try:
            data = pickle.loads(to_load)
        except Exception:
            # We don't want to crash the storage service if reconstruction
            # due to errors fails
            self._logger.exception('Could not reconstruct pickled data.')
            data = None
        return data

    @retry(9, Exception, 0.01, 'pypet.retry')
    def _receive_data(self):
        """Gets data from pipe"""
        while True:
            while len(self._buffer) < self.max_size and self.conn.poll():
                data = self._read_chunks()
                if data is not None:
                    self._buffer.append(data)
            if len(self._buffer) > 0:
                return self._buffer.popleft()


class LockWrapper(MultiprocWrapper, LockAcquisition):
    """For multiprocessing in :const:`~pypet.pypetconstants.WRAP_MODE_LOCK` mode,
    augments a storage service with a lock.

    The lock is acquired before storage or loading and released afterwards.

    """

    def __init__(self, storage_service, lock=None):
        self._storage_service = storage_service
        self.lock = lock
        self.is_locked = False
        self.pickle_lock = True
        self._set_logger()

    def __getstate__(self):
        result = super(LockWrapper, self).__getstate__()
        if not self.pickle_lock:
            result['lock'] = None
        return result

    def __repr__(self):
        return '<%s wrapping Storage Service %s>' % (self.__class__.__name__,
                                                     repr(self._storage_service))

    @property
    def is_open(self):
        """ Normally the file is opened and closed after each insertion.

        However, the storage service may provide the option to keep the store open and signals
        this via this property.

        """
        return self._storage_service.is_open

    @property
    def multiproc_safe(self):
        """Usually storage services are not supposed to be multiprocessing safe"""
        return True

    def store(self, *args, **kwargs):
        """Acquires a lock before storage and releases it afterwards."""
        try:
            self.acquire_lock()
            return self._storage_service.store(*args, **kwargs)
        finally:
            if self.lock is not None:
                try:
                    self.release_lock()
                except RuntimeError:
                    self._logger.error('Could not release lock `%s`!' % str(self.lock))

    def __del__(self):
        """In order to prevent a dead-lock in case of error,
         we close the storage on deletion and release the lock"""
        if self._storage_service.is_open:
            self._storage_service.store(pypetconstants.CLOSE_FILE, None)
        self.release_lock()

    def load(self, *args, **kwargs):
        """Acquires a lock before loading and releases it afterwards."""
        try:
            self.acquire_lock()
            return self._storage_service.load(*args, **kwargs)
        finally:
            if self.lock is not None:
                try:
                    self.release_lock()
                except RuntimeError:
                    self._logger.error('Could not release lock `%s`!' % str(self.lock))


class ReferenceWrapper(MultiprocWrapper):
    """Wrapper that just keeps references to data to be stored."""
    def __init__(self):
        self.references = {}

    def store(self, msg, stuff_to_store, *args, **kwargs):
        """Simply keeps a reference to the stored data """
        trajectory_name = kwargs['trajectory_name']
        if trajectory_name not in self.references:
            self.references[trajectory_name] = []
        self.references[trajectory_name].append((msg, cp.copy(stuff_to_store), args, kwargs))

    def load(self, *args, **kwargs):
        raise NotImplementedError('Queue wrapping does not support loading. If you want to '
                                  'load data in a multiprocessing environment, use the Lock '
                                  'wrapping.')

    def free_references(self):
        self.references = {}


class ReferenceStore(HasLogger):
    """Class that can store references"""
    def __init__(self, storage_service, gc_interval=None):
        self._storage_service = storage_service
        self.gc_interval = gc_interval
        self.operation_counter = 0
        self._set_logger()

    def _check_and_collect_garbage(self):
        if self.gc_interval and self.operation_counter % self.gc_interval == 0:
            collected = gc.collect()
            self._logger.debug('Garbage Collection: Found %d unreachable items.' % collected)
        self.operation_counter += 1

    def store_references(self, references):
        """Stores references to disk and may collect garbage."""
        for trajectory_name in references:
            self._storage_service.store(pypetconstants.LIST,
                                  references[trajectory_name],
                                  trajectory_name=trajectory_name)
        self._check_and_collect_garbage()