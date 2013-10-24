__author__ = 'Robert Meyer'





import numpy as np

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest


from pypet.trajectory import Trajectory
from pypet.utils.explore import cartesian_product
from pypet.environment import Environment
from pypet import pypetconstants
import logging

import os

import tables as pt
from test_helpers import add_params, simple_calculations, create_param_dict, make_run, \
    TrajectoryComparator, make_temp_file



class ContinueTest(TrajectoryComparator):


    def make_run(self,env):

        ### Make a test run
        simple_arg = -13
        simple_kwarg= 13.0
        env.f_run(simple_calculations,simple_arg,simple_kwarg=simple_kwarg)



    def make_environment(self, idx, filename):

        logging.basicConfig(level = logging.INFO)

        #self.filename = '../../experiments/tests/HDF5/test.hdf5'
        logfolder = make_temp_file('experiments/tests/Log')
        trajname = 'Test%d' % idx

        env = Environment(trajectory=trajname,filename=filename,file_title=trajname, log_folder=logfolder)


        self.envs.append(env)
        self.trajs.append( env.v_trajectory)


    def explore(self, traj):
        self.explored ={'Normal.trial': [0,1],
            'Numpy.double': [np.array([1.0,2.0,3.0,4.0]), np.array([-1.0,3.0,5.0,7.0])]}


        traj.f_explore(cartesian_product(self.explored))


    def test_continueing(self):
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


        ### Create a crash and say, that the second last and last run did not work.
        pt_file = pt.openFile(self.filenames[0],mode='a')
        runtable = pt_file.getNode('/'+self.trajs[0].v_name+'/overview/runs')

        for idx,row in enumerate(runtable.iterrows()):
            if idx == 2 or idx == 3:
                row['completed'] = 0
                row.update()

        runtable.flush()
        pt_file.flush()
        pt_file.close()


        continue_file = os.path.split(self.filenames[0])[0]+'/'+self.trajs[0].v_name+'.cnt'
        self.envs[0].f_continue_run(continue_file)

        for irun in range(len(self.filenames)):
            self.trajs[irun].f_update_skeleton()
            self.trajs[irun].f_load(load_parameters=pypetconstants.UPDATE_DATA,
                                    load_derived_parameters=pypetconstants.UPDATE_DATA,
                                    load_results=pypetconstants.UPDATE_DATA)

        self.compare_trajectories(self.trajs[0],self.trajs[1])

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

        self.assertTrue(not 'Delete.Me' in self.trajs[0],'Delete.Me is still in traj')

        self.trajs[0].f_update_skeleton()
        self.trajs[0].f_load_item('Delete.Me')
        self.trajs[0].f_remove_item(self.trajs[0].f_get('Delete.Me'), remove_from_storage=True,
                                        remove_empty_groups=True)

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
        self.trajs[0].f_load(name=temp_name,as_new=False, load_parameters=2, load_derived_parameters=2, load_results=2)
        #self.trajs[0].f_load(trajectory_name=temp_name,as_new=False, load_params=2, load_derived_params=2, load_results=2)

        self.trajs[1].f_update_skeleton()
        self.trajs[1].f_load_items(self.trajs[1].f_to_dict().itervalues(),only_empties=True)
        self.compare_trajectories(self.trajs[0],self.trajs[1])


if __name__ == '__main__':
    make_run()