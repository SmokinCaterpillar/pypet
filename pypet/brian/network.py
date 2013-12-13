__author__ = 'Robert Meyer'


import logging
import copy

from brian import Network, clear
from brian.units import second

from pypet.brian.parameter import BrianParameter



class NetworkComponent(object):

    def add_parameters(self, traj):
        pass

    def pre_build(self, traj, brian_list, network_dict):
        pass

    def build(self, traj, brian_list, network_dict):
        pass

    def add_to_network(self, traj, network, current_subrun, subruns, network_dict):
        pass

    def remove_from_network(self, traj, network, current_subrun, subruns, network_dict):
        pass


class NetworkAnalyser(NetworkComponent):

    def analyse(self, traj, network, current_subrun, subruns, network_dict):
        pass


class NetworkRunner(NetworkComponent):

    def __init__(self, report='text', report_period=10 * second):
        self._report = report
        self._report_period = report_period
        self._set_logger()

    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger'] #pickling does not work with loggers
        return result

    def __setstate__(self, statedict):
        self.__dict__.update( statedict)
        self._set_logger()

    def _set_logger(self):
        self._logger = logging.getLogger('pypet.brian.parameter.NetworkRunner')

    def pre_run_network(self, traj, network,  network_dict, component_list, analyser_list):
        self._run_network(traj, network, network_dict, component_list, analyser_list,
                          pre_run=True)

    def run_network(self, traj, network,  network_dict, component_list, analyser_list):

        if ('pre_run' in traj.parameters.simulation and
                traj.parameters.simulation.f_get('pre_run', fast_access=True)):

            if not traj.config.f_get(traj.v_environment_name+'.multiproc', fast_access=True):
                # We need to remember the old network to get back the original state
                copied_items = copy.deepcopy(
                    [network, network_dict, component_list, analyser_list])

                self._run_network(traj, *copied_items)
                return

        self._run_network(traj, network, network_dict, component_list, analyser_list,
                          pre_run=False)

    def _extract_subruns(self, traj, pre_run=False):

        if pre_run:
            durations = traj.parameters.simulation.pre_durations
        else:
            durations = traj.parameters.simulation.durations

        subruns = {}
        orders = []
        for duration_param in durations.f_iter_leaves():
            order = duration_param.v_order
            if order in subruns:
                raise RuntimeError('Your durations must differ in their order, there are two '
                                   'with order %d.' % order)
            else:
                subruns[order]=duration_param
                orders.append(order)

        return [subruns[order] for order in sorted(orders)]

    def _run_network(self, traj, network, network_dict, component_list,
                     analyser_list, pre_run=False):


        subruns = self._extract_subruns(traj, pre_run=pre_run)

        while len(subruns)>0:

            current_subrun= subruns.pop(0)

            for component in component_list:
                component.add_to_network(self, traj, network, current_subrun,  subruns,
                                 network_dict)

            for analyser in analyser_list:
                analyser.add_to_network(self, traj, network, current_subrun,  subruns,
                                 network_dict)

            network.run(duration=current_subrun.f_get(), report=self._report,
                              report_period=self._report_period)

            for analyser in analyser_list:
                analyser.analyse(self, traj, network, current_subrun,  subruns,
                                 network_dict)

            for component in component_list:
                component.remove_from_network(self, traj, network, current_subrun,  subruns,
                                 network_dict)

            for analyser in self.analyser_list:
                analyser.remove_from_network(self, traj, network, current_subrun,  subruns,
                                 network_dict)



def run_network(traj, network_manager):
    network_manager.run_network(traj)


class NetworkManager(object):

    def __init__(self, network_runner, component_list, analyser_list=()):
        self._component_list = component_list
        self._network_runner = network_runner
        self._analyser_list = analyser_list
        self._network_dict = {}
        self._brian_list = []
        self._set_logger()

    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger'] #pickling does not work with loggers
        return result

    def __setstate__(self, statedict):
        self.__dict__.update( statedict)
        self._set_logger()


    def _set_logger(self):
        self._logger = logging.getLogger('pypet.brian.parameter.NetworkManager')

    def add_parameters(self, traj):

        self._logger.info('Adding Parameters of Components')

        for component in self._component_list:
            component.add_parameters(traj)

        self._network_runner.add_parameters(traj)

        if self._analyser_list:
            self._logger.info('Adding Parameters of Analysers')

            for analyser in self._analyser_list:
                analyser.add_parameters(traj)

    def pre_build(self, traj):

        self._logger('Pre-Building Components')

        for component in self._component_list:
            component.pre_build(traj, self._brian_list, self._network_dict)

        self._logger('Pre-Building NetworkRunner')
        self._network_runner.pre_build(traj, self._brian_list, self._network_dict)


        if self._analyser_list:

            self._logger.info('Pre-Building Analysers')

            for analyser in self._analyser_list:
                analyser.pre_build(traj, self._brian_list, self._network_dict)

        self._network = Network(**self._network_dict)


    def build(self, traj):

        self._logger('Building Components')

        for component in self._component_list:
            component.build(traj, self._brian_list, self._network_dict)

        self._logger('Building NetworkRunner')
        self._network_runner.build(traj, self._brian_list, self._network_dict)



        if self._analyser_list:

            self._logger.info('Pre-Building Analysers')

            for analyser in self._analyser_list:
                analyser.build(traj, self._brian_list, self._network_dict)


    def pre_run_network(self, traj):

        self.pre_build(traj)

        self._logger('------------------------\n'
                     'Pre-Running the Network\n'
                     '------------------------')

        self._network = Network(*self._brian_list)
        self._network_runner.pre_run_network(self, traj, self._network,  self._network_dict,
                                             self._component_list, self._analyser_list)

        self._logger('-----------------------------\n'
                     'Network Simulation successful\n'
                     '-----------------------------')



    def run_network(self, traj):

        self.build(traj)

        self._logger('-------------------\n'
                     'Running the Network\n'
                     '-------------------')

        if (not 'pre_run' in traj.parameters.simulation or
            traj.parameters.simulation.f_get('pre_run', fast_access=True)):
            self._network = Network(*self._brian_list)

        self._network_runner.run_network(self, traj, self._network,  self._network_dict,
                                             self._component_list, self._analyser_list)

        self._logger('-----------------------------\n'
                     'Network Simulation successful\n'
                     '-----------------------------')

