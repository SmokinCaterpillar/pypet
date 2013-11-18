__author__ = 'Robert Meyer'

from pypet.utils.comparisons import results_equal,parameters_equal, nested_equal
from pypet.utils.helpful_functions import nest_dictionary, flatten_dictionary
from pypet.parameter import Parameter, PickleParameter, BaseResult, ArrayParameter, PickleResult, \
    BaseParameter, SparseParameter, SparseResult, ObjectTable
import scipy.sparse as spsp
import os
import logging

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

import shutil
import numpy as np
import pandas as pd


import tempfile

TEMPDIR = 'temp_folder_for_pypet_tests/'
''' Temporary directory for the hdf5 files'''

REMOVE=True
''' Whether or not to remove the temporary directory after the tests'''

actual_tempdir=''
''' Actual temp dir, maybe in tests folder or in `tempfile.gettempdir()`'''

user_tempdir=''
'''If the user specifies in run all test a folder, this variable will be used'''

def make_temp_file(filename):
    global actual_tempdir
    global user_tempdir
    global TEMPDIR
    try:

        if not (user_tempdir == '' or user_tempdir is None) and actual_tempdir=='':
            actual_tempdir=user_tempdir

        if not os.path.isdir(actual_tempdir):
            os.makedirs(actual_tempdir)

        return os.path.join(actual_tempdir,filename)
    except OSError:
        logging.getLogger('').warning('Cannot create a temp file in the specified folder `%s`. ' %
                                    actual_tempdir +
                                    ' I will use pythons gettempdir method instead.')
        actual_tempdir = os.path.join(tempfile.gettempdir(),TEMPDIR)
        return os.path.join(actual_tempdir,filename)
    except:
        logging.getLogger('').error('Could not create a directory. Sorry cannot run them')
        raise

def make_run(remove=None, folder=None):

    if remove is None:
        remove = REMOVE

    global user_tempdir
    user_tempdir=folder

    global actual_tempdir
    try:
        unittest.main()
    finally:
        if remove:
            shutil.rmtree(actual_tempdir,True)

def create_param_dict(param_dict):
    '''Fills a dictionary with some parameters that can be put into a trajectory.
    '''
    param_dict['Normal'] = {}
    param_dict['Numpy'] = {}
    param_dict['Sparse'] ={}
    param_dict['Numpy_2D'] = {}
    param_dict['Numpy_3D'] = {}
    param_dict['Tuples'] ={}
    param_dict['Pickle']={}

    normal_dict = param_dict['Normal']
    normal_dict['string'] = 'Im a test string!'
    normal_dict['int'] = 42
    normal_dict['long'] = long(42)
    normal_dict['double'] = 42.42
    normal_dict['bool'] =True
    normal_dict['trial'] = 0

    numpy_dict=param_dict['Numpy']
    numpy_dict['string'] = np.array(['Uno', 'Dos', 'Tres'])
    numpy_dict['int'] = np.array([1,2,3,4])
    numpy_dict['double'] = np.array([1.0,2.0,3.0,4.0])
    numpy_dict['bool'] = np.array([True,False, True])

    param_dict['Numpy_2D']['double'] = np.matrix([[1.0,2.0],[3.0,4.0]])
    param_dict['Numpy_3D']['double'] = np.array([[[1.0,2.0],[3.0,4.0]],[[3.0,-3.0],[42.0,41.0]]])

    spsparse_csc = spsp.csc_matrix((2222,22))
    spsparse_csc[1,2] = 44.6
    spsparse_csc[1,9] = 44.5

    spsparse_csr = spsp.csr_matrix((2222,22))
    spsparse_csr[1,3] = 44.7
    spsparse_csr[17,17] = 44.755555

    spsparse_bsr = spsp.bsr_matrix(np.matrix([[1, 1, 0, 0, 2, 2],
        [1, 1, 0, 0, 2, 2],
        [0, 0, 0, 0, 3, 3],
        [0, 0, 0, 0, 3, 3],
        [4, 4, 5, 5, 6, 6],
        [4, 4, 5, 5, 6, 6]]))

    spsparse_dia = spsp.dia_matrix(np.matrix([[1, 0, 3, 0],
        [1, 2, 0, 4],
        [0, 2, 3, 0],
        [0, 0, 3, 4]]))


    param_dict['Sparse']['bsr_mat'] = spsparse_bsr
    param_dict['Sparse']['csc_mat'] = spsparse_csc
    param_dict['Sparse']['csr_mat'] = spsparse_csr
    param_dict['Sparse']['dia_mat'] = spsparse_dia

    param_dict['Tuples']['int'] = (1,2,3)
    param_dict['Tuples']['float'] = (44.4,42.1,3.)
    param_dict['Tuples']['str'] = ('1','2wei','dr3i')

    param_dict['Pickle']['list']= ['b','h', 53, (),0]
    param_dict['Pickle']['list']= ['b','h', 42, (),1]
    param_dict['Pickle']['list']= ['b',[444,43], 44, (),2]



def add_params(traj,param_dict):
    '''Adds parameters to a trajectory
    '''
    flat_dict = flatten_dictionary(param_dict,'.')

    for key, val in flat_dict.items():
        if isinstance(val, (np.ndarray,tuple)):
            traj.f_add_parameter(ArrayParameter,key,val )
        elif isinstance(val, (int,str,bool,long,float)):
            traj.f_add_parameter(Parameter,key,val, comment='Im a comment!')
        elif spsp.isspmatrix(val):
            traj.f_add_parameter(SparseParameter,key,val).v_annotations.f_set(
                **{'Name':key,'Val' :str(val),'Favorite_Numbers:':[1,2,3],
                                 'Second_Fav':np.array([43.0,43.0])})
        elif isinstance(val,list):
            # The last item of the list `val` is an int between 0 and 2, we can use it as a
            # protocol read out to test all protocols
            traj.f_add_parameter(PickleParameter,key,val, comment='Im a comment!', protocol=val[-1])
        else:
            raise RuntimeError('You shall not pass, %s is %s!' % (str(val),str(type(val))))


    traj.f_add_derived_parameter('Another.String', 'Hi, how are you?')
    traj.f_add_result('Peter_Jackson',np.str(['is','full','of','suboptimal ideas']),comment='Only my opinion bro!',)

def multipy(traj):
    z=traj.x*traj.y
    traj.f_add_result('z',z)

def simple_calculations(traj, arg1, simple_kwarg):

        print '>>>>>Starting Simple Calculations'
        my_dict = {}

        my_dict2={}
        for key, val in traj.parameters.f_to_dict(fast_access=True,short_names=False).items():
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
        my_dict['__LONG'] = long(42)

        keys = sorted(to_dict_wo_config(traj).keys())
        for idx,key in enumerate(keys):
            keys[idx] = key.replace('.','_')

        traj.f_add_result('List.Of.Keys', dict1=my_dict, dict2=my_dict2)
        traj.f_add_result('DictsNFrame', keys=keys, comment='A dict!')
        traj.f_add_result('ResMatrix',np.array([1.2,2.3]))
        #traj.f_add_derived_parameter('All.To.String', str(traj.f_to_dict(fast_access=True,short_names=False)))

        myframe = pd.DataFrame(data ={'TC1':[1,2,3],'TC2':['Waaa',np.nan,''],'TC3':[1.2,42.2,np.nan]})

        traj.f_get('DictsNFrame').f_set(myframe)

        traj.f_add_result('IStore.SimpleThings',1.0,3,np.float32(5.0), 'Iamstring',(1,2,3),[4,5,6],zwei=2)
        traj.f_add_derived_parameter('super.mega',33, comment='It is huuuuge!')
        traj.super.f_set_annotations(AgainATestAnnotations='I am a string!111elf')

        traj.f_add_result(PickleResult,'pickling.result.proto1', my_dict, protocol=1)
        traj.f_add_result(PickleResult,'pickling.result.proto2', my_dict, protocol=2)
        traj.f_add_result(PickleResult,'pickling.result.proto0', my_dict, protocol=0)

        traj.f_add_result(SparseResult, 'sparse.csc',traj.csc_mat,42)
        traj.f_add_result(SparseResult, 'sparse.bsr',traj.bsr_mat,52)
        traj.f_add_result(SparseResult, 'sparse.csr',traj.csr_mat,62)
        traj.f_add_result(SparseResult, 'sparse.dia',traj.dia_mat,72)

        myobjtab = ObjectTable(data={'strings':['a','abc','qwertt'], 'ints':[1,2,3]})

        traj.f_add_result('object.table', myobjtab).v_annotations.f_set(test=42)
        traj.object.f_set_annotations(test2=42.42)

        #traj.f_add_result('PickleTerror', result_type=PickleResult, test=traj.SimpleThings)
        print '<<<<<<Finished Simple Calculations'


def to_dict_wo_config(traj):
        res_dict={}
        res_dict.update(traj.parameters.f_to_dict(fast_access=False))
        res_dict.update(traj.derived_parameters.f_to_dict(fast_access=False))
        res_dict.update(traj.results.f_to_dict(fast_access=False))

        return res_dict

class TrajectoryComparator(unittest.TestCase):

    def compare_trajectories(self,traj1,traj2):

        old_items = to_dict_wo_config(traj1)
        new_items = to_dict_wo_config(traj2)

        self.assertEqual(len(traj1),len(traj2), 'Length unequal %d != %d.' % (len(traj1), len(traj2)))

        self.assertEqual(len(old_items),len(new_items))
        for key,item in new_items.items():
            old_item = old_items[key]

            if isinstance(item, BaseParameter):
                self.assertTrue(parameters_equal(item,old_item),
                                'For key %s: %s not equal to %s' %(key,str(old_item),str(item)))
            elif isinstance(item,BaseResult):
                self.assertTrue(results_equal(item, old_item),
                                'For key %s: %s not equal to %s' %(key,str(old_item),str(item)))
            else:
                raise RuntimeError('You shall not pass')

            self.assertTrue(nested_equal(item.v_annotations,old_item.v_annotations),'%s != %s' %
                        (item.v_annotations.f_ann_to_str(),old_item.v_annotations.f_ann_to_str()))

        # Check the annotations
        for node in traj1.f_iter_nodes(recursive=True):
            if not node.v_annotations.f_is_empty():
                second_anns = traj2.f_get(node.v_full_name).v_annotations
                self.assertTrue(nested_equal(node.v_annotations, second_anns))

