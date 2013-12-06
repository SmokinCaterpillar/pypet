__author__ = 'Robert Meyer'


import logging
from brian import Network
from brian.units import second

from pypet.brian.parameter import BrianParameter



class NetworkComponent(object):

    def add_parameters(self, traj):
        raise NotImplementedError('You have to implement this')

    def pre_build(self, traj, network_dict, misc_dict):
        raise NotImplementedError('You have to implement this')

    def build(self, traj, network_dict, misc_dict):
        raise NotImplementedError('You have to implement this')


class NetworkAnalyser(NetworkComponent):

    def analyse(self, traj, network_dict, misc_dict):
        raise NotImplementedError('You have to implement this')

    def add_to_network(self, traj, network_dict, misc_dict, network)



class SubRunAnalyser


class NetworkRunner(NetworkComponent):

    def run_network(self, traj, network_dict, misc_dict, analyser_list):
        raise NotImplementedError('You have to implement this')


class SimpleNetworkRunner(NetworkRunner):

    def __init__(self, duration, report=None, report_period=10 * second):
        self._duration = duration
        self._report=report
        self._report_period=report_period

    def add_parameters(self, traj):
        old_standard_param = traj.v_standard_parameter
        traj.f_add_parameter('simulation.duration' ,
                                 self._duration,
                                 comment = 'Duration of simulation')

        traj.v_standard_parameter = old_standard_param

    def pre_build(self, traj, network_dict, misc_dict):

        if 'parameters.simulation.pre_build_network' in traj:
            if traj.parameters.simulation.f_get('pre_build_network').f_get():
                self._network=Network(**network_dict)

    def build(self, traj, network_dict, misc_dict):

        if 'parameters.simulation.pre_build_network' in traj:
            if traj.parameters.simulation.f_get('pre_build_network').f_get():
                return


        self._network = Network(**network_dict)


    def run_network(self, traj, network_dict, misc_dict, analyser_list):

        duration = traj.parameters.simulation.f_get('duration').f_get()
        self._network.run(duration,
                          report = self._report,
                          report_period=self._report_period)

        for analyser in analyser_list:
            analyser.analyse(traj, network_dict, misc_dict)



class GeneralNetworkRunner(SimpleNetworkRunner):

    def __init__(self, durations_dict, report=None, report_period=10 * second):
        self._durations_dict=durations_dict
        self._report = report
        self._report_period = report_period

    def add_parameters(self, traj):
        """Adds durations to the trajectory.


        Under traj.parameters.durations.name_of_subrun
        """
        old_standard_param = traj.v_standard_parameter

        if traj.v_standard_parameter is not BrianParameter:
            traj.v_standard_parameter = BrianParameter

        for subrun_name in self._durations_dict:
            duration = self._durations_dict[subrun_name]

            traj.f_add_parameter('simulation.durations.%s' % subrun_name,
                                 duration,
                                 comment = 'Duration of run %s.' % subrun_name)

        traj.v_standard_parameter = old_standard_param


    def run_network(self, traj, network_dict, misc_dict, analyser_list):

        duration = traj.parameters.simulation.f_get('duration').f_get()
        self._network.run(duration,
                          report = self._report,
                          report_period=self._report_period)

        for analyser in analyser_list:
            analyser.analyse(traj, network_dict, misc_dict)


def run_network(traj, network_manager):
    network_manager.run_network(traj)




class NetworkManager(object):

    def __init__(self, network_runner, component_list, analyser_list=()):
        self._component_list = component_list
        self._network_runner = network_runner
        self._analyser_list = analyser_list
        self._network_dict = {}
        self._misc_dict = {}
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


        self._logger.info('Adding Parameters of Network Runner')

        self._network_runner.add_parameters(traj)


        if self._analyser_list:
            self._logger.info('Adding Parameters of Analysers')

            for analyser in self._analyser_list:
                analyser.add_parameters(traj)

    def pre_build(self, traj):

        self._logger('Pre-Building Components')

        for component in self._component_list:
            component.pre_build(traj, self._network_dict, self._misc_dict)

        self._logger('Pre-Building Network Runner')
        self._network_runner.pre_build(traj, self._network_dict, self._misc_dict)


        if self._analyser_list:

            self._logger.info('Pre-Building Analysers')

            for analyser in self._analyser_list:
                analyser.pre_build(traj, self._network_dict, self._misc_dict)


    def build(self, traj):

        self._logger('Building Components')

        for component in self._component_list:
            component.build(traj, self._network_dict, self._misc_dict)

        self._logger('Building NetworkRunner')

        self._network_runner.build(traj, self._network_dict, self._misc_dict)

        if self._analyser_list:

            self._logger.info('Pre-Building Analysers')

            for analyser in self._analyser_list:
                analyser.build(traj, self._network_dict, self._misc_dict)


    def run_network(self, traj):

        self.build(traj)

        self._logger('-------------------\n'
                     'Running the Network\n'
                     '-------------------')
        self._network_runner.run_network(traj, self._network_dict, self._misc_dict,
                                         self._analyser_list)

        self._logger('-----------------------------\n'
                     'Network Simulation successful\n'
                     '-----------------------------')

