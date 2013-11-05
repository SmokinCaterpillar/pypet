__author__ = 'Robert Meyer'

import numpy as np

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

from pypet.parameter import Parameter
from pypet.trajectory import Trajectory, SingleRun
from pypet.storageservice import LazyStorageService

from pypet.environment import Environment
from pypet.brian.parameter import BrianParameter, BrianMonitorResult
import pickle
import logging
import cProfile
from brian import *
from pypet.utils.explore import cartesian_product
import shutil
from pypet.tests.test_helpers import make_temp_file, TrajectoryComparator, make_run




def add_params(traj):

    traj.v_standard_parameter=BrianParameter
    traj.v_fast_access=True

    traj.f_add_parameter('Sim.defaultclock', 0.01*ms)
    traj.f_add_parameter('Net.C',281*pF)
    traj.f_add_parameter('Net.gL',30*nS)
    traj.f_add_parameter('Net.EL',-70.6*mV)
    traj.f_add_parameter('Net.VT',-50.4*mV)
    traj.f_add_parameter('Net.DeltaT',2*mV)
    traj.f_add_parameter('Net.tauw',40*ms)
    traj.f_add_parameter('Net.a',4*nS)
    traj.f_add_parameter('Net.b',0.08*nA)
    traj.f_add_parameter('Net.I',.8*nA)
    traj.f_add_parameter('Net.Vcut',traj.VT+5*traj.DeltaT) # practical threshold condition
    traj.f_add_parameter('Net.N',100)

    eqs="""
    dvm/dt=(gL*(EL-vm)+gL*DeltaT*exp((vm-VT)/DeltaT)+I-w)/C : volt
    dw/dt=(a*(vm-EL)-w)/tauw : amp
    Vr:volt
    """

    traj.f_add_parameter('Net.eqs', eqs)
    traj.f_add_parameter('reset', 'vm=Vr;w+=b')
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

    #run(25*msecond,report='text') # we discard the first spikes

    MSpike=SpikeMonitor(neuron, delay = 1*ms) # record Vr and w at spike times
    MPopSpike =PopulationSpikeCounter(neuron, delay = 1*ms)
    MPopRate = PopulationRateMonitor(neuron,bin=5*ms)
    MStateV = StateMonitor(neuron,'vm',record=[1,2,3])
    MStatewMean = StateMonitor(neuron,'w',record=False)

    MRecentStateV = RecentStateMonitor(neuron,'vm',record=[1,2,3],duration=10*ms)
    MRecentStatewMean = RecentStateMonitor(neuron,'w',duration=10*ms,record=False)

    MCounts = SpikeCounter(neuron)

    MStateSpike = StateSpikeMonitor(neuron,('w','vm'))

    MMultiState = MultiStateMonitor(neuron,['w','vm'],record=[6,7,8,9])

    ISIHist = ISIHistogramMonitor(neuron,[0,0.0001,0.0002], delay = 1*ms)

    VanRossum = VanRossumMetric(neuron, tau=5*msecond)

    run(25*msecond,report='text')

    traj.v_standard_result = BrianMonitorResult
    traj.f_add_result('SpikeMonitor',MSpike)
    traj.f_add_result('SpikeMonitorAr',MSpike, storage_mode = BrianMonitorResult.ARRAY_MODE)
    traj.f_add_result('PopulationSpikeCounter', MPopSpike)
    traj.f_add_result('PopulationRateMonitor',MPopRate)
    traj.f_add_result('StateMonitorV', MStateV)
    traj.f_add_result('StateMonitorwMean', MStatewMean)
    traj.f_add_result('Counts',MCounts)
    traj.f_add_result('StateSpikevmw', MStateSpike)
    traj.f_add_result('StateSpikevmwAr', MStateSpike,storage_mode = BrianMonitorResult.ARRAY_MODE)
    traj.f_add_result('MultiState',MMultiState)
    traj.f_add_result('ISIHistogrammMonitor',ISIHist)
    traj.f_add_result('RecentStateMonitorV', MRecentStateV)
    traj.f_add_result('RecentStateMonitorwMean', MRecentStatewMean)
    traj.f_add_result('VanRossumMetric', VanRossum)

class NetworkTest(TrajectoryComparator):


    def setUp(self):
        logging.basicConfig(level = logging.INFO)


        env = Environment(trajectory='Test',
                          filename=make_temp_file('experiments/tests/briantests/HDF5/test.hdf5'),
                          file_title='test',
                          log_folder=make_temp_file('experiments/tests/briantests/log'),
                          dynamically_imported_classes=['pypet.brian.parameter.BrianParameter',
                                                        BrianMonitorResult])

        traj = env.v_trajectory

        traj.ncores= 2
        #env._set_standard_storage()
        #env._hdf5_queue_writer._hdf5storageservice = LazyStorageService()
        traj = env.v_trajectory
        #traj.set_storage_service(LazyStorageService())

        add_params(traj)
        #traj.mode='Parallel'


        traj.f_explore(cartesian_product({traj.f_get('N').v_full_name:[50,60],
                               traj.f_get('tauw').v_full_name:[30*ms,40*ms]}))

        self.traj = traj

        self.env = env
        self.traj = traj


    def test_singleprocessing(self):
        self.env.f_run(run_net)

        self.traj.f_load(load_derived_parameters=-2, load_results=-2)

        traj2 = Trajectory(name = self.traj.v_name, add_time=False,
                           filename=make_temp_file('experiments/tests/briantests/HDF5/test.hdf5'),
                           dynamically_imported_classes=['pypet.brian.parameter.BrianParameter',
                                                        BrianMonitorResult])

        traj2.f_load(load_parameters=2, load_derived_parameters=2, load_results=2)

        self.compare_trajectories(self.traj, traj2)


    def test_multiprocessing(self):
        self.traj.multiproc = True
        self.traj.ncores = 3
        self.env.f_run(run_net)

        self.traj.f_load(load_derived_parameters=-2, load_results=-2)

        traj2 = Trajectory(name = self.traj.v_name, add_time=False,
                           filename=make_temp_file('experiments/tests/briantests/HDF5/test.hdf5'),
                           dynamically_imported_classes=['pypet.brian.parameter.BrianParameter',
                                                        BrianMonitorResult])

        traj2.f_load(load_parameters=2, load_derived_parameters=2, load_results=2)

        self.compare_trajectories(self.traj, traj2)


if __name__ == '__main__':
    make_run()