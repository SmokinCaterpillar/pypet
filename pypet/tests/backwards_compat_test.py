__author__ = 'robert'


import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

from pypet import Trajectory

class LoadOldTrajectoryTest(unittest.TestCase):

    def test_backwards_compatibility(self):
        old_pypet_traj = Trajectory()
        old_pypet_traj.f_load(filename='./testdata/pypet_v0_1b_6_testrun.hdf5',
                              load_all=2, force=True, index=-1)

        self.assertTrue(old_pypet_traj.v_version=='0.1b.6')
        self.assertTrue(old_pypet_traj.par.Normal.int==42)
        self.assertTrue(old_pypet_traj.par.Numpy.int[0]==1)
        self.assertTrue(old_pypet_traj.par.Numpy.int[0]==1)
        self.assertTrue(len(old_pypet_traj)==4)
        self.assertTrue(old_pypet_traj.res.runs.r_2.IStore.SimpleThings.SimpleThings_3=='Iamstring')