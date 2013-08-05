import mypet

__author__ = 'robert'


import numpy as np
import unittest
from mypet.parameter import Parameter, SparseParameter
import pickle
import scipy.sparse as spsp

class ParameterTest(unittest.TestCase):



    def testMetaSettings(self):
        self.assertEqual(self.param.get_fullname(), self.fullname)
        self.assertEqual(self.param.get_name(), self.name)
        self.assertEqual(self.param.get_location(), self.location)


    def setUp(self):
        self.val0 = 1
        self.val1 = 1.0
        self.val2 = True
        self.val3 = 'String'
        self.npfloat = np.array([1.0,2.0,3.0])
        self.npfloat_2d = np.array([[1.0,2.0],[3.0,4.0]])
        self.npbool= np.array([True,False, True])
        self.npstr = np.array(['Uno', 'Dos', 'Tres'])
        self.npint = np.array([1,2,3])

        self.fullname = 'MyName.Is.myParam'
        self.split_name = self.fullname.split('.')
        self.name = self.split_name.pop()
        self.location = '.'.join(self.split_name)


        self.param = Parameter(self.fullname, self.val0,self.val1,self.val2,self.val3,
                               npfloat=self.npfloat,
                               npfloat_2d=self.npfloat_2d,
                               npbool=self.npbool,
                               npstr=self.npstr,
                               npint=self.npint)



        with self.assertRaises(AttributeError):
            self.param.set([[1,2,3],[1,2,3]])

        #Add explortation:
        self.explore_dict={'npstr':[np.array(['Uno', 'Dos', 'Tres']),
                               np.array(['Cinco', 'Seis', 'Siette']),
                            np.array(['Ocho', 'Nueve', 'Diez'])]}

        ## Explore the parameter:
        self.param.explore(self.explore_dict)



    def test_the_insertion_made_implicetly_in_setUp(self):
        self.assertEqual(self.param.val,self.val0)
        self.assertEqual(self.param.val0,self.val0)
        self.assertEqual(self.param.get('val0'),self.val0)
        self.assertEqual(self.param.get('val1'),self.val1)
        self.assertEqual(self.param.get('val2'),self.val2)
        self.assertEqual(self.param.get('val3'),self.val3)
        self.assertTrue(np.all(self.param.npfloat == self.npfloat))
        self.assertTrue(np.all(self.param.npfloat_2d == self.npfloat_2d))
        self.assertTrue(np.all(self.param.npbool == self.npbool))
        self.assertTrue(np.all(self.param.npstr == self.npstr))
        self.assertTrue(np.all(self.param.npint==self.npint))


    def test__getstate_and__setstate(self):
        state_dict = self.param.__getstate__()
        data_dict = state_dict['_data']
        for key, vallist in data_dict.items():
            self.assertIsInstance(vallist, list)
            for idx,val in enumerate(vallist):
                self.assertTrue(np.all(val==self.param.get(key,idx)))


        self.param.__setstate__(state_dict)
        self.test_the_insertion_made_implicetly_in_setUp()




    def tes_hasvalue(self):
        self.assertTrue(self.param.has_value('npfloat'))
        self.assertFalse(self.param.has_value('xwfdewfewefe'))


    def test_exploration(self):
        self.assertTrue(len(self.param) == 3)

        self.param.set_parameter_access(n=1)

        arstr = self.param.get('npstr')
        cmparstr = self.explore_dict['npstr'][1]
        self.assertTrue(np.all( arstr== cmparstr))

        #The other values should be changed:
        self.assertEqual(self.param.get('val0'),self.val0)
        self.assertEqual(self.param.get('val1'),self.val1)
        self.assertEqual(self.param.get('val2'),self.val2)
        self.assertEqual(self.param.get('val3'),self.val3)

    def test_storage_and_loading(self):
        store_dict = self.param.__store__()

        constructor = self.param.__class__
        del self.param

        self.param = constructor('')

        self.param.__load__(store_dict)

        self.test_the_insertion_made_implicetly_in_setUp()

        self.test_exploration()

        self.testMetaSettings()


    def test_pickling_without_multiprocessing(self):
        self.param.set(FullCopy = True)

        dump = pickle.dumps(self.param)

        newParam = pickle.loads(dump)

        self.test_exploration()

        self.param = newParam

        self.test_the_insertion_made_implicetly_in_setUp()

        self.testMetaSettings()


    def test_pickling_with_multiprocessing(self):
        self.param.set(FullCopy = False)

        dump = pickle.dumps(self.param)

        newParam = pickle.loads(dump)

        self.assertTrue(len(newParam) == 1)

        self.param = newParam

        self.test_the_insertion_made_implicetly_in_setUp()

        self.testMetaSettings()


class SparseParameterTest(ParameterTest):

    def setUp(self):
        self.val0 = 1
        self.val1 = 1.0
        self.val2 = True
        self.val3 = 'String'
        self.npfloat = np.array([1.0,2.0,3.0])
        self.npfloat_2d = np.array([[1.0,2.0],[3.0,4.0]])
        self.npbool= np.array([True,False, True])
        self.npstr = np.array(['Uno', 'Dos', 'Tres'])
        self.npint = np.array([1,2,3])
        self.spsparse_csc = spsp.csc_matrix((1000,100))
        self.spsparse_csc[1,2] = 44.5

        self.spsparse_csr = spsp.csr_matrix((2222,22))
        self.spsparse_csr[1,3] = 44.5

        self.spsparse_lil = spsp.lil_matrix((111,111))
        self.spsparse_lil[3,2] = 44.5

        self.fullname = 'MyName.Is.myParam'
        self.split_name = self.fullname.split('.')
        self.name = self.split_name.pop()
        self.location = '.'.join(self.split_name)



        self.param = SparseParameter(self.fullname, self.val0,self.val1,self.val2,self.val3,
                               npfloat=self.npfloat,
                               npfloat_2d=self.npfloat_2d,
                               npbool=self.npbool,
                               npstr=self.npstr,
                               npint=self.npint)

        self.param.set(spsparse_csc=self.spsparse_csc)
        self.param.set(spsparse_csr=self.spsparse_csr)
        self.param.set(spsparse_lil=self.spsparse_lil)

        with self.assertRaises(AttributeError):
            self.param.set([[1,2,3],[1,2,3]])

        with self.assertRaises(AttributeError):
            self.param.set(spsp.coo_matrix((12,12)))

        #Add explortation:
        self.explore_dict={'npstr':[np.array(['Uno', 'Dos', 'Tres']),
                               np.array(['Cinco', 'Seis', 'Siette']),
                            np.array(['Ocho', 'Nueve', 'Diez'])]}

        ## Explore the parameter:
        self.param.explore(self.explore_dict)


    def test_the_insertion_made_implicetly_in_setUp(self):
        super(SparseParameterTest,self).test_the_insertion_made_implicetly_in_setUp()

        sp_lil = self.param.spsparse_lil
        sp_csc = self.param.spsparse_csc
        sp_csr = self.param.spsparse_csr



        self.assertTrue(spsp.isspmatrix_lil(sp_lil))
        self.assertTrue(spsp.isspmatrix_csc(sp_csc))
        self.assertTrue(spsp.isspmatrix_csr(sp_csr))

        comp = np.all(sp_lil.todense()==self.spsparse_lil.todense())
        self.assertTrue(comp)

        comp = np.all(sp_csc.todense()==self.spsparse_csc.todense())
        self.assertTrue(comp)

        comp = np.all(sp_csr.todense()==self.spsparse_csr.todense())
        self.assertTrue(comp)

        comp = np.all(self.spsparse_csr.todense()==self.spsparse_lil.todense())
        self.assertFalse(comp)

if __name__ == '__main__':
    unittest.main()
