import mypet

__author__ = 'robert'


import numpy as np
import unittest
from mypet.parameter import Parameter, PickleParameter, BaseParameter
import pickle
import scipy.sparse as spsp
import mypet.petexceptions as pex


class Dummy():
    pass

class ParameterTest(unittest.TestCase):


    def testMetaSettings(self):
        for key, param in self.param.__dict__.items():
            self.assertEqual(param.get_fullname(), self.location+'.'+key)
            self.assertEqual(param.get_name(), key)
            self.assertEqual(param.get_location(), self.location)


    def make_params(self):
        self.param = Dummy()
        for key, val in self.data.__dict__.items():
            self.param.__dict__[key] = Parameter(self.location+'.'+key, val, comment=key)


    def setUp(self):

        if not hasattr(self,'data'):
            self.data=Dummy()

        self.data.val0 = 1
        self.data.val1 = 1.0
        self.data.val2 = True
        self.data.val3 = 'String'
        self.data.npfloat = np.array([1.0,2.0,3.0])
        self.data.npfloat_2d = np.array([[1.0,2.0],[3.0,4.0]])
        self.data.npbool= np.array([True,False, True])
        self.data.npstr = np.array(['Uno', 'Dos', 'Tres'])
        self.data.npint = np.array([1,2,3])

        self.location = 'MyName.Is.myParam'





        self.make_params()




        # with self.assertRaises(AttributeError):
        #     self.param.val0.set([[1,2,3],[1,2,3]])

        #Add explortation:
        self.explore()

    def explore(self):
        self.explore_dict={'npstr':[np.array(['Uno', 'Dos', 'Tres']),
                               np.array(['Cinco', 'Seis', 'Siette']),
                            np.array(['Ocho', 'Nueve', 'Diez'])],
                           'val0':[1,2,3]}

        ## Explore the parameter:
        for key, vallist in self.explore_dict.items():
            self.param.__dict__[key].explore(vallist)




    def test_the_insertion_made_implicetly_in_setUp(self):
        for key, val in self.data.__dict__.items():

            if not key in self.explore_dict:
                param_val = self.param.__dict__[key].get()
                self.assertTrue(np.all(str(val) == str(param_val)),'%s != %s'  %(str(val),str(param_val)))


    # def test__getstate_and__setstate(self):
    #
    #     for key, param in self.param.__dict__.items():
    #         state_dict = param.__getstate__()
    #         vallist = state_dict['_explored_data']
    #
    #         self.assertIsInstance(vallist, tuple)
    #         for idx,val in enumerate(vallist):
    #             self.assertTrue(np.all(val==param.get_array()[idx]))
    #
    #         data = state_dict['_data']
    #
    #         self.assertTrue(np.all(data==param.get()))
    #
    #
    #         param.__setstate__(state_dict)
    #
    #     self.test_the_insertion_made_implicetly_in_setUp()
    #     self.test_exploration()




    def test_exploration(self):
        for key, vallist in self.explore_dict.items():

            param = self.param.__dict__[key]

            for idx, val in enumerate(vallist):
                assert isinstance(param, BaseParameter)
                param.set_parameter_access(idx)

                self.assertTrue(np.all(repr(param.get())==repr(val))),'%s != %s'%( str(param.get()),str(val))


    def test_storage_and_loading(self):

        for key, param in self.param.__dict__.items():
            store_dict = param.__store__()

            constructor = param.__class__

            param.unlock()
            param.empty()

            param = constructor('')

            param.__load__(store_dict)

            param._rename(self.location+'.'+key)

            self.param.__dict__[key] = param


        self.test_the_insertion_made_implicetly_in_setUp()

        self.test_exploration()

        self.testMetaSettings()


    def test_pickling_without_multiprocessing(self):
        for key, param in self.param.__dict__.items():
            param.unlock()
            param.set_full_copy(True)

            dump = pickle.dumps(param)

            newParam = pickle.loads(dump)



            self.param.__dict__[key] = newParam

        self.test_exploration()

        self.test_the_insertion_made_implicetly_in_setUp()

        self.testMetaSettings()


    def test_pickling_with_multiprocessing(self):
        for key, param in self.param.__dict__.items():
            param.unlock()
            param.set_full_copy(False)

            dump = pickle.dumps(param)

            newParam = pickle.loads(dump)



            self.param.__dict__[key] = newParam

        #self.test_exploration()

        self.test_the_insertion_made_implicetly_in_setUp()

        self.testMetaSettings()


    def testresizinganddeletion(self):

        for key, param in self.param.__dict__.items():
            param.lock()
            with self.assertRaises(pex.ParameterLockedException):
                 param.set(42)

            with self.assertRaises(pex.ParameterLockedException):
                param.shrink()

            param.unlock()


            if len(param)> 1:
                self.assertTrue(param.is_array())

            if param.is_array():
                self.assertTrue(len(param)>1)

            param.shrink()
            self.assertTrue(len(param) == 1)

            self.assertFalse(param.is_empty())
            self.assertFalse(param.is_array())



            param.empty()

            self.assertTrue(param.is_empty())
            self.assertFalse(param.is_array())



class PickleParameterTest(ParameterTest):

    def setUp(self):


        if not hasattr(self,'data'):
            self.data=Dummy()

        self.data.spsparse_csc = spsp.csc_matrix((1000,100))
        self.data.spsparse_csc[1,2] = 44.5

        self.data.spsparse_csr = spsp.csr_matrix((2222,22))
        self.data.spsparse_csr[1,3] = 44.5

        self.data.spsparse_lil = spsp.lil_matrix((111,111))
        self.data.spsparse_lil[3,2] = 44.5

        super(PickleParameterTest,self).setUp()


    def make_params(self):
        self.param = Dummy()
        for key, val in self.data.__dict__.items():
            self.param.__dict__[key] = PickleParameter(self.location+'.'+key, val, comment=key)



    def explore(self):




        matrices = []
        for irun in range(3):

            spsparse_lil = spsp.lil_matrix((111,111))
            spsparse_lil[3,2] = 44.5*irun

            matrices.append(spsparse_lil)


        self.explore_dict={'npstr':[np.array(['Uno', 'Dos', 'Tres']),
                               np.array(['Cinco', 'Seis', 'Siette']),
                            np.array(['Ocho', 'Nueve', 'Diez'])],
                           'val0':[1,2,3],
                           'spsparse_lil' : matrices}




        ## Explore the parameter:
        for key, vallist in self.explore_dict.items():
            self.param.__dict__[key].explore(vallist)




if __name__ == '__main__':
    unittest.main()
