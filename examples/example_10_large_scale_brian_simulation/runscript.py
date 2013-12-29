__author__ = 'Robert Meyer'



from pypet.environment import Environment
from clusternet import CNMonitorAnalysis, CNNeuronGroup, CNNetworkRunner, CNConnections,\
    CNFanoFactorComputer
from brian.stdunits import ms
from pypet.brian.network import NetworkManager, run_network

import numpy as np
import logging


def main():

    logging.basicConfig(level=logging.DEBUG)
    env = Environment(trajectory='Clustered_Network',
                      filename='../HDF5/',
                      log_folder='../LOGS/',
                      continuable=False,
                      lazy_debug=False,
                      multiproc=True,
                      ncores=2,
                      use_pool=False,
                      wrap_mode='LOCK')

    traj = env.v_trajectory

    # If we scale the original network by 0.5 but keep the cluster size at 80,
    # experiments run a) faster and b) results are better in terms of neurons being
    # double stochastic
    scale = 0.5
    traj.f_add_parameter('simulation.scale', scale,
            comment='Meta parameter that can scale default settings')


    clustered_network_manager = NetworkManager(CNNetworkRunner(),
                                               (CNNeuronGroup(), CNConnections()),
                                               (CNMonitorAnalysis(),CNFanoFactorComputer()))




    # Add original parameters (but scaled according to `size_scale`)
    clustered_network_manager.add_parameters(traj)

    # We need this cumbersome list comprehension since our original parameter is
    # of type `float` and not `numpy.float64`
    explore_list = np.arange(1.0, 2.5, 0.1).tolist()
    # Explore different values of `R_ee`
    traj.f_explore({'R_ee' : explore_list})

    #traj.R_ee = 2.52
    #traj.analysis.show_plots=1

    # Pre Build Network
    clustered_network_manager.pre_build(traj)

    # Run the network simulation
    results = env.f_run(run_network, clustered_network_manager)

    print results

if __name__=='__main__':
    main()