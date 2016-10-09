"""Module containing wrappers for multiprocessing"""

__author__ = 'Robert Meyer', 'Mehmet Nevvaf Timur'


from threading import ThreadError
import queue
import pickle
try:
    import zmq
except ImportError:
    zmq = None

from collections import deque
import copy as cp
import gc
import sys
from threading import Thread
import time
import os
import socket

import pypet.pypetconstants as pypetconstants
from pypet.pypetlogging import HasLogger
from pypet.utils.decorators import retry
from pypet.utils.helpful_functions import is_ipv6


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


class ZMQServer(HasLogger):
    """ Generic zmq server """

    PING = 'PING'  # for connection testing
    PONG = 'PONG'  # for connection testing
    DONE = 'DONE'  # signals stopping of server
    CLOSED = 'CLOSED'  # signals closing of server

    def __init__(self, url="tcp://127.0.0.1:7777"):
        self._url = url  # server url
        self._set_logger()
        self._context = None
        self._socket = None

    def _start(self):
        self._logger.info('Starting Server at `%s`' % self._url)
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.REP)
        self._socket.ipv6 = is_ipv6(self._url)
        self._socket.bind(self._url)

    def _close(self):
        self._logger.info('Closing Server')
        self._socket.close()
        self._context.term()


class LockerServer(ZMQServer):
    """ Manages a database of locks """

    LOCK = 'LOCK'  # command for locking a lock
    RELEASE_ERROR = 'RELEASE_ERROR'  # signals unsuccessful attempt to unlock
    MSG_ERROR = 'MSG_ERROR'  # signals error in decoding client request
    UNLOCK = 'UNLOCK'  # command for unlocking a lock
    RELEASED = 'RELEASED'  # signals successful unlocking
    LOCK_ERROR = 'LOCK_ERROR'  # signals unsuccessful attempt to lock
    GO = 'GO'  # signals successful locking and and allwos continuing of client
    WAIT = 'WAIT'  # signals lock is already in use and client has to wait for release
    DELIMITER = ':::'  # delimiter to split messages
    DEFAULT_LOCK = '_DEFAULT_'  # default lock name

    def __init__(self, url="tcp://127.0.0.1:7777"):
        super(LockerServer, self).__init__(url)
        self._locks = {}  # lock DB, format 'lock_name': ('client_id', 'request_id')

    def _pre_respond_hook(self, response):
        """ Hook that can be used to temper with the server before responding

        :param response: Response to be send

        :return: Boolean value if response should be send or not

        """
        return True

    def _lock(self, name, client_id, request_id):
        """Hanldes locking of locks

        If a lock is already locked sends a WAIT command,
        else LOCKs it and sends GO.

        Complains if a given client re-locks a lock without releasing it before.

        """
        if name in self._locks:
            other_client_id, other_request_id = self._locks[name]
            if other_client_id == client_id:
                response = (self.LOCK_ERROR + self.DELIMITER +
                            'Re-request of lock `%s` (old request id `%s`) by `%s` '
                            '(request id `%s`)' % (name, client_id, other_request_id, request_id))
                self._logger.warning(response)
                return response
            else:
                return self.WAIT
        else:
            self._locks[name] = (client_id, request_id)
            return self.GO

    def _unlock(self, name, client_id, request_id):
        """Handles unlocking

        Complains if a non-existent lock should be released or
        if a lock should be released that was acquired by
        another client before.

        """
        if name in self._locks:
            other_client_id, other_request_id = self._locks[name]
            if other_client_id != client_id:
                response = (self.RELEASE_ERROR + self.DELIMITER +
                            'Lock `%s` was acquired by `%s` (old request id `%s`) and not by '
                            '`%s` (request id `%s`)' % (name,
                                                        other_client_id,
                                                        other_request_id,
                                                        client_id,
                                                        request_id))
                self._logger.error(response)
                return response
            else:
                del self._locks[name]
                return self.RELEASED
        else:
            response = (self.RELEASE_ERROR + self.DELIMITER +
                        'Lock `%s` cannot be found in database (client id `%s`, '
                        'request id `%s`)' % (name, client_id, request_id))
            self._logger.error(response)
            return response

    def run(self):
        """Runs server"""
        try:
            self._start()

            running = True
            while running:
                msg = ''
                name = ''
                client_id = ''
                request_id = ''

                request = self._socket.recv_string()
                self._logger.log(1, 'Recevied REQ `%s`', request)

                split_msg = request.split(self.DELIMITER)

                if len(split_msg) == 4:
                    msg, name, client_id, request_id = split_msg

                if msg == self.LOCK:
                    response = self._lock(name, client_id, request_id)

                elif msg == self.UNLOCK:
                    response = self._unlock(name, client_id, request_id)

                elif msg == self.PING:
                    response = self.PONG

                elif msg == self.DONE:
                    response = self.CLOSED
                    running = False

                else:
                    response = (self.MSG_ERROR + self.DELIMITER +
                                'Request `%s` not understood '
                                '(or wrong number of delimiters)' % request)
                    self._logger.error(response)

                respond = self._pre_respond_hook(response)
                if respond:
                    self._logger.log(1, 'Sending REP `%s` to `%s` (request id `%s`)',
                                     response, client_id, request_id)
                    self._socket.send_string(response)

            # Close everything in the end
            self._close()
        except Exception:
            self._logger.exception('Crashed Lock Server!')
            raise


class TimeOutLockerServer(LockerServer):
    """ Lock Server where each lock is valid only for a fixed period of time. """

    def __init__(self, url, timeout):
        super(TimeOutLockerServer, self).__init__(url)
        self._timeout = timeout
        self._timeout_locks = {}

    def _lock(self, name, client_id, request_id):
        """Handles locking

        Locking time is stored to determine time out.
        If a lock is timed out it can be acquired by a different client.

        """
        if name in self._locks:
            other_client_id, other_request_id, lock_time = self._locks[name]
            if other_client_id == client_id:
                response = (self.LOCK_ERROR + self.DELIMITER +
                            'Re-request of lock `%s` (old request id `%s`) by `%s` '
                            '(request id `%s`)' % (name, client_id, other_request_id, request_id))
                self._logger.warning(response)
                return response
            else:
                current_time = time.time()
                if current_time - lock_time < self._timeout:
                    return self.WAIT
                else:
                    response = (self.GO + self.DELIMITER + 'Lock `%s` by `%s` (old request id `%s) '
                                                          'timed out' % (name,
                                                                         other_client_id,
                                                                         other_request_id))
                    self._logger.info(response)
                    self._locks[name] = (client_id, request_id, time.time())
                    self._timeout_locks[(name, other_client_id)] = (request_id, lock_time)
                    return response
        else:
            self._locks[name] = (client_id, request_id, time.time())
            return self.GO

    def _unlock(self, name, client_id, request_id):
        """Handles unlocking"""
        if name in self._locks:
            other_client_id, other_request_id, lock_time = self._locks[name]
            if other_client_id != client_id:
                response = (self.RELEASE_ERROR + self.DELIMITER +
                            'Lock `%s` was acquired by `%s` (old request id `%s`) and not by '
                            '`%s` (request id `%s`)' % (name,
                                                        other_client_id,
                                                        other_request_id,
                                                        client_id,
                                                        request_id))
                self._logger.error(response)
                return response
            else:
                del self._locks[name]
                return self.RELEASED
        elif (name, client_id) in self._timeout_locks:
            other_request_id, lock_time = self._timeout_locks[(name, client_id)]
            timeout = time.time() - lock_time - self._timeout
            response = (self.RELEASE_ERROR + self.DELIMITER +
                        'Lock `%s` timed out %f seconds ago (client id `%s`, '
                        'old request id `%s`)' % (name, timeout, client_id, other_request_id))
            return response
        else:
            response = (self.RELEASE_ERROR + self.DELIMITER +
                        'Lock `%s` cannot be found in database (client id `%s`, '
                        'request id `%s`)' % (name, client_id, request_id))
            self._logger.warning(response)
            return response


class ReliableClient(HasLogger):
    """Implements a reliable client that reconnects on server failure"""

    SLEEP = 0.01   # Sleep time before reconnect in seconds
    RETRIES = 9   # Number of reconnect retries
    TIMEOUT = 2222  # Waiting time to reconnect in seconds

    def __init__(self, url):
        self.url = url
        self._context = None
        self._socket = None
        self._poll = None
        self._set_logger()

    def __getstate__(self):
        result_dict = super(ReliableClient, self).__getstate__()
        # Do not pickle zmq data
        result_dict['_context'] = None
        result_dict['_socket'] = None
        result_dict['_poll'] = None
        return result_dict

    def send_done(self):
        """Notifies the Server to shutdown"""
        self.start(test_connection=False)
        self._logger.debug('Sending shutdown signal')
        self._req_rep(ZMQServer.DONE)

    def test_ping(self):
        """Connection test"""
        self.start(test_connection=False)
        response = self._req_rep(ZMQServer.PING)
        if response != ZMQServer.PONG:
            raise RuntimeError('Connection Error to LockServer')

    def finalize(self):
        """Closes socket and terminates context

        NO-OP if already closed.

        """
        if self._context is not None:
            if self._socket is not None:
                self._close_socket(confused=False)
            self._context.term()
            self._context = None
            self._poll = None

    def start(self, test_connection=True):
        """Starts connection to server if not existent.

        NO-OP if connection is already established.
        Makes ping-pong test as well if desired.

        """
        if self._context is None:
            self._logger.debug('Starting Client')
            self._context = zmq.Context()
            self._poll = zmq.Poller()
            self._start_socket()
            if test_connection:
                self.test_ping()

    def _start_socket(self):
        self._socket = self._context.socket(zmq.REQ)
        self._socket.ipv6 = is_ipv6(self.url)
        self._socket.connect(self.url)
        self._poll.register(self._socket, zmq.POLLIN)

    def _close_socket(self, confused=False):
        if confused:
            self._socket.setsockopt(zmq.LINGER, 0)
        self._socket.close()
        self._poll.unregister(self._socket)
        self._socket = None

    def __del__(self):
        # For Python 3.4 to avoid dead-lock due to wrong object clearing
        # i.e. deleting context before socket
        self.finalize()

    def _req_rep(self, request):
        """Returns server response on `request_sketch`"""
        return self._req_rep_retry(request)[0]

    def _req_rep_retry(self, request):
        """Returns response and number of retries"""
        retries_left = self.RETRIES
        while retries_left:
            self._logger.log(1, 'Sending REQ `%s`', request)
            self._send_request(request)
            socks = dict(self._poll.poll(self.TIMEOUT))
            if socks.get(self._socket) == zmq.POLLIN:
                response = self._receive_response()
                self._logger.log(1, 'Received REP `%s`', response)
                return response, self.RETRIES - retries_left
            else:
                self._logger.debug('No response from server (%d retries left)' %
                                   retries_left)
                self._close_socket(confused=True)
                retries_left -= 1
                if retries_left == 0:
                    raise RuntimeError('Server seems to be offline!')
                time.sleep(self.SLEEP)
                self._start_socket()

    def _send_request(self, request):
        """Actual sending of the request over network"""
        self._socket.send_string(request)

    def _receive_response(self):
        """Actual receiving of response"""
        return self._socket.recv_string()


class LockerClient(ReliableClient):
    """ Implements a Lock by requesting lock information from LockServer"""

    def __init__(self, url='tcp://127.0.0.1:7777', lock_name=LockerServer.DEFAULT_LOCK):
        super(LockerClient, self).__init__(url)
        self.lock_name = lock_name
        self.id = None

    def __getstate__(self):
        result_dict = super(LockerClient, self).__getstate__()
        result_dict['id'] = None
        return result_dict

    def start(self, test_connection=True):
        if self._context is None:
            self.id = self._get_id()
            cls = self.__class__
            self._set_logger('%s.%s_%s' % (cls.__module__, cls.__name__, self.id))
            super(LockerClient, self).start(test_connection)

    @staticmethod
    def _get_id():
        return socket.getfqdn().replace(LockerServer.DELIMITER, '-') + '__' + str(os.getpid())

    @staticmethod
    def _get_request_id():
        return str(time.time()).replace(LockerServer.DELIMITER, '-')

    def _compose_request(self, request_sketch):
        request = (request_sketch + LockerServer.DELIMITER +
                   self.lock_name + LockerServer.DELIMITER + self.id +
                   LockerServer.DELIMITER + self._get_request_id())
        return request

    def acquire(self):
        """Acquires lock and returns `True`

        Blocks until lock is available.

        """
        self.start(test_connection=False)
        while True:
            str_response, retries = self._req_rep_retry(LockerServer.LOCK)
            response = str_response.split(LockerServer.DELIMITER)
            if response[0] == LockerServer.GO:
                return True
            elif response[0] == LockerServer.LOCK_ERROR and retries > 0:
                # Message was sent but Server response was lost and we tried again
                self._logger.error(str_response + '; Probably due to retry')
                return True
            elif response[0] == LockerServer.WAIT:
                time.sleep(self.SLEEP)
            else:
                raise RuntimeError('Response `%s` not understood' % response)

    def release(self):
        """Releases lock"""
        # self.start(test_connection=False)
        str_response, retries = self._req_rep_retry(LockerServer.UNLOCK)
        response = str_response.split(LockerServer.DELIMITER)
        if response[0] == LockerServer.RELEASED:
            pass  # Everything is fine
        elif response[0] == LockerServer.RELEASE_ERROR and retries > 0:
            # Message was sent but Server response was lost and we tried again
            self._logger.error(str_response + '; Probably due to retry')
        else:
            raise RuntimeError('Response `%s` not understood' % response)

    def _req_rep_retry(self, request):
        request = self._compose_request(request)
        return super(LockerClient, self)._req_rep_retry(request)


class QueuingServerMessageListener(ZMQServer):
    """ Manages the listening requests"""

    SPACE = 'SPACE'  # for space in the queue
    DATA = 'DATA'  # for sending data
    SPACE_AVAILABLE = 'SPACE_AVAILABLE'
    SPACE_NOT_AVAILABLE = 'SPACE_NOT_AVAILABLE'
    STORING = 'STORING'


    def __init__(self, url, queue, queue_maxsize):
        super(QueuingServerMessageListener, self).__init__(url)
        self.queue = queue
        if queue_maxsize == 0:
            queue_maxsize = float('inf')
        self.queue_maxsize = queue_maxsize

    def listen(self):
        """ Handles listening requests from the client.

        There are 4 types of requests:

        1- Check space in the queue
        2- Tests the socket
        3- If there is a space, it sends data
        4- after data is sent, puts it to queue for storing

        """
        count = 0
        self._start()
        while True:
            result = self._socket.recv_pyobj()

            if isinstance(result, tuple):
                request, data = result
            else:
                request = result
                data = None

            if request == self.SPACE:
                if self.queue.qsize() + count < self.queue_maxsize:
                    self._socket.send_string(self.SPACE_AVAILABLE)
                    count += 1
                else:
                    self._socket.send_string(self.SPACE_NOT_AVAILABLE)

            elif request == self.PING:
                self._socket.send_string(self.PONG)

            elif request == self.DATA:
                self._socket.send_string(self.STORING)
                self.queue.put(data)
                count -= 1

            elif request == self.DONE:
                self._socket.send_string(ZMQServer.CLOSED)
                self.queue.put(('DONE', [], {}))
                self._close()
                break

            else:
                raise RuntimeError('I did not understand your request %s' % request)


class QueuingServer(HasLogger):
    """ Implements server architecture for Queueing"""

    def __init__(self, url, storage_service, queue_maxsize, gc_interval):
        self._url = url
        self._storage_service = storage_service
        self._queue_maxsize = queue_maxsize
        self._gc_interval = gc_interval

    def run(self):
        main_queue = queue.Queue(maxsize=self._queue_maxsize)
        server_message_listener = QueuingServerMessageListener(self._url, main_queue, self._queue_maxsize)
        storage_writer = QueueStorageServiceWriter(self._storage_service, main_queue, self._gc_interval)

        server_queue = Thread(target=server_message_listener.listen, args=())
        server_queue.start()

        storage_writer.run()
        server_queue.join()


class QueuingClient(ReliableClient):
    """ Manages the returning requests"""

    def put(self, data, block=True):
        """ If there is space it sends data to server

        If no space in the queue

        It returns the request in every 10 millisecond

        until there will be space in the queue.

        """

        self.start(test_connection=False)
        while True:
            response = self._req_rep(QueuingServerMessageListener.SPACE)
            if response == QueuingServerMessageListener.SPACE_AVAILABLE:
                self._req_rep((QueuingServerMessageListener.DATA, data))
                break
            else:
                time.sleep(0.01)

    def _send_request(self, request):
        return self._socket.send_pyobj(request)


class ForkDetector(HasLogger):
    def _detect_fork(self):
        """Detects if lock client was forked.

        Forking is detected by comparing the PID of the current
        process with the stored PID.

        """
        if self._pid is None:
            self._pid = os.getpid()
        if self._context is not None:
            current_pid = os.getpid()
            if current_pid != self._pid:
                self._logger.debug('Fork detected: My pid `%s` != os pid `%s`. '
                                   'Restarting connection.' % (str(self._pid), str(current_pid)))
                self._context = None
                self._pid = current_pid


class ForkAwareQueuingClient(QueuingClient, ForkDetector):
    """ Queuing Client can detect forking of process.

    In this case the context and socket are restarted.

    """

    def __init__(self, url='tcp://127.0.0.1:22334'):
        super(ForkAwareQueuingClient, self).__init__(url)
        self._pid = None

    def __getstate__(self):
        result_dict = super(ForkAwareQueuingClient, self).__getstate__()
        result_dict['_pid'] = None
        return result_dict

    def start(self, test_connection=True):
        self._detect_fork()
        super(ForkAwareQueuingClient, self).start(test_connection)


class ForkAwareLockerClient(LockerClient, ForkDetector):
    """Locker Client that can detect forking of processes.

    In this case the context and socket are restarted.

    """

    def __init__(self, url='tcp://127.0.0.1:7777', lock_name=LockerServer.DEFAULT_LOCK):
        super(ForkAwareLockerClient, self).__init__(url, lock_name)
        self._pid = None

    def __getstate__(self):
        result_dict = super(ForkAwareLockerClient, self).__getstate__()
        result_dict['_pid'] = None
        return result_dict

    def start(self, test_connection=True):
        """Checks for forking and starts/restarts if desired"""
        self._detect_fork()
        super(ForkAwareLockerClient, self).start(test_connection)


class QueueStorageServiceSender(MultiprocWrapper, HasLogger):
    """ For multiprocessing with :const:`~pypet.pypetconstants.WRAP_MODE_QUEUE`, replaces the
        original storage service.

        All storage requests are send over a queue to the process running the
        :class:`~pypet.storageservice.QdebugueueStorageServiceWriter`.

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
                                  'load data in a multiprocessing environment, use a Lock '
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
            self.conn.recv()  # wait for signal that message was received
            # print('S: read signal')
        # print('S: sending True')
        self.conn.send(True)
        # print('S: sent True')
        # print('S: recving last signal')
        self.conn.recv()  # wait for signal that message was received
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
        # In order to prevent a dead-lock in case of error,
        # we release the lock once again
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
        """Not implemented"""
        raise NotImplementedError('Reference wrapping does not support loading. If you want to '
                                  'load data in a multiprocessing environment, use a Lock '
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
            self._storage_service.store(pypetconstants.LIST, references[trajectory_name], trajectory_name=trajectory_name)
        self._check_and_collect_garbage()