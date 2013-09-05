__author__ = 'Robert Meyer'





import numpy as np
import unittest
from mypet.parameter import BaseParameter,Parameter, PickleParameter, BaseResult, ArrayParameter, PickleResult
from mypet.trajectory import Trajectory, SingleRun
from mypet.storageservice import LazyStorageService
from mypet.utils.explore import identity,cartesian_product
from mypet.environment import Environment
from mypet.storageservice import HDF5StorageService
from mypet import globally
import pickle
import logging
import cProfile
from mypet.utils.helpful_functions import flatten_dictionary
from mypet.utils.comparisons import results_equal,parameters_equal
import scipy.sparse as spsp
import os
import shutil
import pandas as pd
import tables as pt


REMOVE = True
SINGLETEST=[3]


def simple_calculations(traj, arg1, simple_kwarg):


        # all_mat = traj.csc_mat + traj.lil_mat + traj.csr_mat
        Normal_int= traj.Normal.int
        Sum= np.sum(traj.Numpy.double)

        # result_mat = all_mat * Normal_int * Sum * arg1 * simple_kwarg



        my_dict = {}

        my_dict2={}
        for key, val in traj.parameters.to_dict(fast_access=True,short_names=False).items():
            if 'trial' in key:
                continue
            newkey = key.replace('.','_')
            my_dict[newkey] = str(val)
            my_dict2[newkey] = [str(val)+' juhu!']

        my_dict['__FLOAT'] = 44.0
        my_dict['__INT'] = 66
        my_dict['__NPINT'] = np.int_(55)
        my_dict['__INTaRRAy'] = np.array([1,2,3])
        my_dict['__FLOATaRRAy'] = np.array([1.0,2.0,41.0])
        my_dict['__STRaRRAy'] = np.array(['sds','aea','sf'])

        keys = traj.to_dict(short_names=False).keys()
        for idx,key in enumerate(keys):
            keys[idx] = key.replace('.','_')

        traj.add_result('List.Of.Keys', dict1=my_dict, dict2=my_dict2)
        traj.add_result('DictsNFrame', keys=keys)
        traj.add_result('ResMatrix',np.array([1.2,2.3]))
        #traj.add_derived_parameter('All.To.String', str(traj.to_dict(fast_access=True,short_names=False)))

        myframe = pd.DataFrame(data ={'TC1':[1,2,3],'TC2':['Waaa',np.nan,''],'TC3':[1.2,42.2,np.nan]})

        traj.DictsNFrame.set(myframe)

        traj.add_result('IStore.SimpleThings',1.0,3,np.float32(5.0), 'Iamstring',(1,2,3),[4,5,6],zwei=2)
        traj.adp('mega',33)

        #traj.add_result('PickleTerror', result_type=PickleResult, test=traj.SimpleThings)


class ContinueTest(unittest.TestCase):



    def compare_trajectories(self,traj1,traj2):

        old_items = traj1.to_dict(fast_access=False)
        new_items = traj2.to_dict(fast_access=False)



        self.assertEqual(len(old_items),len(new_items))
        for key,item in new_items.items():
            old_item = old_items[key]
            if key.startswith('config'):
                continue

            if isinstance(item, BaseParameter):
                self.assertTrue(parameters_equal(item,old_item),
                                'For key %s: %s not equal to %s' %(key,str(old_item),str(item)))
            elif isinstance(item,BaseResult):
                self.assertTrue(results_equal(item, old_item),
                                'For key %s: %s not equal to %s' %(key,str(old_item),str(item)))
            else:
                raise RuntimeError('You shall not pass')

    def make_run(self,env):

        ### Make a test run
        simple_arg = -13
        simple_kwarg= 13.0
        env.run(simple_calculations,simple_arg,simple_kwarg=simple_kwarg)

    def _create_param_dict(self):
        self.param_dict = {}

        self.param_dict['Normal'] = {}
        self.param_dict['Numpy'] = {}
        # self.param_dict['Sparse'] ={}
        self.param_dict['Numpy_2D'] = {}
        self.param_dict['Numpy_3D'] = {}
        self.param_dict['Tuples'] ={}

        normal_dict = self.param_dict['Normal']
        normal_dict['string'] = 'Im a test string!'
        normal_dict['int'] = 42
        normal_dict['double'] = 42.42
        normal_dict['bool'] =True
        normal_dict['trial'] = 0

        numpy_dict=self.param_dict['Numpy']
        numpy_dict['string'] = np.array(['Uno', 'Dos', 'Tres'])
        numpy_dict['int'] = np.array([1,2,3,4])
        numpy_dict['double'] = np.array([1.0,2.0,3.0,4.0])
        numpy_dict['bool'] = np.array([True,False, True])

        #self.param_dict['Numpy_2D']['double'] = np.array([[1.0,2.0],[3.0,4.0]])
        #self.param_dict['Numpy_3D']['double'] = np.array([[[1.0,2.0],[3.0,4.0]],[[3.0,-3.0],[42.0,41.0]]])

        # spsparse_csc = spsp.csc_matrix((2222,22))
        # spsparse_csc[1,2] = 44.6
        #
        # spsparse_csr = spsp.csr_matrix((2222,22))
        # spsparse_csr[1,3] = 44.7
        #
        # spsparse_lil = spsp.lil_matrix((2222,22))
        # spsparse_lil[3,2] = 44.5
        #
        # self.param_dict['Sparse']['lil_mat'] = spsparse_lil
        # self.param_dict['Sparse']['csc_mat'] = spsparse_csc
        # self.param_dict['Sparse']['csr_mat'] = spsparse_csr

        self.param_dict['Tuples']['int'] = (1,2,3)
        self.param_dict['Tuples']['float'] = (44.4,42.1,3.)
        self.param_dict['Tuples']['str'] = ('1','2wei','dr3i')


    def add_params(self,traj):

        flat_dict = flatten_dictionary(self.param_dict,'.')

        for key, val in flat_dict.items():
            if isinstance(val, (np.ndarray,list, tuple)):
                traj.ap(key,val, param_type = ArrayParameter)
            elif isinstance(val, (int,str,bool,float)):
                traj.ap(key,val, param_type = Parameter, comment='Im a comment!')
            elif spsp.isspmatrix(val):
                traj.ap(key,val, param_type = PickleParameter)
            else:
                raise RuntimeError('You shall not pass, %s is %s!' % (str(val),str(type(val))))

        traj.adp('Another.String', 'Hi, how are you?')
        traj.add_result('Peter_Jackson',np.str(['is','full','of','suboptimal ideas']),comment='Only my opinion bro!',)

    def make_environment(self, idx, filename):

        logging.basicConfig(level = logging.DEBUG)

        #self.filename = '../../Test/HDF5/test.hdf5'
        logfolder = '../../Test/Log'
        trajname = 'Test%d' % idx

        env = Environment(trajname,filename,trajname,logfolder=logfolder)


        self.envs.append(env)
        self.trajs.append( env.get_trajectory())


    def explore(self, traj):
        self.explored ={'Normal.trial': [0,1],
            'Numpy.double': [np.array([1.0,2.0,3.0,4.0]), np.array([-1.0,3.0,5.0,7.0])]}


        traj.explore(cartesian_product(self.explored))

    @unittest.skipIf(SINGLETEST != [0] and 1 not in SINGLETEST,'Skipping because, '
                                                               'single debug is not pointing to the function ')
    def test_continueing(self):
        self.filenames = ['../../Test/HDF5/merge1.hdf5', 0]



        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment( irun, filename)

        self._create_param_dict()

        for irun in range(len(self.filenames)):
            self.add_params(self.trajs[irun])


        self.explore(self.trajs[0])
        self.explore(self.trajs[1])

        for irun in range(len(self.filenames)):
            self.make_run(self.envs[irun])


        ### Create a crash and say, that the first and last run did not work.
        pt_file = pt.open_file(self.filenames[0],mode='a')
        runtable = pt_file.get_node('/'+self.trajs[0].get_name()+'/run_table')

        for idx,row in enumerate(runtable.iterrows()):
            if idx == 0 or idx == 3:
                row['completed'] = 0
                row.update()

        runtable.flush()
        pt_file.flush()
        pt_file.close()


        continue_file = os.path.split(self.filenames[0])[0]+'/'+self.trajs[0].get_name()+'.cnt'
        self.envs[0].continue_run(continue_file)

        for irun in range(len(self.filenames)):
            self.trajs[irun].update_skeleton()
            self.trajs[irun].load_stuff('ALL',only_empties=True)

        self.compare_trajectories(self.trajs[0],self.trajs[1])

    @unittest.skipIf(SINGLETEST != [0] and 2 not in SINGLETEST,'Skipping because, '
                                                               'single debug is not pointing to the function ')
    def test_removal(self):
        self.filenames = ['../../Test/HDF5/merge1.hdf5', 0]



        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment( irun, filename)

        self._create_param_dict()

        for irun in range(len(self.filenames)):
            self.add_params(self.trajs[irun])


        self.explore(self.trajs[0])
        self.explore(self.trajs[1])





        for irun in range(len(self.filenames)):
            self.make_run(self.envs[irun])

        self.trajs[0].ap('Delete.Me', 'I will be deleted!')
        #self.trajs[0].store_stuff('Delete.Me')
        with self.assertRaises(RuntimeError):
            self.trajs[0].remove_stuff('Delete.Me')

        self.trajs[0].store_stuff('Delete.Me')
        self.trajs[0].remove_stuff('Delete.Me')


        for irun in range(len(self.filenames)):
            self.trajs[irun].update_skeleton()
            self.trajs[irun].load_stuff('ALL',only_empties=True)

        self.compare_trajectories(self.trajs[0],self.trajs[1])

    @unittest.skipIf(SINGLETEST != [0] and 3 not in SINGLETEST,'Skipping because, '
                                                'single debug is not pointing to the function ')
    def test_multiple_storage_and_loading(self):
        self.filenames = ['../../Test/HDF5/merge1.hdf5', 0]



        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment( irun, filename)

        self._create_param_dict()

        for irun in range(len(self.filenames)):
            self.add_params(self.trajs[irun])


        self.explore(self.trajs[0])
        self.explore(self.trajs[1])





        for irun in range(len(self.filenames)):
            self.make_run(self.envs[irun])

        self.trajs[0].store()

        temp_sservice = self.trajs[0].get_storage_service()
        temp_name = self.trajs[0].get_name()

        self.trajs[0] = Trajectory()
        self.trajs[0].set_storage_service(temp_sservice)
        self.trajs[0].load(trajectoryname=temp_name,as_new=False, load_params=2, load_derived_params=2, load_results=2)
        self.trajs[0].load(trajectoryname=temp_name,as_new=False, load_params=2, load_derived_params=2, load_results=2)

        self.trajs[1].update_skeleton()
        self.trajs[1].load_stuff(self.trajs[1].to_dict().itervalues(),only_empties=True)
        self.compare_trajectories(self.trajs[0],self.trajs[1])


if __name__ == '__main__':
    if REMOVE:
        shutil.rmtree('../../Test',True)
    unittest.main()