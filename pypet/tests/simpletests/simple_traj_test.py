__author__ = 'robert'

import os
from pypet import Trajectory
from pypet.tests.test_helpers import make_temp_file, remove_data

filename = make_temp_file(os.path.join('test','test.hdf5'))

traj = Trajectory(filename=filename)

traj.f_add_parameter('x', 42)

traj.f_store()


traj.f_remove_child('parameters', recursive=True)

try:
    traj.x
    print('wtf?')
except AttributeError:
    print('Ain`t no x')

traj.f_load()

print('x:')
print(traj.x)

remove_data()