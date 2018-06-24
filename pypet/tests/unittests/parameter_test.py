__author__ = 'Robert Meyer'

import numpy as np
import sys
import unittest

from pypet.parameter import Parameter, PickleParameter, ArrayParameter,\
    SparseParameter, ObjectTable, Result, SparseResult, PickleResult, BaseParameter
from pypet.trajectory import Trajectory
import pickle
import scipy.sparse as spsp
import pypet.pypetexceptions as pex
import warnings
import pandas as pd
import pypet.utils.comparisons as comp
from pypet.utils.helpful_classes import ChainMap
from pypet.utils.explore import cartesian_product
import pypet.pypetconstants as pypetconstants
from pypet.tests.testutils.ioutils import run_suite, parse_args, make_temp_dir
from pypet.tests.testutils.data import TrajectoryComparator


class ParameterTest(TrajectoryComparator):

    tags = 'unittest', 'parameter'

    def test_type_error_for_not_supported_data(self):

        for param in self.param.values():
            if not isinstance(param, PickleParameter):
                with self.assertRaises(TypeError):
                    param._values_of_same_type(ChainMap(),ChainMap())

                with self.assertRaises(TypeError):
                    param._equal_values(ChainMap(),ChainMap())

    def test_store_load_with_hdf5(self):
        traj_name = 'test_%s' % self.__class__.__name__
        filename = make_temp_dir(traj_name + '.hdf5')
        traj = Trajectory(name=traj_name, dynamic_imports=self.dynamic_imports,
                          filename = filename, overwrite_file=True)

        for param in self.param.values():
            traj.f_add_parameter(param)

        traj.f_store()

        new_traj = Trajectory(name=traj_name, dynamic_imports=self.dynamic_imports,
                              filename = filename)

        new_traj.f_load(load_data=2)
        self.compare_trajectories(traj, new_traj)

    def test_store_load_with_hdf5_no_data(self):
        traj_name = 'test_%s' % self.__class__.__name__
        filename = make_temp_dir(traj_name + 'nodata.hdf5')
        traj = Trajectory(name=traj_name, dynamic_imports=self.dynamic_imports,
                          filename = filename, overwrite_file=True)

        for param in self.param.values():
            param._data = None
            traj.f_add_parameter(param)

        traj.f_store()

        new_traj = Trajectory(name=traj_name, dynamic_imports=self.dynamic_imports,
                              filename = filename)

        new_traj.f_load(load_data=2)
        self.compare_trajectories(traj, new_traj)

    def test_type_error_for_exploring_if_range_does_not_match(self):

        param = self.param['val1']

        with self.assertRaises(TypeError):
            param._explore(['a','b'])

        with self.assertRaises(TypeError):
            param._explore([ChainMap(),ChainMap()])

        with self.assertRaises(ValueError):
            param._explore([])

    def test_cannot_expand_and_not_explore_throwing_type_error(self):

        for param in self.param.values():
            if not param.f_has_range():
                with self.assertRaises(TypeError):
                    param._expand([12,33])
            else:
                with self.assertRaises(TypeError):
                    param._explore([12,33])


    def test_equal_values(self):
        for param in self.param.values():
            self.assertTrue(param._equal_values(param.f_get(), param.f_get()))

            self.assertFalse(param._equal_values(param.f_get(),23432432432))

            self.assertFalse(param._equal_values(param.f_get(),ChainMap()))

            if not isinstance(param, PickleParameter):
                with self.assertRaises(TypeError):
                     self.assertFalse(param._equal_values(ChainMap(),ChainMap()))


    def test_parameter_locking(self):
        for param in self.param.values():

            if not param.v_explored:
                self.assertFalse(param.v_locked, 'Param %s is locked' % param.v_full_name)
                param.f_lock()
            else:
                self.assertTrue(param.v_locked, 'Param %s is locked' % param.v_full_name)

            with self.assertRaises(pex.ParameterLockedException):
                param.f_set(3)

            with self.assertRaises(pex.ParameterLockedException):
                param._explore([3])

            with self.assertRaises(pex.ParameterLockedException):
                param._expand([3])

            with self.assertRaises(pex.ParameterLockedException):
                param._shrink()

            with self.assertRaises(pex.ParameterLockedException):
                param.f_empty()

    def test_param_accepts_not_unsupported_data(self):

        for param in self.param.values():
            if not isinstance(param, PickleParameter):
                with self.assertRaises(TypeError):
                    param.f_set(ChainMap())

    def test_parameter_access_throws_ValueError(self):

        for name,param in self.param.items():
            if name in self.explore_dict:
                self.assertTrue(param.f_has_range())

                with self.assertRaises(ValueError):
                    param._set_parameter_access(1232121321321)

    def test_values_of_same_type(self):
        for param in self.param.values():
            self.assertTrue(param._values_of_same_type(param.f_get(),param.f_get()))

            if not isinstance(param.f_get(), int):
                self.assertFalse(param._values_of_same_type(param.f_get(),23432432432))

            self.assertFalse(param._values_of_same_type(param.f_get(),ChainMap()))

            if not isinstance(param, PickleParameter):
                with self.assertRaises(TypeError):
                     self.assertFalse(param._equal_values(ChainMap(),ChainMap()))

    def test_meta_settings(self):
        for key, param in self.param.items():
            self.assertEqual(param.v_full_name, self.location+'.'+key)
            self.assertEqual(param.v_name, key)
            self.assertEqual(param.v_location, self.location)


    def make_params(self):
        self.param = {}
        for key, val in self.data.items():
            self.param[key] = Parameter(self.location+'.'+key, val, comment=key)


    def setUp(self):

        if not hasattr(self,'data'):
            self.data={}

        self.data['val0']= 1
        self.data['val1']= 1.0
        self.data['val2']= True
        self.data['val3'] = 'String'
        self.data['npfloat'] = np.array([1.0,2.0,3.0])
        self.data['npfloat_2d'] = np.array([[1.0,2.0],[3.0,4.0]])
        self.data['npbool']= np.array([True,False, True])
        self.data['npstr'] = np.array(['Uno', 'Dos', 'Tres'])
        self.data['npint'] = np.array([1,2,3])
        self.data['alist'] = [1,2,3,4]
        self.data['atuple'] = (1,2,3,4)

        self.location = 'MyName.Is.myParam'

        self.dynamic_imports = []


        self.make_params()


        # with self.assertRaises(AttributeError):
        #     self.param.val0.f_set([[1,2,3],[1,2,3]])

        #Add explortation:
        self.explore()

    def test_get_item(self):
        for paramname in self.explore_dict:
            param = self.param[paramname]
            val1=param.f_get_range()[1]
            val2=param[1]
            self.assertTrue(comp.nested_equal(val1,val2), '%s != %s' % (str(val1),str(val2)))

    def test_get_data(self):
        for paramname in self.param:
            param = self.param[paramname]
            val1=param.data
            val2=param.f_get()
            self.assertTrue(comp.nested_equal(val1,val2), '%s != %s' % (str(val1),str(val2)))
            val3=param['data']
            self.assertTrue(comp.nested_equal(val3,val2), '%s != %s' % (str(val3),str(val2)))

            val1=param.default
            val2=param._default
            self.assertTrue(comp.nested_equal(val1,val2), '%s != %s' % (str(val1),str(val2)))
            val3=param['default']
            self.assertTrue(comp.nested_equal(val3,val2), '%s != %s' % (str(val3),str(val2)))
            val4=param.f_get_default()
            self.assertTrue(comp.nested_equal(val4,val2), '%s != %s' % (str(val4),str(val2)))
            val5 = param[-1]
            self.assertTrue(comp.nested_equal(val5,val2), '%s != %s' % (str(val5),str(val2)))

    def test_type_error_for_get_item(self):
        for name,param in self.param.items():
            if not name in self.explore_dict:
                with self.assertRaises(TypeError):
                    param[1]

    def test_type_error_for_shrink(self):
        for name, param in self.param.items():
            if not name in self.explore_dict:
                with self.assertRaises(TypeError):
                    param._shrink()

    def explore(self):
        self.explore_dict=cartesian_product({'npstr':[np.array(['Uno', 'Dos', 'Tres']),
                               np.array(['Cinco', 'Seis', 'Siette']),
                            np.array(['Ocho', 'Nueve', 'Diez'])],
                           'val0':[1,2,3], 'alist':[[1,2,3,4],[3,4,5,6]]})

        ## Explore the parameter:
        for key, vallist in self.explore_dict.items():
            old_data = self.param[key]._data
            self.param[key]._data = None
            with self.assertRaises(TypeError):
                self.param[key]._explore(vallist)
            self.param[key]._data = old_data
            self.param[key]._explore(vallist)

    def test_the_insertion_made_implicetly_in_setUp(self):
        for key, val in self.data.items():

            if not key in self.explore_dict:
                self.param[key]._restore_default()
                param_val = self.param[key].f_get()
                self.assertTrue(np.all(repr(val) == repr(param_val)),'%s != %s'  %(str(val),str(param_val)))



    def test_expanding_type_error(self):
        for name,param in self.param.items():
            if not name in self.explore_dict:
                #Test locking
                with self.assertRaises(TypeError):
                    param._expand([1,2,3])

                #Test wron param type
                with self.assertRaises(TypeError):
                    param.f_unlock()
                    param._expand([1,2,3])


    def test_rename(self):
        for name,param in self.param.items():
            param._rename('test.test.wirsing')
            self.assertTrue(param.v_name=='wirsing')
            self.assertTrue(param.v_full_name=='test.test.wirsing')
            self.assertTrue(param.v_location=='test.test')



    def test_expanding(self):
        for name,param in self.param.items():
            if name in self.explore_dict:
                param.f_unlock()
                param._expand(self.explore_dict[name])

                self.assertTrue(len(param) == 2*len(self.explore_dict[name]),
                                'Expanding of %s did not work.' % name)


    def test_exploration(self):
        for key, vallist in self.explore_dict.items():

            param = self.param[key]

            for idx, val in enumerate(vallist):
                assert isinstance(param, BaseParameter)
                param._set_parameter_access(idx)

                self.assertTrue(np.all(repr(param.f_get())==repr(val))),'%s != %s'%( str(param.f_get()),str(val))

                param_val = self.param[key].f_get_range()[idx]
                self.assertTrue(np.all(str(val) == str(param_val)),'%s != %s'  %(str(val),str(param_val)))

            param._restore_default()
            self.assertTrue(param.v_explored and param.f_has_range(), 'Error for %s' % key)
            val = self.data[key]
            self.assertTrue(np.all(repr(param.f_get())==repr(val))),'%s != %s'%( str(param.f_get()),str(val))


    def test_storage_and_loading(self):

        for key, param in self.param.items():
            store_dict = param._store()

            # Due to smart storing the storage dict should be small and only contain 5 items or less
            # 1 for data, 1 for reference, and 3 for the array/matrices/items
            if param.f_has_range():
                if isinstance(param,(ArrayParameter, PickleParameter)) and \
                        not isinstance(param, SparseParameter):
                    self.assertTrue(len(store_dict)<7)
                # For sparse parameter it is more:
                if isinstance(param, SparseParameter):
                    self.assertTrue(len(store_dict)<23)



            constructor = param.__class__

            param.f_unlock()
            param.f_empty()

            param = constructor('', 42)

            param._load(store_dict)

            param._rename(self.location+'.'+key)

            self.param[key] = param


        self.test_the_insertion_made_implicetly_in_setUp()

        self.test_exploration()

        self.test_meta_settings()


    def test_pickling_without_multiprocessing(self):
        for key, param in self.param.items():
            param.f_unlock()
            param.v_full_copy=True

            dump = pickle.dumps(param)

            newParam = pickle.loads(dump)



            self.param[key] = newParam

        self.test_exploration()

        self.test_the_insertion_made_implicetly_in_setUp()

        self.test_meta_settings()


    def test_pickling_with_mocking_multiprocessing(self):

        self.test_exploration()

        for key, param in self.param.items():
            param.f_unlock()
            param.v_full_copy=False

            dump = pickle.dumps(param)

            newParam = pickle.loads(dump)



            self.param[key] = newParam

            if key in self.explore_dict:
                self.assertTrue(not newParam.f_has_range() and newParam.v_explored)

        #self.test_exploration()

        self.test_the_insertion_made_implicetly_in_setUp()

        self.test_meta_settings()



    def test_resizing_and_deletion(self):

        for key, param in self.param.items():
            param.f_lock()
            with self.assertRaises(pex.ParameterLockedException):
                 param.f_set(42)

            with self.assertRaises(pex.ParameterLockedException):
                param._shrink()


            param.f_unlock()


            if len(param)> 1:
                self.assertTrue(param.f_has_range())

            if param.f_has_range():
                self.assertTrue(len(param)>1)
                param._shrink()

            self.assertTrue(len(param) == 1)

            self.assertFalse(param.f_is_empty())
            self.assertFalse(param.f_has_range())



            param.f_empty()

            self.assertTrue(param.f_is_empty())
            self.assertFalse(param.f_has_range())

class ArrayParameterTest(ParameterTest):

    tags = 'unittest', 'parameter', 'array'

    def setUp(self):


        if not hasattr(self,'data'):
            self.data= {}

        self.data['myemptytuple'] = ()
        self.data['myemptylist'] = []

        self.data['myinttuple'] = (1,2,3)
        self.data['mydoubletuple'] = (42.0,43.7,33.3)
        self.data['mystringtuple'] = ('Eins','zwei','dr3i')

        super(ArrayParameterTest,self).setUp()


    def make_params(self):
        self.param = {}
        for key, val in self.data.items():
            self.param[key] = ArrayParameter(self.location+'.'+key, val, comment=key)


    def explore(self):

        matrices = []


        self.explore_dict=cartesian_product({'npstr':[np.array(['Uno', 'Dos', 'Tres']),
                               np.array(['Cinco', 'Seis', 'Siette']),
                            np.array(['Ocho', 'Nueve', 'Diez'])],
                           'val0':[1,2,3],
                           'myinttuple':[(1,2,1),(4,5,6),(5,6,7)],
                            'alist':[[1,2,3,4],['wooot']]} ,
                                            (('npstr','val0'),'myinttuple', 'alist'))

        ### Convert the explored stuff into numpy arrays
        #for idx, val in enumerate(self.explore_dict['myinttuple']):
         #   self.explore_dict['myinttuple'][idx] = np.array(val)


        ## Explore the parameter:
        for key, vallist in self.explore_dict.items():
            self.param[key]._explore(vallist)


    def test_store_load_with_hdf5(self):
        return super(ArrayParameterTest, self).test_store_load_with_hdf5()




class PickleParameterTest(ParameterTest):

    tags = 'unittest', 'parameter', 'pickle'

    def setUp(self):

        if not hasattr(self,'data'):
            self.data={}

        self.data['spsparse_csc'] = spsp.lil_matrix((1000,100))
        self.data['spsparse_csc'][1,2] = 44.5
        self.data['spsparse_csc'] = self.data['spsparse_csc'].tocsc()

        self.data['spsparse_csr'] = spsp.lil_matrix((2222,22))
        self.data['spsparse_csr'][1,3] = 44.5
        self.data['spsparse_csr'] = self.data['spsparse_csr'].tocsr()

        self.data['spsparse_lil'] = spsp.lil_matrix((111,111))
        self.data['spsparse_lil'][3,2] = 44.5

        super(PickleParameterTest,self).setUp()


    def make_params(self):
        self.param = {}
        count = 0
        self.protocols={}
        for key, val in self.data.items():
            self.param[key] = PickleParameter(self.location+'.'+key, val,
                                              comment=key, protocol=count)
            self.protocols[key]=count
            count +=1
            count = count % 3


    def test_meta_settings(self):
        for key, param in self.param.items():
            self.assertEqual(param.v_full_name, self.location+'.'+key)
            self.assertEqual(param.v_name, key)
            self.assertEqual(param.v_location, self.location)
            self.assertEqual(param.v_protocol, self.protocols[key], '%d != %d' %
                                                        (param.v_protocol, self.protocols[key]))

    def explore(self):

        matrices = []


        for irun in range(3):

            spsparse_lil = spsp.lil_matrix((111,111))
            spsparse_lil[3,2] = 44.5*irun

            matrices.append(spsparse_lil)


        self.explore_dict=cartesian_product({'npstr':[np.array(['Uno', 'Dos', 'Tres']),
                               np.array(['Cinco', 'Seis', 'Siette']),
                            np.array(['Ocho', 'Nueve', 'Diez'])],
                           'val0':[1,2,3],
                           'spsparse_lil' : matrices}, (('npstr','val0'),'spsparse_lil'))




        ## Explore the parameter:
        for key, vallist in self.explore_dict.items():
            self.param[key]._explore(vallist)


class SparseParameterTest(ParameterTest):

    tags = 'unittest', 'parameter', 'sparse'

    def setUp(self):

        if not hasattr(self,'data'):
            self.data={}

        self.data['spsparse_csc'] = spsp.lil_matrix((1000,100))
        self.data['spsparse_csc'][1,2] = 44.5
        self.data['spsparse_csc'] = self.data['spsparse_csc'].tocsc()

        self.data['spsparse_csr'] = spsp.lil_matrix((2222,22))
        self.data['spsparse_csr'][1,3] = 44.5
        self.data['spsparse_csr'] = self.data['spsparse_csr'].tocsr()

        self.data['spsparse_bsr'] = spsp.lil_matrix((111,111))
        self.data['spsparse_bsr'][3,2] = 44.5
        self.data['spsparse_bsr'] = self.data['spsparse_bsr'].tocsr().tobsr()

        self.data['spsparse_dia'] = spsp.lil_matrix((111,111))
        self.data['spsparse_dia'][3,2] = 44.5
        self.data['spsparse_dia'] = self.data['spsparse_dia'].tocsr().todia()

        super(SparseParameterTest,self).setUp()


    def make_params(self):
        self.param = {}
        for key, val in self.data.items():
            self.param[key] = SparseParameter(self.location+'.'+key, val, comment=key)

    def explore(self):

        matrices_csr = []
        for irun in range(3):

            spsparse_csr = spsp.csr_matrix((111,111))
            spsparse_csr[3,2+irun] = 44.5*irun

            matrices_csr.append(spsparse_csr)

        matrices_csc = []
        for irun in range(3):

            spsparse_csc = spsp.csc_matrix((111,111))
            spsparse_csc[3,2+irun] = 44.5*irun

            matrices_csc.append(spsparse_csc)

        matrices_bsr = []
        for irun in range(3):

            spsparse_bsr = spsp.csr_matrix((111,111))
            spsparse_bsr[3,2+irun] = 44.5*irun

            matrices_bsr.append(spsparse_bsr.tobsr())

        matrices_dia = []
        for irun in range(3):

            spsparse_dia = spsp.csr_matrix((111,111))
            spsparse_dia[3,2+irun] = 44.5*irun

            matrices_dia.append(spsparse_dia.todia())


        self.explore_dict=cartesian_product({'npstr':[np.array(['Uno', 'Dos', 'Tres']),
                               np.array(['Cinco', 'Seis', 'Siette']),
                            np.array(['Ocho', 'Nueve', 'Diez'])],
                           'val0':[1,2,3],
                           'spsparse_csr' : matrices_csr,
                           'spsparse_csc' : matrices_csc,
                           'spsparse_bsr' : matrices_bsr,
                           'spsparse_dia' : matrices_dia},
                            (('npstr','val0'),('spsparse_csr',
                            'spsparse_csc', 'spsparse_bsr','spsparse_dia')) )




        ## Explore the parameter:
        for key, vallist in self.explore_dict.items():
            self.param[key]._explore(vallist)


class ResultTest(TrajectoryComparator):

    tags = 'unittest', 'result'

    def make_results(self):
        self.results= {}
        self.results['test.res.on_constructor']=self.Constructor('test.res.on_constructor',
                                                                 **self.data)
        self.results['test.res.args']=self.Constructor('test.res.args')
        self.results['test.res.kwargs']=self.Constructor('test.res.kwargs')
        self.results['test.res.setitem']=self.Constructor('test.res.setitem')

        self.results['test.res.args'].f_set(*list(self.data.values()))
        self.results['test.res.kwargs'].f_set(**self.data)

        for key, value in self.data.items():
            self.results['test.res.setitem'][key]=value

    def test_set_item_via_number(self):
        res = self.results['test.res.args']

        res[0] = 'Hi'
        res[777] = 777

        self.assertTrue(getattr(res, res.v_name) == 'Hi')
        self.assertTrue(res.f_get(0) == 'Hi')
        self.assertTrue(getattr(res, res.v_name + '_777') == 777)
        self.assertTrue(res[777] == 777)
        self.assertTrue(res.f_get(777) == 777)

        self.assertTrue(0 in res)
        self.assertTrue(777 in res)
        self.assertTrue(99999999 not in res)

        del res[0]
        self.assertTrue(0 not in res)

        del res[777]
        self.assertTrue(777 not in res)

    def test_iter(self):
        for res in self.results.values():
            keyset1 = set([x for x in res])
            keyset2 = set(res.f_to_dict().keys())
            self.assertTrue(keyset1 == keyset2)


    def make_constructor(self):
        self.Constructor=Result
        self.dynamic_imports = [Result]

    def test_warning(self):
        for res in self.results.values():
            with warnings.catch_warnings(record=True) as w:
                res._stored=True
                res.XxxXXXXxxxx = 14

    def test_f_get_many_items(self):
        for res in self.results.values():
            if 'integer' in res and 'float' in res:
                myreslist = res.f_get('integer', 'float')
                self.assertEqual([self.data['integer'], self.data['float']],myreslist)

    def test_getattr_and_setattr(self):
        for res in self.results.values():
            res.iamanewvar = 42
            self.assertTrue(res.iamanewvar,42)
            with self.assertRaises(AttributeError):
                res.iamanonexistingvar

    def test_deletion_throws_error_if_item_not_there(self):
        for res in self.results.values():
            with self.assertRaises(AttributeError):
                del res.idonotexistforsure


    def test_get_data(self):
        for res in self.results.values():
            if len(res._data)==1:
                val1=res.data
                val2=res.f_get()
                self.assertTrue(comp.nested_equal(val1,val2), '%s != %s' % (str(val1),str(val2)))
                val3=res['data']
                self.assertTrue(comp.nested_equal(val3,val2), '%s != %s' % (str(val3),str(val2)))
            else:
                with self.assertRaises(AttributeError):
                    res.data
                with self.assertRaises(AttributeError):
                    res['data']
                with self.assertRaises(ValueError):
                    res.f_get()

    def test_f_get_errors(self):

        res = Result('test')

        with self.assertRaises(AttributeError):
            res.f_get()

        res.f_set(1,2,42)

        with self.assertRaises(ValueError):
            res.f_get()

    def test_contains(self):
        if 'test.res.kwargs' in self.results:
            res = self.results['test.res.kwargs']
            self.assertTrue('integer' in res)

            self.assertFalse('integoAr' in res)

    def test_deletion(self):

        for res in self.results.values():
            for key in res.f_to_dict():
                delattr(res,key)

            self.assertTrue(res.f_is_empty())

    def test_set_numbering(self):
        int_list = list(range(10))
        for res in self.results.values():
            res.f_set(*int_list)

            self.assertEqual(res.f_get(*int_list), int_list)

    def test_dir(self):
        res = self.results['test.res.on_constructor']

        dirlist = dir(res)

        self.assertTrue('integer' in dirlist)
        self.assertTrue('dict' in dirlist)
        self.assertTrue('float' in dirlist)
        self.assertTrue('tuple' in dirlist)

        res = self.results['test.res.args']

        dirlist = dir(res)

        self.assertTrue(res.v_name in dirlist)
        self.assertTrue('%s_1' % res.v_name in dirlist)

    def setUp(self):

        if not hasattr(self,'data'):
            self.data={}

        self.data['integer'] = 42
        self.data['float'] = 42.424242
        self.data['string'] = 'TestString! 66'
        self.data['long'] = 444444444444444444
        self.data['numpy_array'] = np.array([[3232.3,323232323232.32323232],[4.,4.]])
        self.data['tuple'] = (444,444,443)
        self.data['list'] = ['3','4','666']
        self.data['dict'] = {'a':'b','c':42, 'd': (1,2,3)}
        self.data['object_table'] = ObjectTable(data={'characters':['Luke', 'Han', 'Spock'],
                                    'Random_Values' :[42,43,44],
                                    'Arrays': [np.array([1,2]),np.array([3, 4]), np.array([5,5])]})
        self.data['pandas_frame'] = pd.DataFrame(data={'characters':['Luke', 'Han', 'Spock'],
                                    'Random_Values' :[42,43,44],
                                    'Doubles': [1.2,3.4,5.6]})

        self.data['nested_data.hui.buh.integer'] = 42

        myframe = pd.DataFrame(data ={'TC1':[1,2,3],'TC2':['Waaa',np.nan,''],'TC3':[1.2,42.2,np.nan]})


        myseries = myframe['TC1']

        self.data['series'] = myseries

        self.make_constructor()
        self.make_results()

    def test_store_load_with_hdf5(self):
        traj_name = 'test_%s' % self.__class__.__name__
        filename = make_temp_dir(traj_name + '.hdf5')
        traj = Trajectory(name=traj_name, dynamic_imports=self.dynamic_imports,
                          filename = filename, overwrite_file=True)

        for res in self.results.values():
            traj.f_add_result(res)

        traj.f_store()

        new_traj = Trajectory(name=traj_name, dynamic_imports=self.dynamic_imports,
                              filename = filename)

        new_traj.f_load(load_data=2)
        self.compare_trajectories(traj, new_traj)

    def test_rename(self):
        for name,res in self.results.items():
            res._rename('test.test.wirsing')
            self.assertTrue(res.v_name=='wirsing')
            self.assertTrue(res.v_full_name=='test.test.wirsing')
            self.assertTrue(res.v_location=='test.test')

    def test_emptying(self):
        for res in self.results.values():

            self.assertFalse(res.f_is_empty())
            res.f_empty()

            self.assertTrue(res.f_is_empty())


    def test_string_representation(self):
        self.results['kkk']=self.Constructor('test.res.kkk', answer=42)
        self.results['rrr']=self.Constructor('test.res.rrr')
        for res in self.results.values():
            resstrlist = []
            strlen = 0
            for key in res._data:
                val = res._data[key]
                resstr = '%s=%s, ' % (key, repr(val))
                resstrlist.append(resstr)

                strlen += len(resstr)
                if strlen > pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH:
                    break

            return_string = "".join(resstrlist)
            if len(return_string) > pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH:
                return_string =\
                    return_string[0:pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH - 3] + '...'
            else:
                return_string = return_string[0:-2] # Delete the last `, `


            valstr = res.f_val_to_str()
            self.assertTrue(return_string==valstr)
            self.assertTrue(len(valstr)<=pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH)


    def test_meta_settings(self):
        for key, res in self.results.items():
            self.assertEqual(res.v_full_name, key)
            self.assertEqual(res.v_name, key.split('.')[-1])
            self.assertEqual(res.v_location, '.'.join(key.split('.')[0:-1]))

    def test_natural_naming(self):
        for res_name,res in self.results.items():
            for key, val1 in res.f_to_dict().items():
                val2 = getattr(res, key)
                self.assertTrue(comp.nested_equal(val1,val2))

    def test_get_item(self):
        for res_name,res in self.results.items():
            for key, val1 in res.f_to_dict().items():
                val2 = res[key]
                self.assertTrue(comp.nested_equal(val1,val2))

    def test_f_to_dict_no_copy(self):
        for res_name,res in self.results.items():
            for key, val1 in res.f_to_dict(copy=False).items():
                val2 = res[key]
                self.assertTrue(comp.nested_equal(val1,val2))


    def test_Attribute_error_for_get_item(self):
        for res in self.results.values():
            with self.assertRaises(AttributeError):
                res['IDONOTEXIST']

    def test_reject_outer_data_structure(self):
        for res in self.results.values():
            with self.assertRaises(TypeError):
                res.f_set(doesntwork=ChainMap({},{}))

    def test_the_insertion_made_implicetly_in_setUp(self):
        for key, val1 in self.data.items():
            res = self.results['test.res.kwargs']
            val2 = res[key]
            if isinstance(val1, dict):
                for innerkey in val1:
                    innerval1 = val1[innerkey]
                    innerval2 = val2[innerkey]
                    self.assertEqual(repr(innerval1), repr(innerval2),
                                     '%s != %s' % (str(val1),str(val2)))
            else:
                self.assertEqual(repr(val1),repr(val2), '%s != %s' % (str(val1),str(val2)))


    def test_pickling(self):
        for key, res in self.results.items():

            dump = pickle.dumps(res)

            newRes = pickle.loads(dump)

            self.results[key] = newRes

        self.test_the_insertion_made_implicetly_in_setUp()

        self.test_meta_settings()

    def test_storage_and_loading(self):

        for key, res in self.results.items():
            store_dict = res._store()

            constructor = res.__class__


            res = constructor('')

            res._load(store_dict)

            res._rename(key)

            self.results[key] = res


        self.test_the_insertion_made_implicetly_in_setUp()

        self.test_meta_settings()

class PickleResultTest(ResultTest):

    tags = 'unittest', 'result', 'pickle'

    def make_constructor(self):
        self.Constructor=PickleResult
        self.dynamic_imports = [PickleResult]

    def test_reject_outer_data_structure(self):
        # Since it pickles everything, it does accept all sorts of objects
        pass

    def test_meta_settings(self):
        for key, res in self.results.items():
            self.assertEqual(res.v_full_name, key)
            self.assertEqual(res.v_name, key.split('.')[-1])
            self.assertEqual(res.v_location, '.'.join(key.split('.')[0:-1]))
            self.assertEqual(res.v_protocol, self.protocols[key])

    def make_results(self):
        self.results= {}
        self.results['test.res.on_constructor']=self.Constructor('test.res.on_constructor',protocol=0,**self.data)
        self.results['test.res.args']=self.Constructor('test.res.args',protocol=1)
        self.results['test.res.kwargs']=self.Constructor('test.res.kwargs',protocol=2)

        self.protocols={'test.res.on_constructor':0,
                        'test.res.args':1,
                        'test.res.kwargs':2}

        self.results['test.res.args'].f_set(*list(self.data.values()))
        self.results['test.res.kwargs'].f_set(**self.data)

class SparseResultTest(ResultTest):

    tags = 'unittest', 'result', 'sparse'

    def make_constructor(self):
        self.Constructor=SparseResult
        self.dynamic_imports = [SparseResult]

    def setUp(self):

        if not hasattr(self,'data'):
            self.data={}

        self.data['spsparse_csc'] = spsp.csc_matrix((1000,100))
        self.data['spsparse_csc'][1,2] = 44.5

        self.data['spsparse_csr'] = spsp.csr_matrix((2222,22))
        self.data['spsparse_csr'][1,3] = 44.5

        self.data['spsparse_bsr'] = spsp.csr_matrix((111,111))
        self.data['spsparse_bsr'][3,2] = 44.5
        self.data['spsparse_bsr'] = self.data['spsparse_bsr'].tobsr()

        self.data['spsparse_dia'] = spsp.csr_matrix((111,111))
        self.data['spsparse_dia'][3,2] = 44.5
        self.data['spsparse_dia'] = self.data['spsparse_dia'].todia()

        super(SparseResultTest,self).setUp()

    def test_illegal_naming(self):
        for res in self.results.values():
            data_dict = {'val'+SparseResult.IDENTIFIER:42}
            with self.assertRaises(AttributeError):
                res.f_set(**data_dict)

    def make_results(self):
        self.results= {}
        self.results['test.res.on_constructor']=self.Constructor('test.res.on_constructor',
                                                                  protocol=0, **self.data)
        self.results['test.res.args']=self.Constructor('test.res.args')
        self.results['test.res.args'].v_protocol=1

        self.results['test.res.kwargs']=self.Constructor('test.res.kwargs', protocol=2)

        self.results['test.res.args'].f_set(*list(self.data.values()))
        self.results['test.res.kwargs'].f_set(**self.data)


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)
