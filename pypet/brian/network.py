__author__ = 'Robert Meyer'


import logging
from multiprocessing import Process

from brian import Network, clear, reinit
from brian.units import second




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
                component.add_to_network(traj, network, current_subrun,  subruns,
                                 network_dict)

            for analyser in analyser_list:
                analyser.add_to_network(traj, network, current_subrun,  subruns,
                                 network_dict)

            self._logger.info('Starting subrun `%s`' % current_subrun.v_name)
            network.run(duration=current_subrun.f_get(), report=self._report,
                              report_period=self._report_period)

            for analyser in analyser_list:
                analyser.analyse( traj, network, current_subrun,  subruns,
                                 network_dict)

            for component in component_list:
                component.remove_from_network(traj, network, current_subrun,  subruns,
                                 network_dict)

            for analyser in analyser_list:
                analyser.remove_from_network( traj, network, current_subrun,  subruns,
                                 network_dict)


def run_network(traj, network_manager):
    network_manager.run_network(traj)


class NetworkManager(object):

    def __init__(self, network_runner, component_list, analyser_list=(),
                 force_single_core=False):
        self._component_list = component_list
        self._network_runner = network_runner
        self._analyser_list = analyser_list
        self._network_dict = {}
        self._brian_list = []
        self._set_logger()
        self._pre_built=False
        self._network = None
        self._force_single_core =force_single_core

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

        self._logger.info('Adding Parameters of Runner')

        self._network_runner.add_parameters(traj)

        self._logger.info('Adding Parameters of Components')

        for component in self._component_list:
            component.add_parameters(traj)

        if self._analyser_list:
            self._logger.info('Adding Parameters of Analysers')

            for analyser in self._analyser_list:
                analyser.add_parameters(traj)

    def pre_build(self, traj):

        self._logger.info('Pre-Building Components')

        for component in self._component_list:
            component.pre_build(traj, self._brian_list, self._network_dict)

        self._logger.info('Pre-Building NetworkRunner')
        self._network_runner.pre_build(traj, self._brian_list, self._network_dict)


        if self._analyser_list:

            self._logger.info('Pre-Building Analysers')

            for analyser in self._analyser_list:
                analyser.pre_build(traj, self._brian_list, self._network_dict)

        self._pre_built = True


    def build(self, traj):

        self._logger.info('Building Components')

        for component in self._component_list:
            component.build(traj, self._brian_list, self._network_dict)

        self._logger.info('Building NetworkRunner')
        self._network_runner.build(traj, self._brian_list, self._network_dict)

        if self._analyser_list:

            self._logger.info('Building Analysers')

            for analyser in self._analyser_list:
                analyser.build(traj, self._brian_list, self._network_dict)


    def pre_run_network(self, traj):

        self.pre_build(traj)

        self._logger.info('\n------------------------\n'
                     'Pre-Running the Network\n'
                     '------------------------')


        self._network = Network(*self._brian_list)
        self._network_runner.pre_run_network( traj, self._network,  self._network_dict,
                                             self._component_list, self._analyser_list)

        self._logger.info('\n-----------------------------\n'
                     'Network Simulation successful\n'
                     '-----------------------------')


    def run_network(self, traj):

        if self._pre_built:
            multiproc = traj.f_get('config.environment.%s.multiproc' % traj.v_environment_name).f_get()
            if multiproc:
                self._run_network(traj)
            else:
                if self._force_single_core:
                    self._logger.warning('Running Single Core Mode. Be aware that the network '
                                         'evolves over ALL your runs and is not reset. '
                                         'Use this setting only for debugging purposes '
                                         'because your results will be not correct in case '
                                         'your trajectory contains more than a single run. ')
                    self._run_network(traj)
                else:
                    raise RuntimeError('You cannot run a pre-built network without multiprocessing.\n'
                                       'The network configuration must be copied either by '
                                       'pickling (using a `multiproc=True` and `use_pool=True` in '
                                       'your environemnt) or by forking ( multiprocessing with '
                                       '`use_pool=False`).\n If your network cannot be pickled use '
                                       'the latter. In order to come close to iterative processing '
                                       'you could use multiprocessing with `ncores=1`.')
        else:
            clear(True,True)
            reinit()
            self._run_network(traj)

    def _run_network(self, traj):

        self.build(traj)

        self._logger.info('\n-------------------\n'
                     'Running the Network\n'
                     '-------------------')

        if (not 'pre_run' in traj.parameters.simulation or
            traj.parameters.simulation.f_get('pre_run', fast_access=True)):

            self._network = Network(*self._brian_list)



        self._network_runner.run_network( traj, self._network,  self._network_dict,
                                             self._component_list, self._analyser_list)

        self._logger.info('\n-----------------------------\n'
                     'Network Simulation successful\n'
                     '-----------------------------')


