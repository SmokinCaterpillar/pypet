__author__ = 'Robert Meyer'


import unittest


from environment_test import *
from hdf5_storage_test import *
from parameter_test import *
from speed_test import *
from trajectory_test import *
from hdf5_merge_test import *
from hdf5_removal_and_continue_tests import *
from utilstest import *

# Works only if someone has installed Brian
try:
    from brian_parameter_test import *
    from brian_full_network_test import *
except ImportError:
    pass


if __name__ == '__main__':
    unittest.main()