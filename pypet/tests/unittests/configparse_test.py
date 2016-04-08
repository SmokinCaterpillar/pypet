__author__ = 'Robert Meyer'

import os

from pypet.tests.testutils.ioutils import  run_suite, make_temp_dir,\
    parse_args, handle_config_file
from pypet.tests.testutils.data import  TrajectoryComparator
from pypet import Environment
import pypet


class ConfigParseTest(TrajectoryComparator):

    tags = 'configparser', 'unittest'

    def setUp(self):

        pypet_path = os.path.abspath(os.path.dirname(pypet.environment.__file__))
        init_path = os.path.join(pypet_path, 'logging')
        self.config_file = os.path.join(init_path, 'env_config_test.ini')
        self.parser = handle_config_file(self.config_file)


    def test_parsing(self):

        filename = make_temp_dir('config_test.hdf5')
        env = Environment(filename=filename, config=self.parser)

        traj = env.v_traj
        self.assertTrue(traj.v_auto_load)
        self.assertEqual(traj.v_storage_service.filename, filename)

        self.assertEqual(traj.x, 42)
        self.assertEqual(traj.f_get('y').v_comment, 'This is the second variable')
        self.assertTrue(traj.testconfig)

        self.assertTrue(env._logging_manager.log_config is not None)
        self.assertTrue(env._logging_manager._sp_config is not None)

        env.f_disable_logging()


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)