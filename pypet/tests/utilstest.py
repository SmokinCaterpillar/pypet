

__author__ = 'Robert Meyer'



from pypet.tests.test_helpers import add_params, create_param_dict, simple_calculations, make_run,\
    make_temp_file, TrajectoryComparator, multiply, make_trajectory_name

from pypet.trajectory import Trajectory

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

from pypet.utils.explore import cartesian_product

from pypet.utils.helpful_functions import progressbar

from pypet.utils.comparisons import nested_equal

from pypet.utils.to_new_tree import FileUpdater


class CartesianTest(unittest.TestCase):

    def test_cartesian_product(self):

        cartesian_dict=cartesian_product({'param1':[1,2,3], 'param2':[42.0, 52.5]},
                                          ('param1','param2'))
        result_dict = {'param1':[1,1,2,2,3,3],'param2': [42.0,52.5,42.0,52.5,42.0,52.5]}

        self.assertTrue(nested_equal(cartesian_dict,result_dict), '%s != %s' %
                                                        (str(cartesian_dict),str(result_dict)))

    def test_cartesian_product_combined_params(self):
        cartesian_dict=cartesian_product( {'param1': [42.0, 52.5], 'param2':['a', 'b'],\
            'param3' : [1,2,3]}, (('param3',),('param1', 'param2')))

        result_dict={'param3':[1,1,2,2,3,3],'param1' : [42.0,52.5,42.0,52.5,42.0,52.5],
                      'param2':['a','b','a','b','a','b']}

        self.assertTrue(nested_equal(cartesian_dict,result_dict), '%s != %s' %
                                                    (str(cartesian_dict),str(result_dict)))



class ProgressBarTest(unittest.TestCase):

    def test_progressbar(self):

        total = 55
        percentage_step = 17

        for irun in range(total):
            progressbar(irun, total)



class TestNewTreeTranslation(unittest.TestCase):

    def test_file_translation(self):
        filename = make_temp_file('to_new_tree.hdf5')
        mytraj = Trajectory('SCRATCH', filename=filename)

        mytraj.f_add_parameter('Test.Group.Test', 42)

        mytraj.f_add_derived_parameter('trajectory.saaaa',33)

        mytraj.f_add_derived_parameter('trajectory.intraj.dpar1',33)

        mytraj.f_add_derived_parameter('run_00000008.inrun.dpar2',33)
        mytraj.f_add_derived_parameter('run_00000001.inrun.dpar3',35)


        mytraj.f_add_result('trajectory.intraj.res1',33)

        mytraj.f_add_result('run_00000008.inrun.res1',33)

        mytraj.f_store()

        mytraj.f_migrate(new_name=mytraj.v_name + 'PETER', in_store=True)

        mytraj.f_store()

        fu=FileUpdater(filename=filename, backup=True)

        fu.update_file()

        mytraj = Trajectory(name=mytraj.v_name, add_time=False, filename=filename)
        mytraj.f_load(load_parameters=2, load_derived_parameters=2, load_results=2)

        for node in mytraj.f_iter_nodes():
            self.assertTrue(node.v_name != 'trajectory')

            if 'run_' in node.v_full_name:
                self.assertTrue('.runs.' in node.v_full_name)


if __name__ == '__main__':
    make_run()



