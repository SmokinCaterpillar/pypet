import os

import pypet.tests.testutils.ioutils as tu
from pypet import LazyStorageService
from pypet.tests.integration.environment_scoop_test import (
    EnvironmentTest,
    check_nice,
    pypetconstants,
    unittest,
)
from pypet.tests.integration.environment_test import (
    Environment,
    Parameter,
    add_params,
    create_param_dict,
    get_log_config,
    make_temp_dir,
    make_trajectory_name,
    random,
)

tu.testParams["log_config"] = "debug"
tu.prepare_log_config()


@unittest.skip
class MultiprocSCOOPNetlockTest(EnvironmentTest):
    tags = "integration", "hdf5", "environment", "multiproc", "netlock", "scoop"

    def compare_trajectories(self, traj1, traj2):
        return True

    def setUp(self):
        self.set_mode()
        self.logfolder = make_temp_dir(os.path.join("experiments", "tests", "Log"))

        random.seed()
        self.trajname = make_trajectory_name(self)
        self.filename = make_temp_dir(
            os.path.join("experiments", "tests", "HDF5", f"test{self.trajname}.hdf5")
        )

        env = Environment(
            trajectory=self.trajname,
            storage_service=LazyStorageService,
            filename=self.filename,
            file_title=self.trajname,
            log_stdout=self.log_stdout,
            log_config=get_log_config(),
            results_per_run=5,
            wildcard_functions=self.wildcard_functions,
            derived_parameters_per_run=5,
            multiproc=self.multiproc,
            ncores=self.ncores,
            wrap_mode=self.mode,
            use_pool=self.use_pool,
            gc_interval=self.gc_interval,
            freeze_input=self.freeze_input,
            fletcher32=self.fletcher32,
            complevel=self.complevel,
            complib=self.complib,
            shuffle=self.shuffle,
            pandas_append=self.pandas_append,
            pandas_format=self.pandas_format,
            encoding=self.encoding,
            niceness=self.niceness,
            use_scoop=self.use_scoop,
            port=self.url,
        )

        traj = env.v_trajectory

        traj.v_standard_parameter = Parameter

        ## Create some parameters
        self.param_dict = {}
        create_param_dict(self.param_dict)
        ### Add some parameter:
        add_params(traj, self.param_dict)

        # remember the trajectory and the environment
        self.traj = traj
        self.env = env

    def set_mode(self):
        super().set_mode()
        self.mode = pypetconstants.WRAP_MODE_NETLOCK
        self.multiproc = True
        self.freeze_input = False
        self.ncores = 4
        self.gc_interval = 3
        self.niceness = check_nice(1)
        self.use_pool = False
        self.use_scoop = True
        self.url = None

    @unittest.skip("Does not work with scoop (fully), because scoop uses main frame.")
    def test_niceness(self):
        pass
