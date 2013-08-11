__author__ = 'robert'

import numpy as np
import unittest
from mypet.parameter import Parameter
from mypet.trajectory import Trajectory, SingleRun
from mypet.storageservice import LazyStorageService
from mypet.utils.explore import identity
from mypet.environment import Environment
from mypet.brian.parameter import BrianParameter, BrianMonitorResult
import pickle
import logging
import cProfile
from brian import *
from mypet.utils.explore import identity, cartesian_product

def add_params(traj):

    traj.set_standard_param_type(BrianParameter)
    traj.set_fast_access(True)

    traj.ap('Sim.defaultclock', 0.01*ms)
    traj.ap('Net.C',281*pF)
    traj.ap('Net.gL',30*nS)
    traj.ap('Net.EL',-70.6*mV)
    traj.ap('Net.VT',-50.4*mV)
    traj.ap('Net.DeltaT',2*mV)
    traj.ap('Net.tauw',40*ms)
    traj.ap('Net.a',4*nS)
    traj.ap('Net.b',0.08*nA)
    traj.ap('Net.I',.8*nA)
    traj.ap('Net.Vcut',traj.VT+5*traj.DeltaT) # practical threshold condition
    traj.ap('Net.N',500)

    eqs="""
    dvm/dt=(gL*(EL-vm)+gL*DeltaT*exp((vm-VT)/DeltaT)+I-w)/C : volt
    dw/dt=(a*(vm-EL)-w)/tauw : amp
    Vr:volt
    """

    traj.ap('Net.eqs', eqs)
    traj.ap('reset', 'vm=Vr;w+=b')
    pass

def run_net(traj):
    defaultclock.dt=traj.defaultclock

    C=traj.C
    gL=traj.gL
    EL=traj.EL
    VT=traj.VT
    DeltaT=traj.DeltaT
    tauw=traj.tauw
    a=traj.a
    b=traj.b
    I=traj.I
    Vcut=traj.Vcut# practical threshold condition
    N=traj.N

    eqs=traj.eqs

    neuron=NeuronGroup(N,model=eqs,threshold=Vcut,reset=traj.reset)
    neuron.vm=EL
    neuron.w=a*(neuron.vm-EL)
    neuron.Vr=linspace(-48.3*mV,-47.7*mV,N) # bifurcation parameter

    run(50*msecond,report='text') # we discard the first spikes

    MSpike=SpikeMonitor(neuron) # record Vr and w at spike times
    MPopSpike =PopulationSpikeCounter(neuron)
    MPopRate = PopulationRateMonitor(neuron)
    MStateV = StateMonitor(neuron,'vm')


    run(50*msecond,report='text')


    traj.add_result('SpikeMonitor',BrianMonitorResult,MSpike)
    traj.add_result('PopulationSpikeCounter', BrianMonitorResult, MPopSpike)
    traj.add_result('PopulationRateMonitor', BrianMonitorResult,MPopRate)
    traj.add_result('StateMonitor', BrianMonitorResult, MStateV)


class NetworkTest(unittest.TestCase):


    def setUp(self):
        logging.basicConfig(level = logging.DEBUG)


        env = Environment('Test','../../Brian/HDF5/test.hdf5','test',logfolder='../../Brian/log')

        traj = env.get_trajectory()
        #traj.multiproc = True
        traj.change_config('ncores', 2)
        #env._set_standard_storage()
        #env._hdf5_queue_writer._hdf5storageservice = LazyStorageService()
        traj = env.get_trajectory()
        #traj.set_storage_service(LazyStorageService())

        add_params(traj)
        #traj.mode='Parallel'


        traj.explore(cartesian_product,{traj.get('N').gfn('val0'):[100,200],
                               traj.get('tauw').gfn('val0'):[30*ms,40*ms]})

        self.traj = traj

        self.env = env
        self.traj = traj

    def test_multiprocessing(self):

        self.env.run(run_net)


if __name__ == '__main__':
    unittest.main()