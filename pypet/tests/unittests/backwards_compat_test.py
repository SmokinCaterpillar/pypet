__author__ = 'Robert Meyer'


import sys
import os
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

from pypet import Trajectory
from pypet.tests.testutils.ioutils import run_suite, parse_args
import pypet
import platform

class LoadOldTrajectoryTest(unittest.TestCase):

    tags = 'unittest', 'legacy'

    @unittest.skipIf(not sys.version_info < (3, 0, 0), 'Can only be run in python 2.7')
    def test_backwards_compatibility(self):
        # Test only makes sense with python 2.7 or lower
        old_pypet_traj = Trajectory()
        module_path, init_file = os.path.split(pypet.__file__)
        filename= os.path.join(module_path, 'tests','testdata','pypet_v0_1b_6.hdf5')
        old_pypet_traj.f_load(index=-1, load_data=2, force=True, filename=filename)

        self.assertTrue(old_pypet_traj.v_version=='0.1b.6')
        self.assertTrue(old_pypet_traj.par.x==0)
        self.assertTrue(len(old_pypet_traj)==9)
        self.assertTrue(old_pypet_traj.res.runs.r_4.z==12)
        nexplored = len(old_pypet_traj._explored_parameters)
        self.assertGreater(nexplored, 0)
        for param in old_pypet_traj.f_get_explored_parameters():
            self.assertTrue(old_pypet_traj.f_contains(param))


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)