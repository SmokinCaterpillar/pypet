"""Starting script to run a network simulation of the clustered network
by Litwin-Kumar and Doiron (Nature neuroscience 2012).

The network has been implemented using the *pypet* network framework.

"""

__author__ = 'Robert Meyer'

import numpy as np
import os # To allow path names work under Windows and Linux

from pypet.environment import Environment
from pypet.brian.network import NetworkManager, run_network

from clusternet import CNMonitorAnalysis, CNNeuronGroup, CNNetworkRunner, CNConnections,\
    CNFanoFactorComputer


def main():
    filename = os.path.join('experiments', 'example_11', 'HDF5', 'Clustered_Network.hdf5')
    log_folder = os.path.join('experiments', 'example_11', 'LOGS')
    env = Environment(trajectory='Clustered_Network',
                      add_time=False,
                      filename=filename,
                      log_folder=log_folder,
                      continuable=False,
                      lazy_debug=False,
                      multiproc=True,
                      ncores=2,
                      use_pool=False, # We cannot use a pool, our network cannot be pickled
                      wrap_mode='QUEUE',
                      new_file=True)

    #Get the trajectory container
    traj = env.v_trajectory

    # We introduce a `meta` parameter that we can use to easily rescale our network
    scale = 0.25 # To obtain the results from the paper scale this to 1.0
    # Be aware that your machine will need a lot of memory then!
    traj.f_add_parameter('simulation.scale', scale,
            comment='Meta parameter that can scale default settings. '
                    'Rescales number of neurons and connections strenghts, but '
                    'not the clustersize.')


    # We create a Manager and pass all our components to the Manager.
    # Note the order, CNNeuronGroups are scheduled before CNConnections,
    # and the Fano Factor computation depends on the CNMonitorAnalysis
    clustered_network_manager = NetworkManager(network_runner=CNNetworkRunner(),
                                component_list=(CNNeuronGroup(), CNConnections()),
                                analyser_list=(CNMonitorAnalysis(),CNFanoFactorComputer()))




    # Add original parameters (but scaled according to `scale`)
    clustered_network_manager.add_parameters(traj)

    # We need `tolist` here since our parameter is a python float and not a
    # numpy float.
    explore_list = np.arange(1.0, 2.6, 0.25).tolist()
    # Explore different values of `R_ee`
    traj.f_explore({'R_ee' : explore_list})

    # Pre-build network components
    clustered_network_manager.pre_build(traj)


    # Run the network simulation
    traj.f_store() # Let's store the parameters already before the run
    env.f_run(clustered_network_manager.run_network)


if __name__=='__main__':
    main()