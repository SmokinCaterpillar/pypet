'''
Created on 05.06.2013

@author: robert
'''

from mypet.environment import Environment
from mypet.trajectory import SingleRun, Trajectory
from mypet.utils.explore import identity
from mypet.configuration import config
from mypet.parameter import SimpleResult

import multiprocessing as multip
import logging
from mypet.brian.parameter import BrianParameter

def test_run(traj, to_print):
    
    assert isinstance(traj, SingleRun)
    
    print to_print
    
    x = traj.x.value
    y = traj.add_derived_parameter('y')
    y.val = x**2
    
    smurf = SimpleResult('','','','')
    z = traj.add_result('Nada.Moo',smurf)
    
    z.val = y()+1
    
    print 'Dat wars'


#multip.log_to_stderr().setLevel(logging.INFO) 

config['multiproc']=False
config['ncores']=2

env = Environment(trajectory='MyExperiment', filename='../experiments/env.hdf5',dynamicly_imported_classes=[BrianParameter])

traj = env.get_trajectory()
assert isinstance(traj, Trajectory)
par=traj.add_parameter('x',param_type=BrianParameter, value=3, unit = 'mV')
par.hui='buh'
print par()
print par.val


traj.explore(identity, {traj.x.gfn('value'):[1,2,3,4]})

env.run(test_run,to_print='test')


