__author__ = 'robert'


import unittest

from brian_parameter_test import *
from environment_test import *
from hdf5_storage_test import *
from parameter_test import *
from speed_test import *
from trajectory_test import *
from brian_full_network_test import *
from hdf5_merge_test import *
from hdf5_removal_and_continue_tests import *


if __name__ == '__main__':
    unittest.main()