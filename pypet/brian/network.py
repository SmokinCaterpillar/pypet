"""Module for easy compartmental implementation of a `BRIAN network`_.

Build parts of a network via subclassing :class:`~pypet.brian.network.NetworkComponent` and
:class:`~pypet.brian.network.NetworkAnalyser` for recording and statistical analysis.

Specify a :class:`~pypet.brian.network.NetworkRunner` (subclassing optionally) that handles
the execution of your experiment in different subruns. Subruns can be defined
as :class:`~pypet.brian.parameter.BrianDurationParameter` instances added to
`traj.parameters.simulation.durations` or `traj.parameters.simulation.pre_durations` for
pre runs, respectively.

The creation and management of a `BRIAN network`_ is handled by the
:class:`~pypet.brian.network.NetworkManager` (no need for subclassing). Pass your
components, analyser and your runner to the manager.

Pass the ;func:`~pypet.brian.network.run_network` function together with a
:class:`~pypet.brian.network.NetworkManager` to your main environment function
:func:`~pypet.environment.Environment.f_run` to start a simulation and parallel
parameter exploration. Be aware that successful parameter exploration
requires parallel processing (see :class:`~pypet.brian.network.NetworkManager`).


.. _`BRIAN network`: http://briansimulator.org/docs/reference-network.html

"""

__author__ = 'Robert Meyer'

import logging

from brian import Network, clear, reinit
from brian.units import second


def run_network(traj, network_manager):
    """Top-level simulation function, pass this together with a NetworkManager to the environment.

    :param traj: Trajectory container

    :param network_manager: :class:`~pypet.brian.network.NetworkManager` instance

        *   Creates a `BRIAN network`_.

        *   Manages all :class:`~pypet.brian.network.NetworkComponent` instances,
            all :class:`~pypet.brian.network.NetworkAnalyser` and a single
            :class:`~pypet.brian.network.NetworkRunner`.

        .. _`BRIAN network`: http://briansimulator.org/docs/reference-network.html

    """
    network_manager.run_network(traj)


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
            These objects will be automatically added at the instantiation of the network
            via `Network(*brian_list)` (see the `BRIAN network class`_).

            .. _`BRIAN network class`: http://briansimulator.org/docs/reference-network.html#brian.Network


        :param network_dict:

            Add any item to this dictionary that should be shared or accessed by all
            your components and which are not part of the trajectory container.
            It is recommended to also put all items from the `brian_list` into
            the dictionary for completeness.


        For convenience I would recommend documenting the implementation of `build` and
        `pre-build` and so on in the subclass like the following. Use statements like `Adds`
        for items that are added to the list and the dict and statements like `Expects`
        for what is needed to be part of the `network_dict` in order to build the
        current component.

            brian_list:

                Adds:

                4 Connections, between all types of neurons (e->e, e->i, i->e, i->i)

            network_dict:

                Expects:

                'neurons_i': Inhibitory neuron group

                'neurons_e': Excitatory neuron group


                Adds:

                4 Connections, between all types of neurons (e->e, e->i, i->e, i->i)

        """
        pass

    def build(self, traj, brian_list, network_dict):
        """Builds network objects at the beginning of each individual experimental run.

        Function called from the :class:`~pypet.brian.network.NetworkManager`
        at the beginning of every experimental run,

        :param brian_list:

            Add BRIAN network objects like NeuronGroups or Connections to this list.
            These objects will be automatically added at the instantiation of the network
            in case the network was not pre-run
            via `Network(*brian_list)` (see the `BRIAN network class`_).

            .. _`BRIAN network class`: http://briansimulator.org/docs/reference-network.html#brian.Network


        :param network_dict:

            Add any item to this dictionary that should be shared or accessed by all
            your components and which are not part of the trajectory container.
            It is recommended to also put all items from the `brian_list` into
            the dictionary for completeness.


        For convenience I would recommend documenting the implementation of `build` and
        `pre-build` and so on in the subclass like the following. Use statements like `Adds`
        for items that are added to the list and the dict and statements like `Expects`
        for what is needed to be part of the `network_dict` in order to build the
        current component.

            brian_list:

                Adds:

                4 Connections, between all types of neurons (e->e, e->i, i->e, i->i)

            network_dict:

                Expects:

                'neurons_i': Inhibitory neuron group

                'neurons_e': Excitatory neuron group


                Adds:

                4 Connections, between all types of neurons (e->e, e->i, i->e, i->i)
                'conn_ee`, 'conn_ie', 'conn_ei', 'conn_ii'.

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
    """Specific NetworkComponent that analysis a network experiment.

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
    """Specific NetworkComponent to carry out the running of a BRIAN network experiment.

    A NetworRunner only handles the execution of a network simulation, the `BRIAN network`_ is
    created by a :class:`~pypet.brian.network.NetworkManager`.

    Can potentially be subclassed to allow the adding of parameters via
    :func:`~pypet.brian.network.NetworkComponent.add_parameters`. These parameters
    should specify an experimental run with a :class:~pypet.brian.parameter.BrianDurationParameter`
    to define the order and duration of network subruns. For the actual experimental runs,
    all subruns must be stored in `traj.parameters.simulation.durations`. For a pre-run
    the subruns must be stored in `traj.parameters.simulation.pre_durations`.

    :param report:

        How simulation progress should be reported, see also the parameters of
        `run(...)` in a `BRIAN network`_ and the `magic run`_ method.

        .. _`BRIAN network`: http://briansimulator.org/docs/reference-network.html

        .. _`magic run`: http://briansimulator.org/docs/reference-network.html#brian.run

    :param report_period:

        How often progress is reported. If not specified 10 seconds is chosen.

    Can log messages with the attribute `logger` which is initialised in
    :func:`~pypet.brian.network.NetworkRunner.set_logger`.

    """
    def __init__(self, report='text', report_period=None):

        if report_period is None:
            report_period=10 * second

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
        the `v_order` attributes. There must be at least one subrun in the trajectory,
        otherwise an AttributeError is thrown. If two subruns equal in their order
        property a RuntimeError is thrown.

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
        the `v_order` attributes. There must be at least one subrun in the trajectory,
        otherwise an AttributeError is thrown. If two subruns equal in their order
        property a RuntimeError is thrown.

        For every subrun the following steps are executed:

        1.  Calling :func:`~pypet.brian.network.NetworkComponent.add_to_network` for every
            every :class:`~pypet.brian.network.NetworkComponent` in the order as
            they were passed to the :class:`pypet.brian.network.NetworkManager`.

        2.  Calling :func:`~pypet.brian.network.NetworkComponent.add_to_network` for every
            every :class:`~pypet.brian.network.NetworkAnalyser` in the order as
            they were passed to the :class:`pypet.brian.network.NetworkManager`.

        3.  Calling :func:`~pypet.brian.network.NetworkComponent.add_to_network` of the
            NetworkRunner itself (usually the network runner should not add or remove
            anything from the network, but this step is executed for completeness).

        4.  Running the `BRIAN network`_ for the duration of the current subrun by calling
            the network's `run` function.

            .. `BRIAN network`_: http://briansimulator.org/docs/reference-network.html#brian.Network

        5.  Calling :func:`~pypet.brian.network.NetworkAnalyser.analyse` for every
            every :class:`~pypet.brian.network.NetworkAnalyser` in the order as
            they were passed to the :class:`pypet.brian.network.NetworkManager`.

        6.  Calling :func:`~pypet.brian.network.NetworkComponent.remove_from_network` of the
            NetworkRunner itself (usually the network runner should not add or remove
            anything from the network, but this step is executed for completeness).

        7.  Calling :func:`~pypet.brian.network.NetworkComponent.remove_from_network` for every
            every :class:`~pypet.brian.network.NetworkComponent` in the order as
            they were passed to the :class:`pypet.brian.network.NetworkManager`.

        8.  Calling :func:`~pypet.brian.network.NetworkComponent.remove_from_network` for every
            every :class:`~pypet.brian.network.NetworkAnalyser` in the order as
            they were passed to the :class:`pypet.brian.network.NetworkManager`.


        These 8 steps are repeated for every subrun in the `subruns` list.
        The the list `subruns` passed to all `add_to_network`, `analyse` and
        `remove_from_network` methods can be modified
        within these functions to potentially alter the order of execution or
        even erase or add upcoming subruns if necessary.

        For example, a NetworkAnalyser checks
        for epileptic pathological activity and cancels all coming subruns in case
        of undesired network dynamics.

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
        """Extracts subruns from the trajectory.

        All :class:`~pypet.brian.parameter.BrianDurationParameters` must be added below
        `traj.parameters.simulation.durations` for experimental runs and
        `traj.parameters.simulation.pre_durations` for the pre-run.

        :param traj: Trajectory container

        :param pre_run: Boolean whether current run is regular or a pre-run

        """
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
        """Generic `run_network` function, handles normal experimental runs as well as pre-runs.

        See also :func:`~pypet.brian.network.NetworkRunner.run_network` and
         :func:`~pypet.brian.network.NetworkRunner.pre_run_network`.

        """

        # Initially extract the `subruns` list
        subruns = self._extract_subruns(traj, pre_run=pre_run)

        # Execute all subruns in order
        while len(subruns)>0:

            # Get the next subrun
            current_subrun= subruns.pop(0)

            # 1. Call `add` of all normal components
            for component in component_list:
                component.add_to_network(traj, network, current_subrun,  subruns,
                                 network_dict)

            # 2. Call `add` of all analyser components
            for analyser in analyser_list:
                analyser.add_to_network(traj, network, current_subrun,  subruns,
                                 network_dict)

            # 3. Call `add` of the network runner itself
            self.add_to_network(traj, network, current_subrun,  subruns,
                                 network_dict)

            # 4. Run the network
            self.logger.info('Starting subrun `%s`' % current_subrun.v_name)
            network.run(duration=current_subrun.f_get(), report=self._report,
                              report_period=self._report_period)

            # 5. Call `analyse` of all analyser components
            for analyser in analyser_list:
                analyser.analyse( traj, network, current_subrun,  subruns,
                                 network_dict)

            # 6. Call `remove? of the network runner itself
            self.remove_from_network(traj, network, current_subrun,  subruns,
                                 network_dict)

            # 7. Call `remove` for all normal components
            for component in component_list:
                component.remove_from_network(traj, network, current_subrun,  subruns,
                                 network_dict)

            # 8. Call `remove` for all analyser components
            for analyser in analyser_list:
                analyser.remove_from_network( traj, network, current_subrun,  subruns,
                                 network_dict)




class NetworkManager(object):
    """Manages a BRIAN network experiment and creates the network.

    An experiment consists of

    :param network_runnner:  A :class:`~pypet.brian.network.NetworkRunner`

        Special component that handles the execution of maybe several subruns.
        A NetworkRunner ids usually subclassed and one implements the
        :func:`~pypet.brian.network.NetworkComponent.add_parameters` method to add
        :class:`~pypet.brian.parameter.BrianDurationParameter` instances defining the
        order and duration of subruns.

    :param component_list:

        List of :class:`~pypet.brian.network.NetworkComponents` instances to create
        and manage individual parts of a network.
        They are build and added to the network in the order defined in the list.

        :class:`~pypet.brian.network.NetworkComponent` always needs to be sublcassed and
        defines only an abstract interface. For instance, one could create her or his
        own subclass called NeuronGroupComponent that creates NeuronGroups, Whereas
        a SynapseComponent creates Synapses between the before built NeuronGroups.
        Accordingly, the SynapseComponent instance is listed after
        the NeuronGroupComponent.

    :param analyser_list:

        List of :class:`~pypet.brian.network.Analyser` instances for recording and
        statistical evaluation of a BRIAN network. They should be used to add monitors
        to a network and to do further processing of the monitor data.

    This division allows to create compartmental network models where one can easily
    replace parts of a network simulation.

    :param force_single_core:

        In case you :func:`~pypet.brian.network.NetworkManager.pre_build` or even
        :func:`~pypet.brian.network.NetworkManager.pre_run` a network, you usually cannot
        use single core processing.
        The problem with single core processing is that iterative exploration of the
        parameter space alters the network on every iteration and the network cannot be
        reset to the initial conditions holding before the very first experimental run.
        This is an inherent problem of BRIAN. The only way to overcome this problem is
        multiprocessing and copying (either by pickling or by forking) the whole
        BRIAN environment.

        If you are not bothered by not starting every experimental run with the very same
        network you can set `force_single_core=True`. The NetworkManager will
        do iterative single processing and ignore the ongoing modification of the network
        throughout all runs.

        In case `multiproc=True` for your environment, the setting of `force_single_core`
        is irrelevant and has no effect.

    """
    def __init__(self, network_runner, component_list, analyser_list=(),
                 force_single_core=False):
        self._component_list = component_list
        self._network_runner = network_runner
        self._analyser_list = analyser_list
        self._network_dict = {}
        self._brian_list = []
        self._set_logger()
        self._pre_built=False
        self._pre_run=False
        self._network = None
        self._force_single_core =force_single_core

    def __getstate__(self):
        """Called for pickling.

        Removes the logger to allow pickling and returns a copy of `__dict__`.

        """
        result = self.__dict__.copy()
        del result['_logger'] #pickling does not work with loggers
        return result

    def __setstate__(self, statedict):
        """Called after loading a pickle dump.

        Restores `__dict__` from `statedict` and adds a new logger.

        """
        self.__dict__.update( statedict)
        self._set_logger()


    def _set_logger(self):
        """Creates a logger"""
        self._logger = logging.getLogger('pypet.brian.parameter.NetworkManager')

    def add_parameters(self, traj):
        """Adds parameters for a network simulation.

        Calls :func:`~pypet.brian.network.NetworkComponent.add_parameters` for all components,
        analyser, and the network runner (in this order).

        :param traj:  Trajectory container

        """
        self._logger.info('Adding Parameters of Components')

        for component in self._component_list:
            component.add_parameters(traj)

        if self._analyser_list:
            self._logger.info('Adding Parameters of Analysers')

            for analyser in self._analyser_list:
                analyser.add_parameters(traj)

        self._logger.info('Adding Parameters of Runner')

        self._network_runner.add_parameters(traj)

    def pre_build(self, traj):
        """Pre-builds network components.

        Calls :func:`~pypet.brian.network.NetworkComponent.pre_build` for all components,
        analysers and the network runner.

        `pre_build` is not automatically called but either needs to be executed manually
        by the user, either calling it directly or by using
        :func:`~pypet.brian.network.NetworkManager.pre_run`.

        This function does not create a `BRIAN network`_, but only it's components.

        .. `BRIAN network`_: http://briansimulator.org/docs/reference-network.html#brian.Network


        :param traj: Trajectory container

        """
        self._logger.info('Pre-Building Components')

        for component in self._component_list:
            component.pre_build(traj, self._brian_list, self._network_dict)


        if self._analyser_list:

            self._logger.info('Pre-Building Analysers')

            for analyser in self._analyser_list:
                analyser.pre_build(traj, self._brian_list, self._network_dict)

        self._logger.info('Pre-Building NetworkRunner')
        self._network_runner.pre_build(traj, self._brian_list, self._network_dict)

        self._pre_built = True


    def build(self, traj):
        """Pre-builds network components.

        Calls :func:`~pypet.brian.network.NetworkComponent.build` for all components,
        analysers and the network runner.

        `build` does not need to be called by the user. If `~pypet.brian.network.run_network`
        is passed to an :class:`~pypet.environment.Environment` with this Network manager,
        `build` is automatically called for each individual experimental run.

        :param traj: Trajectory container

        """
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
        """Starts a network run before the individual run.

        Useful if a network needs an initial run that can be shared by all individual
        experimental runs during parameter exploration.

        Needs to be called by the user. If `pre_run_network` is started by the user,
        :func:`~pypet.brian.network.NetworkManager.pre_build` will be automatically called
        from this function.

        This function will create a new `BRIAN network`_ which is run by
        the :class:`~pypet.brian.network.NetworkRunner` and it's
        :func:`~pypet.brian.network.NetworkRunner.pre_run_network`.

        To see how a network run is structured also take a look at
        :func:`~pypet.brian.network.NetworkRunner.run_network`.

        .. `BRIAN network`_: http://briansimulator.org/docs/reference-network.html#brian.Network

        :param traj: Trajectory container

        """
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

        self._pre_run = True


    def run_network(self, traj):
        """Performs an individual network run during parameter exploration.

        `run_network` does not need to be called by the user. If the top-level
        `~pypet.brian.network.run_network` method (not this one of the NetworkManager)
        is passed to an :class:`~pypet.environment.Environment` with this NetworkManager,
        `run_network` and :func:`~pypet.brian.network.NetworkManager.build`
        are automatically called for each individual experimental run.

        This function will create a new `BRIAN network`_ in case one was not pre-run.
        The execution of the network run is carried out by
        the :class:`~pypet.brian.network.NetworkRunner` and it's
        :func:`~pypet.brian.network.NetworkRunner.run_network` (also take
        a look at this function's documentation to see the structure of a network run).

        .. `BRIAN network`_: http://briansimulator.org/docs/reference-network.html#brian.Network

        :param traj: Trajectory container

        """
        # Check if the network was pre-built
        if self._pre_built:
            # If yes check for multiprocessing or if a single core processing is forced
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
        """Starts a single run carried out by a NetworkRunner.

        Called from the public function :func:`~pypet.brian.network.NetworkManger.run_network`.

        :param traj: Trajectory container

        """
        self.build(traj)

        self._logger.info('\n-------------------\n'
                     'Running the Network\n'
                     '-------------------')

        # We need to construct a network object in case one was not pre-run
        if not self._pre_run:

            self._network = Network(*self._brian_list)

        # Start the experimental run
        self._network_runner.run_network( traj, self._network,  self._network_dict,
                                             self._component_list, self._analyser_list)

        self._logger.info('\n-----------------------------\n'
                     'Network Simulation successful\n'
                     '-----------------------------')


