"""Module to run the clustered Neural Network Simulations as in Litwin-Kumar & Doiron 2012"""

__author__ = 'Robert Meyer'

import os
import numpy as np
import matplotlib.pyplot as plt

from pypet.trajectory import Trajectory, SingleRun
from pypet.brian.parameter import BrianParameter, BrianMonitorResult, BrianDurationParameter
from pypet.brian.network import NetworkComponent, NetworkRunner, NetworkAnalyser
from brian.stdunits import ms

from brian import NeuronGroup, rand, Connection, Equations, Network, SpikeMonitor, second, \
    raster_plot, show, StateMonitor, clear, reinit_default_clock

def run_network(traj, clustered_net):
    """Top-level function for running the network

    :param traj: Container for parameters and results

    :param clustered_net: *pypet* NetworkManager

    """
    clustered_net.run_network(traj)


def _explored_parameters_in_group(traj, group_node):
    """Checks if one the parametes in `group_node` is explored.

    :param traj: Trajectory container
    :param group_node: Group node
    :return: `True` or `False`

    """
    explored = False
    for param in traj.f_get_explored_parameters():
            if param in group_node:
                explored = True
                break

    return explored

class CNNeuronGroup(NetworkComponent):
    """Class to create neuron groups.

    Creates two groups of excitatory and inhibitory neurons.

    """

    @staticmethod
    def add_parameters(traj):
        """Adds all neuron group parameters to `traj`."""
        assert(isinstance(traj,Trajectory))

        scale = traj.simulation.scale


        traj.v_standard_parameter = BrianParameter

        model_eqs = '''dV/dt= 1.0/tau_POST * (mu - V) + I_syn : 1
                       mu : 1
                       I_syn =  - I_syn_i + I_syn_e : Hz
                    '''

        conn_eqs = '''I_syn_PRE = x_PRE*invtau2_PRE/2.0 : Hz
                      dx_PRE/dt = (invpeak_PRE*y_PRE-x_PRE)*invtau1_PRE : 1
                      dy_PRE/dt = -y_PRE*invtau2_PRE : 1
                   '''

        traj.f_add_parameter('model.eqs', model_eqs,
                           comment='The differential equation for the neuron model')

        traj.f_add_parameter('model.synaptic.eqs', conn_eqs,
                           comment='The differential equation for the synapses. '
                                   'PRE will be replaced by `i` or `e` depending '
                                   'on the source population')

        traj.f_add_parameter('model.synaptic.tau1', 1*ms, comment = 'The decay time')
        traj.f_add_parameter('model.synaptic.tau2_e', 3*ms, comment = 'The rise time, excitatory')
        traj.f_add_parameter('model.synaptic.tau2_i', 2*ms, comment = 'The rise time, inhibitory')

        traj.f_add_parameter('model.V_th', 1.0, comment = "Threshold value")
        traj.f_add_parameter('model.reset_func', 'V=0.0',
                             comment = "String representation of reset function")
        traj.f_add_parameter('model.refractory', 5*ms, comment = "Absolute refractory period")

        traj.f_add_parameter('model.N_e', int(4000*scale), comment = "Amount of excitatory neurons")
        traj.f_add_parameter('model.N_i', int(1000*scale), comment = "Amount of inhibitory neurons")

        traj.f_add_parameter('model.tau_e', 15*ms, comment = "Membrane time constant, excitatory")
        traj.f_add_parameter('model.tau_i', 10*ms, comment = "Membrane time constant, inhibitory")

        traj.f_add_parameter('model.mu_e_min', 1.1, comment = "Lower bound for bias, excitatory")
        traj.f_add_parameter('model.mu_e_max', 1.2, comment = "Upper bound for bias, excitatory")

        traj.f_add_parameter('model.mu_i_min', 1.0, comment = "Lower bound for bias, inhibitory")
        traj.f_add_parameter('model.mu_i_max', 1.05, comment = "Upper bound for bias, inhibitory")


    @staticmethod
    def _build_model_eqs(traj):
        """Computes model equations for the excitatory and inhibitory population.

        Equation objects are created by fusing `model.eqs` and `model.synaptic.eqs`
        and replacing `PRE` by `i` (for inhibitory) or `e` (for excitatory) depending
        on the type of population.

        :return: Dictionary with 'i' equation object for inhibitory neurons and 'e' for excitatory

        """
        model_eqs = traj.model.eqs
        post_eqs={}
        for name_post in ['i','e']:
            variables_dict ={}
            new_model_eqs=model_eqs.replace('POST', name_post)
            for name_pre in ['i', 'e']:
                conn_eqs = traj.model.synaptic.eqs
                new_conn_eqs = conn_eqs.replace('PRE', name_pre)
                new_model_eqs += new_conn_eqs

                tau1 = traj.model.synaptic['tau1'].f_get()
                tau2 = traj.model.synaptic['tau2_'+name_pre].f_get()

                invpeak = (tau2/tau1) ** (tau1 / (tau2 - tau1))
                invtau1=1.0/tau1
                invtau2 = 1.0/tau2

                variables_dict['invtau1_'+name_pre] = invtau1
                variables_dict['invtau2_'+name_pre] = invtau2
                variables_dict['invpeak_'+name_pre] = invpeak

            variables_dict['tau_'+name_post] = traj.model['tau_'+name_post].f_get()

            post_eqs[name_post] = Equations(new_model_eqs, **variables_dict)

        return post_eqs

    def pre_build(self, traj, brian_list, network_dict):
        """Pre-builds the neuron groups.

        Pre-build is only performed if none of the
        relevant parameters is explored.

        :param traj: Trajectory container

        :param brian_list:

            List of objects passed to BRIAN network constructor.

            Adds
            -----

            Inhibitory neuron group

            Excitatory neuron group

        :param network_dict:

            Dictionary of elements shared among the components

            Adds
            ----

            'neurons_i': Inhibitory neuron group

            'neurons_e': Excitatory neuron group

        """
        self._pre_build = not _explored_parameters_in_group(traj, traj.parameters.model)

        if self._pre_build:
            self._build_model(traj, brian_list, network_dict)


    def build(self, traj, brian_list, network_dict):
        """Builds the neuron groups.

        Build is only performed if neuron group was not
        pre-build before.

        :param traj: Trajectory container

        :param brian_list:

            List of objects passed to BRIAN network constructor.

            Adds
            -----

            Inhibitory neuron group

            Excitatory neuron group

        :param network_dict:

            Dictionary of elements shared among the components

            Adds
            ----

            'neurons_i': Inhibitory neuron group

            'neurons_e': Excitatory neuron group

        """
        if not hasattr(self, '_pre_build') or not self._pre_build:
            self._build_model(traj, brian_list, network_dict)


    def _build_model(self, traj, brian_list, network_dict):
        """Builds the neuron groups from `traj`.

        Adds the neuron groups to `brian_list` and `network_dict`.

        """
        assert(isinstance(traj,SingleRun))

        model = traj.parameters.model

        # Create the equations for both models
        eqs_dict = self._build_model_eqs(traj)

        # Create inhibitory neurons
        eqs_i = eqs_dict['i']
        neurons_i = NeuronGroup(N=model.N_i,
                              model = eqs_i,
                              threshold=model.V_th,
                              reset=model.reset_func,
                              refractory=model.refractory,
                              freeze=True,
                              compile=True,
                              method='Euler')

        # Create excitatory neurons
        eqs_e = eqs_dict['e']
        neurons_e = NeuronGroup(N=model.N_e,
                              model = eqs_e,
                              threshold=model.V_th,
                              reset=model.reset_func,
                              refractory=model.refractory,
                              freeze=True,
                              compile=True,
                              method='Euler')


        # Set the bias terms
        neurons_e.mu =rand(model.N_e) * (model.mu_e_max - model.mu_e_min) + model.mu_e_min
        neurons_i.mu =rand(model.N_i) * (model.mu_i_max - model.mu_i_min) + model.mu_i_min

        # Set initial membrane potentials
        neurons_e.V = rand(model.N_e)
        neurons_i.V = rand(model.N_i)

        # Add both groups to the `brian_list` and the `network_dict`
        brian_list.append(neurons_i)
        brian_list.append(neurons_e)
        network_dict['neurons_e']=neurons_e
        network_dict['neurons_i']=neurons_i



class CNConnections(NetworkComponent):
    """Class to connect neuron groups.

    In case of no clustering `R_ee=1,0` there are 4 connection instances (i->i, i->e, e->i, e->e).

    Otherwise there are 3 + 3*N_c-2 connections with N_c the number of clusters
    (i->i, i->e, e->i, N_c conns within cluster, 2*N_c-2 connections from cluster to outside).

    """

    @staticmethod
    def add_parameters(traj):
        """Adds all neuron group parameters to `traj`."""
        assert(isinstance(traj,Trajectory))

        traj.v_standard_parameter = BrianParameter
        scale = traj.simulation.scale

        traj.f_add_parameter('connections.R_ee', 1.0, comment='Scaling factor for clustering')

        traj.f_add_parameter('connections.clustersize_e', 80, comment='Size of a cluster')
        traj.f_add_parameter('connections.strength_factor', 1.9,
                             comment='Factor for scaling cluster weights')

        traj.f_add_parameter('connections.p_ii', 0.5,
                            comment='Connection probability from inhibitory to inhibitory' )
        traj.f_add_parameter('connections.p_ei', 0.5,
                            comment='Connection probability from inhibitory to excitatory' )
        traj.f_add_parameter('connections.p_ie', 0.5,
                            comment='Connection probability from excitatory to inhibitory' )
        traj.f_add_parameter('connections.p_ee', 0.2,
                            comment='Connection probability from excitatory to excitatory' )

        traj.f_add_parameter('connections.J_ii', 0.057/np.sqrt(scale),
                             comment='Connection strength from inhibitory to inhibitory')
        traj.f_add_parameter('connections.J_ei', 0.045/np.sqrt(scale),
                             comment='Connection strength from inhibitory to excitatroy')
        traj.f_add_parameter('connections.J_ie', 0.014/np.sqrt(scale),
                             comment='Connection strength from excitatory to inhibitory')
        traj.f_add_parameter('connections.J_ee', 0.024/np.sqrt(scale),
                             comment='Connection strength from excitatory to excitatory')


    def pre_build(self, traj, brian_list, network_dict):
        """Pre-builds the connections.

        Pre-build is only performed if none of the
        relevant parameters is explored and the relevant neuron groups
        exist.

        :param traj: Trajectory container

        :param brian_list:

            List of objects passed to BRIAN network constructor.

            Adds
            -----

            Connections, amount depends on clustering

        :param network_dict:

            Dictionary of elements shared among the components

            Expects
            --------

            'neurons_i': Inhibitory neuron group

            'neurons_e': Excitatory neuron group

            Adds
            -----

            Connections, amount depends on clustering

        """
        self._pre_build = not _explored_parameters_in_group(traj, traj.parameters.connections)

        self._pre_build = (self._pre_build and 'neurons_i' in network_dict and
                           'neurons_e' in network_dict)

        if self._pre_build:
            self._build_connections(traj, brian_list, network_dict)


    def build(self, traj, brian_list, network_dict):
        """Builds the connections.

        Build is only performed if connections have not
        been pre-build.

        :param traj: Trajectory container

        :param brian_list:

            List of objects passed to BRIAN network constructor.

            Adds
            -----

            Connections, amount depends on clustering

        :param network_dict:

            Dictionary of elements shared among the components

            Expects
            --------

            'neurons_i': Inhibitory neuron group

            'neurons_e': Excitatory neuron group

            Adds
            -----

            Connections, amount depends on clustering

        """
        if not hasattr(self, '_pre_build') or not self._pre_build:
            self._build_connections(traj, brian_list, network_dict)


    def _build_connections(self, traj, brian_list, network_dict):
        """Connects neuron groups `neurons_i` and `neurons_e`.

        Adds all connections to `brian_list` and adds a list of connections
        with the key 'connections' to the `network_dict`.

        """

        connections = traj.connections

        neurons_i = network_dict['neurons_i']
        neurons_e = network_dict['neurons_e']

        print 'Connecting ii'
        self.conn_ii = Connection(neurons_i,neurons_i,state='y_i',
                                  weight=connections.J_ii,
                                  sparseness=connections.p_ii)

        print 'Connecting ei'
        self.conn_ei = Connection(neurons_i,neurons_e,state='y_i',
                                  weight=connections.J_ei,
                                  sparseness=connections.p_ei)

        print 'Connecting ie'
        self.conn_ie = Connection(neurons_e,neurons_i,state='y_e',
                                  weight=connections.J_ie,
                                  sparseness=connections.p_ie)

        conns_list = [self.conn_ii, self.conn_ei, self.conn_ie]


        if connections.R_ee > 1.0:
            # If we come here we want to create clusters

            cluster_list=[]
            cluster_conns_list=[]
            model=traj.model

            # Compute the number of clusters
            clusters = model.N_e/connections.clustersize_e
            traj.f_add_derived_parameter('connections.clusters', clusters, comment='Number of clusters')

            # Compute outgoing connection probability
            p_out = (connections.p_ee*model.N_e) / \
                    (connections.R_ee*connections.clustersize_e+model.N_e- connections.clustersize_e)

            # Compute within cluster connection probability
            p_in = p_out * connections.R_ee

            # We keep these derived parameters
            traj.f_add_derived_parameter('connections.p_ee_in', p_in ,
                                         comment='Connection prob within cluster')
            traj.f_add_derived_parameter('connections.p_ee_out', p_out ,
                                         comment='Connection prob to outside of cluster')


            low_index = 0
            high_index = connections.clustersize_e
            # Iterate through cluster and connect within clusters and to the rest of the neurons
            for irun in range(clusters):

                cluster = neurons_e[low_index:high_index]

                # Connections within cluster
                print 'Connecting ee cluster #%d of %d' % (irun, clusters)
                conn = Connection(cluster,cluster,state='y_e',
                                  weight=connections.J_ee*connections.strength_factor,
                                  sparseness=p_in)

                cluster_conns_list.append(conn)

                # Connections reaching out from cluster
                # A cluster consists of `clustersize_e` neurons with consecutive indices.
                # So usually the outside world consists of two groups, neurons with lower
                # indices than the cluster indices, and neurons with higher indices.
                # Only the clusters at the index boundaries project to neurons with only either
                # lower or higher indices
                if low_index > 0:
                    rest_low = neurons_e[0:low_index]
                    print 'Connecting cluster with other neurons of lower index'
                    low_conn = Connection(cluster,rest_low,state='y_e',
                                      weight=connections.J_ee,
                                      sparseness=p_out)

                    cluster_conns_list.append(low_conn)

                if high_index < model.N_e:
                    rest_high = neurons_e[high_index:model.N_e]
                    print 'Connecting cluster with other neurons of higher index'
                    high_conn = Connection(cluster,rest_high,state='y_e',
                                      weight=connections.J_ee,
                                      sparseness=p_out)

                    cluster_conns_list.append(high_conn)

                low_index=high_index
                high_index+=connections.clustersize_e

            self.cluster_conns=cluster_conns_list
            conns_list+=cluster_conns_list
        else:
            # Here we don't cluster and connection probabilities are homogeneous
            print 'Connectiong ee'
            self.conn_ee = Connection(neurons_e,neurons_e,state='y_e',
                                      weight=connections.J_ee,
                                      sparseness=connections.p_ee)

            conns_list.append(self.conn_ee)


        # Add the connections to the `brian_list` and the network dict
        brian_list += conns_list #TODO, is that right?
        network_dict['connections'] = conns_list


class CNNetworkRunner(NetworkRunner):
    """Class to create neurons.

    :param size_scale:

        Meta parameter to quickly scale the network size. Scales number of neurons linearly
        and connection strength with `np.sqrt(size_scale)`.
        Clustersize is NOT scaled!

        Apparently using the original network size of the paper does not work as good as
        using `size_scale=0.5`.

    """


    def add_parameters(self, traj):
        """Adds all necessary parameters to `traj` container."""
        traj.f_add_parameter(BrianDurationParameter,'simulation.durations.initial_run', 1000*ms,
                             order = 0, comment='Runtime of  the simulation')
        traj.f_add_parameter(BrianDurationParameter,'simulation.durations.measurement_run', 20000*ms,
                             order = 1, comment='Runtime of  the simulation')



class CNFanoFactorComputer(NetworkAnalyser):
    """Computes the FanoFactor if the MonitorAnalyser has extracted data"""

    def add_parameters(self, traj):
        traj.f_add_parameter('analysis.statistics.time_window', 0.1 , 'Time window for FF computation')
        traj.f_add_parameter('analysis.statistics.neuron_ids', tuple(range(500)),
                             comment= 'Neurons to be taken into account to compute FF')

    @staticmethod
    def _compute_fano_factor(spike_table, neuron_id, time_window, start_time, end_time):

        assert(end_time >= start_time+time_window)

        bins = (end_time-start_time)/float(time_window)
        bins = int(np.floor(bins))
        binned_spikes = np.zeros(bins)
        binned_times = np.zeros(bins)

        spike_table_neuron = spike_table[spike_table.neuron==neuron_id]

        for bin in range(bins):
            lower_time = start_time+time_window*bin
            upper_time = start_time+time_window*(bin+1)

            spike_table_interval = spike_table_neuron[spike_table_neuron.spiketimes >= lower_time]
            spike_table_interval = spike_table_interval[spike_table_interval.spiketimes < upper_time]

            spikes = len(spike_table_interval)

            binned_times[bin]=lower_time
            binned_spikes[bin]=spikes


        var = np.var(binned_spikes)
        avg = np.mean(binned_spikes)

        if avg > 0:
            return var/float(avg)
        else:
            return 0

    @staticmethod
    def _compute_mean_fano_factor( neuron_ids, spike_table, time_window, start_time, end_time):

        ffs = np.zeros(len(neuron_ids))

        for idx, neuron_id in enumerate(neuron_ids):
            ff=CNFanoFactorComputer._compute_fano_factor(
                            spike_table, neuron_id, time_window, start_time, end_time)
            ffs[idx]=ff

        mean_ff = np.mean(ffs)
        return mean_ff

    def analyse(self, traj, network, current_subrun, subruns, network_dict):

        #Check if we finished all subruns
        if len(subruns)==0:
            spikes_e = traj.results.monitors.spikes_e
            exc_neurons = traj.parameters.model.N_e

            time_window = traj.parameters.analysis.statistics.time_window
            start_time = float(traj.parameters.simulation.durations.initial_run)
            end_time = start_time+float(traj.parameters.simulation.durations.measurement_run)
            neuron_ids = traj.parameters.analysis.statistics.neuron_ids

            mean_ff = self._compute_mean_fano_factor(
                neuron_ids, spikes_e.spikes, time_window, start_time, end_time)

            traj.f_add_result('statistics.mean_fano_factor', mean_ff, comment='Average Fano '
                                                                      'Factor over all '
                                                                      'exc neurons')

            print 'R_ee: %f, Mean FF: %f' % (traj.R_ee, mean_ff)




class CNMonitorAnalysis(NetworkAnalyser):
    """Helps analysing (ok so far only plots some stuff) a completed network run"""

    @staticmethod
    def add_parameters( traj):
        """Adds a tuple of neuron indices to record from, a folder to plot to
        and whether to show the plots.

        """
        traj.f_add_parameter('analysis.neuron_records',(0,1,100,101),
                             comment='Neuron indices to record from.')
        traj.f_add_parameter('analysis.plot_folder', '../PLOTS/', comment='Folder for plots')
        traj.f_add_parameter('analysis.show_plots', 0, comment='Whether to show plots.')
        traj.f_add_parameter('analysis.make_plots', 1, comment='Whether to make plots.')
        pass


    def pre_build(self, traj, brian_list, network_dict):

        self._pre_build = not _explored_parameters_in_group(traj, traj.parameters.analysis)

        self._pre_build = (self._pre_build and 'neurons_i' in network_dict and
                           'neurons_e' in network_dict)



    def add_to_network(self, traj, network, current_subrun, subruns, network_dict):

         if current_subrun.v_order == 1:
            self._add_monitors(traj, network, network_dict)

    def _add_monitors(self, traj,  network, network_dict):
        """Adds monitors to the network"""

        neurons_e = network_dict['neurons_e']
        neurons_i = network_dict['neurons_i']

        monitor_list = []

        self.spike_monitor = SpikeMonitor(neurons_e, delay=0*ms)
        monitor_list.append(self.spike_monitor)

        self.V_monitor = StateMonitor(neurons_e,'V',
                                              record=list(traj.neuron_records))

        monitor_list.append(self.V_monitor)

        self.I_syn_e_monitor = StateMonitor(neurons_e, 'I_syn_e',
                                            record=list(traj.neuron_records))
        monitor_list.append(self.I_syn_e_monitor)

        self.I_syn_i_monitor = StateMonitor(neurons_e, 'I_syn_i',
                                            record=list(traj.neuron_records))
        monitor_list.append(self.I_syn_i_monitor)


        network.add(*monitor_list)
        network_dict['monitors'] = monitor_list

    def _make_folder(self, traj):
        """Makes a subfolder for plots

        :return: Pathname to print folder

        """

        sub_folder = '%s/%s/' % (traj.v_trajectory_name, traj.v_name)
        print_folder = os.path.join(traj.analysis.plot_folder, sub_folder )
        print_folder = os.path.abspath(print_folder)
        if not os.path.isdir(print_folder):
            os.makedirs(print_folder)

        return print_folder


    def _plot_result(self, traj, result_name):
        """Plots a state variable graph for several neurons into one figure"""
        result = traj.f_get(result_name)
        values = result.values
        varname = result.varname
        unit = result.unit
        times = result.times

        record = result.record

        for idx, celia_neuron in enumerate(record):
            plt.subplot(len(record), 1, idx+1)
            plt.plot(times, values[idx,:])
            if idx==0:
                plt.title('%s' % varname)
            if idx==1:
                plt.ylabel('%s/%s' % ( varname,unit))
            if idx == len(record)-1:
                plt.xlabel('t/ms')




    def _print_graphs(self, traj):
        """Makes some plots and stores them into subfolders"""
        print_folder = self._make_folder(traj)

        # plt.figure()
        # #filename=os.path.join(print_folder,'testfig.png')
        # filename = 'testfig.png'
        # plt.subplot(111)
        # plt.plot([1,2,3],[3,4,5],'o')
        # print 'Test'
        # plt.savefig(filename)
        # plt.close()

        raster_plot(self.spike_monitor, newfigure=True, xlabel='t', ylabel='Exc. Neurons',
                    title='Spike Raster Plot')

        filename=os.path.join(print_folder,'spike.png')

        print filename
        plt.savefig(filename)
        plt.close()

        fig=plt.figure()
        self._plot_result(traj, 'monitors.V')
        filename=os.path.join(print_folder,'V.png')
        print filename
        fig.savefig(filename)
        plt.close()

        plt.figure()
        self._plot_result(traj, 'monitors.I_syn_e')
        filename=os.path.join(print_folder,'I_syn_e.png')
        print filename
        plt.savefig(filename)
        plt.close()

        plt.figure()
        self._plot_result(traj, 'monitors.I_syn_i')
        filename=os.path.join(print_folder,'I_syn_i.png')
        print filename
        plt.savefig(filename)
        plt.close()

        if not traj.analysis.show_plots:
            plt.close('all')
        else:
            plt.show()


    def analyse(self, traj, network, current_subrun, subruns, network_dict):
        if len(subruns)==0:
            self._add_results(traj)

    def _add_results(self, traj):
        """Performs analysis, aka Plotting

        First, extracts results from the monitors and stores them into `traj`.

        Next, uses the extracted data for plots.

        """

        traj.f_add_result(BrianMonitorResult, 'monitors.spikes_e', self.spike_monitor,
                          comment = 'The spiketimes of the excitatory population')

        traj.f_add_result(BrianMonitorResult, 'monitors.V', self.V_monitor,
                          comment = 'Membrane voltage of four neurons from 2 clusters')

        traj.f_add_result(BrianMonitorResult, 'monitors.I_syn_e', self.I_syn_e_monitor,
                          comment = 'I_syn_e of four neurons from 2 clusters')

        traj.f_add_result(BrianMonitorResult, 'monitors.I_syn_i', self.I_syn_i_monitor,
                          comment = 'I_syn_i of four neurons from 2 clusters')

        print 'Plotting'

        if traj.parameters.analysis.make_plots:
            self._print_graphs(traj)




