

__author__ = 'Robert Meyer'



import numpy as np

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

from pypet.parameter import Parameter, PickleParameter, Result, BaseResult
from pypet.trajectory import Trajectory, SingleRun
from pypet.storageservice import LazyStorageService
import pickle
import logging
import cProfile
import scipy.sparse as spsp
import pypet.pypetexceptions as pex
import multiprocessing as multip
import pypet.utils.comparisons as comp

import copy

import pypet.storageservice as stsv

class ImAParameterInDisguise(Parameter):
    pass

class ImAResultInDisguise(Result):
    pass

class TrajectoryTest(unittest.TestCase):


    def setUp(self):
        name = 'Moop'

        self.traj = Trajectory(name,dynamically_imported_classes=[ImAParameterInDisguise,
                                                                  'pypet.tests.test_helpers.ImAResultInDisguise'])

        self.assertTrue(self.traj.f_is_empty())

        comment = 'This is a comment'
        self.traj.v_comment=comment

        self.assertTrue(comment == self.traj.v_comment)

        self.traj.f_add_parameter('IntParam',3)
        sparsemat = spsp.csr_matrix((1000,1000))
        sparsemat[1,2] = 17.777

        self.traj.f_add_parameter(PickleParameter,'SparseParam', sparsemat)

        self.traj.f_add_parameter('FloatParam')

        self.traj.f_add_derived_parameter(Parameter('FortyTwo', 42))

        self.traj.f_add_result(Result,'Im.A.Simple.Result',44444)

        self.traj.FloatParam=4.0

        self.traj.f_explore({'FloatParam':[1.0,1.1,1.2,1.3]})

        self.assertTrue(len(self.traj) == 4)

        self.traj.f_add_parameter_group('peter.paul')

        self.traj.f_add_parameter('peter.markus.yve',6)

        self.traj.f_add_result('Test',42)

        self.traj.peter.f_add_parameter('paul.peter')

        self.traj.f_add_config('make.impossible.promises',1)

        with self.assertRaises(AttributeError):
            self.traj.markus.peter

        with self.assertRaises(ValueError):
            self.traj.f_add_parameter('Peter.  h ._hurz')

    def test_value_error_on_search_strategy_assignment(self):
        with self.assertRaises(ValueError):
            self.traj.v_search_strategy = 'ewnforenfre'

    def test_get_data_dictionaries_directly(self):

        ############## Cofig ###################
        config_dict_from_subtree = self.traj.config.f_to_dict()

        self.assertTrue(len(config_dict_from_subtree)>0)

        config_dict_directly = self.traj.f_get_config(copy=True)

        self.assertTrue(comp.nested_equal(config_dict_directly,config_dict_from_subtree),
                        '%s!=%s' % (str(config_dict_directly),str(config_dict_directly)))

        config_dict_directly = self.traj.f_get_config(copy=False)

        self.assertTrue(comp.nested_equal(config_dict_directly,config_dict_from_subtree),
                        '%s!=%s' % (str(config_dict_directly),str(config_dict_directly)))


        config_dict_from_subtree = self.traj.config.f_to_dict(fast_access=True)

        with self.assertRaises(ValueError):
            config_dict_directly = self.traj.f_get_config(copy=False, fast_access=True)

        config_dict_directly = self.traj.f_get_config(copy=True, fast_access=True)

        self.assertTrue(comp.nested_equal(config_dict_directly,config_dict_from_subtree),
                        '%s!=%s' % (str(config_dict_directly),str(config_dict_directly)))

        ############## Parameters #############################
        parameters_dict_from_subtree = self.traj.parameters.f_to_dict()

        self.assertTrue(len(parameters_dict_from_subtree)>0)

        parameters_dict_directly = self.traj.f_get_parameters(copy=True)

        self.assertTrue(comp.nested_equal(parameters_dict_directly,parameters_dict_from_subtree),
                        '%s!=%s' % (str(parameters_dict_directly),str(parameters_dict_directly)))

        parameters_dict_directly = self.traj.f_get_parameters(copy=False)

        self.assertTrue(comp.nested_equal(parameters_dict_directly,parameters_dict_from_subtree),
                        '%s!=%s' % (str(parameters_dict_directly),str(parameters_dict_directly)))


        ### Empty Parameters won't support fast access so we need to set
        self.traj.paul.peter.f_set(42)

        parameters_dict_from_subtree = self.traj.parameters.f_to_dict(fast_access=True)

        with self.assertRaises(ValueError):
            parameters_dict_directly = self.traj.f_get_parameters(copy=False, fast_access=True)

        parameters_dict_directly = self.traj.f_get_parameters(copy=True, fast_access=True)

        self.assertTrue(comp.nested_equal(parameters_dict_directly,parameters_dict_from_subtree),
                        '%s!=%s' % (str(parameters_dict_directly),str(parameters_dict_directly)))

        ################# Derived Parameters ############################
        derived_parameters_dict_from_subtree = self.traj.derived_parameters.f_to_dict()

        self.assertTrue(len(derived_parameters_dict_from_subtree)>0)

        derived_parameters_dict_directly = self.traj.f_get_derived_parameters(copy=True)

        self.assertTrue(comp.nested_equal(derived_parameters_dict_directly,derived_parameters_dict_from_subtree),
                        '%s!=%s' % (str(derived_parameters_dict_directly),str(derived_parameters_dict_directly)))

        derived_parameters_dict_directly = self.traj.f_get_derived_parameters(copy=False)

        self.assertTrue(comp.nested_equal(derived_parameters_dict_directly,derived_parameters_dict_from_subtree),
                        '%s!=%s' % (str(derived_parameters_dict_directly),str(derived_parameters_dict_directly)))


        derived_parameters_dict_from_subtree = self.traj.derived_parameters.f_to_dict(fast_access=True)

        with self.assertRaises(ValueError):
            derived_parameters_dict_directly = self.traj.f_get_derived_parameters(copy=False, fast_access=True)

        derived_parameters_dict_directly = self.traj.f_get_derived_parameters(copy=True, fast_access=True)

        self.assertTrue(comp.nested_equal(derived_parameters_dict_directly,derived_parameters_dict_from_subtree),
                        '%s!=%s' % (str(derived_parameters_dict_directly),str(derived_parameters_dict_directly)))



        ############## Results #################################
        results_dict_from_subtree = self.traj.results.f_to_dict()

        self.assertTrue(len(results_dict_from_subtree)>0)

        results_dict_directly = self.traj.f_get_results(copy=True)

        self.assertTrue(comp.nested_equal(results_dict_directly,results_dict_from_subtree),
                        '%s!=%s' % (str(results_dict_directly),str(results_dict_directly)))

        results_dict_directly = self.traj.f_get_results(copy=False)

        self.assertTrue(comp.nested_equal(results_dict_directly,results_dict_from_subtree),
                        '%s!=%s' % (str(results_dict_directly),str(results_dict_directly)))


        results_dict_from_subtree = self.traj.results.f_to_dict(fast_access=True)

        with self.assertRaises(ValueError):
            results_dict_directly = self.traj.f_get_results(copy=False, fast_access=True)

        results_dict_directly = self.traj.f_get_results(copy=True, fast_access=True)

        self.assertTrue(comp.nested_equal(results_dict_directly,results_dict_from_subtree),
                        '%s!=%s' % (str(results_dict_directly),str(results_dict_directly)))


        ################### Explored Parameters #######################


        #We need to unlock the parameter because we have accessed it above
        self.traj.f_get('yve').f_unlock()
        explore_dict = {'yve':[4,5,65,66]}

        # We can add to existing explored parameters if we match the length
        self.traj.f_explore(explore_dict)

        explore_dict_directly = self.traj.f_get_explored_parameters(copy=False)

        for key in explore_dict:
            self.assertTrue(comp.nested_equal(self.traj.f_get(key),
                                              explore_dict_directly[self.traj.f_get(key).v_full_name]))

        explore_dict_directly = self.traj.f_get_explored_parameters(copy=True)

        for key in explore_dict:
            self.assertTrue(comp.nested_equal(self.traj.f_get(key),
                                              explore_dict_directly[self.traj.f_get(key).v_full_name]))

        with self.assertRaises(ValueError):
            explore_dict_directly = self.traj.f_get_explored_parameters(copy=False, fast_access=True)

        explore_dict_directly = self.traj.f_get_explored_parameters(copy=True, fast_access=True)

        for key in explore_dict:
            self.assertTrue(comp.nested_equal(self.traj.f_get(key,fast_access=True),
                                              explore_dict_directly[self.traj.f_get(key).v_full_name]))



    def test_f_get(self):
        self.traj.v_fast_access=True
        self.traj.f_get('FloatParam', fast_access=True) == self.traj.FloatParam

        self.traj.v_fast_access=False

        self.assertTrue(self.traj.f_get('FloatParam').f_get() == 4.0 , '%d != 4.0' %self.traj.f_get('FloatParam').f_get())

        self.assertTrue(self.traj.FortyTwo.f_get() == 42)


    def test_get_item(self):

        self.assertEqual(self.traj.markus.yve, self.traj['markus.yve'].f_get())

    @staticmethod
    def get_depth_dict(traj, as_run=None):

        bfs_queue=[traj]
        depth_dict={}
        while len(bfs_queue)>0:
            item = bfs_queue.pop(0)
            depth = item.v_depth
            if not depth in depth_dict:
                depth_dict[depth]=[]

            depth_dict[depth].append(item)

            if not item.v_is_leaf:
                if as_run in item._children:
                    bfs_queue.append(item._children[as_run])
                else:
                    for child in item._children.itervalues():
                        bfs_queue.append(child)

        return depth_dict


    def test_iter_bfs(self):

        depth_dict = self.get_depth_dict(self.traj)

        depth_dict[0] =[]

        prev_depth = 0

        for node in self.traj.f_iter_nodes(recursive=True, search_strategy='BFS'):
            if prev_depth != node.v_depth:
                self.assertEqual(len(depth_dict[prev_depth]),0)
                prev_depth = node.v_depth

            depth_dict[node.v_depth].remove(node)

    def test_iter_dfs(self):

        prev_node = None

        x= [x for x in self.traj.f_iter_nodes(recursive=True, search_strategy='DFS')]

        for node in self.traj.f_iter_nodes(recursive=True, search_strategy='DFS'):
            if not prev_node is None:
                if not prev_node.v_is_leaf and len(prev_node._children) > 0:
                    self.assertTrue(node.v_name in prev_node._children)

            prev_node = node

    def test_iter_bfs_as_run(self):
        as_run = 1

        self.traj.f_add_result('results.run_00000000.resulttest', 42)
        self.traj.f_add_result('results.run_00000001.resulttest', 43)

        self.traj.f_as_run(as_run)

        depth_dict = self.get_depth_dict(self.traj, self.traj.f_idx_to_run(as_run))

        depth_dict[0] =[]

        prev_depth = 0

        for node in self.traj.f_iter_nodes(recursive=True, search_strategy='BFS'):
            self.assertTrue('run_00000000' not in node.v_full_name)
            if prev_depth != node.v_depth:
                self.assertEqual(len(depth_dict[prev_depth]),0)
                prev_depth = node.v_depth

            depth_dict[node.v_depth].remove(node)

    def test_iter_dfs_as_run(self):

        self.traj.f_add_result('results.run_00000000.resulttest', 42)
        self.traj.f_add_result('results.run_00000001.resulttest', 43)

        self.traj.f_as_run('run_00000001')

        prev_node = None

        x= [x for x in self.traj.f_iter_nodes(recursive=True, search_strategy='DFS')]

        for node in self.traj.f_iter_nodes(recursive=True, search_strategy='DFS'):
            self.assertTrue('run_00000000' not in node.v_full_name)

            if not prev_node is None:
                if not prev_node.v_is_leaf and len(prev_node._children) > 0:
                    self.assertTrue(node.v_name in prev_node._children)

            prev_node = node






    def test_illegal_namings(self):
        self.traj=Trajectory()

        with self.assertRaises(ValueError):
            self.traj.f_add_parameter('f_get')

        with self.assertRaises(ValueError):
            self.traj.f_add_parameter('ewhfiuehfhewfheufhewhfewhfehiueufhwfiuhfiuewhfiuewhfei'
                                      'ewfewnfiuewnfiewfhnifuhnrifnhreifnheirfirenfhirefnhifri'
                                      'weoiufwfjwfjewfurehiufhreiuhfiurehfriufhreiufhrifhrfri')
        with self.assertRaises(ValueError):
            self.traj.f_add_parameter('ewhfiuehfhewfheufhewhfewhfehiueufhwfiuhfiuewhfiuewhfei'
                                      'ewfewnfiuewnfiewfhnifuhnrifnhreifnheirfirenfhirefnhifri'
                                      'weoiufwfjwfjewfurehiufhreiuhfiurehfriufhreiufhrifhrfri.test')


        with self.assertRaises(ValueError):
            self.traj.f_add_parameter('tr',22)



    def test_attribute_error_raises_when_leaf_and_group_with_same_name_are_added(self):

        self.traj = Trajectory()

        self.traj.f_add_parameter('test.param1')

        with self.assertRaises(AttributeError):
            self.traj.f_add_parameter('test.param1.param2')

        with self.assertRaises(AttributeError):
            self.traj.f_add_parameter('test')


    def testremove(self):
        self.traj.f_remove_item(self.traj.f_get('peter.markus.yve'),remove_empty_groups=True)

        with self.assertRaises(AttributeError):
            self.traj.peter.markus.yve

        self.assertFalse('peter.markus.yve' in self.traj)

        #self.assertTrue(len(self.traj)==1)

        self.traj.f_remove_item('FortyTwo',remove_empyt_groups=True)

        self.traj.f_remove_item('SparseParam')
        self.traj.f_remove_item('IntParam')

        #self.assertTrue(len(self.traj)==1)

    def test_changing(self):

        self.traj.f_preset_config('testconf', 1)
        self.traj.f_preset_parameter('testparam', 1)
        self.traj.f_preset_parameter('I_do_not_exist', 2)

        self.traj.f_add_parameter('testparam', 0)
        self.traj.f_add_config('testconf', 0)

        self.traj.v_fast_access=True

        self.assertTrue(self.traj.testparam == 1)
        self.assertTrue(self.traj.testconf == 1)

        ### should raise an error because 'I_do_not_exist', does not exist:
        with self.assertRaises(pex.PresettingError):
            self.traj._prepare_experiment()

    def test_f_is_completed(self):
        traj = Trajectory()

        traj.f_add_parameter('test', 42)

        traj.f_explore({'test':[1,2,3,4]})

        self.assertFalse(traj.f_is_completed())

        for run_name in traj.f_get_run_names():
            self.assertFalse(traj.f_is_completed(run_name))

        traj._run_information[traj.f_idx_to_run(1)]['completed']=1

        self.assertFalse(traj.f_is_completed())

        self.assertTrue(traj.f_is_completed(1))

        for run_name in traj.f_get_run_names():
            traj._run_information[run_name]['completed']=1

        self.assertTrue(traj.f_is_completed())

        for run_name in traj.f_get_run_names():
            self.assertTrue(traj.f_is_completed(run_name))



    def test_if_picklable(self):

        self.traj.v_fast_access=True

        #self.traj.v_full_copy=True
        dump = pickle.dumps(self.traj)

        newtraj = pickle.loads(dump)


        self.assertTrue(len(newtraj) == len(self.traj))

        new_items = newtraj.f_to_dict(fast_access=True)

        for key, val in self.traj.f_to_dict(fast_access=True).items():
            #val = newtraj.f_get(table_name)
            nval = new_items[key]
            if isinstance(val, BaseResult):
                for ikey in val._data:
                    self.assertTrue(str(nval.f_get(ikey))==str(val.f_get(ikey)))
            else:

                self.assertTrue(str(val)==str(nval), '%s != %s' %(str(val),str(nval)))

    def test_dynamic_class_loading(self):
        self.traj.f_add_parameter(ImAParameterInDisguise,'Rolf', 1.8)

    def test_standard_change_param_change(self):
        self.traj.v_standard_parameter=ImAParameterInDisguise

        self.traj.f_add_parameter('I.should_be_not.normal')

        self.assertIsInstance(self.traj.f_get('normal'), ImAParameterInDisguise,'Param is %s insted of ParamInDisguise.' %str(type(self.traj.normal)))

        self.traj.v_standard_result=ImAResultInDisguise

        self.traj.f_add_result('Peter.Parker')

        self.assertIsInstance(self.traj.Parker, ImAResultInDisguise)


    def test_remove_of_explored_stuff_if_saved(self):

        self.traj = Trajectory()

        self.traj.f_add_parameter('test', 42)

        self.traj.f_explore({'test':[1,2,3,4]})

        self.traj._stored=True

        self.traj.parameters.f_remove_child('test')

        len(self.traj) == 4

    def test_remov_of_explored_stuff_if_not_saved(self):

        self.traj = Trajectory()

        self.traj.f_add_parameter('test', 42)

        self.traj.f_explore({'test':[1,2,3,4]})

        self.traj.parameters.f_remove_child('test')

        len(self.traj) == 1

    def test_not_unique_search(self):
        self.traj = Trajectory()

        self.traj.f_add_parameter('ghgghg.test')
        self.traj.f_add_parameter('ghdsfdfdsfdsghg.test')

        self.traj.v_check_uniqueness=True
        with self.assertRaises(pex.NotUniqueNodeError):
            self.traj.test


    def test_contains_item_identity(self):

        peterpaul = self.traj.f_get('peter.paul')

        self.assertTrue(peterpaul in self.traj)

        peterpaulcopy = copy.deepcopy(peterpaul)

        self.assertFalse(peterpaulcopy in self.traj)


    def test_get_children(self):

        for node in self.traj.f_iter_nodes():
            if not node.v_is_leaf:
                self.assertEqual(id(node.f_get_children(copy=False)), id(node._children))

                self.assertNotEqual(id(node.f_get_children(copy=True)), id(node._children))

                self.assertEqual(sorted(node.f_get_children(copy=True).keys()),
                                 sorted(node._children.keys()))

    def test_short_cuts(self):

        self.traj = Trajectory()

        self.traj.f_add_parameter('test', 42)

        self.traj.f_add_result('safd', 42)

        self.traj.f_explore({'test':[1,2,3,4]})

        self.assertEqual(id(self.traj.par), id(self.traj.parameters))
        self.assertEqual(id(self.traj.param), id(self.traj.parameters))


        self.assertEqual(id(self.traj.dpar), id(self.traj.derived_parameters))
        self.assertEqual(id(self.traj.dparam), id(self.traj.derived_parameters))

        self.assertEqual(id(self.traj.conf), id(self.traj.config))

        self.assertEqual(id(self.traj.res), id(self.traj.results))

        self.assertEqual(id(self.traj.results.traj), id(self.traj.results.trajectory))
        self.assertEqual(id(self.traj.results.tr), id(self.traj.results.trajectory))

        srun = self.traj._make_single_run(3)

        srun.f_add_result('sdffds',42)


        self.assertEqual(id(srun.results.cr), id(srun.results.f_get(srun.v_name)))
        self.assertEqual(id(srun.results.currentrun), id(srun.results.f_get(srun.v_name)))
        self.assertEqual(id(srun.results.current_run), id(srun.results.f_get(srun.v_name)))



class TrajectoryFindTest(unittest.TestCase):
    def setUp(self):
        name = 'Traj'
        traj = Trajectory(name)

        traj.f_add_parameter('x',0)
        traj.f_add_parameter('y',0.0)
        traj.f_add_parameter('z','test')
        traj.f_add_parameter('ar', np.array([1,2,3]))
        traj.f_add_parameter('scalar', 42)
        self.explore(traj)
        self.traj=traj

    def test_simple_find_idx(self):
        pred = lambda x: x==2

        it = self.traj.f_find_idx('x',pred)
        it_list = [i for i in it]

        self.assertEqual(len(it_list),1, 'Should find 1 item but found %d' % len(it_list) )

        self.assertEqual(it_list[0],1, 'Found wrong index, should find 1 but found %s' % it_list[0])

    def test_complex_find_statement(self):
        pred = lambda x,ar,z,scalar: (scalar == 42 and
                                     (x == 2 or x==4 or x==5) and
                                     (z == 'meter' or z=='berserker' ) and
                                     np.all(np.array([4,5,6]) == ar))

        it = self.traj.f_find_idx(('x', 'ar','z','scalar'),pred)
        it_list = [i for i in it]

        self.assertEqual(len(it_list),2, 'Should find 2 items but found %d' % len(it_list) )

        self.assertEqual(it_list[0],1, 'Found wrong index, should find 1 but found %s' % it_list[0])
        self.assertEqual(it_list[1],3, 'Found wrong index, should find 1 but found %s' % it_list[1])

    def test_find_nothing(self):
        pred = lambda x: x==12

        it = self.traj.f_find_idx('x',pred)
        it_list = [i for i in it]

        self.assertEqual(len(it_list),0, 'Should find 0 items but found %d' % len(it_list) )


    def explore(self,traj):
        explore_dict = {'x':[1,2,3,4],
                        'y':[0.0,42.0,44.0,44.0],
                        'z':['peter','meter','treter', 'berserker'],
                        'ar': [np.array([1,2,3]),np.array([4,5,6]),np.array([1,2,3]),np.array([4,5,6])]
                        }

        traj.f_explore(explore_dict)

class TrajectoryMergeTest(unittest.TestCase):

    def setUp(self):
        name = 'Moop'

        self.traj = Trajectory(name,[ImAParameterInDisguise])

        comment = 'This is a comment'
        self.traj.v_comment=comment

        self.assertTrue(comment == self.traj.v_comment)

        self.traj.f_add_parameter('IntParam',3)
        sparsemat = spsp.csr_matrix((1000,1000))
        sparsemat[1,2] = 17.777

        #self.traj.f_add_parameter('SparseParam', sparsemat, param_type=PickleParameter)

        self.traj.f_add_parameter('FloatParam')

        self.traj.f_add_derived_parameter(Parameter('FortyTwo', 42))
        self.traj.f_add_parameter('Trials',0)

        self.traj.f_add_result(Result,'Im.A.Simple.Result',44444)

        self.traj.FloatParam=4.0
        self.traj.v_storage_service = LazyStorageService()


        self.traj.f_explore({'FloatParam':[1.0,1.1,1.2,1.3],'Trials':[0,1,2,3]})


        self.assertTrue(len(self.traj) == 4)


        name2 = 'aaaaah'
        self.traj2 = Trajectory(name2,[ImAParameterInDisguise])

        comment = 'This is a comment'
        self.traj2.v_comment=comment

        self.assertTrue(comment == self.traj2.v_comment)

        self.traj2.f_add_parameter('IntParam',3)
        sparsemat = spsp.csr_matrix((1000,1000))
        sparsemat[1,2] = 17.777

        #self.traj2.f_add_parameter('SparseParam', sparsemat, param_type=PickleParameter)
        self.traj2.f_add_parameter('Trials',0)

        self.traj2.f_add_parameter('FloatParam')

        self.traj2.f_add_derived_parameter(Parameter('FortyTwo', 42))

        self.traj2.f_add_result(Result,'Im.A.Simple.Result',44444)

        self.traj2.FloatParam=4.0

        self.traj2.f_explore({'FloatParam':[42.0,43.0,1.2,1.3],'Trials':[0,1,2,3]})
        self.traj2.v_storage_service = LazyStorageService()

        self.assertTrue(len(self.traj2) == 4)



    def test_merge_parameters_without_remove(self):
        # remove_duplicates = True should be discarded by the trial parameter
        self.traj._merge_parameters(self.traj2, trial_parameter_name='Trials',remove_duplicates=True)

    def test_merge_parameters_with_remove(self):
        self.traj._merge_parameters(self.traj2,remove_duplicates=True)

    def test_merge_without_remove(self):
        self.traj.f_merge(self.traj2, remove_duplicates=True,trial_parameter='Trials')

    def test_merge_with_remove(self):
        self.traj.f_merge(self.traj2, remove_duplicates=True)

class SingleRunTest(unittest.TestCase):


    def setUp(self):

        logging.basicConfig(level = logging.INFO)
        traj = Trajectory('Test')

        traj.v_storage_service = LazyStorageService()

        large_amount = 111

        for irun in range(large_amount):
            name = 'There.Are.Many.Parameters.Like.Me' + str(irun)

            traj.f_add_parameter(name, irun)


        traj.f_add_parameter('TestExplorer', 1)

        traj.v_fast_access=False
        traj.f_explore({traj.TestExplorer.v_full_name:[1,2,3,4,5]})
        traj.v_fast_access=True

        self.traj = traj
        self.n = 1
        self.single_run = self.traj._make_single_run(self.n)
        self.assertTrue(len(self.single_run)==1)



    def test_if_single_run_can_be_pickled(self):

        self.single_run._storageservice=stsv.QueueStorageServiceSender()
        dump = pickle.dumps(self.single_run)

        single_run_rec = pickle.loads(dump)

        #print single_run.f_get('Test').val

        elements_dict = self.single_run.f_to_dict()
        for key in elements_dict:
            val = self.single_run.f_get(key,fast_access=True)
            val_rec = single_run_rec.f_get(key).f_get()
            self.assertTrue(np.all(val==val_rec))



    def test_adding_derived_parameter_and_result(self):
        value = 44.444
        self.single_run.f_add_derived_parameter('Im.A.Nice.Guy.Yo', value)
        self.assertTrue(self.single_run.Nice.Yo == value)

        self.single_run.f_add_result('Puberty.Hacks', val=value)
        resval= self.single_run.f_get('Hacks').f_get('val')
        self.assertTrue(resval == value, '%s != %s' % ( str(resval),str(value)))


    def test_standard_change_param_change(self):
        self.single_run.v_standard_parameter=ImAParameterInDisguise

        self.single_run.f_add_derived_parameter('I.should_be_not.normal')

        self.assertIsInstance(self.single_run.f_get('normal'), ImAParameterInDisguise)

        self.single_run.v_standard_result=ImAResultInDisguise

        self.single_run.f_add_result('Peter.Parker')

        self.assertIsInstance(self.single_run.Parker, ImAResultInDisguise)

class SingleRunQueueTest(unittest.TestCase):


    def setUp(self):

        logging.basicConfig(level = logging.INFO)
        traj = Trajectory('Test')

        traj.v_storage_service=LazyStorageService()

        large_amount = 11

        for irun in range(large_amount):
            name = 'There.Are.Many.Parameters.Like.Me' + str(irun)

            traj.f_add_parameter(name, irun)


        traj.f_add_parameter('TestExplorer', 1)

        traj.f_explore({traj.f_get('TestExplorer').v_full_name:[1,2,3,4,5]})

        self.traj = traj
        self.n = 1
        self.single_run = self.traj._make_single_run(self.n)
        self.assertTrue(len(self.single_run)==1)


    def test_queue(self):

        manager = multip.Manager()
        queue = manager.Queue()

        to_put = ('msg',[self.single_run],{})

        queue.put(to_put)

        pass


if __name__ == '__main__':
    unittest.main()