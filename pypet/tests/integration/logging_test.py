__author__ = 'Robert Meyer'

import logging

from pypet import Result
from pypet.tests.testutils.data import TrajectoryComparator
from pypet.tests.testutils.ioutils import parse_args, run_suite, get_root_logger, make_temp_dir,\
    make_trajectory_name, get_log_level, get_log_options
from pypet import Environment, Trajectory
import pypet.pypetconstants as pypetconstants
import os


class LogWhenStored(Result):

    def __init__(self, full_name, *args, **kwargs):
        self._level = kwargs['level']
        super(LogWhenStored, self).__init__(full_name, *args, **kwargs)

    def _store(self):
        self._logger.log(self._level, 'LOG_Test in Parameter')
        return super(LogWhenStored, self)._store()

def add_result(traj, level=logging.ERROR):
    traj.f_ares(LogWhenStored, 'logging.test',
                42, level=level, comment='I log an error when stored to disk!')

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
        self.mode.log_levels=get_log_level()
        self.mode.log_options=get_log_options()


    def make_env(self, **kwargs):

        self.mode.__dict__.update(kwargs)
        filename = 'log_testing.hdf5'
        self.filename = make_temp_dir(filename)
        self.log_folder = make_temp_dir('logs')
        self.traj_name = make_trajectory_name(self)
        self.env = Environment(trajectory=self.traj_name, log_folder=self.log_folder,
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
        self.make_env(log_options=(pypetconstants.LOG_MODE_FILE), log_levels=logging.INFO)
        self.add_params(self.traj)
        self.explore(self.traj)

        self.env.f_run(log_wo_error_levels)
        self.env.f_disable_logging()

        log_path = self.env.v_log_path

        if self.mode.multiproc:
            if self.mode.wrap_mode == 'LOCK':
                length = len(self.traj) + 1
            elif self.mode.wrap_mode == 'QUEUE':
                length = len(self.traj) + 2
            else:
                raise RuntimeError('You shall not pass!')
        else:
            length = 1


        file_list = [file for file in os.listdir(log_path)]

        self.assertEqual(len(file_list), length) # assert that there are as many
        # files as runs plus main.txt and errors and warnings

        for file in file_list:
            openfile = False
            if 'main' in file:
                openfile = True
            elif 'process' in file:
                openfile = True
            elif 'poolworker' in file:
                openfile = True
            elif 'queue' in file:
                openfile = True
            else:
                self.assertTrue(False, 'There`s a file in the log folder that does not '
                                       'belong there: %s' % str(file))
            if openfile:
                with open(os.path.join(log_path, file), mode='r') as fh:
                    text = fh.read()
                    self.assertIn('pypet.', text)

    # @unittest.skipIf(platform.system() == 'Windows', 'Log file creation might fail under windows.')
    def test_logfile_creation_with_errors(self):
         # if not self.multiproc:
        #     return
        self.make_env(log_options=(pypetconstants.LOG_MODE_FILE))
        self.add_params(self.traj)
        self.explore(self.traj)

        self.env.f_run(log_error)
        if self.mode.multiproc:
            logging.getLogger('pypet.test').error('ttt')
        self.env.f_disable_logging()

        log_path = self.env.v_log_path

        if self.mode.multiproc:
            if self.mode.wrap_mode == 'LOCK':
                length = 2*len(self.traj) + 2
            elif self.mode.wrap_mode == 'QUEUE':
                length = 2*len(self.traj) + 4
            else:
                raise RuntimeError('You shall not pass!')
        else:
            length = 2

        file_list = [file for file in os.listdir(log_path)]

        self.assertEqual(len(file_list), length) # assert that there are as many
        # files as runs plus main.txt and errors and warnings

        for file in file_list:
            openfile = False
            if 'main' in file:
                openfile = True
            elif 'process' in file:
                openfile = True
            elif 'poolworker' in file:
                openfile = True
            elif 'queue' in file:
                openfile = True
            else:
                self.assertTrue(False, 'There`s a file in the log folder that does not '
                                       'belong there: %s' % str(file))
            if openfile:
                with open(os.path.join(log_path, file), mode='r') as fh:
                    text = fh.read()
                    self.assertIn('pypet.', text)

    # @unittest.skipIf(platform.system() == 'Windows', 'Log file creation might fail under windows.')
    def test_logfile_creation_normal_queue(self):
        # if not self.multiproc:
        #     return
        self.make_env(log_options=(pypetconstants.LOG_MODE_QUEUE), log_levels=logging.WARNING)
        self.add_params(self.traj)
        self.explore(self.traj)

        self.env.f_run(log_wo_error_levels)
        self.env.f_disable_logging()

        log_path = self.env.v_log_path
        length = 1

        file_list = [file for file in os.listdir(log_path)]

        self.assertEqual(len(file_list), length) # assert that there are as many
        # files as runs plus main.txt and errors and warnings

        for file in file_list:
            openfile = False
            if 'main' in file:
                openfile = True
            elif 'process' in file:
                openfile = True
            elif 'poolworker' in file:
                openfile = True
            elif 'queue' in file:
                openfile = True
            else:
                self.assertTrue(False, 'There`s a file in the log folder that does not '
                                       'belong there: %s' % str(file))
            if openfile:
                with open(os.path.join(log_path, file), mode='r') as fh:
                    text = fh.read()
                    self.assertIn('pypet.', text)

    # @unittest.skipIf(platform.system() == 'Windows', 'Log file creation might fail under windows.')
    def test_logfile_creation_with_errors_queue(self):
         # if not self.multiproc:
        #     return
        self.make_env(log_options=(pypetconstants.LOG_MODE_QUEUE))
        self.add_params(self.traj)
        self.explore(self.traj)

        self.env.f_run(log_all_levels)
        self.env.f_disable_logging()

        log_path = self.env.v_log_path

        length = 2

        file_list = [file for file in os.listdir(log_path)]

        self.assertEqual(len(file_list), length) # assert that there are as many
        # files as runs plus main.txt and errors and warnings

        for file in file_list:
            openfile = False
            if 'main' in file:
                openfile = True
            elif 'process' in file:
                openfile = True
            elif 'poolworker' in file:
                openfile = True
            elif 'queue' in file:
                openfile = True
            else:
                self.assertTrue(False, 'There`s a file in the log folder that does not '
                                       'belong there: %s' % str(file))
            if openfile:
                with open(os.path.join(log_path, file), mode='r') as fh:
                    text = fh.read()
                    self.assertIn('pypet.', text)

    def test_logfile_creation_with_errors_all_loggers(self):
         # if not self.multiproc:
        #     return
        self.make_env(log_options=(pypetconstants.LOG_MODE_QUEUE, pypetconstants.LOG_MODE_FILE,
                                    pypetconstants.LOG_MODE_QUEUE_STREAM,
                                    pypetconstants.LOG_MODE_STREAM,
                                    pypetconstants.LOG_MODE_MAIN_STREAM,
                                    pypetconstants.LOG_MODE_NULL))

        self.add_params(self.traj)
        self.explore(self.traj)

        self.env.f_run(log_all_levels)
        if self.mode.multiproc:
            logging.getLogger('pypet.test').error('ttt')
        self.env.f_disable_logging()

        log_path = self.env.v_log_path

        if self.mode.multiproc:
            if self.mode.wrap_mode == 'LOCK':
                length = 2*len(self.traj) + 4
            elif self.mode.wrap_mode == 'QUEUE':
                length = 2*len(self.traj) + 6
            else:
                raise RuntimeError('You shall not pass!')
        else:
            length = 4

        file_list = [file for file in os.listdir(log_path)]

        self.assertEqual(len(file_list), length) # assert that there are as many
        # files as runs plus main.txt and errors and warnings

        for file in file_list:
            openfile = False
            if 'main' in file:
                openfile = True
            elif 'process' in file:
                openfile = True
            elif 'poolworker' in file:
                openfile = True
            elif 'queue' in file:
                openfile = True
            else:
                self.assertTrue(False, 'There`s a file in the log folder that does not '
                                       'belong there: %s' % str(file))
            if openfile:
                with open(os.path.join(log_path, file), mode='r') as fh:
                    text = fh.read()
                    self.assertIn('pypet.', text)

    def test_multiple_loggers_defined(self):
        filename = make_temp_dir('full_store.hdf5')
        logfolder = make_temp_dir('logs')
        custom_logger = logging.getLogger('custom')
        custom2_logger = logging.getLogger('custom2')
        custom3_logger = logging.getLogger('custom3')

        root = logging.getLogger()
        rootstr = 'NOTLOGGED'

        logstr = 'TEST CUSTOM LOGGING!'
        logstr2 = 'AAAAAAAAAAAA'
        logstr3 = 'ISHOULDNOTBE'
        with Environment(log_folder=logfolder, filename=filename,
                         log_options=pypetconstants.LOG_MODE_QUEUE,
                         logger_names=('', 'custom', 'custom2'),
                         log_levels=(logging.CRITICAL, logging.DEBUG, logging.DEBUG)) as env:
            custom_logger.debug(logstr)
            custom2_logger.debug(logstr2)
            custom3_logger.debug(logstr3)
            root.debug(rootstr)

            logpath = env.v_log_path

        with open(os.path.join(logpath, 'main_queue_log.txt'), 'r') as fh:
            text = fh.read()
            self.assertTrue(logstr in text)
            self.assertTrue(logstr2 in text)
            self.assertFalse(logstr3 in text)
            self.assertFalse(rootstr in text)

    #@unittest.skipIf(platform.system() == 'Windows', 'Log file creation might fail under windows.')
    def test_logging_stdout(self):
        filename = 'teststdoutlog.hdf5'
        filename = make_temp_dir(filename)
        env = Environment(filename=filename, log_levels=logging.CRITICAL, # needed for the test
                          log_folder=make_temp_dir('logs'),
                          log_stdout=('STDOUT', 50),
                          logger_names=('STDERR', 'STDOUT'),
                          log_options=pypetconstants.LOG_MODE_QUEUE)

        path = env.v_log_path

        mainstr = 'sTdOuTLoGGinG'
        print(mainstr)
        env.f_disable_logging()

        mainfilename = os.path.join(path, 'main_queue_log.txt')
        with open(mainfilename, mode='r') as mainf:
            full_text = mainf.read()

        self.assertTrue(mainstr in full_text)
        self.assertTrue('4444444' not in full_text)
        self.assertTrue('pypet' not in full_text)


    def test_logging_show_progress(self):
        self.make_env(log_options=(pypetconstants.LOG_MODE_QUEUE),
                      log_levels=logging.INFO,
                      report_progress=(3, 'progress'))
        self.add_params(self.traj)
        self.explore(self.traj)

        self.env.f_run(log_all_levels)
        self.env.f_disable_logging()

        path = self.env.v_log_path
        mainfilename = os.path.join(path, 'main_queue_log.txt')
        with open(mainfilename, mode='r') as mainf:
            full_text = mainf.read()

        progress = 'PROGRESS: Finished'
        self.assertTrue(progress in full_text)
        bar = '[=='
        self.assertTrue(bar in full_text)


    def test_logging_show_progress_print(self):
        self.make_env(log_options=(pypetconstants.LOG_MODE_QUEUE),
                      log_levels=logging.INFO,
                      log_stdout='prostdout',
                      report_progress=(3, 'print'))
        self.add_params(self.traj)
        self.explore(self.traj)

        self.env.f_run(log_all_levels)
        self.env.f_disable_logging()

        path = self.env.v_log_path
        mainfilename = os.path.join(path, 'main_queue_log.txt')
        with open(mainfilename, mode='r') as mainf:
            full_text = mainf.read()

        progress = 'prostdout INFO     PROGRESS: Finished'
        self.assertTrue(progress in full_text)
        bar = '[=='
        self.assertTrue(bar in full_text)



if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)