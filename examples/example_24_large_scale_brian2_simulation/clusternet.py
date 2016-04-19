"""Module to run the clustered Neural Network Simulations as in Litwin-Kumar & Doiron 2012"""

__author__ = 'Robert Meyer'

import os
import numpy as np
import matplotlib.pyplot as plt

from pypet.trajectory import Trajectory
from pypet.brian2.parameter import Brian2Parameter, Brian2MonitorResult
from pypet.brian2.network import NetworkComponent, NetworkRunner, NetworkAnalyser

from brian2 import NeuronGroup, rand, Synapses, Equations, SpikeMonitor, StateMonitor, ms


def _explored_parameters_in_group(traj, group_node):
    """Checks if one the parameters in `group_node` is explored.

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


        traj.v_standard_parameter = Brian2Parameter

        model_eqs = '''dV/dt= 1.0/tau_POST * (mu - V) + I_syn : 1
                       mu : 1
                       I_syn =  - I_syn_i + I_syn_e : Hz
                    '''

        conn_eqs = '''I_syn_PRE = x_PRE/(tau2_PRE-tau1_PRE) : Hz
                      dx_PRE/dt = -(normalization_PRE*y_PRE+x_PRE)*invtau1_PRE : 1
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

        traj.f_add_parameter('model.V_th', 'V >= 1.0', comment = "Threshold value")
        traj.f_add_parameter('model.reset_func', 'V=0.0',
                             comment = "String representation of reset function")
        traj.f_add_parameter('model.refractory', 5*ms, comment = "Absolute refractory period")

        traj.f_add_parameter('model.N_e', int(2000*scale), comment = "Amount of excitatory neurons")
        traj.f_add_parameter('model.N_i', int(500*scale), comment = "Amount of inhibitory neurons")

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

                tau1 = traj.model.synaptic['tau1']
                tau2 = traj.model.synaptic['tau2_'+name_pre]

                normalization = (tau1-tau2) / tau2
                invtau1=1.0/tau1
                invtau2 = 1.0/tau2

                variables_dict['invtau1_'+name_pre] = invtau1
                variables_dict['invtau2_'+name_pre] = invtau2
                variables_dict['normalization_'+name_pre] = normalization
                variables_dict['tau1_'+name_pre] = tau1
                variables_dict['tau2_'+name_pre] = tau2

            variables_dict['tau_'+name_post] = traj.model['tau_'+name_post]

            post_eqs[name_post] = Equations(new_model_eqs, **variables_dict)

        return post_eqs

    def pre_build(self, traj, brian_list, network_dict):
        """Pre-builds the neuron groups.

        Pre-build is only performed if none of the
        relevant parameters is explored.

        :param traj: Trajectory container

        :param brian_list:

            List of objects passed to BRIAN network constructor.

            Adds:

            Inhibitory neuron group

            Excitatory neuron group

        :param network_dict:

            Dictionary of elements shared among the components

            Adds:

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

            Adds:

            Inhibitory neuron group

            Excitatory neuron group

        :param network_dict:

            Dictionary of elements shared among the components

            Adds:

            'neurons_i': Inhibitory neuron group

            'neurons_e': Excitatory neuron group

        """
        if not hasattr(self, '_pre_build') or not self._pre_build:
            self._build_model(traj, brian_list, network_dict)


    def _build_model(self, traj, brian_list, network_dict):
        """Builds the neuron groups from `traj`.

        Adds the neuron groups to `brian_list` and `network_dict`.

        """

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
                              method='Euler')

        # Create excitatory neurons
        eqs_e = eqs_dict['e']
        neurons_e = NeuronGroup(N=model.N_e,
                              model = eqs_e,
                              threshold=model.V_th,
                              reset=model.reset_func,
                              refractory=model.refractory,
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

        traj.v_standard_parameter = Brian2Parameter
        scale = traj.simulation.scale

        traj.f_add_parameter('connections.R_ee', 1.0, comment='Scaling factor for clustering')

        traj.f_add_parameter('connections.clustersize_e', 100, comment='Size of a cluster')
        traj.f_add_parameter('connections.strength_factor', 2.5,
                             comment='Factor for scaling cluster weights')

        traj.f_add_parameter('connections.p_ii', 0.25,
                            comment='Connection probability from inhibitory to inhibitory' )
        traj.f_add_parameter('connections.p_ei', 0.25,
                            comment='Connection probability from inhibitory to excitatory' )
        traj.f_add_parameter('connections.p_ie', 0.25,
                            comment='Connection probability from excitatory to inhibitory' )
        traj.f_add_parameter('connections.p_ee', 0.1,
                            comment='Connection probability from excitatory to excitatory' )

        traj.f_add_parameter('connections.J_ii', 0.027/np.sqrt(scale),
                             comment='Connection strength from inhibitory to inhibitory')
        traj.f_add_parameter('connections.J_ei', 0.032/np.sqrt(scale),
                             comment='Connection strength from inhibitory to excitatroy')
        traj.f_add_parameter('connections.J_ie', 0.009/np.sqrt(scale),
                             comment='Connection strength from excitatory to inhibitory')
        traj.f_add_parameter('connections.J_ee', 0.012/np.sqrt(scale),
                             comment='Connection strength from excitatory to excitatory')


    def pre_build(self, traj, brian_list, network_dict):
        """Pre-builds the connections.

        Pre-build is only performed if none of the
        relevant parameters is explored and the relevant neuron groups
        exist.

        :param traj: Trajectory container

        :param brian_list:

            List of objects passed to BRIAN network constructor.

            Adds:

            Connections, amount depends on clustering

        :param network_dict:

            Dictionary of elements shared among the components

            Expects:

            'neurons_i': Inhibitory neuron group

            'neurons_e': Excitatory neuron group

            Adds:

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

            Adds:

            Connections, amount depends on clustering

        :param network_dict:

            Dictionary of elements shared among the components

            Expects:

            'neurons_i': Inhibitory neuron group

            'neurons_e': Excitatory neuron group

            Adds:

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

        print('Connecting ii')
        self.conn_ii = Synapses(neurons_i,neurons_i, on_pre='y_i += %f' % connections.J_ii)
        self.conn_ii.connect('i != j', p=connections.p_ii)

        print('Connecting ei')
        self.conn_ei = Synapses(neurons_i,neurons_e, on_pre='y_i += %f' % connections.J_ei)
        self.conn_ei.connect('i != j', p=connections.p_ei)

        print('Connecting ie')
        self.conn_ie = Synapses(neurons_e,neurons_i, on_pre='y_e += %f' % connections.J_ie)
        self.conn_ie.connect('i != j', p=connections.p_ie)

        conns_list = [self.conn_ii, self.conn_ei, self.conn_ie]


        if connections.R_ee > 1.0:
            # If we come here we want to create clusters

            cluster_list=[]
            cluster_conns_list=[]
            model=traj.model

            # Compute the number of clusters
            clusters = int(model.N_e/connections.clustersize_e)
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
                print('Connecting ee cluster #%d of %d' % (irun, clusters))
                conn = Synapses(cluster,cluster,
                                on_pre='y_e += %f' % (connections.J_ee*connections.strength_factor))
                conn.connect('i != j', p=p_in)
                cluster_conns_list.append(conn)

                # Connections reaching out from cluster
                # A cluster consists of `clustersize_e` neurons with consecutive indices.
                # So usually the outside world consists of two groups, neurons with lower
                # indices than the cluster indices, and neurons with higher indices.
                # Only the clusters at the index boundaries project to neurons with only either
                # lower or higher indices
                if low_index > 0:
                    rest_low = neurons_e[0:low_index]
                    print('Connecting cluster with other neurons of lower index')
                    low_conn = Synapses(cluster,rest_low,
                                on_pre='y_e += %f' % connections.J_ee)
                    low_conn.connect('i != j', p=p_out)

                    cluster_conns_list.append(low_conn)

                if high_index < model.N_e:
                    rest_high = neurons_e[high_index:model.N_e]
                    print('Connecting cluster with other neurons of higher index')

                    high_conn = Synapses(cluster,rest_high,
                                on_pre='y_e += %f' % connections.J_ee)
                    high_conn.connect('i != j', p=p_out)

                    cluster_conns_list.append(high_conn)

                low_index=high_index
                high_index+=connections.clustersize_e

            self.cluster_conns=cluster_conns_list
            conns_list+=cluster_conns_list
        else:
            # Here we don't cluster and connection probabilities are homogeneous
            print('Connectiong ee')

            self.conn_ee = Synapses(neurons_e,neurons_e,
                                on_pre='y_e += %f' % connections.J_ee)
            self.conn_ee.connect('i != j', p=connections.p_ee)

            conns_list.append(self.conn_ee)


        # Add the connections to the `brian_list` and the network dict
        brian_list.extend(conns_list)
        network_dict['connections'] = conns_list


class CNNetworkRunner(NetworkRunner):
    """Runs the network experiments.

    Adds two BrianParameters, one for an initial run, and one for a run
    that is actually measured.

    """


    def add_parameters(self, traj):
        """Adds all necessary parameters to `traj` container."""
        par= traj.f_add_parameter(Brian2Parameter,'simulation.durations.initial_run', 500*ms,
                             comment='Initialisation run for more realistic '
                                            'measurement conditions.')

        par.v_annotations.order=0
        par=traj.f_add_parameter(Brian2Parameter,'simulation.durations.measurement_run', 1500*ms,
                             comment='Measurement run that is considered for '
                                                'statistical evaluation')
        par.v_annotations.order=1



class CNFanoFactorComputer(NetworkAnalyser):
    """Computes the FanoFactor if the MonitorAnalyser has extracted data"""

    def add_parameters(self, traj):
        traj.f_add_parameter('analysis.statistics.time_window', 100*ms , 'Time window for FF computation')
        traj.f_add_parameter('analysis.statistics.neuron_ids', tuple(range(500)),
                             comment= 'Neurons to be taken into account to compute FF')

    @staticmethod
    def _compute_fano_factor(spike_res, neuron_id, time_window, start_time, end_time):
        """Computes Fano Factor for one neuron.

        :param spike_res:

            Result containing the spiketimes of all neurons

        :param neuron_id:

            Index of neuron for which FF is computed

        :param time_window:

            Length of the consecutive time windows to compute the FF

        :param start_time:

            Start time of measurement to consider

        :param end_time:

            End time of measurement to consider

        :return:

            Fano Factor (float) or
            returns 0 if mean firing activity is 0.

        """
        assert(end_time >= start_time+time_window)

        # Number of time bins
        bins = (end_time-start_time)/time_window
        bins = int(np.floor(bins))

        # Arrays for binning of spike counts
        binned_spikes = np.zeros(bins)

        # DataFrame only containing spikes of the particular neuron
        spike_array_neuron = spike_res.t[spike_res.i==neuron_id]

        for bin in range(bins):
            # We iterate over the bins to calculate the spike counts
            lower_time = start_time+time_window*bin
            upper_time = start_time+time_window*(bin+1)

            # Filter the spikes
            spike_array_interval = spike_array_neuron[spike_array_neuron >= lower_time]
            spike_array_interval = spike_array_interval[spike_array_interval < upper_time]

            # Add count to bins
            spikes = len(spike_array_interval)
            binned_spikes[bin]=spikes


        var = np.var(binned_spikes)
        avg = np.mean(binned_spikes)

        if avg > 0:
            return var/float(avg)
        else:
            return 0

    @staticmethod
    def _compute_mean_fano_factor( neuron_ids, spike_res, time_window, start_time, end_time):
        """Computes average Fano Factor over many neurons.

        :param neuron_ids:

            List of neuron indices to average over

        :param spike_res:

            Result containing all the spikes

        :param time_window:

            Length of the consecutive time windows to compute the FF

        :param start_time:

            Start time of measurement to consider

        :param end_time:

            End time of measurement to consider

        :return:

            Average fano factor

        """
        ffs = np.zeros(len(neuron_ids))

        for idx, neuron_id in enumerate(neuron_ids):
            ff=CNFanoFactorComputer._compute_fano_factor(
                            spike_res, neuron_id, time_window, start_time, end_time)
            ffs[idx]=ff

        mean_ff = np.mean(ffs)
        return mean_ff

    def analyse(self, traj, network, current_subrun, subrun_list, network_dict):
        """Calculates average Fano Factor of a network.

        :param traj:

            Trajectory container

            Expects:

            `results.monitors.spikes_e`: Data from SpikeMonitor for excitatory neurons

            Adds:

            `results.statistics.mean_fano_factor`: Average Fano Factor

        :param network:

            The BRIAN network

        :param current_subrun:

            BrianParameter

        :param subrun_list:

            Upcoming subruns, analysis is only performed if subruns is empty,
            aka the final subrun has finished.

        :param network_dict:

            Dictionary of items shared among componetns

        """
        #Check if we finished all subruns
        if len(subrun_list)==0:
            spikes_e = traj.results.monitors.spikes_e

            time_window = traj.parameters.analysis.statistics.time_window
            start_time = traj.parameters.simulation.durations.initial_run
            end_time = start_time+traj.parameters.simulation.durations.measurement_run
            neuron_ids = traj.parameters.analysis.statistics.neuron_ids

            mean_ff = self._compute_mean_fano_factor(
                neuron_ids, spikes_e, time_window, start_time, end_time)

            traj.f_add_result('statistics.mean_fano_factor', mean_ff, comment='Average Fano '
                                                                      'Factor over all '
                                                                      'exc neurons')

            print('R_ee: %f, Mean FF: %f' % (traj.R_ee, mean_ff))


class CNMonitorAnalysis(NetworkAnalyser):
    """Adds monitors for recoding and plots the monitor output."""

    @staticmethod
    def add_parameters( traj):
        traj.f_add_parameter('analysis.neuron_records',(0,1,100,101),
                             comment='Neuron indices to record from.')
        traj.f_add_parameter('analysis.plot_folder',
                             os.path.join('experiments', 'example_24', 'PLOTS'),
                             comment='Folder for plots')
        traj.f_add_parameter('analysis.show_plots', 0, comment='Whether to show plots.')
        traj.f_add_parameter('analysis.make_plots', 1, comment='Whether to make plots.')

    def add_to_network(self, traj, network, current_subrun, subrun_list, network_dict):
        """Adds monitors to the network if the measurement run is carried out.

        :param traj: Trajectory container

        :param network: The BRIAN network

        :param current_subrun: BrianParameter

        :param subrun_list: List of coming subrun_list

        :param network_dict:

            Dictionary of items shared among the components

            Expects:

            'neurons_e': Excitatory neuron group

            Adds:

            'monitors': List of monitors

                0. SpikeMonitor of excitatory neurons

                1. StateMonitor of membrane potential of some excitatory neurons
                (specified in `neuron_records`)

                2. StateMonitor of excitatory synaptic currents of some excitatory neurons

                3. State monitor of inhibitory currents of some excitatory neurons

        """
        if current_subrun.v_annotations.order == 1:
            self._add_monitors(traj, network, network_dict)

    def _add_monitors(self, traj,  network, network_dict):
        """Adds monitors to the network"""

        neurons_e = network_dict['neurons_e']

        monitor_list = []

        # Spiketimes
        self.spike_monitor = SpikeMonitor(neurons_e)
        monitor_list.append(self.spike_monitor)

        # Membrane Potential
        self.V_monitor = StateMonitor(neurons_e,'V',
                                              record=list(traj.neuron_records))

        monitor_list.append(self.V_monitor)

        # Exc. syn .Current
        self.I_syn_e_monitor = StateMonitor(neurons_e, 'I_syn_e',
                                            record=list(traj.neuron_records))
        monitor_list.append(self.I_syn_e_monitor)

        # Inh. syn. Current
        self.I_syn_i_monitor = StateMonitor(neurons_e, 'I_syn_i',
                                            record=list(traj.neuron_records))
        monitor_list.append(self.I_syn_i_monitor)

        # Add monitors to network and dictionary
        network.add(*monitor_list)
        network_dict['monitors'] = monitor_list

    def _make_folder(self, traj):
        """Makes a subfolder for plots.

        :return: Path name to print folder

        """
        print_folder = os.path.join(traj.analysis.plot_folder,
                                    traj.v_name, traj.v_crun)
        print_folder = os.path.abspath(print_folder)
        if not os.path.isdir(print_folder):
            os.makedirs(print_folder)

        return print_folder

    def _plot_result(self, traj, result_name):
        """Plots a state variable graph for several neurons into one figure"""
        result = traj.f_get(result_name)
        varname = result.record_variables[0]
        values = result[varname]
        times = result.t

        record = result.record

        for idx, celia_neuron in enumerate(record):
            plt.subplot(len(record), 1, idx+1)
            plt.plot(times, values[idx,:])
            if idx==0:
                plt.title('%s' % varname)
            if idx==1:
                plt.ylabel('%s' % ( varname))
            if idx == len(record)-1:
                plt.xlabel('t')

    def _print_graphs(self, traj):
        """Makes some plots and stores them into subfolders"""
        print_folder = self._make_folder(traj)

        # If we use BRIAN's own raster_plot functionality we
        # need to sue the SpikeMonitor directly
        plt.figure()
        plt.scatter(self.spike_monitor.t, self.spike_monitor.i, s=1)
        plt.xlabel('t')
        plt.ylabel('Exc. Neurons')
        plt.title('Spike Raster Plot')

        filename=os.path.join(print_folder,'spike.png')

        print('Current plot: %s ' % filename)
        plt.savefig(filename)
        plt.close()

        fig=plt.figure()
        self._plot_result(traj, 'monitors.V')
        filename=os.path.join(print_folder,'V.png')
        print('Current plot: %s ' % filename)
        fig.savefig(filename)
        plt.close()

        plt.figure()
        self._plot_result(traj, 'monitors.I_syn_e')
        filename=os.path.join(print_folder,'I_syn_e.png')
        print('Current plot: %s ' % filename)
        plt.savefig(filename)
        plt.close()

        plt.figure()
        self._plot_result(traj, 'monitors.I_syn_i')
        filename=os.path.join(print_folder,'I_syn_i.png')
        print('Current plot: %s ' % filename)
        plt.savefig(filename)
        plt.close()

        if not traj.analysis.show_plots:
            plt.close('all')
        else:
            plt.show()


    def analyse(self, traj, network, current_subrun, subrun_list, network_dict):
        """Extracts monitor data and plots.

        Data extraction is done if all subruns have been completed,
        i.e. `len(subrun_list)==0`

        First, extracts results from the monitors and stores them into `traj`.

        Next, uses the extracted data for plots.

        :param traj:

            Trajectory container

            Adds:

            Data from monitors

        :param network: The BRIAN network

        :param current_subrun: BrianParameter

        :param subrun_list: List of coming subruns

        :param network_dict: Dictionary of items shared among all components

        """
        if len(subrun_list)==0:

            traj.f_add_result(Brian2MonitorResult, 'monitors.spikes_e', self.spike_monitor,
                              comment = 'The spiketimes of the excitatory population')

            traj.f_add_result(Brian2MonitorResult, 'monitors.V', self.V_monitor,
                              comment = 'Membrane voltage of four neurons from 2 clusters')

            traj.f_add_result(Brian2MonitorResult, 'monitors.I_syn_e', self.I_syn_e_monitor,
                              comment = 'I_syn_e of four neurons from 2 clusters')

            traj.f_add_result(Brian2MonitorResult, 'monitors.I_syn_i', self.I_syn_i_monitor,
                              comment = 'I_syn_i of four neurons from 2 clusters')

            print('Plotting')

            if traj.parameters.analysis.make_plots:
                self._print_graphs(traj)




