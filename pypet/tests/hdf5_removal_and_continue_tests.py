__author__ = 'Robert Meyer'

import numpy as np


from pypet.trajectory import Trajectory
from pypet.utils.explore import cartesian_product
from pypet.environment import Environment
from pypet import pypetconstants
from pypet.parameter import Parameter
import logging
import multiprocessing as mp
import pickle
import tables

import os
import dill

import tables as pt
from pypet.tests.test_helpers import add_params, simple_calculations, create_param_dict, make_run, \
    TrajectoryComparator, make_temp_file, multiply

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



class ContinueTest(TrajectoryComparator):


    def make_run(self,env):

        ### Make a test run
        simple_arg = -13
        simple_kwarg= 13.0
        env.f_run(simple_calculations, simple_arg, simple_kwarg=simple_kwarg)

    def make_environment(self, idx, filename):



        #self.filename = '../../experiments/tests/HDF5/test.hdf5'
        self.logfolder = make_temp_file('experiments/tests/Log')
        self.cnt_folder = make_temp_file('experiments/tests/cnt/')
        trajname = 'Test%d' % idx

        env = Environment(trajectory=trajname,
                          filename=filename,
                          file_title=trajname,
                          log_folder=self.logfolder,
                          log_stdout=False,
                          continuable=True,
                          continue_folder=self.cnt_folder,
                          delete_continue=False,
                          large_overview_tables=True)


        self.envs.append(env)
        self.trajs.append( env.v_trajectory)


    def explore(self, traj):
        self.explored ={'Normal.trial': [0,1],
            'Numpy.double': [np.array([1.0,2.0,3.0,4.0]), np.array([-1.0,3.0,5.0,7.0])]}


        traj.f_explore(self.explored)


    def _remove_nresults_from_traj(self, nresults):

        hdf5_file = tables.openFile(self.filenames[0], mode='a')
        runtable = hdf5_file.getNode('/'+self.trajs[0].v_name +'/overview/runs')

        for row in runtable.iterrows(0, nresults, 1):
            row['completed'] = 0
            row.update()

        runtable.flush()
        hdf5_file.flush()
        hdf5_file.close()

    def _remove_nresults(self, nresults, continue_folder):

        result_tuple_list = []
        for filename in os.listdir(continue_folder):
            _, ext = os.path.splitext(filename)

            if ext != '.rcnt':
                continue

            cnt_file = open(os.path.join(continue_folder, filename), 'rb')
            result_dict = dill.load(cnt_file)
            cnt_file.close()
            result_tuple_list.append((result_dict['timestamp'], result_dict['result']))

        # Sort according to counter
        result_tuple_list = sorted(result_tuple_list, key=lambda x: x[0])
        timestamp_list = [x[0] for x in result_tuple_list]

        timestamp_list = timestamp_list[-nresults:]

        for timestamp in timestamp_list:
            filename = os.path.join(continue_folder, 'result_%s.rcnt' % repr(timestamp).replace('.','_'))
            os.remove(filename)


    def test_continueing(self):
        self.filenames = [make_temp_file('test_removal.hdf5'), 0]

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

        traj_name = self.trajs[0].v_name
        continue_folder = os.path.join(self.cnt_folder, self.trajs[0].v_name)
        self._remove_nresults(3, continue_folder)
        self.make_environment(0, self.filenames[0])
        self.envs[-1].f_continue(trajectory_name = traj_name)

        self.trajs[-1]=self.envs[-1].v_trajectory

        for irun in range(len(self.filenames)+1):
            self.trajs[irun].f_update_skeleton()
            self.trajs[irun].f_load(load_parameters=pypetconstants.OVERWRITE_DATA,
                                    load_derived_parameters=pypetconstants.OVERWRITE_DATA,
                                    load_results=pypetconstants.OVERWRITE_DATA,
                                    load_other_data=pypetconstants.OVERWRITE_DATA)

        self.compare_trajectories(self.trajs[-1],self.trajs[1])

    def test_continueing_remove_completed(self):
        self.filenames = [make_temp_file('test_removal_comp.hdf5'), 0]

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

        traj_name = self.trajs[0].v_name
        continue_folder = os.path.join(self.cnt_folder, self.trajs[0].v_name)
        self._remove_nresults_from_traj(2)
        self.make_environment(0, self.filenames[0])
        self.envs[-1].f_continue(trajectory_name = traj_name)

        self.trajs[-1]=self.envs[-1].v_trajectory

        for irun in range(len(self.filenames)+1):
            self.trajs[irun].f_update_skeleton()
            self.trajs[irun].f_load(load_parameters=pypetconstants.OVERWRITE_DATA,
                                    load_derived_parameters=pypetconstants.OVERWRITE_DATA,
                                    load_results=pypetconstants.OVERWRITE_DATA,
                                    load_other_data=pypetconstants.OVERWRITE_DATA)

        self.compare_trajectories(self.trajs[-1],self.trajs[1])


    def test_removal(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge1.hdf5'), 0]



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

        self.trajs[0].f_remove_item(self.trajs[0].f_get('Delete.Me'),
                                        remove_empty_groups=True)

        self.assertTrue('Delete.Me' not in self.trajs[0],'Delete.Me is still in traj')

        self.trajs[0].f_update_skeleton()
        self.trajs[0].f_load_item('Delete.Me')
        self.trajs[0].f_delete_item(self.trajs[0].f_get('Delete.Me'),
                                        remove_empty_groups=True,
                                        remove_from_trajectory=True)

        self.trajs[0].f_update_skeleton()
        self.assertTrue(not 'Delete.Me' in self.trajs[0],'Delete.Me is still in traj')


        for irun in range(len(self.filenames)):
            self.trajs[irun].f_update_skeleton()
            self.trajs[irun].f_load_child('results',recursive=True,load_data=pypetconstants.UPDATE_DATA)
            self.trajs[irun].f_load_child('derived_parameters',recursive=True,load_data=pypetconstants.UPDATE_DATA)

        self.compare_trajectories(self.trajs[0],self.trajs[1])


    def test_multiple_storage_and_loading(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge1.hdf5'), 0]



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
        self.trajs[0].f_load(name=temp_name,as_new=False, load_parameters=2, load_derived_parameters=2, load_results=2,
                             load_other_data=2)
        #self.trajs[0].f_load(trajectory_name=temp_name,as_new=False, load_params=2, load_derived_params=2, load_results=2)

        self.trajs[1].f_update_skeleton()
        self.trajs[1].f_load_items(self.trajs[1].f_to_dict().values(),only_empties=True)
        self.compare_trajectories(self.trajs[0],self.trajs[1])


class ContinueMPTest(ContinueTest):

    def make_run_mp(self,env):
        env.f_run(multiply)


    def make_environment_mp(self, idx, filename):
        #self.filename = '../../experiments/tests/HDF5/test.hdf5'
        self.logfolder = make_temp_file('experiments/tests/Log')
        self.cnt_folder = make_temp_file('experiments/tests/cnt/')
        trajname = 'Test%d' % idx

        env = Environment(trajectory=trajname,
                          dynamically_imported_classes=[CustomParameter],
                          filename=filename,
                          file_title=trajname,
                          log_folder=self.logfolder,
                          log_stdout=False,
                          continuable=True,
                          continue_folder=self.cnt_folder,
                          delete_continue=False,
                          multiproc=True,
                          ncores=2)


        self.envs.append(env)
        self.trajs.append( env.v_trajectory)

    def explore_mp(self, traj):
        self.explored={'x':[0.0, 1.0, 2.0, 3.0, 4.0], 'y':[0.1, 2.2, 3.3, 4.4, 5.5]}

        traj.f_explore(cartesian_product(self.explored))

    def test_continueing_mp2(self):
        self.filenames = [make_temp_file('test_removal2.hdf5'), 0]



        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment_mp( irun, filename)

        self.param_dict={'x':1.0, 'y':2.0}



        for irun in range(len(self.filenames)):
            self.trajs[irun].f_add_parameter(CustomParameter,'x', 1.0)
            self.trajs[irun].f_add_parameter(CustomParameter, 'y', 1.0)


        self.explore_mp(self.trajs[0])
        self.explore_mp(self.trajs[1])

        arg=33
        for irun in range(len(self.filenames)):

            self.envs[irun].f_run(Multiply(), arg)



        traj_name = self.trajs[0].v_name
        continue_folder = os.path.join(self.cnt_folder, self.trajs[0].v_name)
        self._remove_nresults(3, continue_folder)
        self.make_environment(0, self.filenames[0])
        results = self.envs[-1].f_continue(trajectory_name = traj_name)
        results = [result[1] for result in results]

        self.trajs[-1]=self.envs[-1].v_trajectory


        for irun in range(len(self.filenames)+1):
            self.trajs[irun].f_update_skeleton()
            self.trajs[irun].f_load(load_parameters=pypetconstants.OVERWRITE_DATA,
                                    load_derived_parameters=pypetconstants.OVERWRITE_DATA,
                                    load_results=pypetconstants.OVERWRITE_DATA,
                                    load_other_data=pypetconstants.OVERWRITE_DATA)

        self.compare_trajectories(self.trajs[-1],self.trajs[1])

        for run_name in self.trajs[-1].f_iter_runs():
            self.assertTrue(self.trajs[-1].z in results)

        self.assertTrue(len(self.trajs[-1])== len(results))


    def test_continueing_mp(self):
        self.filenames = [make_temp_file('test_removal2.hdf5'), 0]



        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment_mp( irun, filename)

        self.param_dict={'x':1.0, 'y':2.0}



        for irun in range(len(self.filenames)):
            self.trajs[irun].f_add_parameter(CustomParameter,'x', 1.0)
            self.trajs[irun].f_add_parameter(CustomParameter, 'y', 1.0)


        self.explore_mp(self.trajs[0])
        self.explore_mp(self.trajs[1])

        for irun in range(len(self.filenames)):
            self.envs[irun].f_run(multiply)



        traj_name = self.trajs[0].v_name
        continue_folder = os.path.join(self.cnt_folder, self.trajs[0].v_name)
        self._remove_nresults(3, continue_folder)
        self.make_environment(0, self.filenames[0])
        results = self.envs[-1].f_continue(trajectory_name = traj_name)
        results = [result[1] for result in results]

        self.trajs[-1]=self.envs[-1].v_trajectory

        for irun in range(len(self.filenames)+1):
            self.trajs[irun].f_update_skeleton()
            self.trajs[irun].f_load(load_parameters=pypetconstants.OVERWRITE_DATA,
                                    load_derived_parameters=pypetconstants.OVERWRITE_DATA,
                                    load_results=pypetconstants.OVERWRITE_DATA,
                                    load_other_data=pypetconstants.OVERWRITE_DATA)

        self.compare_trajectories(self.trajs[-1],self.trajs[1])

        for run_name in self.trajs[0].f_iter_runs():
            self.assertTrue(self.trajs[0].z in results)

class ContinueMPPoolTest(ContinueMPTest):

    def make_environment_mp(self, idx, filename):
        #self.filename = '../../experiments/tests/HDF5/test.hdf5'
        self.logfolder = make_temp_file('experiments/tests/Log')
        self.cnt_folder = make_temp_file('experiments/tests/cnt/')
        trajname = 'Test%d' % idx

        env = Environment(trajectory=trajname,
                          dynamically_imported_classes=[CustomParameter],
                          filename=filename,
                          file_title=trajname,
                          log_folder=self.logfolder,
                          log_stdout=False,
                          continuable=True,
                          continue_folder=self.cnt_folder,
                          delete_continue=False,
                          multiproc=True,
                          use_pool=True,
                          ncores=4)

        self.envs.append(env)
        self.trajs.append( env.v_trajectory)

if __name__ == '__main__':
    make_run()