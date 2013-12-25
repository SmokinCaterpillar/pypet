__author__ = 'Robert Meyer'


import logging
from multiprocessing import Process

from brian import Network, clear, reinit
from brian.units import second




class NetworkComponent(object):
    """Abstract class to define a component of a BRIAN network.

    Can be subclassed to define the construction of NeuronGroups or
    Connections, for instance.

    """

    def add_parameters(self, traj):
        """Adds parameters to `traj`.

        Function called from the :class:`~pypet.brian.network.NetworkManager` to
        define and add parameters to `traj` the trajectory container.

        """
        pass

    def pre_build(self, traj, brian_list, network_dict):
        """Builds network objects before the actual experimental runs.

        Function called from the :class:`~pypet.brian.network.NetworkManager` if
        components can be built before the actual experimental runs or in
        case the network is pre-run.

        :param traj: Trajectory container

        :param brian_list:

            Add BRIAN network objects like NeuronGroups or Connections to this list.
            These objects will be automatically added at the instantiation of the network.

        :param network_dict:

            Add any item to this dictionary that should be shared or accessed by all
            your components and which are not part of the trajectory container.
            It is recommended to also put all items from the `brian_list` into
            the dictionary for completeness.

        """
        pass

    def build(self, traj, brian_list, network_dict):
        """Builds network objects at the beginning of each individual experimental run.

        Function called from the :class:`~pypet.brian.network.NetworkManager`
        at the beginning of every experimental run,

        :param brian_list:

            Add BRIAN network objects like NeuronGroups or Connections to this list.
            These objects will be automatically added at the instantiation of the network
            in case the network was not pre-run.

        :param network_dict:

            Add any item to this dictionary that should be shared or accessed by all
            your components and which are not part of the trajectory container.
            It is recommended to also put all items from the `brian_list` into
            the dictionary for completeness.

        """
        pass

    def add_to_network(self, traj, network, current_subrun, subruns, network_dict):
        """Can add network objects before a specific `subrun`.

        Called by a :class:`~pypet.brian.network.NetworkRunner` before a the
        given `subrun`.

        Potentially one wants to add some BRIAN objects later to the network than
        at the very beginning of an experimental run. For example, a monitor might
        be added at the second subrun after an initial phase that is not supposed
        to be recorded.

        :param traj: Trajectoy container

        :param network:

            `BRIAN network`_ where elements could be added via `add(...)`.

            .. _`BRIAN network`: http://briansimulator.org/docs/reference-network.html

        :param current_subrun:

            :class:`~pypet.brian.parameter.BrianDurationParameter` specifying the very next
            subrun to be simulated.

        :param subruns:

            List of :class:`~pypet.brian.parameter.BrianDurationParameter` objects that are to be run
            after the current subrun.

        :param network_dict:

            Dictionary of items shared by all components.

        """
        pass

    def remove_from_network(self, traj, network, current_subrun, subruns, network_dict):
        """Can remove network objects before a specific `subrun`.

        Called by a :class:`~pypet.brian.network.NetworkRunner` after a
        given `subrun` and shortly after analysis (see
        :class:`~pypet.brian.network.NetworkAnalyser`).

        :param traj: Trajectoy container

        :param network:

            `BRIAN network`_ where elements could be removed via `remove(...)`.

            .. _`BRIAN network`: http://briansimulator.org/docs/reference-network.html

        :param current_subrun:

            :class:`~pypet.brian.parameter.BrianDurationParameter` specifying current subrun that
            was executed shortly before.

        :param subruns:

            List of :class:`~pypet.brian.parameter.BrianDurationParameter` objects that are to be run
            after the current subrun.

        :param network_dict:

            Dictionary of items shared by all components.

        """
        pass

class NetworkAnalyser(NetworkComponent):
    """Specific Network Component that analysis a network experiment.

    Can be subclassed to create components for statistical analysis of a network
    and network monitors.

    """
    def analyse(self, traj, network, current_subrun, subruns, network_dict):
        """Can perform statistical analysis on a given network.

        Called by a :class:`~pypet.brian.network.NetworkRunner` directly after a
        given `subrun`.

        :param traj: Trajectoy container

        :param network: `BRIAN network`_

            .. _`BRIAN network`: http://briansimulator.org/docs/reference-network.html

        :param current_subrun:

            :class:`~pypet.brian.parameter.BrianDurationParameter` specifying current subrun that
            was executed shortly before.

        :param subruns:

            List of :class:`~pypet.brian.parameter.BrianDurationParameter` objects that are to
            be run after the current subrun. Can be deleted or added to change the actual course
            of the experiment.

        :param network_dict:

            Dictionary of items shared by all components.

        """
        pass


class NetworkRunner(NetworkComponent):
    """Specific NetworkComponent to carried out the running of a BRIAN network experiment.

    Can potentially be subclassed to allow the adding of parameters via
    :func:`~pypet.brian.network.NetworkComponent.add_parameters`. These parameters
    should specify an experimental run like :class:~pypet.brian.parameter.BrianDurationParameter`
    to define the order and duration of network subruns.

    :param report:

        How simulation progress should be reported, see also the parameters of
        `run(...)` in a `BRIAN network`_ and the `magic run`_ method.

        .. _`BRIAN network`: http://briansimulator.org/docs/reference-network.html

        .. _`magic run`: http://briansimulator.org/docs/reference-network.html#brian.run

    :param report_period:

        How often progress is reported.

    Can log messages with the attribute `logger` which is initialised in
    :func:`~pypet.brian.network.NetworkRunner.set_logger`.

    """
    def __init__(self, report='text', report_period=10 * second):
        self._report = report
        self._report_period = report_period
        self.set_logger()

    def __getstate__(self):
        """Called for pickling.

        Removes the logger to allow pickling and returns a copy of `__dict__`.

        """
        result = self.__dict__.copy()
        del result['logger'] #pickling does not work with loggers
        return result

    def __setstate__(self, statedict):
        """Called after loading a pickle dump.

        Restores `__dict__` from `statedict` and adds a new logger.

        """
        self.__dict__.update( statedict)
        self.set_logger()

    def set_logger(self):
        """Adds a logger with the name `'pypet.brian.parameter.NetworkRunner'`."""
        self.logger = logging.getLogger('pypet.brian.parameter.NetworkRunner')

    def pre_run_network(self, traj, network,  network_dict, component_list, analyser_list):
        """Runs a network before the actual experiment.

        Called by a :class:`~pypet.brian.network.NetworkManager`.
        Similar to :func:`~pypet.brian.network.NetworkRunner.run_network`.

        Subruns and their durations are extracted from the trajectory. All
        :class:`~pypet.brian.parameter.BrianDurationParameter` instances found under
        `traj.parameters.simulation.pre_durations`. The order is determined from
        the `v_order` attributes.

        :param traj: Trajectory container

        :param network: `BRIAN network`_

            .. `BRIAN network`_: http://briansimulator.org/docs/reference-network.html#brian.Network

        :param network_dict: Dictionary of items shared among all components

        :param component_list: List of :class:`~pypet.brian.network.NetworkComponent` objects

        :param analyser_list: List of :class:`~pypet.brian.network.NetworkAnalyser` objects

        """
        self._run_network(traj, network, network_dict, component_list, analyser_list,
                          pre_run=True)

    def run_network(self, traj, network,  network_dict, component_list, analyser_list):
        """Runs a network in an experimental run.

        Called by a :class:`~pypet.brian.network.NetworkManager`.

        A network run is divided into several subruns which are defined as
        :class:`~pypet.brian.parameter.BrianDurationParameter` instances.

        These subruns are extracted from the trajectory. All
        :class:`~pypet.brian.parameter.BrianDurationParameter` instances found under
        `traj.parameters.simulation.pre_durations`. The order is determined from
        the `v_order` attributes.

        For every subrun the following steps are executed:

        1.  Calling :func:`~pypet.brian.network.NetworkComponent.add_to_network` for every
            every :class:`~pypet.brian.network.NetworkComponent` in the order as
            they were passed to the :class:`pypet.brian.network.NetworkManager`.

        2.  Calling :func:`~pypet.brian.network.NetworkComponent.add_to_network` for every
            every :class:`~pypet.brian.network.NetworkAnalyser` in the order as
            they were passed to the :class:`pypet.brian.network.NetworkManager`.

        3.  Running the `BRIAN network`_ for the duration of the current subrun by calling
            the network's `run` function.

            .. `BRIAN network`_: http://briansimulator.org/docs/reference-network.html#brian.Network


        :param traj: Trajectory container

        :param network: `BRIAN network`_

        :param network_dict: Dictionary of items shared among all components

        :param component_list: List of :class:`~pypet.brian.network.NetworkComponent` objects

        :param analyser_list: List of :class:`~pypet.brian.network.NetworkAnalyser` objects

        .. `BRIAN network`_: http://briansimulator.org/docs/reference-network.html#brian.Network

        """
        self._run_network(traj, network, network_dict, component_list, analyser_list,
                          pre_run=False)

    def _extract_subruns(self, traj, pre_run=False):

        if pre_run:
            if 'parameters.simulation.pre_durations' in traj:
                durations = traj.parameters.simulation.pre_durations
            else:
                return []
        else:
            if 'parameters.simulation.pre_durations' in traj:
                durations = traj.parameters.simulation.durations
            else:
                return []

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

            self.logger.info('Starting subrun `%s`' % current_subrun.v_name)
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
                if traj.v_idx == 0 or self._force_single_core:
                    # We allows allow a the very first run since this by definition
                    # cannot have altered the network configuration
                    if traj.v_idx > 0:
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


