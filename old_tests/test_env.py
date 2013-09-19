'''
Created on 05.06.2013

@author: robert
'''

from pypet.environment import Environment
from pypet.trajectory import SingleRun, Trajectory
from pypet.utils.explore import identity
from pypet.configuration import config
from pypet.parameter import Result

import multiprocessing as multip
import logging
from pypet.brian.parameter import BrianParameter

def test_run(traj, to_print):
    
    assert isinstance(traj, SingleRun)
    
    print to_print
    
    x = traj.x.value
    y = traj.f_add_derived_parameter('y')
    y.val = x**2
    
    smurf = Result('','','','')
    z = traj.f_add_result('Nada.Moo',smurf)
    
    z.val = y()+1
    
    print 'Dat wars'


#multip.log_to_stderr().setLevel(logging.INFO) 

config['multiproc']=False
config['ncores']=2

env = Environment(trajectory='MyExperiment', filename='../experiments/env.hdf5',dynamicly_imported_classes=[BrianParameter])

traj = env.get_trajectory()
assert isinstance(traj, Trajectory)
par=traj.f_add_parameter('x',param_type=BrianParameter, value=3, unit = 'mV')
par.hui='buh'
print par()
print par.val


traj.f_explore(identity, {traj.x.gfn('value'):[1,2,3,4]})

env.run(test_run,to_print='test')


