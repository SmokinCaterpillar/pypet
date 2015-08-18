__author__ = 'robert'

import random
import time
import multiprocessing as mp
import logging
import os
import sys

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
    get_root_logger, parse_args, unittest, get_random_port_url
from pypet.tests.testutils.data import TrajectoryComparator
from pypet.utils.mpwrappers import LockerClient, LockerServer
from pypet import progressbar


def run_server(server):
    #logging.basicConfig(level=logging.INFO)
    server.run()


def the_job(args):
    """Simple job executed in parallel

    Just sleeps randomly and prints to console.
    Capital letter signal parallel printing

    """
    idx, lock, filename = args

    random.seed()

    sleep_time = random.uniform(0.0, 0.05)  # Random sleep time
    lock.start()
    sidx = ':' + str(lock._get_id()) + ':' + str(idx) +'\n'

    with open(filename, mode='a') as fh:
        fh.write('PAR:__THIS__:0' + sidx)
    time.sleep(sleep_time * 2.0)
    with open(filename, mode='a') as fh:
        fh.write('PAR:__HAPPENING__:1' + sidx)
    time.sleep(sleep_time)
    with open(filename, mode='a') as fh:
        fh.write('PAR:__PARALLEL__:2' + sidx)
    time.sleep(sleep_time * 1.5)
    with open(filename, mode='a') as fh:
        fh.write('PAR:__ALL__:3' + sidx)
    time.sleep(sleep_time / 3.0)
    with open(filename, mode='a') as fh:
        fh.write('PAR:__TIMES__:4' + sidx)
    time.sleep(sleep_time / 1.5)

    lock.acquire()

    with open(filename, mode='a') as fh:
        fh.write('SEQ:BEGIN:0' + sidx)
    time.sleep(sleep_time / 2.0)
    with open(filename, mode='a') as fh:
        fh.write('SEQ:This:1' + sidx)
    time.sleep(sleep_time)
    with open(filename, mode='a') as fh:
        fh.write('SEQ:is:2' + sidx)
    time.sleep(sleep_time * 1.5)
    with open(filename, mode='a') as fh:
        fh.write('SEQ:a:3' + sidx)
    time.sleep(sleep_time / 3.0)
    with open(filename, mode='a') as fh:
        fh.write('SEQ:sequential:4' + sidx)
    time.sleep(sleep_time / 1.5)
    with open(filename, mode='a') as fh:
        fh.write('SEQ:block:5' + sidx)
    time.sleep(sleep_time / 3.0)
    with open(filename, mode='a') as fh:
        fh.write('SEQ:END:6' + sidx)

    lock.release()


@unittest.skipIf(zmq is None, 'Cannot be run without zmq')
class TestNetLock(TrajectoryComparator):

    ITERATIONS = 250

    tags = 'unittest', 'mpwrappers', 'netlock'

    def check_file(self, filename):
        current_msg = 'END'
        current_id = -1
        current_counter = 0
        iterations = set()
        with open(filename) as fh:
            for line in fh:
                seq, msg, counter, id_, iteration = line.split(':')
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
        self.assertEqual(len(iterations), self.ITERATIONS)
        for irun in range(self.ITERATIONS):
            self.assertIn(irun, iterations)

    def start_server(self, url):
        ls = LockerServer(url)
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
        sck.connect(url)
        sck.send_string(LockerServer.UNLOCK + LockerServer.DELIMITER + 'test'
                        + LockerServer.DELIMITER + 'hi')
        response = sck.recv_string()
        self.assertTrue(response.startswith(LockerServer.RELEASE_ERROR))

        sck.send_string(LockerServer.LOCK + LockerServer.DELIMITER + 'test'
                        + LockerServer.DELIMITER + 'hi')
        response = sck.recv_string()
        self.assertEqual(response, LockerServer.GO)

        sck.send_string(LockerServer.UNLOCK + LockerServer.DELIMITER + 'test'
                        + LockerServer.DELIMITER + 'ha')
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
        map(the_job, iterator)
        lock.send_done()
        self.check_file(filename)
        self.lock_process.join()

    def test_concurrent_pool(self):
        pool = mp.Pool(5)
        url = get_random_port_url()
        filename = make_temp_dir('locker_test/pool.txt')
        self.create_file(filename)
        self.start_server(url)
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
        url = get_random_port_url()
        filename = make_temp_dir('locker_test/scoop.txt')
        self.create_file(filename)
        self.start_server(url)
        lock = LockerClient(url)
        iterator = [(irun, lock, filename) for irun in range(self.ITERATIONS)]
        [x for x  in futures.map(the_job, iterator)]
        lock.send_done()
        self.check_file(filename)
        self.lock_process.join()


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)