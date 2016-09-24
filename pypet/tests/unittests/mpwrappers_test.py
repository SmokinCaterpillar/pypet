__author__ = 'robert'

import random
import time
import multiprocessing as mp
import logging
import os

try:
    import scoop
    from scoop import futures
except ImportError:
    scoop = None
try:
    import zmq
except ImportError:
    zmq = None

from pypet.tests.testutils.ioutils import run_suite, make_temp_dir, remove_data, \
    get_root_logger, parse_args, unittest, get_random_port_url, errwrite
from pypet.tests.testutils.data import TrajectoryComparator
from pypet.utils.mpwrappers import LockerClient, LockerServer, TimeOutLockerServer
from pypet.pypetlogging import DisableAllLogging
from pypet.utils.helpful_functions import is_ipv6


class FaultyServer(LockerServer):
    """Simulates a server that forgets to send from time to time"""
    def __init__(self, url):
        super(FaultyServer, self).__init__(url)
        self._srep = 0

    def _pre_respond_hook(self, response):
        fail_every = 27
        load_every = 5
        respond = True
        if self._srep % fail_every == 0 and response != self.CLOSED:
            self._logger.warn('Simulating message loss; '
                              'Loosing: `%s`; '
                              'LockDB: %s' % (response, str(self._locks)))
            self._socket.close(0)
            self._context.term()
            time.sleep(2.5)
            self._context = zmq.Context()
            self._socket = self._context.socket(zmq.REP)
            self._socket.ipv6 = is_ipv6(self._url)
            self._socket.bind(self._url)
            respond = False
        elif self._srep % load_every == 0:
            self._logger.warn('Simulating heavy CPU load')
            time.sleep(0.11)

        self._srep += 1

        return respond


def run_server(server):
    # logging.basicConfig(level=1)
    server.run()


NTIMEOUTS = 3


def time_out_job(args):

    timed_out = False
    idx, lock = args
    lock.acquire()
    if idx < NTIMEOUTS:
        time.sleep(0.5)
    try:
        lock.release()
    except RuntimeError:
        if idx < NTIMEOUTS:
            timed_out = True
        else:
            raise
    return timed_out


def flush_and_sync(fh):
    fh.flush()
    try:
        os.fsync(fh.fileno())
    except OSError:
        pass


def the_job(args):
    """Simple job executed in parallel

    Just sleeps randomly and prints to console.
    Capital letter signal parallel printing

    """
    # logging.basicConfig(level=1)
    idx, lock, filename = args
    client_id = 'N/A'
    try:
        random.seed()

        sleep_time = random.uniform(0.0, 0.05)  # Random sleep time
        lock.start()
        client_id = str(lock._get_id())
        sidx = ':' + client_id + ':' + str(idx) +'\n'

        lock.acquire()
        with open(filename, mode='a') as fh:
            fh.write('PAR:__THIS__:0' + sidx)
        lock.release()
        time.sleep(sleep_time / 2.0)

        lock.acquire()
        with open(filename, mode='a') as fh:
            fh.write('PAR:__HAPPENING__:1' + sidx)
        lock.release()
        time.sleep(sleep_time * 1.5)

        lock.acquire()
        with open(filename, mode='a') as fh:
            fh.write('PAR:__PARALLEL__:2' + sidx)
        lock.release()
        time.sleep(sleep_time)

        # lock.acquire()
        # with open(filename, mode='a') as fh:
        #     fh.write('PAR:__ALL__:3' + sidx)
        # lock.release()
        # time.sleep(sleep_time / 3.0)
        #
        # lock.acquire()
        # with open(filename, mode='a') as fh:
        #     fh.write('PAR:__TIMES__:4' + sidx)
        # lock.release()
        # time.sleep(sleep_time / 1.5)


        lock.acquire()

        with open(filename, mode='a') as fh:
            fh.write('SEQ:BEGIN:0' + sidx)
            flush_and_sync(fh)
        time.sleep(sleep_time / 2.0)
        with open(filename, mode='a') as fh:
            fh.write('SEQ:This:1' + sidx)
            flush_and_sync(fh)
        time.sleep(sleep_time)
        with open(filename, mode='a') as fh:
            fh.write('SEQ:is:2' + sidx)
            flush_and_sync(fh)
        time.sleep(sleep_time * 1.5)
        with open(filename, mode='a') as fh:
            fh.write('SEQ:a:3' + sidx)
            flush_and_sync(fh)
        time.sleep(sleep_time / 3.0)
        with open(filename, mode='a') as fh:
            fh.write('SEQ:sequential:4' + sidx)
            flush_and_sync(fh)
        time.sleep(sleep_time / 1.5)
        with open(filename, mode='a') as fh:
            fh.write('SEQ:block:5' + sidx)
            flush_and_sync(fh)
        time.sleep(sleep_time / 3.0)
        with open(filename, mode='a') as fh:
            fh.write('SEQ:END:6' + sidx)
            flush_and_sync(fh)

        lock.release()
    except:
        logging.getLogger().exception('Error in job `%d` (%s)' % (idx, client_id))


@unittest.skipIf(zmq is None, 'Cannot be run without zmq')
class TestNetLock(TrajectoryComparator):

    ITERATIONS = 33

    tags = 'unittest', 'mpwrappers', 'netlock'

    def check_file(self, filename):
        current_msg = 'END'
        current_id = -1
        current_counter = 0
        iterations = set()
        lines = []
        with open(filename) as fh:
            for line in fh:
                lines.append(line)
                split_line = line.split(':')
                if len(split_line) == 5:
                    seq, msg, counter, id_, iteration = split_line
                    if seq == 'PAR':
                        continue
                    iteration = int(iteration)
                    counter = int(counter)
                    iterations.add(iteration)
                    errstring = ('\nCurrent idx `%s` new `%s`;\n '
                               'Current msg `%s`, new `%s`;\n'
                               'Curent counter `%d`, '
                               'new `%d`;\n '
                               'Iteration %d' % (current_id, id_,
                                                 current_msg, msg,
                                                 current_counter, counter, iteration))
                    if msg == 'BEGIN':
                        self.assertEqual(current_msg, 'END', 'MSG beginning in the middle.' +
                                         errstring)

                    else:
                        self.assertEqual(current_counter, counter - 1,
                                                   'Counters not matching.' + errstring)
                        self.assertEqual(current_id, id_,
                                                   'IDs not matching.' + errstring)
                    current_counter = counter
                    current_id = id_
                    current_msg = msg
                else:
                    self.assertEqual(len(split_line), 5, 'Cannot split `%s`\n '
                                                         '---Text:---\n '
                                                         '%s' % (str(split_line),
                                                                 '\n'.join(lines)))

        self.assertEqual(len(iterations), self.ITERATIONS, '%d != %d, Iterations:\n'
                         % (len(iterations), self.ITERATIONS) +  str(iterations))
        for irun in range(self.ITERATIONS):
            self.assertIn(irun, iterations)

    def start_server(self, url, faulty=False):
        if faulty:
            ls = FaultyServer(url)
        else:
            ls = LockerServer(url)
        self.lock_process = mp.Process(target=run_server, args=(ls,))
        self.lock_process.start()

    def start_timeout_server(self, url, timeout):
        ls = TimeOutLockerServer(url, timeout)
        self.lock_process = mp.Process(target=run_server, args=(ls,))
        self.lock_process.start()

    def create_file(self, filename):
        path, file = os.path.split(filename)
        if not os.path.isdir(path):
            os.makedirs(path)
        fh = open(filename, mode='w')
        fh.close()

    def test_errors(self):
        url = get_random_port_url()
        self.start_server(url)
        ctx = zmq.Context()
        sck = ctx.socket(zmq.REQ)
        sck.ipv6 = is_ipv6(url)
        sck.connect(url)
        sck.send_string(LockerServer.UNLOCK + LockerServer.DELIMITER + 'test'
                        + LockerServer.DELIMITER + 'hi' + LockerServer.DELIMITER + '12344')
        response = sck.recv_string()
        self.assertTrue(response.startswith(LockerServer.RELEASE_ERROR))

        sck.send_string(LockerServer.LOCK + LockerServer.DELIMITER + 'test'
                        + LockerServer.DELIMITER + 'hi' + LockerServer.DELIMITER + '12344')
        response = sck.recv_string()
        self.assertEqual(response, LockerServer.GO)

        sck.send_string(LockerServer.UNLOCK + LockerServer.DELIMITER + 'test'
                        + LockerServer.DELIMITER + 'ha' + LockerServer.DELIMITER + '12344')
        response = sck.recv_string()
        self.assertTrue(response.startswith(LockerServer.RELEASE_ERROR))

        sck.send_string(LockerServer.UNLOCK + LockerServer.DELIMITER + 'test')
        response = sck.recv_string()
        self.assertTrue(response.startswith(LockerServer.MSG_ERROR))

        sck.send_string(LockerServer.LOCK + LockerServer.DELIMITER + 'test')
        response = sck.recv_string()
        self.assertTrue(response.startswith(LockerServer.MSG_ERROR))

        sck.send_string('Wooopiee!')
        response = sck.recv_string()
        self.assertTrue(response.startswith(LockerServer.MSG_ERROR))

        sck.close()

        lock = LockerClient(url)
        lock.send_done()
        self.lock_process.join()
        lock.finalize()

    def test_single_core(self):
        url = get_random_port_url()
        filename = make_temp_dir('locker_test/score.txt')
        self.create_file(filename)
        self.start_server(url)
        lock = LockerClient(url)
        iterator = [(irun, lock, filename) for irun in range(self.ITERATIONS)]
        list(map(the_job, iterator))
        lock.send_done()
        self.check_file(filename)
        self.lock_process.join()

    def test_concurrent_pool_faulty(self):
        prev = self.ITERATIONS
        self.ITERATIONS = 11
        #logging.basicConfig(level=1)
        with DisableAllLogging():
            self.test_concurrent_pool(faulty=True, filename='locker_test/faulty_pool.txt')
        self.ITERATIONS = prev

    def test_concurrent_pool(self, faulty=False, filename='locker_test/pool.txt'):
        pool = mp.Pool(5)
        url = get_random_port_url()
        filename = make_temp_dir(filename)
        self.create_file(filename)
        self.start_server(url, faulty)
        lock = LockerClient(url)
        iterator = [(irun, lock, filename) for irun in range(self.ITERATIONS)]
        pool.imap(the_job, iterator)
        pool.close()
        pool.join()
        lock.send_done()
        self.check_file(filename)
        self.lock_process.join()

    @unittest.skipIf(scoop is None, 'Can only be run with scoop')
    def test_concurrent_scoop(self):
        # test several restarts
        old_iter = self.ITERATIONS
        for jrun in range(3):
            self.ITERATIONS = 11
            url = get_random_port_url()
            filename = make_temp_dir('locker_test/scoop.txt')
            self.create_file(filename)
            self.start_server(url)
            lock = LockerClient(url)
            lock.start()
            iterator = [(irun, lock, filename) for irun in range(self.ITERATIONS)]
            list(futures.map(the_job, iterator))
            lock.send_done()
            self.check_file(filename)
            self.lock_process.join()
            # errwrite(str(irun))
        self.ITERATIONS = old_iter

    def test_timout_pool(self):
        pool = mp.Pool(5)
        url = get_random_port_url()
        self.start_timeout_server(url, 0.25)
        lock = LockerClient(url)
        lock.start()
        iterator = [(irun, lock) for irun in range(self.ITERATIONS)]
        potential_timeouts = list(pool.imap(time_out_job, iterator))
        pool.close()
        pool.join()
        all_time_outs = [x for x in potential_timeouts if x]
        self.assertGreaterEqual(len(all_time_outs), 1)
        lock.send_done()
        self.lock_process.join()

if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)