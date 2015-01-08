__author__ = 'robert'

import os
from pypet import Trajectory

filename = os.path.join('test','test.hdf5')

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