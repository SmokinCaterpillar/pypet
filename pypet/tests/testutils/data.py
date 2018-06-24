import sys
import unittest
import logging

import numpy as np
import time
import pandas as pd
from scipy import sparse as spsp
from pypet import ArrayParameter, Parameter, SparseParameter, PickleParameter, \
    PickleResult, SparseResult, ObjectTable, BaseParameter, BaseResult
from pypet.tests.testutils.ioutils import remove_data, get_root_logger
from pypet.utils.comparisons import parameters_equal, results_equal
from pypet.utils.helpful_functions import flatten_dictionary
from pypet.utils.mpwrappers import LockWrapper
from pypet.utils.siginthandling import sigint_handling

__author__ = 'Robert Meyer'


def create_param_dict(param_dict):
    '''Fills a dictionary with some parameters that can be put into a trajectory.
    '''
    param_dict['Normal'] = {}
    param_dict['Numpy'] = {}
    param_dict['Sparse'] ={}
    param_dict['Numpy_2D'] = {}
    param_dict['Numpy_3D'] = {}
    param_dict['Tuples'] ={}
    param_dict['Lists'] ={}
    param_dict['Pickle']={}

    normal_dict = param_dict['Normal']
    normal_dict['string'] = 'Im a test string!'
    normal_dict['int'] = 42
    normal_dict['long'] = 42
    normal_dict['double'] = 42.42
    normal_dict['bool'] =True
    normal_dict['trial'] = 0

    numpy_dict=param_dict['Numpy']
    numpy_dict['string'] = np.array(['Uno', 'Dos', 'Tres'])
    numpy_dict['int'] = np.array([1,2,3,4])
    numpy_dict['double'] = np.array([1.0,2.0,3.0,4.0])
    numpy_dict['bool'] = np.array([True, False, True])

    param_dict['Numpy_2D']['double'] = np.matrix([[1.0,2.0],[3.0,4.0]])
    param_dict['Numpy_3D']['double'] = np.array([[[1.0,2.0],[3.0,4.0]],[[3.0,-3.0],[42.0,41.0]]])

    spsparse_csc = spsp.lil_matrix((222,22))
    spsparse_csc[1,2] = 44.6
    spsparse_csc[1,9] = 44.5
    spsparse_csc = spsparse_csc.tocsc()

    spsparse_csr = spsp.lil_matrix((222,22))
    spsparse_csr[1,3] = 44.7
    spsparse_csr[17,17] = 44.755555
    spsparse_csr = spsparse_csr.tocsr()

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

    param_dict['Tuples']['empty'] = ()
    param_dict['Tuples']['int'] = (1,2,3)
    param_dict['Tuples']['float'] = (44.4,42.1,3.)
    param_dict['Tuples']['str'] = ('1','2wei','dr3i')

    param_dict['Lists']['lempty'] = []
    param_dict['Lists']['lint'] = [1,2,3]
    param_dict['Lists']['lfloat'] = [44.4,42.1,3.]
    param_dict['Lists']['lstr'] = ['1','2wei','dr3i']

    param_dict['Pickle']['list']= ['b','h', 53, (), 0]
    param_dict['Pickle']['list']= ['b','h', 42, (), 1]
    param_dict['Pickle']['list']= ['b',[444,43], 44, (),2]


def add_params(traj,param_dict):
    '''Adds parameters to a trajectory
    '''
    flat_dict = flatten_dictionary(param_dict,'.')

    for key, val in flat_dict.items():
        if isinstance(val, (np.ndarray, tuple)) or (isinstance(val, list) and
                                                        (len(val) < 4 or val[3] != ())):
            traj.f_add_parameter(ArrayParameter,key,val, comment='comment')
        elif isinstance(val, (str,bool,float, int)):
            traj.f_add_parameter(Parameter,key,val, comment='Im a comment!')
        elif spsp.isspmatrix(val):
            traj.f_add_parameter(SparseParameter,key,val, comment='comment').v_annotations.f_set(
                **{'Name':key,'Val' :str(val),'Favorite_Numbers:':[1,2,3],
                                 'Second_Fav':np.array([43.0,43.0])})
        elif isinstance(val,list):
            # The last item of the list `val` is an int between 0 and 2, we can use it as a
            # protocol read out to test all protocols
            traj.f_add_parameter(PickleParameter,key,val, comment='Im a comment!', protocol=val[-1])
        else:
            raise RuntimeError('You shall not pass, %s is %s!' % (str(val),str(type(val))))


    traj.f_add_derived_parameter('Another.String', 'Hi, how are you?', comment='test1')
    traj.f_add_derived_parameter('Another.StringGroup.$', 'too bad!?', comment='test2')
    traj.f_add_derived_parameter('Another.$set.$.String', 'Really?', comment='test3')
    traj.f_add_derived_parameter('Another.crun.String2', 'Really, again?', comment='test4')


    traj.f_add_result('Peter_Jackson',np.str(['is','full','of','suboptimal ideas']),
                      comment='Only my opinion bro!',)

    traj.results.f_add_leaf('Test', 42, comment='NC')
    traj.f_add_group('derived_parameters.uo', comment='Yeah, this is unsuals')
    traj.dpar.f_add_leaf('uo.adsad', 3333, comment='Yo')
    traj.derived_parameters.f_add_leaf('Test2', 42, comment='sfsdf')

    traj.par.f_add_leaf('er.Test3', 42, comment='sdfds')

    for irun in range(13):
        traj.f_add_leaf('testleaf%d' % irun, 42, comment='f')

    traj.par.f_add_group('Empty', comment='Notting!')

    traj.f_add_group('imgeneric.bitch', comment='Generic_Group')
    traj.imgeneric.f_add_leaf('gentest', 'fortytwo', comment='Oh yeah!')


def multiply(traj):
    rootlogger = get_root_logger()
    z=traj.x*traj.y
    rootlogger.info('z=x*y: '+str(z)+'='+str(traj.x)+'*'+str(traj.y))
    traj.f_add_result('z',z)
    return z


def multiply_with_graceful_exit(traj):
    z=traj.x*traj.y
    rootlogger = get_root_logger()
    rootlogger.info('z=x*y: '+str(z)+'='+str(traj.x)+'*'+str(traj.y))
    traj.f_add_result('z',z)
    if traj.v_idx > 3:
        if not sigint_handling.hit:
            sigint_handling._handle_sigint(None, None)
    return z

def multiply_with_storing(traj):
    rootlogger = get_root_logger()
    z=traj.x*traj.y
    rootlogger.info('z=x*y: '+str(z)+'='+str(traj.x)+'*'+str(traj.y))
    traj.f_add_result('z',z)
    traj.f_store()
    return z


def multiply_args(traj, arg1=0, arg2=0, arg3=0):
    rootlogger = get_root_logger()
    z=traj.x*traj.y + arg1 + arg2 + arg3
    rootlogger.info('z=x*y: '+str(z)+'='+str(traj.x)+'*'+str(traj.y) +
                    '+'+str(arg1)+'+'+str(arg2)+'+'+str(arg3))
    traj.f_add_result('z',z)
    return z


def simple_calculations(traj, arg1, simple_kwarg):

        if traj.v_idx == 0:
            # to shuffle runs
            time.sleep(0.1)

        rootlogger = get_root_logger()

        if not 'runs' in traj.res:
            traj.res.f_add_result_group('runs')

        rootlogger.info('>>>>>Starting Simple Calculations')
        my_dict = {}

        my_dict2={}
        param_dict=traj.parameters.f_to_dict(fast_access=True,short_names=False)
        for key in sorted(param_dict.keys())[0:5]:
            val = param_dict[key]
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
        my_dict['__FLOATaRRAy_nested'] = np.array([np.array([1.0,2.0,41.0]),np.array([1.0,2.0,41.0])])
        my_dict['__STRaRRAy'] = np.array(['sds','aea','sf'])
        my_dict['__LONG'] = 4266
        my_dict['__UNICODE'] = u'sdfdsf'
        my_dict['__BYTES'] = b'zweiundvierzig'
        my_dict['__NUMPY_UNICODE'] = np.array([u'$%&ddss'])
        my_dict['__NUMPY_BYTES'] = np.array([b'zweiundvierzig'])

        keys = sorted(to_dict_wo_config(traj).keys())
        for idx,key in enumerate(keys[0:5]):
            keys[idx] = key.replace('.', '_')

        listy=traj.f_add_result_group('List', comment='Im a result group')
        traj.f_add_result_group('Iwiiremainempty.yo', comment='Empty group!')
        traj.Iwiiremainempty.f_store_child('yo')

        traj.Iwiiremainempty.f_add_link('kkk',listy )
        listy.f_add_link('hhh', traj.Iwiiremainempty)

        if not traj.Iwiiremainempty.kkk.v_full_name == traj.List.v_full_name:
            raise RuntimeError()

        if not traj.Iwiiremainempty.kkk.v_full_name == traj.List.hhh.kkk.v_full_name:
            raise RuntimeError()

        traj.f_add_result('runs.' + traj.v_crun + '.ggg', 5555, comment='ladida')
        traj.res.runs.f_add_result(traj.v_crun + '.ggjg', 5555, comment='didili')
        traj.res.runs.f_add_result('hhg', 5555, comment='jjjj')

        traj.res.f_add_result(name='lll', comment='duh', data=444)

        x = traj.res.f_add_result(name='nested', comment='duh')

        x['nested0.nested1.nested2.nested3'] =  44

        traj.res.f_add_result(name='test.$set.$', comment='duh', data=444)

        try:
            traj.f_add_config('teeeeest', 12)
            raise RuntimeError()
        except TypeError:
            pass

        # if not traj.f_contains('results.runs.' + traj.v_crun + '.ggjg', shortcuts=False):
        #     raise RuntimeError()
        # if not traj.f_contains('results.runs.' + traj.v_crun + '.ggg', shortcuts=False):
        #     raise RuntimeError()
        if not traj.f_contains('results.runs.' + traj.v_crun + '.hhg', shortcuts=False):
            raise RuntimeError()

        traj.f_add_result('List.Of.Keys', dict1=my_dict, dict2=my_dict2, comment='Test')
        traj.List.f_store_child('Of', recursive=True)
        traj.f_add_result('DictsNFrame', keys=keys, comment='A dict!')
        traj.f_add_result('ResMatrix',np.array([1.2,2.3]), comment='ResMatrix')

        traj.f_add_result('empty.stuff', (), [], {}, np.array([]), comment='empty stuff')
        #traj.f_add_derived_parameter('All.To.String', str(traj.f_to_dict(fast_access=True,short_names=False)))

        myframe = pd.DataFrame(data ={'TC1':[1,2,3],'TC2':['Waaa','',''],'TC3':[1.2,42.2,77]})

        myseries = myframe['TC1']

        traj.f_add_result('myseries', myseries, comment='dd')
        traj.f_store_item('myseries')

        traj.f_get('DictsNFrame').f_set(myframe)

        traj.f_add_result('IStore.SimpleThings',1.0,3,np.float32(5.0),
                          'Iamstring',
                          (1,2,3), [4,5,6],
                          zwei=2).v_comment='test'
        traj.f_add_derived_parameter('super.mega',33, comment='It is huuuuge!')
        traj.super.f_set_annotations(AgainATestAnnotations='I am a string!111elf')

        traj.f_add_result(PickleResult,'pickling.result.proto1', my_dict2, protocol=1, comment='p1')
        traj.f_add_result(PickleResult,'pickling.result.proto2', my_dict2, protocol=2, comment='p2')
        traj.f_add_result(PickleResult,'pickling.result.proto0', my_dict2, protocol=0, comment='p0')

        traj.f_add_result(SparseResult, 'sparse.csc', traj.csc_mat, 42).v_comment='sdsa'
        traj.f_add_result(SparseResult, 'sparse.bsr', traj.bsr_mat, 52).v_comment='sdsa'
        traj.f_add_result(SparseResult, 'sparse.csr', traj.csr_mat, 62).v_comment='sdsa'
        traj.f_add_result(SparseResult, 'sparse.dia', traj.dia_mat, 72).v_comment='sdsa'

        traj.sparse.v_comment = 'I contain sparse data!'

        myobjtab = ObjectTable(data={'strings':['a','abc','qwertt'], 'ints':[1,2,3]})

        traj.f_add_result('object.table', myobjtab, comment='k').v_annotations.f_set(test=42)
        traj.object.f_set_annotations(test2=42.42)

        traj.f_add_result('$.here', 77, comment='huhu')
        traj.f_add_result('tor.hot.$', dollah=77, comment='duh!')
        traj.f_add_result('tor.hot.rrr.$.j', 77, comment='duh!')
        traj.f_add_result('tor.hot.rrr.crun.jjj', 777, comment='duh**2!')

        #traj.f_add_result('PickleTerror', result_type=PickleResult, test=traj.SimpleThings)
        rootlogger.info('<<<<<<Finished Simple Calculations')

        # let's see if the traj can also always be returned
        if isinstance(traj.v_storage_service, LockWrapper):
            traj.v_storage_service.pickle_lock = False
        return 42, traj


def to_dict_wo_config(traj):
        res_dict={}

        for child_name in traj._children:

            child = traj._children[child_name]
            if child_name == 'config':
                continue

            if child.v_is_leaf:
                res_dict[child_name] = child
            else:
                res_dict.update(child.f_to_dict(fast_access=False))

        return res_dict


class TrajectoryComparator(unittest.TestCase):

    def are_results_in_order(self, results):
        self.assertGreater(len(results), 0)
        sorted_res = sorted(results, key=lambda key: key[0])
        self.assertEqual(results, sorted_res)

    def clear_handlers(self):
        """Deletes all handlers and closes all log-files"""
        root = logging.getLogger()
        for logger in list(root.manager.loggerDict.values()) + [root]:
            if hasattr(logger, 'handlers'):
                handlers = logger.handlers
                for handler in handlers:
                    if hasattr(handler, 'flush'):
                        handler.flush()
                    if hasattr(handler, 'close'):
                        handler.close()
                logger.handlers = []
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def tearDown(self):
        if hasattr(self, 'env') and hasattr(self.env, 'f_disable_logging'):
            self.env.f_disable_logging()
        self.clear_handlers()
        remove_data()

    def compare_trajectories(self,traj1,traj2):

        trajlength = len(traj1)

        if traj1.f_get_run_information(0)['completed']:

            # We need this fix in case the trajectory was never run
            # thus it does not contain any run groups but still has a length
            if 'results.runs' in traj1:
                rungroups = traj1.results.runs.f_children()
            else:
                rungroups = 1

            self.assertEqual(trajlength, rungroups, 'len of traj1 is %d, rungroups %d' % (trajlength, rungroups))

        old_items = to_dict_wo_config(traj1)
        new_items = to_dict_wo_config(traj2)

        self.assertEqual(len(traj1),len(traj2), 'Length unequal %d != %d.' % (len(traj1), len(traj2)))

        self.assertEqual(len(old_items),len(new_items))
        for key,item in new_items.items():
            old_item = old_items[key]

            if isinstance(item, BaseParameter):
                self.assertTrue(parameters_equal(item,old_item),
                                'For key %s: %s not equal to %s' % (key,str(old_item),str(item)))
            elif isinstance(item,BaseResult):
                self.assertTrue(results_equal(item, old_item),
                                'For key %s: %s not equal to %s' % (key, str(old_item),str(item)))
            else:
                raise RuntimeError('You shall not pass')


            self.assertTrue(str(item.v_annotations)==str(old_item.v_annotations),'%s != %s' %
                        (item.v_annotations.f_ann_to_str(),old_item.v_annotations.f_ann_to_str()))

        # Check the annotations
        for node in traj1.f_iter_nodes(recursive=True):

            if node.v_run_branch == traj1.f_wildcard('$', 0) or node.v_run_branch == 'trajectory':
                if node.v_comment != '' and node.v_full_name in traj2:
                    second_comment = traj2.f_get(node.v_full_name).v_comment
                    self.assertEqual(node.v_comment, second_comment, '%s != %s, for %s' %
                                                (node.v_comment, second_comment, node.v_full_name))

            if not node.v_annotations.f_is_empty():
                second_anns = traj2.f_get(node.v_full_name).v_annotations
                self.assertTrue(str(node.v_annotations) == str(second_anns))
