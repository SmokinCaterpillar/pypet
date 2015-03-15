__author__ = 'Robert Meyer'

import logging

from pypet import Result
from pypet.tests.testutils.data import TrajectoryComparator
from pypet.tests.testutils.ioutils import parse_args, run_suite, get_root_logger, make_temp_dir,\
    make_trajectory_name,  get_log_config, get_log_path, prepare_log_config
import pypet.tests.testutils.ioutils as ioutils
from pypet import Environment, Trajectory
import pypet.pypetconstants as pypetconstants
import os


class LogWhenStored(Result):

    def __init__(self, full_name, *args, **kwargs):
        self._level = kwargs['level']
        super(LogWhenStored, self).__init__(full_name, *args, **kwargs)

    def _store(self):
        self._logger.log(self._level, 'STORE_Test! in parameter')
        return super(LogWhenStored, self)._store()

def add_result(traj, level=logging.ERROR):
    traj.f_ares(LogWhenStored, 'logging.test',
                42, level=level, comment='STORE_Test!')

def log_error(traj):
    add_result(traj)
    logging.getLogger('pypet.only.ERROR').error('Test of Error Logging during run!')


def log_wo_error_levels(traj):
    add_result(traj, level=logging.INFO)
    logging.getLogger('pypet.DEBUG').debug('DEBUG_Test!')
    logging.getLogger('pypet.INFO').info('INFO_Test!')
    logging.getLogger('pypet.WARNING').warning('WARNING_Test!')

def log_all_levels(traj):
    add_result(traj)
    logging.getLogger('pypet.DEBUG').debug('DEBUG_Test!')
    logging.getLogger('pypet.INFO').info('INFO_Test!')
    logging.getLogger('pypet.WARNING').warning('WARNING_Test!')
    logging.getLogger('pypet.ERROR').error('ERROR_Test!')
    logging.getLogger('pypet.CRITICAL').critical('CRITICAL_Test!')


class Dummy(object):
    pass


class LoggingTest(TrajectoryComparator):

    tags = 'integration', 'environment', 'logging'

    def setUp(self):
        self.set_mode()

    def set_mode(self):
        self.mode = Dummy()
        self.mode.wrap_mode = 'LOCK'
        self.mode.multiproc = False
        self.mode.ncores = 1
        self.mode.use_pool=True
        self.mode.pandas_format='fixed'
        self.mode.pandas_append=False
        self.mode.complib = 'blosc'
        self.mode.complevel=9
        self.mode.shuffle=True
        self.mode.fletcher32 = False
        self.mode.encoding = 'utf8'
        self.mode.log_stdout=False
        self.mode.log_allow_fork=False
        self.mode.log_config=get_log_config()


    def make_env(self, **kwargs):

        self.mode.__dict__.update(kwargs)
        filename = 'log_testing.hdf5'
        self.filename = make_temp_dir(filename)
        self.traj_name = make_trajectory_name(self)
        self.env = Environment(trajectory=self.traj_name,
                               filename=self.filename, **self.mode.__dict__)
        self.traj = self.env.v_traj


    def add_params(self, traj):

        traj.par.p1 = 42, 'Hey'
        traj.f_apar('g1.p2', 145, comment='Test')


    def explore(self, traj):
        traj.f_explore({'p1': range(7)})



    # @unittest.skipIf(platform.system() == 'Windows', 'Log file creation might fail under windows.')
    def test_logfile_creation_normal(self):
        # if not self.multiproc:
        #     return
        self.make_env()
        self.add_params(self.traj)
        self.explore(self.traj)

        self.env.f_run(log_wo_error_levels)
        self.env.f_disable_logging()

        traj = self.env.v_traj

        log_path = get_log_path(traj)

        if self.mode.multiproc:
            if self.mode.use_pool:
                length = self.mode.ncores * 2
            else:
                length = 2 * len(traj)
            if self.mode.wrap_mode == 'LOCK':
                length += 2
            elif self.mode.wrap_mode == 'QUEUE':
                length += + 4
            else:
                raise RuntimeError('You shall not pass!')
        else:
            length = 2


        file_list = [file for file in os.listdir(log_path)]

        self.assertEqual(len(file_list), length) # assert that there are as many
        # files as runs plus main.txt and errors and warnings

        for file in file_list:
            with open(os.path.join(log_path, file), mode='r') as fh:
                text = fh.read()
            count = text.count('INFO_Test!')
            store_count = text.count('STORE_Test!')
            if 'LOG.txt' == file:
                if self.mode.multiproc:
                    self.assertEqual(count,0)
                    self.assertEqual(store_count, 0)
                else:
                    self.assertEqual(count, len(traj))
                    self.assertEqual(store_count, len(traj))
            elif 'ERROR' in file:
                filesize = os.path.getsize(os.path.join(log_path, file))
                self.assertEqual(filesize, 0)
            elif 'Queue' in file:
                self.assertEqual(store_count, len(traj))
            elif 'LOG' in file:
                if self.mode.multiproc and self.mode.use_pool:
                    self.assertGreaterEqual(count, 1)
                else:
                    self.assertEqual(count, 1)
                    if self.mode.wrap_mode == 'QUEUE':
                        self.assertEqual(store_count, 0)
                    else:
                        self.assertEqual(store_count, 1)
            else:
                self.assertTrue(False, 'There`s a file in the log folder that does not '
                                       'belong there: %s' % str(file))


    # @unittest.skipIf(platform.system() == 'Windows', 'Log file creation might fail under windows.')
    def test_logfile_creation_with_errors(self):
         # if not self.multiproc:
        #     return
        self.make_env()
        self.add_params(self.traj)
        self.explore(self.traj)

        self.env.f_run(log_all_levels)
        if self.mode.multiproc:
            logging.getLogger('pypet.test').error('ttt')
        self.env.f_disable_logging()

        traj = self.env.v_traj
        log_path = get_log_path(traj)

        if self.mode.multiproc:
            if self.mode.use_pool:
                length = self.mode.ncores * 2
            else:
                length = 2 * len(traj)
            if self.mode.wrap_mode == 'LOCK':
                length += 2
            elif self.mode.wrap_mode == 'QUEUE':
                length += + 4
            else:
                raise RuntimeError('You shall not pass!')
        else:
            length = 2

        file_list = [file for file in os.listdir(log_path)]

        self.assertEqual(len(file_list), length) # assert that there are as many
        # files as runs plus main.txt and errors and warnings

        for file in file_list:
            with open(os.path.join(log_path, file), mode='r') as fh:
                text = fh.read()
            count = text.count('INFO_Test!')
            error_count = text.count('ERROR_Test!')
            store_count = text.count('STORE_Test!')
            if 'LOG.txt' == file:
                if self.mode.multiproc:
                    self.assertEqual(count,0)
                    self.assertEqual(store_count, 0)
                else:
                    self.assertEqual(count, len(traj))
                    self.assertEqual(store_count, len(traj))
            elif 'ERROR.txt' == file:
                self.assertEqual(count, 0)
                if self.mode.multiproc:
                    self.assertEqual(error_count,0)
                    self.assertEqual(store_count, 0)
                else:
                    self.assertEqual(error_count, len(traj))
                    self.assertEqual(store_count, len(traj))

            elif 'Queue' in file and 'ERROR' in file:
                self.assertEqual(store_count, len(traj))
            elif 'Queue' in file and 'LOG' in file:
                self.assertEqual(store_count, len(traj))
            elif 'LOG' in file:
                if self.mode.multiproc and self.mode.use_pool:
                    self.assertGreaterEqual(count, 1)
                    self.assertGreaterEqual(error_count, 1)
                else:
                    self.assertEqual(count, 1)
                    self.assertEqual(error_count, 1)
                    if self.mode.wrap_mode == 'QUEUE':
                        self.assertEqual(store_count, 0)
                    else:
                        self.assertEqual(store_count, 1)
            elif 'ERROR' in file:
                if self.mode.multiproc and self.mode.use_pool:
                    self.assertEqual(count, 0)
                    self.assertGreaterEqual(error_count, 1)
                else:
                    self.assertEqual(count, 0)
                    self.assertEqual(error_count, 1)
                    if self.mode.wrap_mode == 'QUEUE':
                        self.assertEqual(store_count, 0)
                    else:
                        self.assertEqual(store_count, 1)
            else:
                self.assertTrue(False, 'There`s a file in the log folder that does not '
                                       'belong there: %s' % str(file))

      # @unittest.skipIf(platform.system() == 'Windows', 'Log file creation might fail under windows.')
    def test_logfile_old_way_creation_with_errors(self):
         # if not self.multiproc:
        #     return
        self.make_env(logger_names = ('','pypet'), log_level=logging.ERROR, log_config=None,
                      log_folder=make_temp_dir('logs'))
        self.add_params(self.traj)
        self.explore(self.traj)

        self.env.f_run(log_all_levels)
        if self.mode.multiproc:
            logging.getLogger('pypet.test').error('ttt')
        self.env.f_disable_logging()

        traj = self.env.v_traj
        log_path = get_log_path(traj)

        if self.mode.multiproc:
            if self.mode.use_pool:
                length = self.mode.ncores * 2
            else:
                length = 2 * len(traj)
            if self.mode.wrap_mode == 'LOCK':
                length += 2
            elif self.mode.wrap_mode == 'QUEUE':
                length += + 4
            else:
                raise RuntimeError('You shall not pass!')
        else:
            length = 2

        file_list = [file for file in os.listdir(log_path)]

        self.assertEqual(len(file_list), length) # assert that there are as many
        # files as runs plus main.txt and errors and warnings

        for file in file_list:
            with open(os.path.join(log_path, file), mode='r') as fh:
                text = fh.read()
            count = text.count('INFO_Test!')
            error_count = text.count('ERROR_Test!')
            store_count = text.count('STORE_Test!')
            if 'LOG.txt' == file:
                if self.mode.multiproc:
                    self.assertEqual(count,0)
                    self.assertEqual(store_count, 0)
                else:
                    self.assertEqual(count, 0)
                    self.assertEqual(store_count, 2*len(traj))
            elif 'ERROR.txt' == file:
                self.assertEqual(count, 0)
                if self.mode.multiproc:
                    self.assertEqual(error_count,0)
                    self.assertEqual(store_count, 0)
                else:
                    self.assertEqual(error_count, 2*len(traj))
                    self.assertEqual(store_count, 2*len(traj))

            elif 'Queue' in file and 'ERROR' in file:
                self.assertEqual(store_count, 2*len(traj))
            elif 'Queue' in file and 'LOG' in file:
                self.assertEqual(store_count, 2*len(traj))
            elif 'LOG' in file:
                if self.mode.multiproc and self.mode.use_pool:
                    self.assertEqual(count, 0)
                    self.assertGreaterEqual(error_count, 2)
                else:
                    self.assertEqual(count, 0)
                    self.assertEqual(error_count, 2)
                    if self.mode.wrap_mode == 'QUEUE':
                        self.assertEqual(store_count, 0)
                    else:
                        self.assertEqual(store_count, 2)
            elif 'ERROR' in file:
                if self.mode.multiproc and self.mode.use_pool:
                    self.assertEqual(count, 0)
                    self.assertGreaterEqual(error_count, 2)
                else:
                    self.assertEqual(count, 0)
                    self.assertEqual(error_count, 2)
                    if self.mode.wrap_mode == 'QUEUE':
                        self.assertEqual(store_count, 0)
                    else:
                        self.assertEqual(store_count, 2)
            else:
                self.assertTrue(False, 'There`s a file in the log folder that does not '
                                       'belong there: %s' % str(file))


    #@unittest.skipIf(platform.system() == 'Windows', 'Log file creation might fail under windows.')
    def test_logging_stdout(self):
        filename = 'teststdoutlog.hdf5'
        filename = make_temp_dir(filename)
        folder = make_temp_dir('logs')
        env = Environment(filename=filename, #log_config=get_log_config(),
                          log_levels=logging.CRITICAL, # needed for the test
                          log_stdout=('STDOUT', 50), log_folder=folder
                          )

        env.f_run(log_error)
        traj = env.v_traj
        path = get_log_path(traj)

        mainstr = 'sTdOuTLoGGinG'
        print(mainstr)
        env.f_disable_logging()

        mainfilename = os.path.join(path, 'LOG.txt')
        with open(mainfilename, mode='r') as mainf:
            full_text = mainf.read()

        self.assertTrue(mainstr in full_text)
        self.assertTrue('4444444' not in full_text)
        self.assertTrue('ERROR' not in full_text)


    def test_logging_show_progress(self):
        self.make_env(log_config=None,log_folder=make_temp_dir('logs'),
                      log_levels=logging.ERROR,
                      report_progress=(3, 'progress', 40))
        self.add_params(self.traj)
        self.explore(self.traj)

        self.env.f_run(log_all_levels)
        self.env.f_disable_logging()

        traj = self.env.v_traj

        path = get_log_path(traj)
        mainfilename = os.path.join(path, 'LOG.txt')
        with open(mainfilename, mode='r') as mainf:
            full_text = mainf.read()

        progress = 'PROGRESS: Finished'
        self.assertTrue(progress in full_text)
        bar = '[=='
        self.assertTrue(bar in full_text)


    def test_logging_show_progress_print(self):
        self.make_env(log_config=get_log_config(), log_stdout=('prostdout', 20),
                      report_progress=(3, 'print'))
        self.add_params(self.traj)
        self.explore(self.traj)

        self.env.f_run(log_all_levels)
        self.env.f_disable_logging()

        path = get_log_path(self.env.v_traj)
        mainfilename = os.path.join(path, 'LOG.txt')
        with open(mainfilename, mode='r') as mainf:
            full_text = mainf.read()

        progress = 'prostdout INFO     PROGRESS: Finished'
        self.assertTrue(progress in full_text)
        bar = '[=='
        self.assertIn(bar, full_text)


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)