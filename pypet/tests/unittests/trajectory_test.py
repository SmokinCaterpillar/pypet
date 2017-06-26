import pypet.utils.mpwrappers

__author__ = 'Robert Meyer'


import numpy as np
import warnings

import sys
import unittest

from pypet.parameter import Parameter, PickleParameter, Result
from pypet.trajectory import Trajectory
from pypet.naturalnaming import NaturalNamingInterface, ParameterGroup, NNGroupNode
from pypet.storageservice import LazyStorageService
import pickle
import logging
import scipy.sparse as spsp
import pypet.pypetexceptions as pex
from pypet.utils.mpwrappers import QueueStorageServiceSender
import multiprocessing as multip
import pypet.utils.comparisons as comp
from pypet import pypetconstants, BaseResult, Environment
from pypet.tests.testutils.data import TrajectoryComparator
from pypet.tests.testutils.ioutils import parse_args, run_suite, get_log_config, make_temp_dir
from pypet.utils.comparisons import nested_equal

import copy as cp

import pypet.storageservice as stsv

class ImAParameterInDisguise(Parameter):
    pass

class ImAResultInDisguise(Result):
    pass

class TrajectoryTest(unittest.TestCase):

    tags = 'unittest', 'trajectory'

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

        self.traj.par.FloatParam=4.0

        self.traj.par.expexp = Parameter('', 42, 'another param to explore')

        self.explore_dict = {'FloatParam':[1.0, 1.1, 1.2, 1.3]}

        self.traj.f_explore(self.explore_dict)

        self.explore_dict = {'expexp': [42, 42, 42, 43]}

        self.traj.f_explore(self.explore_dict)

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

    # def test_very_lazy_adding(self):
    #     self.traj.v_very_lazy_adding = True
    #     self.traj.Iam.very.very.new = 4
    #     self.traj.Iam.new = 5
    #     self.traj.v_very_lazy_adding = False
    #     self.assertEqual(self.traj.new, 5)
    #     self.assertEqual(self.traj.very.new, 4)

    def test_no_clobber(self):
        x = self.traj.f_add_parameter('test.test2', 42, comment='Here to stay')
        with self.assertRaises(AttributeError):
            self.traj.f_add_parameter('test.test2', 43, comment='Here to stay')

        with self.assertRaises(AttributeError):
            self.traj.f_add_parameter_group('test')
        self.traj.v_no_clobber = True
        y = self.traj.f_add_parameter('test.test2', 43, comment='Here to stay')
        z = self.traj.f_add_parameter_group('test')
        self.assertEqual(y.data, x.data)
        self.assertTrue(z is self.traj.par.test)
        self.traj.v_no_clobber = False

    def test_kids(self):
        self.traj.f_add_parameter('test.test2', 42, comment='Here to stay')
        data = self.traj.kids.parameters.kids.test.kids.test2.data
        self.assertEqual(data, 42)
        with self.assertRaises(AttributeError):
            self.traj.kids.parameters.kids.test.kids.test5
        self.assertEqual(set(self.traj._children.keys()),
                         set(dir(self.traj._kids)))

    def test_re_raise_old_wildcard_error(self):
        self.traj.v_idx = 0
        with self.assertRaises(AttributeError):
            try:
                self.traj.par.crun.test
            except AttributeError as exc:
                self.assertIn(self.traj.v_crun, str(exc))
                raise
        self.traj.f_add_result('hhh.crun.ewrrew', 42)
        with self.assertRaises(AttributeError):
            try:
                self.traj.par.crun.test
            except AttributeError as exc:
                self.assertIn(self.traj.v_crun, str(exc))
                raise
        self.traj.v_idx = -1
        with self.assertRaises(AttributeError):
            try:
                self.traj.par.crun.test
            except AttributeError as exc:
                self.assertIn('ALL', str(exc))
                raise
        self.traj.f_add_result('hhh.crun.ewrrew', 42)
        with self.assertRaises(AttributeError):
            try:
                self.traj.par.crun.test
            except AttributeError as exc:
                self.assertIn('ALL', str(exc))
                raise

    def test_lazy_setitem(self):
        self.traj['r_1'] = NNGroupNode('')
        with self.assertRaises(AttributeError):
            self.traj['r_1.new'] = Result('', 5)
        self.traj['r_1.new'] = Result('new', 5)
        with self.assertRaises(AttributeError):
            self.traj['mistake.mistake']
        self.assertEqual(self.traj.run_00000001.new, 5)

    def test_no_prefixes(self):
        self.assertEqual(self.traj.vars.name, self.traj.v_name)
        res = self.traj.func.add_result('testgroup.test', k=42)
        self.assertEqual(res.v_comment, res.vars.comment)
        with self.assertRaises(AttributeError):
            res.vars.k
        with self.assertRaises(AttributeError):
            res.func.k
        tg = self.traj.testgroup
        tg.func.add_result('test2', 43)
        self.assertEqual(tg.v_location, tg.vars.location)
        self.assertEqual(self.traj.v_crun, self.traj.vars.crun)
        self.assertEqual(self.traj.v_crun_, self.traj.vars.crun_)
        self.assertEqual(self.traj.vars.idx, self.traj.v_idx)
        self.traj.func.add_leaf('ggg.idx', 12345)
        self.assertEqual(self.traj.vars.idx, self.traj.v_idx)
        self.traj.vars.idx = 0
        self.assertEqual(self.traj.vars.idx, self.traj.v_idx)
        self.assertEqual(0, self.traj.v_idx)

    def test_prefixes_dir(self):
        f_dir = dir(self.traj.func)
        v_dir = dir(self.traj.vars)
        t_dir = dir(self.traj)
        for f in f_dir:
            self.assertIn('f_' + f, t_dir)
        for v in v_dir:
            self.assertIn('v_' + v, t_dir)
        for g in t_dir:
            if g.startswith('f_'):
                self.assertIn(g[2:], f_dir)
            elif g.startswith('v_'):
                self.assertIn(g[2:], v_dir)

    def test_data_dir(self):
        memberset = set(self.traj.f_dir_data())
        memberset2 = set(self.traj.func.get_children().keys())
        self.assertEqual(memberset, memberset2)


    def test_deletion(self):
        x = []
        self.traj.f_add_result('fff', x)
        self.assertEqual(sys.getrefcount(x),3)
        self.traj.f_get('fff').f_empty()
        self.assertEqual(sys.getrefcount(x),2)
        self.traj.f_add_link('jj', self.traj.results)
        self.assertEqual(len(self.traj._linked_by), 1)
        self.traj.f_remove_child('results', recursive=True)
        self.assertEqual(len(self.traj._linked_by), 0)
        self.assertEqual(len(self.traj._results), 0)

        p = self.traj.parameters

        self.assertEqual(p.vars.name, p.v_name)
        self.assertEqual(p.func.get_children, p.f_get_children)

        self.assertEqual(sys.getrefcount(p),9)
        self.traj.f_remove_child('parameters', recursive=True)
        self.assertEqual(sys.getrefcount(p),2)

        self.assertEqual(len(self.traj._parameters), 0)

        self.traj.f_remove_child('config', recursive=True)

        self.assertEqual(len(self.traj._config), 0)

        self.traj.f_adpar('ii.promisess',1)
        self.traj.f_remove_child('derived_parameters', recursive=True)

        self.assertEqual(len(self.traj._derived_parameters), 0)

        self.assertEqual(len(self.traj._all_groups), 0)

        self.assertEqual(len(self.traj._new_nodes), 0)
        self.assertEqual(len(self.traj._new_links), 0)

        self.assertEqual(len(self.traj._nn_interface._flat_leaf_storage_dict), 0)
        self.assertEqual(len(self.traj._nn_interface._nodes_and_leaves), 0)
        self.assertEqual(len(self.traj._nn_interface._nodes_and_leaves_runs_sorted), 0)
        self.assertEqual(len(self.traj._nn_interface._links_count), 0)

        x = []
        z = self.traj.f_add_result('fff', x)
        self.assertEqual(sys.getrefcount(x),3)

        self.assertEqual(sys.getrefcount(z),8)

        self.traj.f_remove_item('fff')

        self.assertEqual(sys.getrefcount(z),2)
        del z
        self.assertEqual(sys.getrefcount(x),2)




    def test_deletion_during_run(self):
        self.traj._make_single_run()
        self.traj._stored = True
        self.traj.f_add_result('fff', 444)
        self.traj.f_add_leaf('jjj', 16)
        self.traj.f_adpar('jjj.promisess',1)


        self.traj.f_add_link('jj', self.traj.results)
        self.assertEqual(len(self.traj._linked_by), 1)

        self.assertEqual(len(self.traj._new_nodes), 8)
        self.assertEqual(len(self.traj._new_links), 1)

        self.assertEqual(len(self.traj._nn_interface._flat_leaf_storage_dict), 13)
        self.assertEqual(len(self.traj._nn_interface._nodes_and_leaves), 26)
        self.assertEqual(len(self.traj._nn_interface._nodes_and_leaves_runs_sorted), 26)
        self.assertEqual(len(self.traj._nn_interface._links_count), 1)

        self.traj.f_remove_child('jjj')
        self.assertTrue('jjj' not in self.traj._children)
        self.assertTrue('jjj' not in self.traj._leaves)


        p = self.traj.jjj

        self.assertEqual(sys.getrefcount(p),9)
        self.traj.dpar.crun.f_remove_child('jjj', recursive=True)
        self.assertEqual(sys.getrefcount(p),2)

        for child in list(self.traj._groups.keys()):
            self.traj.f_remove_child(child, recursive=True)
        self.assertEqual(len(self.traj._children), 0)
        self.assertEqual(len(self.traj._links), 0)
        self.assertEqual(len(self.traj._groups), 0)
        self.assertEqual(len(self.traj._leaves), 0)


        self.assertEqual(len(self.traj._new_nodes), 0)
        self.assertEqual(len(self.traj._new_links), 0)

        self.assertEqual(len(self.traj._nn_interface._flat_leaf_storage_dict), 0)
        self.assertEqual(len(self.traj._nn_interface._nodes_and_leaves), 0)
        self.assertEqual(len(self.traj._nn_interface._nodes_and_leaves_runs_sorted), 0)
        self.assertEqual(len(self.traj._nn_interface._links_count), 0)



        self.traj.f_add_leaf('hh', 16)

        self.traj.f_add_link('jj.dd', 'hh')

        self.assertEqual(len(self.traj._new_nodes), 2)
        self.assertEqual(len(self.traj._new_links), 1)

        self.assertEqual(len(self.traj._linked_by), 1)

        z = self.traj.f_get('hh')
        self.assertEqual(sys.getrefcount(z),12)
        self.traj.jj.f_remove_link('dd')
        self.assertEqual(sys.getrefcount(z),9)

        self.assertEqual(len(self.traj._new_links), 0)
        self.assertEqual(len(self.traj._linked_by), 0)
        self.traj.f_remove_child('jj')
        self.traj.f_remove_child('hh')

        self.assertEqual(sys.getrefcount(z),2)


        self.assertEqual(len(self.traj._nn_interface._flat_leaf_storage_dict), 0)
        self.assertEqual(len(self.traj._nn_interface._nodes_and_leaves), 0)
        self.assertEqual(len(self.traj._nn_interface._nodes_and_leaves_runs_sorted), 0)
        self.assertEqual(len(self.traj._nn_interface._links_count), 0)

        self.assertEqual(len(self.traj._children), 0)
        self.assertEqual(len(self.traj._links), 0)
        self.assertEqual(len(self.traj._groups), 0)
        self.assertEqual(len(self.traj._leaves), 0)

    def test_change_properties_with_environment(self):
        filename = make_temp_dir('dummy.h5')
        with Environment(trajectory=self.traj,
                        log_config=get_log_config(), filename=filename,
                        v_auto_load=False, with_links=False) as env:

            self.assertFalse(self.traj.v_auto_load)
            self.assertFalse(self.traj.v_with_links)


    def test_truncation_of_string_statements_of_group_nodes(self):

        self.traj.f_add_group('suiting_subgroups')

        for irun in range(5):
            self.traj.suiting_subgroups.f_add_group('test%d' % irun)

        self.assertFalse(str(self.traj.suiting_subgroups).endswith('...'))

        self.traj.f_add_group('non_suiting_subgroups')
        for irun in range(6):
            self.traj.non_suiting_subgroups.f_add_group('test%d' % irun)

        self.assertTrue(str(self.traj.non_suiting_subgroups).endswith('...'))


    def test_shrink(self):

        self.assertTrue(len(self.traj)>1)

        self.traj.f_shrink()

        self.assertTrue(len(self.traj)==1)

        self.assertTrue(len(self.traj.f_get_explored_parameters())==0)

    def test_get_all(self):
        all_nodes = self.traj.f_get_all('peter')

        self.assertTrue(len(all_nodes)==2)

        all_nodes = self.traj.f_get_all('peter.yve')

        self.assertTrue(len(all_nodes)==1)

        all_nodes = self.traj.f_get_all('paul.yve')

        self.assertTrue(len(all_nodes)==0)

        self.traj.f_add_parameter('paul.paul')

        all_nodes = self.traj.peter.f_get_all('paul')

        self.assertTrue(len(all_nodes)==1)

        self.traj.f_add_result('results.runs.run_00000000.x.y',10)

        self.traj.f_add_result('results.runs.run_00000001.x.y',10)

        self.traj.f_add_derived_parameter('hfhfhf.x.y')

        self.traj.f_add_result('x.y.y')

        self.traj.v_crun=1

        all_nodes=self.traj.f_get_all('x.y')

        self.assertTrue(len(all_nodes)==5, '%s != 5' % str(len(all_nodes)))

    # def test_backwards_search(self):
    #
    #     x=self.traj.peter.f_get('paul.peter', backwards_search=False)
    #
    #     y=self.traj.f_get('peter.peter', backwards_search=True)
    #
    #     self.assertTrue(x is y)
    # #
    # # def test_value_error_on_search_strategy_assignment(self):
    # #     with self.assertRaises(ValueError):
    # #         self.traj.v_search_strategy = 'ewnforenfre'

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


        # #We need to unlock the parameter because we have accessed it above
        # self.traj.f_get('yve').f_unlock()
        # explore_dict = {'yve':[4,5,65,66]}

        # # We can add to existing explored parameters if we match the length
        # self.traj.f_expand(explore_dict)

        explore_dict_directly = self.traj.f_get_explored_parameters(copy=False)

        for key in self.explore_dict:
            self.assertTrue(comp.nested_equal(self.traj.f_get(key),
                                              explore_dict_directly[self.traj.f_get(key).v_full_name]))

        explore_dict_directly = self.traj.f_get_explored_parameters(copy=True)

        for key in self.explore_dict:
            self.assertTrue(comp.nested_equal(self.traj.f_get(key),
                                              explore_dict_directly[self.traj.f_get(key).v_full_name]))

        with self.assertRaises(ValueError):
            explore_dict_directly = self.traj.f_get_explored_parameters(copy=False, fast_access=True)

        explore_dict_directly = self.traj.f_get_explored_parameters(copy=True, fast_access=True)

        for key in self.explore_dict:
            self.assertTrue(comp.nested_equal(self.traj.f_get(key,fast_access=True),
                                              explore_dict_directly[self.traj.f_get(key).v_full_name]))

    def test_not_increase_exploration(self):

        self.assertTrue(len(self.traj._explored_parameters)==2)

        with self.assertRaises(TypeError):
            self.traj.f_explore(self.explore_dict)

    def test_f_get(self):
        self.traj.v_fast_access=True
        self.traj.f_get('FloatParam', fast_access=True) == self.traj.FloatParam

        self.assertTrue(self.traj.f_get('FloatParam').v_branch == 'parameters')

        self.traj.v_fast_access=False

        self.assertTrue(self.traj.f_get('FloatParam').f_get() == 4.0 , '%d != 4.0' %self.traj.f_get('FloatParam').f_get())

        self.assertTrue(self.traj.FortyTwo.f_get() == 42)


    def test_get_item(self):

        self.assertEqual(self.traj.markus.yve, self.traj['markus.yve'])
        self.assertEqual(self.traj.markus.yve, self.traj['markus','yve'])

    # def test_round_brackets(self):
    #     x='markus'
    #
    #     y='yve'
    #
    #     self.assertEqual(self.traj(x)(y), self.traj.markus.f_get('yve'))

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
                    for child in item._children.values():
                        if not (child.v_name.startswith(pypetconstants.RUN_NAME) and
                                        child.v_name != pypetconstants.RUN_NAME_DUMMY):
                            bfs_queue.append(child)
                else:
                    for child in item._children.values():
                        bfs_queue.append(child)

        return depth_dict


    def test_iter_bfs(self):

        depth_dict = self.get_depth_dict(self.traj)

        depth_dict[0] =[]

        prev_depth = 0

        for node in self.traj.f_iter_nodes(recursive=True):
            if prev_depth != node.v_depth:
                self.assertEqual(len(depth_dict[prev_depth]),0)
                prev_depth = node.v_depth

            depth_dict[node.v_depth].remove(node)


        depth_dict = self.get_depth_dict(self.traj)

        depth_dict[0] =[]

        prev_depth = 0

        self.traj.v_iter_recursive = True

        for node in self.traj:
            if prev_depth != node.v_depth:
                self.assertEqual(len(depth_dict[prev_depth]),0)
                prev_depth = node.v_depth

            depth_dict[node.v_depth].remove(node)

    def test_iter_bfs_as_run(self):
        as_run = 1

        self.traj.f_add_result('results.run_ALL.resulttest', 42)
        self.traj.f_add_result('results.run_00000000.resulttest', 42)
        self.traj.f_add_result('results.run_00000001.resulttest', 43)

        depth_dict = self.get_depth_dict(self.traj, self.traj.f_idx_to_run(as_run))

        depth_dict[0] =[]

        prev_depth = 0

        for node in self.traj.f_iter_nodes(recursive=True, predicate=('run_00000001',-1)):
            self.assertTrue('run_00000000' not in node.v_full_name)
            if prev_depth != node.v_depth:
                self.assertEqual(len(depth_dict[prev_depth]),0)
                prev_depth = node.v_depth

            depth_dict[node.v_depth].remove(node)

    def test_find_in_all_runs_with_groups(self):

        self.traj.f_add_result('results.runs.run_set_00001.run_00000000.sub.resulttest', 42)
        self.traj.f_add_result('results.runs.run_set_00001.run_00000001.sub.resulttest', 43)
        self.traj.f_add_result('results.runs.run_set_00003.run_00000002.sub.resulttest', 44)

        self.traj.f_add_result('results.runs.run_set_00004.run_00000002.sub.resulttest2', 42)
        self.traj.f_add_result('results.runs.run_00000003.sub.resulttest2', 43)



        self.traj.f_add_derived_parameter('derived_parameters.runs.run_00000002.testing', 44)

        res_dict = self.traj.f_get_from_runs('kkkkkkdjfoiuref')

        self.assertTrue(len(res_dict)==0)

        res_dict = self.traj.f_get_from_runs('resulttest', fast_access=True)

        self.assertTrue(len(res_dict)==3)
        self.assertTrue(res_dict['run_00000001']==43)
        self.assertTrue('run_00000003' not in res_dict)

        res_dict = self.traj.f_get_from_runs(name='sub.resulttest2', use_indices=True)

        self.assertTrue(len(res_dict)==2)
        self.assertTrue(res_dict[3] is self.traj.f_get('run_00000003.resulttest2'))
        self.assertTrue(1 not in res_dict)

        res_dict = self.traj.f_get_from_runs(name='testing', where='derived_parameters')

        self.assertTrue(len(res_dict)==1)

        self.traj.f_add_result('results.runs.run_ALL.sub.resulttest2', 44)

        res_dict = self.traj.f_get_from_runs(name='sub.resulttest2', use_indices=True)

        self.assertTrue(len(res_dict)==4)
        self.assertTrue(res_dict[3] is self.traj.f_get('run_00000003.resulttest2'))
        self.assertTrue(res_dict[1] is self.traj.f_get('run_ALL.resulttest2'))
        self.assertTrue(res_dict[0] is self.traj.f_get('run_ALL.resulttest2'))
        self.assertTrue(1 in res_dict)


        res_dict = self.traj.f_get_from_runs(name='sub.resulttest2', include_default_run=False,
                                             use_indices=True)

        self.assertTrue(len(res_dict)==2)
        self.assertTrue(res_dict[3] is self.traj.f_get('run_00000003.resulttest2'))
        self.assertTrue(1 not in res_dict)

        res_dict =  self.traj.f_get_from_runs('test')
        self.assertTrue(len(res_dict) == 0)

    def test_find_in_all_runs(self):


        self.traj.f_add_result('results.runs.run_00000000.sub.resulttest', 42)
        self.traj.f_add_result('results.runs.run_00000001.sub.resulttest', 43)
        self.traj.f_add_result('results.runs.run_00000002.sub.resulttest', 44)

        self.traj.f_add_result('results.runs.run_00000002.sub.resulttest2', 42)
        self.traj.f_add_result('results.runs.run_00000003.sub.resulttest2', 43)



        self.traj.f_add_derived_parameter('derived_parameters.runs.run_00000002.testing', 44)

        res_dict = self.traj.f_get_from_runs('kkkkkkdjfoiuref')

        self.assertTrue(len(res_dict)==0)

        res_dict = self.traj.f_get_from_runs('resulttest', fast_access=True)

        self.assertTrue(len(res_dict)==3)
        self.assertTrue(res_dict['run_00000001']==43)
        self.assertTrue('run_00000003' not in res_dict)

        res_dict = self.traj.f_get_from_runs(name='sub.resulttest2', use_indices=True)

        self.assertTrue(len(res_dict)==2)
        self.assertTrue(res_dict[3] is self.traj.f_get('run_00000003.resulttest2'))
        self.assertTrue(1 not in res_dict)

        res_dict = self.traj.f_get_from_runs(name='testing', where='derived_parameters')

        self.assertTrue(len(res_dict)==1)

        self.traj.f_add_result('results.runs.run_ALL.sub.resulttest2', 44)

        res_dict = self.traj.f_get_from_runs(name='sub.resulttest2', use_indices=True)

        self.assertTrue(len(res_dict)==4)
        self.assertTrue(res_dict[3] is self.traj.f_get('run_00000003.resulttest2'))
        self.assertTrue(res_dict[1] is self.traj.f_get('run_ALL.resulttest2'))
        self.assertTrue(res_dict[0] is self.traj.f_get('run_ALL.resulttest2'))
        self.assertTrue(1 in res_dict)


        res_dict = self.traj.f_get_from_runs(name='sub.resulttest2', include_default_run=False,
                                             use_indices=True)

        self.assertTrue(len(res_dict)==2)
        self.assertTrue(res_dict[3] is self.traj.f_get('run_00000003.resulttest2'))
        self.assertTrue(1 not in res_dict)

        res_dict =  self.traj.f_get_from_runs('test')
        self.assertTrue(len(res_dict) == 0)

    def test_illegal_namings(self):
        self.traj=Trajectory('resulttest2')

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            self.traj.f_add_parameter('f_get')
            self.assertEqual(len(w), 1)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            self.traj.f_add_parameter('get')
            self.assertEqual(len(w), 0)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            self.traj.f_add_parameter('not.for.continue')
            self.assertEqual(len(w), 3)

        with self.assertRaises(ValueError):
            self.traj.f_add_result('test..hh')

        with self.assertRaises(ValueError):
            self.traj.f_add_result('test.::!.h')

        with self.assertRaises(ValueError):
            self.traj.f_add_result('test.$.k.$dsa')

        with self.assertRaises(ValueError):
            self.traj.f_add_parameter('e'*129)

        with self.assertRaises(ValueError):
            self.traj.f_add_parameter('_crun',22)

    def test_f_getting_of_children(self):
        my_groups = self.traj.par.f_get_groups()
        self.assertTrue(my_groups == self.traj.par._groups)
        self.assertTrue(my_groups is not self.traj.par._groups)

        my_groups = self.traj.par.f_get_groups(copy=False)
        self.assertTrue(my_groups == self.traj.par._groups)
        self.assertTrue(my_groups is self.traj.par._groups)

        my_leaves = self.traj.par.f_get_leaves()
        self.assertTrue(my_leaves == self.traj.par._leaves)
        self.assertTrue(my_leaves is not self.traj.par._leaves)

        my_leaves = self.traj.par.f_get_leaves(copy=False)
        self.assertTrue(my_leaves == self.traj.par._leaves)
        self.assertTrue(my_leaves is self.traj.par._leaves)

        self.traj.par.k = self.traj.par
        my_links = self.traj.par.f_get_links()
        self.assertTrue(my_links == self.traj.par._links)
        self.assertTrue(my_links is not self.traj.par._links)

        my_links = self.traj.par.f_get_links(copy=False)
        self.assertTrue(my_links == self.traj.par._links)
        self.assertTrue(my_links is self.traj.par._links)

    def test_max_depth(self):
        self.traj.f_add_parameter('halo.this.is.a.depth.testrr')

        contains = self.traj.par.f_contains(self.traj['is'], shortcuts=True, max_depth=3)

        self.assertTrue(contains)

        contains = self.traj.par.f_contains(self.traj['is'], shortcuts=True, max_depth=2)

        self.assertFalse(contains)

        self.traj.par.mylink = self.traj.this

        contains = self.traj.par.f_contains('is', shortcuts=True, max_depth=2)

        self.assertTrue(contains)

        contains = self.traj.par.f_contains('halo.this', max_depth=1)

        self.assertFalse(contains)

        contains = self.traj.f_contains('a.depth.testrr', max_depth=3)

        self.assertFalse(contains)

        contains = self.traj.par.f_contains('halo.this.is.a.depth.testrr', shortcuts=False)

        self.assertTrue(contains)

        contains = self.traj.par.f_contains('halo.this.depth.testrr', shortcuts=True)

        self.assertTrue(contains)

        contains = self.traj.par.f_contains('testrr', shortcuts=True)

        self.assertTrue(contains)

        contains = 'testrr' in self.traj

        self.assertTrue(contains)

        contains = self.traj.par.f_contains('testrr', max_depth=5)

        self.assertFalse(contains)

        self.traj.v_max_depth = 5

        contains = 'testrr' in self.traj

        self.assertFalse(contains)

        l = [x for x in self.traj.f_iter_nodes(max_depth=1)]
        self.assertTrue(len(l) == 4)

    def test_root_getting(self):

        traj = Trajectory()

        traj.f_add_config_group('ff')

        root = traj.ff.v_root

        self.assertTrue(root is traj)

    def test_not_adding_pars_during_single_run(self):
        traj = Trajectory()

        traj._is_run = True

        with self.assertRaises(TypeError):
            traj.f_add_parameter('dd')

        with self.assertRaises(TypeError):
            traj.f_add_parameter_group('dd')

        with self.assertRaises(TypeError):
            traj.f_add_config('dd')

        with self.assertRaises(TypeError):
            traj.f_add_config_group('dd')

    def test_attribute_error_raises_when_leaf_and_group_with_same_name_are_added(self):

        self.traj = Trajectory()

        self.traj.f_add_parameter('test.param1')

        with self.assertRaises(AttributeError):
            self.traj.f_add_parameter('test.param1.param2')

        with self.assertRaises(AttributeError):
            self.traj.f_add_parameter('test')


    def test_remove(self):

        with self.assertRaises(TypeError):
            self.traj.peter.f_remove_child('markus')

        self.traj.f_remove_item(self.traj.f_get('peter.markus.yve'))

        with self.assertRaises(AttributeError):
            self.traj.peter.markus.yve

        self.assertFalse('peter.markus.yve' in self.traj)

        #self.assertTrue(len(self.traj)==1)

        self.traj.f_remove_item('FortyTwo')

        self.traj.f_remove_item('SparseParam')
        self.traj.f_remove_item('IntParam')

        self.assertTrue('IntParam' not in self.traj)

        with self.assertRaises(ValueError):
            self.traj.f_remove(recursive=False)

        self.traj.Im.f_remove()

        self.assertTrue('Im' not in self.traj)

        self.traj.f_remove()

        self.assertTrue(self.traj.f_is_empty())

        #self.assertTrue(len(self.traj)==1)

    def test_changing(self):

        self.traj.f_preset_config('testconf', 1)
        self.traj.f_preset_parameter('testparam', 1)
        self.traj.f_preset_parameter('I_do_not_exist', 2)

        self.traj.f_add_parameter('testparam', 0)
        self.traj.f_add_config('testconf', 0)

        self.traj.f_add_config('testconf2', 0)

        with self.assertRaises(ValueError):
            self.traj.f_preset_config('testconf2', 33)

        self.traj.v_fast_access=True

        self.assertTrue(self.traj.testparam == 1)
        self.assertTrue(self.traj.testconf == 1)

        ### should raise an error because 'I_do_not_exist', does not exist:
        with self.assertRaises(pex.PresettingError):
            self.traj._prepare_experiment()

    def test_f_get_run_information(self):
        traj = Trajectory()

        traj.f_add_parameter('test', 42)

        traj.f_explore({'test':[1,2,3,4]})

        self.assertFalse(traj.f_is_completed())

        runinfo = traj.f_get_run_information()

        self.assertTrue(len(runinfo) == 4)
        self.assertTrue(runinfo == traj._run_information)
        self.assertTrue(runinfo is not traj._run_information)

        runinfo = traj.f_get_run_information(copy=False)

        self.assertTrue(len(runinfo) == 4)
        self.assertTrue(runinfo == traj._run_information)
        self.assertTrue(runinfo is traj._run_information)

    def test_mutual_exclusive_kwargs(self):
        traj = Trajectory()
        with self.assertRaises(ValueError):
            traj.f_store(only_init=True, recursive=False)

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

        with self.assertRaises(TypeError):
            self.traj.f_add_to_dynamic_imports(44)
        self.traj.f_add_parameter(ImAParameterInDisguise,'Rolf', 1.8)

    def test_standard_change_param_change(self):
        self.traj.v_standard_parameter=ImAParameterInDisguise

        self.traj.f_add_parameter('I.should_be_not.normal')

        self.assertIsInstance(self.traj.f_get('normal'), ImAParameterInDisguise,'Param is %s insted of ParamInDisguise.' %str(type(self.traj.normal)))

        self.traj.v_standard_result=ImAResultInDisguise

        self.traj.f_add_result('Peter.Parker')

        self.assertIsInstance(self.traj.Parker, ImAResultInDisguise)

    def test_remove_of_all_type(self):
        traj = Trajectory()

        traj.par.x = Parameter('', 42, 'param')

        traj.dpar.y = Parameter('', 43, 'dpar')

        traj.conf.z = Parameter('', 44, 'conf')

        traj.res.k = Result('k', 44, 'jj')

        traj.l =Result('l', 111, 'kkkk')

        self.assertTrue(len(traj._parameters) == 1)
        self.assertTrue(len(traj._derived_parameters) == 1)
        self.assertTrue(len(traj._results) == 1)
        self.assertTrue(len(traj._config) == 1)
        self.assertTrue(len(traj._other_leaves) == 1)

        traj.zzz = traj.f_get('x')

        self.assertTrue(len(traj._linked_by) == 1)
        self.assertTrue(traj.zzz == traj.x)
        self.assertTrue(traj.x == 42)

        traj.par.f_remove_child('x')
        self.assertTrue('zzz' not in traj)

        self.assertTrue('x' not in traj)

        self.assertTrue(traj.y == 43)
        traj.f_remove_child('derived_parameters', recursive=True)
        self.assertTrue('y' not in traj)

        self.assertEqual(traj.k[0], 44)
        traj.f_remove_child('results', recursive = True)
        self.assertTrue('k' not in traj)

        self.assertTrue(traj.z == 44)
        traj.f_remove_child('config', recursive = True)
        self.assertTrue('z' not in traj)

        self.assertTrue(traj.l[0] == 111)
        traj.f_remove_child('l')
        self.assertTrue('l' not in traj)


        self.assertTrue(len(traj._parameters) == 0)
        self.assertTrue(len(traj._derived_parameters) == 0)
        self.assertTrue(len(traj._results) == 0)
        self.assertTrue(len(traj._config) == 0)
        self.assertTrue(len(traj._other_leaves) == 0)

        self.assertTrue(len(traj._linked_by) == 0)

    def test_remove_of_explored_stuff_if_saved(self):

        self.traj = Trajectory()

        self.traj.f_add_parameter('test', 42)

        self.traj.f_explore({'test':[1,2,3,4]})

        self.traj._stored=True

        self.traj.parameters.f_remove_child('test')

        len(self.traj) == 4

    def test_remove_of_explored_stuff_if_not_saved(self):

        self.traj = Trajectory()

        self.traj.f_add_parameter('test', 42)

        self.traj.f_explore({'test':[1,2,3,4]})

        self.traj.parameters.f_remove_child('test')

        self.assertTrue(len(self.traj) == 1)

    def test_not_unique_search(self):
        self.traj = Trajectory()

        self.traj.f_add_parameter('ghgghg.test')
        self.traj.f_add_parameter('ghdsfdfdsfdsghg.test')

        with self.assertRaises(pex.NotUniqueNodeError):
            self.traj.test

        self.traj.f_add_parameter('depth0.depth1.depth2.findme', 42)
        self.traj.f_add_parameter('depth0.depth1.findme', 43)

        self.assertTrue(self.traj.findme==43)

        # with self.assertRaises(pex.NotUniqueNodeError):
        #     self.traj.f_get('depth0.findme', backwards_search=True)


    def test_contains_item_identity(self):

        peterpaul = self.traj.f_get('peter.paul')

        self.assertTrue(peterpaul in self.traj)

        peterpaulcopy = cp.deepcopy(peterpaul)

        self.assertFalse(peterpaulcopy in self.traj)

    def test_get_children(self):

        for node in self.traj.f_iter_nodes():
            if not node.v_is_leaf:
                self.assertEqual(id(node.f_get_children(copy=False)), id(node._children))

                self.assertNotEqual(id(node.f_get_children(copy=True)), id(node._children))

                self.assertEqual(sorted(node.f_get_children(copy=True).keys()),
                                 sorted(node._children.keys()))

        l = [x for x in self.traj.f_iter_nodes(recursive=False)]
        self.assertTrue(len(l) == 4)
        self.assertTrue(self.traj.conf in l)

    def test_dir(self):

        self.traj.par.ggg = Parameter('', 444, 'Hey')
        self.assertTrue('(' in str(self.traj.f_get('ggg')))


        dirlist = dir(self.traj)

        self.assertTrue('config' in dirlist)
        self.assertTrue('parameters' in dirlist)

    def test_debug(self):

        self.traj.f_add_link('me', 'parameters')
        self.assertTrue(self.traj.f_links() == 1)
        self.assertTrue(self.traj.me is self.traj.par)
        debug_tree = self.traj.f_debug()
        self.assertTrue(hasattr(debug_tree, 'parameters'))
        self.assertTrue(hasattr(debug_tree, 'results'))
        self.assertTrue(hasattr(debug_tree, 'me'))


    def test_short_names_to_dict_failure(self):

        self.traj.f_add_parameter('lll.ggg' , 44)
        self.traj.par.ggg = Parameter('', 444, 'Hey')

        with self.assertRaises(ValueError):
            self.traj.f_to_dict(short_names=True)

    def test_short_names_and_nested_failure(self):

        with self.assertRaises(ValueError):
            self.traj.f_to_dict(short_names=True, nested=True)

    def test_to_nested_dict(self):
        traj = Trajectory()
        traj.f_add_parameter('my.param', 42)
        traj.f_add_parameter('my.fff', 44)
        traj.f_add_result('runs.$.myresult',55)

        lookout = {
            'parameters': {
                'my': {
                    'param': 42,
                    'fff': 44
                }
            },
            'results': {
                'runs':{
                    'run_ALL':{
                        'myresult': 55
                    }
                }
            }
        }
        result = traj.f_to_dict(nested=True, fast_access=True)
        self.assertTrue(nested_equal(result, lookout),
                        '{} != {}'.format(result, lookout))

    def test_to_nested_dict_intermediate_node(self):
        traj = Trajectory()
        traj.f_add_parameter('my.param', 42)
        traj.f_add_parameter('my.fff', 44)
        traj.f_add_result('runs.$.myresult',55)

        lookout = {
                'runs':{
                    'run_ALL':{
                        'myresult': 55
                    }
                }
            }
        result = traj.res.f_to_dict(nested=True, fast_access=True)
        self.assertTrue(nested_equal(result, lookout),
                        '{} != {}'.format(result, lookout))

    def test_to_nested_dict_intermediate_node2(self):
        traj = Trajectory()
        traj.f_add_parameter('my.param', 42)
        traj.f_add_parameter('my.fff', 44)
        traj.f_add_result('runs.$.myresult',55)

        lookout = {
                    'run_ALL':{
                        'myresult': 55
                    }
            }
        result = traj.res.runs.f_to_dict(nested=True, fast_access=True)
        self.assertTrue(nested_equal(result, lookout),
                        '{} != {}'.format(result, lookout))

    def test_iter_leaves(self):

        count = 0
        for node in self.traj.f_iter_leaves():
            self.assertTrue(node.v_is_leaf)
            count +=1

        all_leaves = len(self.traj._config) + len(self.traj._parameters) +\
            len(self.traj._results) + len(self.traj._derived_parameters) +\
            len(self.traj._other_leaves)
        self.assertTrue(count == all_leaves)

    def test_changing_of_result(self):

        traj = Trajectory()

        traj.res.x = Result('x', 42)

        traj.res.x=44
        self.assertEqual(traj.x, 44)

        traj.res.y = Result('', a=1, b=2)
        with self.assertRaises(AttributeError):
            traj.res.y = 44

    def test_new_grouping(self):

        traj = Trajectory()

        traj.par.x = Parameter('x', 42)

        therange = range(2001)
        traj.f_explore({'x':therange})

        for irun in therange:
            traj.v_idx = irun
            traj.f_add_result('$set.$')
        traj.v_idx = -1

        self.assertTrue('run_set_00001' in traj)
        self.assertTrue('run_set_00004' not in traj)
        self.assertEqual(len(traj.res._children), 3)
        self.assertEqual(len(traj.run_set_00001._children), 1000)
        self.assertTrue('rts_1000' in traj)
        self.assertFalse('rts_4000' in traj)
        self.assertTrue('runtoset_1000' in traj)
        self.assertFalse('runtoset_4000' in traj)


    def test_short_cuts(self):

        self.traj = Trajectory()

        self.traj.f_add_parameter('test', 42)

        self.traj.f_add_config('tefffst', 42)

        self.traj.f_add_derived_parameter('dtest', 42)

        self.traj.f_add_result('safd', 42)

        self.traj.f_explore({'test':[1,2,3,4]})

        self.assertEqual(id(self.traj.par), id(self.traj.parameters))
        #self.assertEqual(id(self.traj.param), id(self.traj.parameters))


        self.assertEqual(id(self.traj.dpar), id(self.traj.derived_parameters))
        #self.assertEqual(id(self.traj.dparam), id(self.traj.derived_parameters))

        self.assertEqual(id(self.traj.conf), id(self.traj.config))

        self.assertEqual(id(self.traj.res), id(self.traj.results))

        self.traj.f_set_crun(3)
        srun = self.traj._make_single_run()

        srun.f_add_result('sdffds',42)

        self.assertEqual(id(srun.results.crun), id(srun.results.f_get(srun.v_crun)))
        # self.assertEqual(id(srun.results.currentrun), id(srun.results.f_get(srun.v_name)))
        # self.assertEqual(id(srun.results.current_run), id(srun.results.f_get(srun.v_name)))


class CustomParam(Parameter):
    pass


class GetStateFlunk(Parameter):
    def __getstate__(self):
        return {'haha': 42}


class TrajectoryCopyTreeTest(TrajectoryComparator):

    tags = 'unittest', 'trajectory', 'tree_copy'

    def test_copy_tree_simple(self):
        traj1 = Trajectory()
        traj1.par['hi'] = Parameter('hi.my.name.is.parameter', 42, 'A parameter')


        traj2 = Trajectory()
        traj2.par['hi'] = Parameter('hi.my.name.is.another', 43, 'Another')


        traj1._copy_from(traj2)

        self.assertTrue('another' in traj1)
        self.assertTrue(traj1.another, 43)
        self.assertTrue(traj1.f_get('another') is not traj2.f_get('another'))

    def test_overwrite(self):

        traj1 = Trajectory()
        traj1.par['hi'] = Parameter('hi.my.name.is.parameter', 42, 'A parameter')
        traj1.f_apar(GetStateFlunk, 'hi.my.name.is.parameter2', 42, 'hui')

        traj1.my.v_annotations['test'] = 2

        traj2 = Trajectory()
        traj2.par['hi'] = Parameter('hi.my.name.is.parameter', 43, 'Another')
        traj2.f_apar(GetStateFlunk, 'hi.my.name.is.parameter2', 77, 'buh')

        traj1._copy_from(traj2, overwrite=True)

        self.assertEqual(traj1.parameter, 43)
        self.assertEqual(traj1.f_get('parameter').v_comment, 'Another')

        self.assertEqual(traj1.f_get('parameter2').haha, 42)

        self.assertTrue(traj1.my.v_annotations.f_is_empty())

    def test_copy_custom_parameter(self):
        traj1 = Trajectory()
        traj1.par['hi'] = Parameter('hi.my.name.is.parameter', 42, 'A parameter')

        traj2 = Trajectory()
        traj2.f_apar(CustomParam, 'hi.my.name.is.another', 43, 'Another')
        traj1._copy_from(traj2)

        self.assertTrue('another' in traj1)
        self.assertTrue(traj1.another, 43)
        self.assertTrue(traj1.f_get('another') is not traj2.f_get('another'))

        self.assertTrue(traj1.f_get('another').__class__ is CustomParam)

    def test_not_copy_leaves(self):
        traj1 = Trajectory()
        traj1.par['hi'] = Parameter('hi.my.name.is.parameter', 42, 'A parameter')
        traj2 = Trajectory()
        traj2.f_apar(CustomParam, 'hi.my.name.is.another', 43, 'Another')
        traj1._copy_from(traj2, copy_leaves=False)

        self.assertTrue('another' in traj1)
        self.assertTrue(traj1.another, 43)
        self.assertTrue(traj1.f_get('another') is traj2.f_get('another'))

    def test_copy_tree_annotations(self):
        traj1 = Trajectory()
        traj1.par['hi'] = Parameter('hi.my.name.is.parameter', 42, 'A parameter')
        traj1.res['ha'] = Result('ha.my3.name3.is3.res', 555, 55, 5)
        traj1.hi.v_annotations['test'] = 'ddd'

        traj2 = Trajectory()

        traj2.par['hi'] = Parameter('hi.my.name.is.another', 43, 'Another')
        traj2.hi.v_annotations['test'] = 'jjj'
        traj2.res['ha'] = Result('ha.my3.name3.is3.res', 555, 55, 7)
        traj2.hi.name.v_annotations['test'] = 'lll'

        traj1._copy_from(traj2)

        self.assertTrue('another' in traj1)
        self.assertEqual(traj1.hi.v_annotations['test'], 'ddd')

    def test_copy_links(self):
        traj1 = Trajectory()
        traj1.par['hi'] = Parameter('hi.my.name.is.parameter', 42, 'A parameter')
        traj2 = Trajectory()
        traj2.par['hi'] = Parameter('hi.my.name.is.another', 43, 'Another')
        traj2['ands'] = Result('ands.moreover', 43, 'Another')
        traj2.ands.test = traj2.name

        traj1._copy_from(traj2, with_links=False)
        with self.assertRaises(AttributeError):
            traj1.ands.test

        traj1._copy_from(traj2, with_links=True)
        self.assertTrue(traj1.ands.test is traj1.name)

    def test_not_copy_from_node(self):
        traj1 = Trajectory()
        traj1.par['hi'] = Parameter('hi.my.name.is.parameter', 42, 'A parameter')
        traj2 = Trajectory()
        traj2.par['hi'] = Parameter('hi.my.name.is.another', 43, 'Another')
        traj2['ands'] = Result('ands.moreover', 43, 'Another')
        traj2.ands.test = traj2.name

        traj1._copy_from(traj2.ands, with_links=False)
        with self.assertRaises(AttributeError):
            traj1.ands.test

        self.assertEqual(traj1.moreover[1], 'Another')

        traj1._copy_from(traj2.ands, with_links=True)
        self.assertTrue(traj1.ands.test is traj1.name)

    def test_copy_explored(self):
        traj1 = Trajectory()
        traj1.par['hi'] = ParameterGroup('hi.my.name.is')
        traj1.par['hi.my.name.is.parameter'] = Parameter('', 42, 'A parameter')
        traj1.par['hi.my.name.is.parameter2'] = Parameter('',44, 'A second parameter')


        traj1['hi.my.name.is.another'] = Parameter('',43, 'Another')
        traj1['ands'] = Result('ands.moreover', 43, 'Another')
        traj1.ands.test = traj1.name

        traj1.f_explore({'parameter':[1,2,3,4]})


        traj1.v_full_copy = True
        traj2 = traj1.f_copy(copy_leaves='explored')

        self.assertTrue(traj2.f_get('another') is traj1.f_get('another'))
        self.assertTrue(traj2.f_get('parameter2') is traj1.f_get('parameter2'))
        self.assertTrue(traj2.f_get('parameter') is not traj1.f_get('parameter'))

        self.assertTrue(traj2.f_get('parameter').v_explored)

        self.assertTrue(traj2.f_get('parameter').f_has_range())


        traj1.v_full_copy = False
        traj2 = traj1.f_copy(copy_leaves=True)

        self.assertTrue(traj2.f_get('another') is not traj1.f_get('another'))
        self.assertTrue(traj2.f_get('parameter2') is not traj1.f_get('parameter2'))
        self.assertTrue(traj2.f_get('parameter') is not traj1.f_get('parameter'))

        self.assertTrue(traj2.f_get('parameter').v_explored)

        self.assertFalse(traj2.f_get('parameter').f_has_range())

        traj1.v_full_copy = False
        traj2 = traj1.f_copy(copy_leaves=False)

        self.assertTrue(traj2.f_get('another') is traj1.f_get('another'))
        self.assertTrue(traj2.f_get('parameter2') is traj1.f_get('parameter2'))
        self.assertTrue(traj2.f_get('parameter') is traj1.f_get('parameter'))

        self.assertTrue(traj2.f_get('parameter').v_explored)

        self.assertTrue(traj2.f_get('parameter').f_has_range())


    def test_shallow_copy_not_full_copy(self):
        traj1 = Trajectory()
        traj1.par['hi'] = ParameterGroup('hi.my.name.is')
        traj1.par['hi.my.name.is.parameter'] = Parameter('', 42, 'A parameter')

        traj1['hi.my.name.is.another'] = Parameter('', 43, 'Another')
        traj1['ands'] = Result('ands.moreover', 43, 'Another')
        traj1.ands.test = traj1.name

        traj1.f_explore({'parameter':[1,2,3,4]})

        traj1.v_full_copy = False

        traj1.f_add_result('ggg.hhh.result', 42)
        traj1.f_add_result('lll.res32', 32, 33)
        traj1.f_add_link('ff', traj1.res32)

        traj2 = cp.copy(traj1)
        self.assertFalse(traj2.f_get('parameter').f_has_range())
        self.assertTrue(traj2.f_get('parameter').v_explored)


    def test_shallow_copy(self):
        traj1 = Trajectory()
        traj1.par['hi'] = ParameterGroup('hi.my.name.is')
        traj1.par['hi.my.name.is.parameter'] = Parameter('', 42, 'A parameter')

        traj1['hi.my.name.is.another'] = Parameter('', 43, 'Another')
        traj1['ands'] = Result('ands.moreover', 43, 'Another')


        traj1.ands.test = traj1.name

        traj1.f_explore({'parameter':[1,2,3,4]})

        traj1.v_full_copy = True

        for irun in range(4):
            traj1.f_start_run(irun, True)

            traj1.f_add_result('ggg.hhh.result', 42)
            traj1.f_add_result('lll.res32', 32, 33)
            traj1.f_add_link('res.runs.crun.ff', traj1.crun.res32)

            traj1.f_finalize_run(store_meta_data=False, clean_up=False)

        traj2 = cp.copy(traj1)

        self.assertEqual(set(traj1.__dict__.keys()), set(traj2.__dict__.keys()))
        for key in traj1.__dict__:
            val1 = traj1.__dict__[key]
            val2 = traj2.__dict__[key]
            if hasattr(val1, 'keys'):
                self.assertEqual(set(val1.keys()), set(val2.keys()))
            else:
                self.assertEqual(val1, val2)

        self.assertTrue(traj1.r_0.res32 is not traj2.r_0.res32)
        self.assertTrue(traj2.f_get('parameter') is not traj1.f_get('parameter'))

        self.assertEqual(len(list(traj1.f_iter_nodes())), len(list(traj2.f_iter_nodes())))
        self.assertEqual(len(traj1._new_nodes), len(traj2._new_nodes))
        self.assertEqual(len(traj1._new_links), len(traj2._new_links))

        self.compare_trajectories(traj1, traj2)

    def test_overwrite_leaves(self):
        traj1 = Trajectory()
        traj1.res['hi'] = Result('hi.my.name.is.resr', 42, 'resr')
        traj2 = Trajectory()

        traj2.res['hi'] = Result('hi.my.name.is.resr', 43, 'resr')
        traj2['ands'] = Result('ands.moreover', 43, 'Another')
        traj2.ands.test = traj2.name

        traj1._copy_from(traj2)
        self.assertEqual(traj1.name.resr.resr, 42)

        self.assertTrue(traj1.name.resr is not traj2.name.resr)

class TrajectoryFindTest(unittest.TestCase):

    tags = 'unittest', 'trajectory', 'search'

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


class SingleRunTest(unittest.TestCase):

    tags = 'unittest', 'trajectory', 'single_run'

    def setUp(self):

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
        self.traj.v_idx = self.n

        self.single_run = self.traj.__copy__()._make_single_run()

    def test_different_dir(self):
        traj_dir = dir(self.traj)

        run_dir = dir(self.single_run)

        self.assertGreater(len(traj_dir), len(run_dir))

    def test_if_single_run_can_be_pickled(self):

        self.single_run._storageservice= QueueStorageServiceSender(None)
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
        resval= self.single_run.res.crun.f_get('Hacks').f_get('val')
        self.assertTrue(resval == value, '%s != %s' % ( str(resval),str(value)))

        with self.assertRaises(ValueError):
            self.traj.f_add_result(comment='55')

    def test_auto_prepend(self):
        self.single_run.f_adpar('hi.test', 44)

        self.assertEqual(self.single_run.dpar.runs.crun.hi.test, 44)

        self.single_run.v_auto_run_prepend = False
        self.single_run.f_adpar('huhu.test', 990)

        self.assertEqual(self.single_run.f_get('dpar.huhu.test', shortcuts=False,
                                               fast_access=True), 990)

    def test_standard_change_param_change(self):
        self.single_run.v_standard_parameter=ImAParameterInDisguise

        self.single_run.f_add_derived_parameter('I.should_be_not.normal')

        self.assertIsInstance(self.single_run.f_get('normal'), ImAParameterInDisguise)

        self.single_run.v_standard_result=ImAResultInDisguise

        self.single_run.f_add_result('Peter.Parker')

        self.assertIsInstance(self.single_run.Parker, ImAResultInDisguise)


class SingleRunQueueTest(unittest.TestCase):

    tags = 'unittest', 'trajectory', 'single_run', 'queue'

    def setUp(self):

        logging.basicConfig(level = logging.ERROR)
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
        self.single_run = self.traj._make_single_run()


    def test_queue(self):

        manager = multip.Manager()
        queue = manager.Queue()

        to_put = ('msg',[self.single_run],{})

        queue.put(to_put)

        pass

if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)