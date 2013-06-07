'''
Created on 05.06.2013

@author: robert
'''

from mypet.environment import Environment
from mypet.trajectory import SingleRun, Trajectory
from mypet.utils.explore import identity

def test_run(traj, to_print):
    
    assert isinstance(traj, SingleRun)
    
    print to_print
    
    x = traj.x.val
    y = traj.add_derived_parameter('y')
    y.val = x^2
    
    print 'Dat wars'
    

env = Environment(trajectoryname='MyExperiment', filename='../experiments/env.hdf5')

traj = env.get_trajectory()
assert isinstance(traj, Trajectory)
traj.add_parameter('x', val=3)

traj.explore(identity, {traj.x.gfn('val'):[1,2,3,4]})

env.run(test_run,to_print='test')