__author__ = 'Robert Meyer'

import os
import unittest
import numpy as np
import tables
try:
    import dill
except ImportError:
    dill = None
import logging
import shutil

from pypet.trajectory import Trajectory
from pypet.utils.explore import cartesian_product
from pypet.environment import Environment
from pypet import pypetconstants
from pypet.parameter import Parameter
from pypet.tests.testutils.ioutils import run_suite, make_temp_dir, make_trajectory_name, \
     parse_args, get_log_config
from pypet.tests.testutils.data import create_param_dict, add_params, multiply, \
    simple_calculations, TrajectoryComparator, multiply_args


class CustomParameter(Parameter):

    def __init__(self, *args, **kwargs):
        super(CustomParameter, self).__init__(*args, **kwargs)


class Multiply(object):

    def __init__(self):
        self.var=42

    def __call__(self, traj, i):
        z = traj.x * traj.y + i
        traj.f_add_result('z', z)
        return z


@unittest.skipIf(dill is None, 'Only makes sense if dill is installed')
class ContinueTest(TrajectoryComparator):

    tags = 'integration', 'hdf5', 'environment', 'continue', 'dill'

    def tearDown(self):
        if hasattr(self, 'envs'):
            for env in self.envs:
                env.f_disable_logging()

        super(ContinueTest, self).tearDown()

    def make_run(self,env):

        ### Make a test run
        simple_arg = -13
        simple_kwarg= 13.0
        env.f_run(simple_calculations, simple_arg, simple_kwarg=simple_kwarg)

    def make_environment(self, idx, filename, continuable=True, delete_continue=False):

        #self.filename = '../../experiments/tests/HDF5/test.hdf5'
        self.logfolder = make_temp_dir(os.path.join('experiments',
                                                     'tests',
                                                     'Log'))
        self.cnt_folder = make_temp_dir(os.path.join('experiments','tests','cnt'))
        trajname = 'Test%d' % idx + '_' + make_trajectory_name(self)

        env = Environment(trajectory=trajname,
                          filename=filename,
                          file_title=trajname,
                          log_stdout=False,
                          log_config=get_log_config(),
                          continuable=continuable,
                          continue_folder=self.cnt_folder,
                          delete_continue=delete_continue,
                          large_overview_tables=True)


        self.envs.append(env)
        self.trajs.append( env.v_trajectory)


    def explore(self, traj):
        self.explored =cartesian_product({'Normal.trial': [0,1],
            'Numpy.double': [np.array([1.0,2.0,3.0,4.0]), np.array([-1.0,3.0,5.0,7.0])]})


        traj.f_explore(self.explored)

    # def _remove_nresults_from_traj(self, nresults):
    #
    #     hdf5_file = tables.open_file(self.filenames[0], mode='a')
    #     runtable = hdf5_file.getNode('/'+self.trajs[0].v_name +'/overview/runs')
    #
    #     for row in runtable.iterrows(0, nresults, 1):
    #         row['completed'] = 0
    #         row.update()
    #
    #     runtable.flush()
    #     hdf5_file.flush()
    #     hdf5_file.close()

    def _remove_nresults(self, traj, nresults, continue_folder):

        result_tuple_list = []

        n = 0
        for filename in os.listdir(continue_folder):
            _, ext = os.path.splitext(filename)

            if ext != '.rcnt':
                continue

            n += 1

            cnt_file = open(os.path.join(continue_folder, filename), 'rb')
            try:
                result = dill.load(cnt_file)
                cnt_file.close()
                result_tuple_list.append((result))
            except Exception:
                # delete broken files
                logging.getLogger().exception('Could not open continue snapshot '
                                              'file `%s`.' % filename)
                cnt_file.close()
                os.remove(filename)

        self.assertGreaterEqual(n, nresults)

        result_tuple_list = sorted(result_tuple_list, key=lambda x: x[0])
        timestamp_list = [x[1]['finish_timestamp'] for x in result_tuple_list]
        timestamp_list = timestamp_list[-nresults:]

        for timestamp in timestamp_list:
            filename = os.path.join(continue_folder, 'result_%s.rcnt' % repr(timestamp).replace('.','_'))
            os.remove(filename)

        result_tuple_list = []
        for filename in os.listdir(continue_folder):
            _, ext = os.path.splitext(filename)

            if ext != '.rcnt':
                continue

            cnt_file = open(os.path.join(continue_folder, filename), 'rb')
            result = dill.load(cnt_file)
            cnt_file.close()
            result_tuple_list.append((result))

        name_set = set([x[1]['name']  for x in result_tuple_list])
        removed = 0
        for run_name in traj.f_iter_runs():
            if run_name not in name_set:
                run_dict = traj.f_get_run_information(run_name, copy=False)
                run_dict['completed'] = 0
                idx = run_dict['idx']
                traj._updated_run_information.add(idx)
                removed += 1

        self.assertGreaterEqual(removed, nresults)
        logging.getLogger().error('Removed %s runs for continuing' % removed)
        traj.f_store(only_init=True)

    def test_continueing(self):
        self.filenames = [make_temp_dir('test_continuing.hdf5'), 0]

        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment( irun, filename, continuable=irun==1, delete_continue=False)

        self.param_dict={}
        create_param_dict(self.param_dict)

        for irun in range(len(self.filenames)):
            add_params(self.trajs[irun], self.param_dict)

        self.explore(self.trajs[0])
        self.explore(self.trajs[1])

        for irun in range(len(self.filenames)):
            self.make_run(self.envs[irun])

        traj_name = self.trajs[1].v_name
        continue_folder = os.path.join(self.cnt_folder, self.trajs[1].v_name)


        self.trajs[1]=self.envs[1].v_trajectory
        self._remove_nresults(self.trajs[1], 3, continue_folder)

        self.envs[1].v_current_idx = 0
        results = self.envs[1].resume(trajectory_name = traj_name)


        for irun in range(len(self.filenames)):
            self.trajs[irun].f_load(load_parameters=pypetconstants.OVERWRITE_DATA,
                                    load_derived_parameters=pypetconstants.OVERWRITE_DATA,
                                    load_results=pypetconstants.OVERWRITE_DATA,
                                    load_other_data=pypetconstants.OVERWRITE_DATA)


        self.compare_trajectories(self.trajs[0],self.trajs[1])
        #shutil.rmtree(self.cnt_folder)

        self.assertEqual(len(self.trajs[1]), len(results))

    def test_continueing_remove_completed(self):
        self.filenames = [make_temp_dir('test_continueing_remove_completed.hdf5')]

        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment( irun, filename, continuable=True, delete_continue=True)

        self.param_dict={}
        create_param_dict(self.param_dict)

        for irun in range(len(self.filenames)):
            add_params(self.trajs[irun], self.param_dict)


        self.explore(self.trajs[0])

        for irun in range(len(self.filenames)):
            self.make_run(self.envs[irun])

        traj_name = self.trajs[0].v_name
        continue_folder = os.path.join(self.cnt_folder, self.trajs[0].v_name)
        self.assertFalse(os.path.isdir(continue_folder))


    def test_removal(self):
        self.filenames = [make_temp_dir(os.path.join('experiments',
                                                      'tests',
                                                      'HDF5',
                                                      'removal.hdf5')), 0]

        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment( irun, filename)

        self.param_dict={}
        create_param_dict(self.param_dict)

        for irun in range(len(self.filenames)):
            add_params(self.trajs[irun], self.param_dict)


        self.explore(self.trajs[0])
        self.explore(self.trajs[1])


        for irun in range(len(self.filenames)):
            self.make_run(self.envs[irun])

        self.trajs[0].f_add_parameter('Delete.Me', 'I will be deleted!')
        self.trajs[0].f_store_item('Delete.Me')

        self.trajs[0].f_remove_item(self.trajs[0].f_get('Delete.Me'))

        self.assertTrue('Delete.Me' not in self.trajs[0],'Delete.Me is still in traj')

        self.trajs[0].f_load_skeleton()
        self.trajs[0].f_load_item('Delete.Me')
        self.trajs[0].f_delete_item(self.trajs[0].f_get('Delete.Me'),
                                        remove_from_trajectory=True)

        self.trajs[0].f_load_skeleton()
        self.assertTrue(not 'Delete.Me' in self.trajs[0],'Delete.Me is still in traj')


        for irun in range(len(self.filenames)):
            self.trajs[irun].f_load_child('results',recursive=True,load_data=pypetconstants.OVERWRITE_DATA)
            self.trajs[irun].f_load_child('derived_parameters',recursive=True,load_data=pypetconstants.OVERWRITE_DATA)

        self.compare_trajectories(self.trajs[0],self.trajs[1])


    def test_multiple_storage_and_loading(self):
        self.filenames = [make_temp_dir(os.path.join('experiments',
                                                      'tests',
                                                      'HDF5',
                                                      'multiple_storage_and_loading.hdf5')), 0]

        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment( irun, filename)

        self.param_dict={}
        create_param_dict(self.param_dict)

        for irun in range(len(self.filenames)):
            add_params(self.trajs[irun],self.param_dict)

        self.explore(self.trajs[0])
        self.explore(self.trajs[1])

        for irun in range(len(self.filenames)):
            self.make_run(self.envs[irun])

        #self.trajs[0].f_store()

        temp_sservice = self.trajs[0].v_storage_service
        temp_name = self.trajs[0].v_name

        self.trajs[0] = Trajectory()
        self.trajs[0].v_storage_service=temp_sservice
        self.trajs[0].f_load(name=temp_name, as_new=False, load_parameters=2,
                             load_derived_parameters=2, load_results=2, load_other_data=2)
        #self.trajs[0].f_load(trajectory_name=temp_name,as_new=False, load_params=2, load_derived_params=2, load_results=2)

        self.trajs[1].f_load_skeleton()
        self.trajs[1].f_load_items(self.trajs[1].f_to_dict().values(),only_empties=True)
        self.compare_trajectories(self.trajs[0],self.trajs[1])


@unittest.skipIf(dill is None, 'Only makes sense if dill is installed')
class ContinueMPTest(ContinueTest):

    # def test_removal(self):
    #     return super(ContinueMPTest, self).test_removal()

    tags = 'integration', 'hdf5', 'environment', 'continue', 'multiproc', 'nopool', 'dill'

    def make_run_mp(self,env):
        env.f_run(multiply)


    def make_environment(self, idx, filename, continuable=True, delete_continue=False,
                         add_time=True,
                         trajectory=None):
        #self.filename = '../../experiments/tests/HDF5/test.hdf5'
        self.logfolder = make_temp_dir(os.path.join('experiments',
                                                     'tests',
                                                     'Log'))
        self.cnt_folder = make_temp_dir(os.path.join('experiments',
                                                      'tests',
                                                      'cnt'))
        trajname = 'Test%d' % idx + '_' + make_trajectory_name(self)

        env = Environment(trajectory=trajname if trajectory is None else trajectory,
                          dynamically_imported_classes=[CustomParameter],
                          filename=filename,
                          add_time=add_time,
                          file_title=trajname,
                          log_stdout=False,
                          use_pool=False,
                          log_config=get_log_config(),
                          continuable=continuable,
                          continue_folder=self.cnt_folder,
                          delete_continue=delete_continue,
                          multiproc=True,
                          purge_duplicate_comments=False,
                          ncores=2)


        self.envs.append(env)
        self.trajs.append( env.v_trajectory)

    def explore_mp(self, traj):
        self.explored={'x':[0.0, 1.0, 2.0, 3.0, 4.0], 'y':[0.1, 2.2, 3.3, 4.4, 5.5]}

        traj.f_explore(cartesian_product(self.explored))

    def test_continueing_mp_custom(self):
        self.filenames = [make_temp_dir('test_continueing_mp_custom.hdf5'),
                          make_temp_dir('test_continueing_mp_custom2.hdf5')]

        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment(irun, filename, continuable=irun == 1)

        self.param_dict={'x':1.0, 'y':2.0}

        for irun in range(len(self.filenames)):
            self.trajs[irun].f_add_parameter(CustomParameter,'x', 1.0)
            self.trajs[irun].f_add_parameter(CustomParameter, 'y', 1.0)


        self.explore_mp(self.trajs[0])
        self.explore_mp(self.trajs[1])

        arg=33
        for irun in range(len(self.filenames)):

            self.envs[irun].f_run(Multiply(), arg)

        traj_name = self.trajs[1].v_name
        continue_folder = os.path.join(self.cnt_folder, self.trajs[1].v_name)

        self.envs.pop()
        self.assertEqual(len(self.envs), 1)
        self.make_environment(1, self.filenames[1], continuable=True, add_time=False,
                              trajectory=traj_name)
        self.trajs[1] = self.envs[1].v_traj
        self.trajs[1].f_load(load_data=pypetconstants.LOAD_NOTHING)
        self._remove_nresults(self.trajs[1], 3, continue_folder)

        results = self.envs[1].resume(trajectory_name = traj_name)
        results = sorted(results, key = lambda x: x[0])

        for irun in range(len(self.filenames)):
            self.trajs[irun].f_load(load_parameters=pypetconstants.OVERWRITE_DATA,
                                    load_derived_parameters=pypetconstants.OVERWRITE_DATA,
                                    load_results=pypetconstants.OVERWRITE_DATA,
                                    load_other_data=pypetconstants.OVERWRITE_DATA)

        self.compare_trajectories(self.trajs[1],self.trajs[0])

        for run_name in self.trajs[0].f_iter_runs():
            z = (self.trajs[0].v_idx, self.trajs[0].crun.z)
            self.assertTrue(z in results, '%s not in %s' % (z, results))

        self.assertTrue(len(self.trajs[-1])== len(results))
        #os.removedirs(self.cnt_folder)

    def test_continueing_mp(self):
        self.filenames = [make_temp_dir('test_continueing_mp.hdf5'), 0]

        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment( irun, filename, continuable=irun==1, delete_continue=False)

        self.param_dict={'x':1.0, 'y':2.0}

        for irun in range(len(self.filenames)):
            self.trajs[irun].f_add_parameter(CustomParameter,'x', 1.0)
            self.trajs[irun].f_add_parameter(CustomParameter, 'y', 1.0)

        self.explore_mp(self.trajs[0])
        self.explore_mp(self.trajs[1])

        for irun in range(len(self.filenames)):
            self.envs[irun].f_run(multiply)

        traj_name = self.trajs[1].v_name
        continue_folder = os.path.join(self.cnt_folder, self.trajs[1].v_name)


        self.trajs[1]=self.envs[1].v_trajectory
        self._remove_nresults(self.trajs[1], 3, continue_folder)

        self.envs[1].v_current_idx = 0
        results = self.envs[1].resume(trajectory_name = traj_name)
        results = sorted(results, key = lambda x: x[0])

        for irun in range(len(self.filenames)):
            self.trajs[irun].f_load(load_parameters=pypetconstants.OVERWRITE_DATA,
                                    load_derived_parameters=pypetconstants.OVERWRITE_DATA,
                                    load_results=pypetconstants.OVERWRITE_DATA,
                                    load_other_data=pypetconstants.OVERWRITE_DATA)

        self.compare_trajectories(self.trajs[1],self.trajs[0])

        self.assertEqual(len(self.trajs[1]), len(results))

        for run_name in self.trajs[0].f_iter_runs():
            z = (self.trajs[0].v_idx, self.trajs[0].crun.z)
            self.assertTrue( z in results, '%s not in %s' % (z, results))


@unittest.skipIf(dill is None, 'Only makes sense if dill is installed')
class ContinueMPPoolTest(ContinueMPTest):

    tags = 'integration', 'hdf5', 'environment', 'continue', 'multiproc', 'pool', 'dill'

    def make_environment_mp(self, idx, filename):
        #self.filename = '../../experiments/tests/HDF5/test.hdf5'
        self.logfolder = make_temp_dir(os.path.join('experiments',
                                                      'tests',
                                                      'Log'))
        self.cnt_folder = make_temp_dir(os.path.join('experiments',
                                                      'tests',
                                                      'cnt'))
        trajname = 'Test%d' % idx + '_' + make_trajectory_name(self)

        env = Environment(trajectory=trajname,
                          dynamic_imports=[CustomParameter],
                          filename=filename,
                          file_title=trajname,
                          log_stdout=False,
                          purge_duplicate_comments=False,
                          log_config=get_log_config(),
                          continuable=True,
                          continue_folder=self.cnt_folder,
                          delete_continue=False,
                          multiproc=True,
                          use_pool=True,
                          ncores=4)

        self.envs.append(env)
        self.trajs.append( env.v_trajectory)


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)