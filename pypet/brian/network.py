"""Module for easy compartmental implementation of a `BRIAN network`_.

Build parts of a network via subclassing :class:`~pypet.brian.network.NetworkComponent` and
:class:`~pypet.brian.network.NetworkAnalyser` for recording and statistical analysis.

Specify a :class:`~pypet.brian.network.NetworkRunner` (subclassing optionally) that handles
the execution of your experiment in different subruns. Subruns can be defined
as :class:`~pypet.brian.parameter.BrianParameter` instances in a particular
trajectory group. You must add to every parameter's :class:`~pypet.annotations.Annotations` the
attribute `order`. This order must be an integer specifying the index or order
the subrun should about to be executed in.

The creation and management of a `BRIAN network`_ is handled by the
:class:`~pypet.brian.network.NetworkManager` (no need for subclassing). Pass your
components, analyser and your runner to the manager.

Pass the :func:`~pypet.brian.network.run_network` function together with a
:class:`~pypet.brian.network.NetworkManager` to your main environment function
:func:`~pypet.environment.Environment.f_run` to start a simulation and parallel
parameter exploration. Be aware that in case of a *pre-built* network,
successful parameter exploration
requires parallel processing (see :class:`~pypet.brian.network.NetworkManager`).

.. _`BRIAN network`: http://briansimulator.org/docs/reference-network.html

"""

__author__ = 'Robert Meyer'

import logging

from brian import Network, clear, reinit
from brian.units import second

from pypet.brian.parameter import BrianDurationParameter
from pypet.utils.decorators import deprecated
from pypet.pypetlogging import HasLogger


@deprecated('Please use `environment.f_run(manager.run_network)` instead of '
            '`environment.f_run(run_network, manager)`.')
def run_network(traj, network_manager):
    """Top-level simulation function, pass this together with a NetworkManager to the environment.

    DEPRECATED: Please pass `network_manager.run_network` to the environment's `f_run` function

    :param traj: Trajectory container

    :param network_manager: :class:`~pypet.brian.network.NetworkManager` instance

        *   Creates a `BRIAN network`_.

        *   Manages all :class:`~pypet.brian.network.NetworkComponent` instances,
            all :class:`~pypet.brian.network.NetworkAnalyser` and a single
            :class:`~pypet.brian.network.NetworkRunner`.

        .. _`BRIAN network`: http://briansimulator.org/docs/reference-network.html

    """
    network_manager.run_network(traj)


class NetworkComponent(HasLogger):
    """Abstract class to define a component of a BRIAN network.

    Can be subclassed to define the construction of NeuronGroups_ or
    Connections_, for instance.

    .. _NeuronGroups: http://briansimulator.org/docs/reference-models-and-groups.html

    .. _Connections: http://briansimulator.org/docs/reference-connections.html

    """

    def add_parameters(self, traj):
        """Adds parameters to `traj`.

        Function called from the :class:`~pypet.brian.network.NetworkManager` to
        define and add parameters to the trajectory container.

        """
        pass

    def pre_build(self, traj, brian_list, network_dict):
        """Builds network objects before the actual experimental runs.

        Function called from the :class:`~pypet.brian.network.NetworkManager` if
        components can be built before the actual experimental runs or in
        case the network is pre-run.

        Parameters are the same as for the :func:`~pypet.brian.network.NetworkComponent.build`
        method.

        """
        pass

    def build(self, traj, brian_list, network_dict):
        """Builds network objects at the beginning of each individual experimental run.

        Function called from the :class:`~pypet.brian.network.NetworkManager`
        at the beginning of every experimental run,

        :param traj:

            Trajectory container

        :param brian_list:

            Add BRIAN network objects like NeuronGroups_ or Connections_ to this list.
            These objects will be automatically added at the instantiation of the network
            in case the network was not pre-run
            via `Network(*brian_list)` (see the `BRIAN network class`_).

            .. _NeuronGroups: http://briansimulator.org/docs/reference-models-and-groups.html

            .. _Connections: http://briansimulator.org/docs/reference-connections.html

            .. _`BRIAN network class`: http://briansimulator.org/docs/reference-network.html#brian.Network


        :param network_dict:

            Add any item to this dictionary that should be shared or accessed by all
            your components and which are not part of the trajectory container.
            It is recommended to also put all items from the `brian_list` into
            the dictionary for completeness.


        For convenience I recommend documenting the implementation of `build` and
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

                'connections':  List of 4 Connections,
                                between all types of neurons (e->e, e->i, i->e, i->i)

        """
        pass

    def add_to_network(self, traj, network, current_subrun, subrun_list, network_dict):
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

            :class:`~pypet.brian.parameter.BrianParameter` specifying the very next
            subrun to be simulated.

        :param subrun_list:

            List of :class:`~pypet.brian.parameter.BrianParameter` objects that are to
            be run after the current subrun.

        :param network_dict:

            Dictionary of items shared by all components.

        """
        pass

    def remove_from_network(self, traj, network, current_subrun, subrun_list, network_dict):
        """Can remove network objects before a specific `subrun`.

        Called by a :class:`~pypet.brian.network.NetworkRunner` after a
        given `subrun` and shortly after analysis (see
        :class:`~pypet.brian.network.NetworkAnalyser`).

        :param traj: Trajectoy container

        :param network:

            `BRIAN network`_ where elements could be removed via `remove(...)`.

            .. _`BRIAN network`: http://briansimulator.org/docs/reference-network.html

        :param current_subrun:

            :class:`~pypet.brian.parameter.BrianParameter` specifying the current subrun
            that was executed shortly before.

        :param subrun_list:

            List of :class:`~pypet.brian.parameter.BrianParameter` objects that are to
            be run after the current subrun.

        :param network_dict:

            Dictionary of items shared by all components.

        """
        pass


class NetworkAnalyser(NetworkComponent):
    """Specific NetworkComponent that analysis a network experiment.

    Can be subclassed to create components for statistical analysis of a network
    and network monitors.

    """
    def analyse(self, traj, network, current_subrun, subrun_list, network_dict):
        """Can perform statistical analysis on a given network.

        Called by a :class:`~pypet.brian.network.NetworkRunner` directly after a
        given `subrun`.

        :param traj: Trajectoy container

        :param network: `BRIAN network`_

            .. _`BRIAN network`: http://briansimulator.org/docs/reference-network.html

        :param current_subrun:

            :class:`~pypet.brian.parameter.BrianParameter` specifying the current subrun
            that was executed shortly before.

        :param subrun_list:

            List of :class:`~pypet.brian.parameter.BrianParameter` objects that are to
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
    should specify an experimental run with a :class:~pypet.brian.parameter.BrianParameter`
    to define the order and duration of network subruns. For the actual experimental runs,
    all subruns must be stored in a particular trajectory group.
    By default this `traj.parameters.simulation.durations`. For a pre-run
    the default is `traj.parameters.simulation.pre_durations`. These default group names
    can be changed at runner initialisation (see below).

    The network runner will look in the `v_annotations` property of each parameter
    in the specified trajectory group. It searches for the entry `order`
    to determine the order of subruns.

    :param report:

        How simulation progress should be reported, see also the parameters of
        `run(...)` in a `BRIAN network`_ and the `magic run`_ method.

        .. _`BRIAN network`: http://briansimulator.org/docs/reference-network.html

        .. _`magic run`: http://briansimulator.org/docs/reference-network.html#brian.run

    :param report_period:

        How often progress is reported. If not specified 10 seconds is chosen.

    :param durations_group_name:

        Name where to look for :class:`~pypet.brian.parameter.BrianParameter` instances
        in the trajectory which specify the order and durations of subruns.

    :param pre_durations_group_name:

        As above, but for pre running a network.



    Moreover, in your subclass you can log messages with the private attribute `_logger`
    which is initialised in :func:`~pypet.pypetlogging.HasLogger._set_logger`.

    """
    def __init__(self, report='text', report_period=None,
                 durations_group_name='simulation.durations',
                 pre_durations_group_name='simulation.pre_durations'):

        if report_period is None:
            report_period = 10 * second

        self._report = report
        self._report_period = report_period

        self._durations_group_name = durations_group_name
        self._pre_durations_group_name = pre_durations_group_name


        self._set_logger()


    def execute_network_pre_run(self, traj, network, network_dict, component_list, analyser_list):
        """Runs a network before the actual experiment.

        Called by a :class:`~pypet.brian.network.NetworkManager`.
        Similar to :func:`~pypet.brian.network.NetworkRunner.run_network`.

        Subruns and their durations are extracted from the trajectory. All
        :class:`~pypet.brian.parameter.BrianParameter` instances found under
        `traj.parameters.simulation.pre_durations` (default, you can change the
        name of the group where to search for durations at runner initialisation).
        The order is determined from
        the `v_annotations.order` attributes. There must be at least one subrun in the trajectory,
        otherwise an AttributeError is thrown. If two subruns equal in their order
        property a RuntimeError is thrown.

        :param traj: Trajectory container

        :param network: `BRIAN network`_

            .. `BRIAN network`_: http://briansimulator.org/docs/reference-network.html#brian.Network

        :param network_dict: Dictionary of items shared among all components

        :param component_list: List of :class:`~pypet.brian.network.NetworkComponent` objects

        :param analyser_list: List of :class:`~pypet.brian.network.NetworkAnalyser` objects

        """
        self._execute_network_run(traj, network, network_dict, component_list, analyser_list,
                                  pre_run=True)

    def execute_network_run(self, traj, network, network_dict, component_list, analyser_list):
        """Runs a network in an experimental run.

        Called by a :class:`~pypet.brian.network.NetworkManager`.

        A network run is divided into several subruns which are defined as
        :class:`~pypet.brian.parameter.BrianParameter` instances.

        These subruns are extracted from the trajectory. All
        :class:`~pypet.brian.parameter.BrianParameter` instances found under
        `traj.parameters.simulation.durations` (default, you can change the
        name of the group where to search for durations at runner initialisation).
        The order is determined from
        the `v_annotations.order` attributes. An error is thrown if no orders attribute
        can be found or if two parameters have the same order.

        There must be at least one subrun in the trajectory,
        otherwise an AttributeError is thrown. If two subruns equal in their order
        property a RuntimeError is thrown.

        For every subrun the following steps are executed:

        1.  Calling :func:`~pypet.brian.network.NetworkComponent.add_to_network` for every
            every :class:`~pypet.brian.network.NetworkComponent` in the order as
            they were passed to the :class:`~pypet.brian.network.NetworkManager`.

        2.  Calling :func:`~pypet.brian.network.NetworkComponent.add_to_network` for every
            every :class:`~pypet.brian.network.NetworkAnalyser` in the order as
            they were passed to the :class:`~pypet.brian.network.NetworkManager`.

        3.  Calling :func:`~pypet.brian.network.NetworkComponent.add_to_network` of the
            NetworkRunner itself (usually the network runner should not add or remove
            anything from the network, but this step is executed for completeness).

        4.  Running the `BRIAN network`_ for the duration of the current subrun by calling
            the network's `run` function.

            .. `BRIAN network`_: http://briansimulator.org/docs/reference-network.html#brian.Network

        5.  Calling :func:`~pypet.brian.network.NetworkAnalyser.analyse` for every
            every :class:`~pypet.brian.network.NetworkAnalyser` in the order as
            they were passed to the :class:`~pypet.brian.network.NetworkManager`.

        6.  Calling :func:`~pypet.brian.network.NetworkComponent.remove_from_network` of the
            NetworkRunner itself (usually the network runner should not add or remove
            anything from the network, but this step is executed for completeness).

        7.  Calling :func:`~pypet.brian.network.NetworkComponent.remove_from_network` for every
            every :class:`~pypet.brian.network.NetworkAnalyser` in the order as
            they were passed to the :class:`~pypet.brian.network.NetworkManager`

        8.  Calling :func:`~pypet.brian.network.NetworkComponent.remove_from_network` for every
            every :class:`~pypet.brian.network.NetworkComponent` in the order as
            they were passed to the :class:`~pypet.brian.network.NetworkManager`.


        These 8 steps are repeated for every subrun in the `subrun_list`.
        The `subrun_list` passed to all `add_to_network`, `analyse` and
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
        self._execute_network_run(traj, network, network_dict, component_list, analyser_list,
                                  pre_run=False)

    def _extract_subruns(self, traj, pre_run=False):
        """Extracts subruns from the trajectory.

        :param traj: Trajectory container

        :param pre_run: Boolean whether current run is regular or a pre-run

        :raises: RuntimeError if orders are duplicates or even missing

        """
        if pre_run:
            durations_list = traj.f_get_all(self._pre_durations_group_name)
        else:
            durations_list = traj.f_get_all(self._durations_group_name)


        subruns = {}
        orders = []


        for durations in durations_list:
            for duration_param in durations.f_iter_leaves():

                if isinstance(duration_param, BrianDurationParameter):
                    self._logger.warning('BrianDurationParameters are deprecated. '
                                         'Please use a normal BrianParameter and '
                                         'specify the order in `v_annotations.order`!')

                if 'order' in duration_param.v_annotations:
                    order = duration_param.v_annotations.order
                else:
                    raise RuntimeError('Your duration parameter %s has no order. Please add '
                                       'an order in `v_annotations.order`.' %
                                       duration_param.v_full_name)

                if order in subruns:
                    raise RuntimeError('Your durations must differ in their order, there are two '
                                       'with order %d.' % order)
                else:
                    subruns[order] = duration_param
                    orders.append(order)

        return [subruns[order] for order in sorted(orders)]

    def _execute_network_run(self, traj, network, network_dict, component_list,
                             analyser_list, pre_run=False):
        """Generic `execute_network_run` function, handles experimental runs as well as pre-runs.

        See also :func:`~pypet.brian.network.NetworkRunner.execute_network_run` and
         :func:`~pypet.brian.network.NetworkRunner.execute_network_pre_run`.

        """

        # Initially extract the `subrun_list`
        subrun_list = self._extract_subruns(traj, pre_run=pre_run)


        # counter for subruns
        subrun_number = 0

        # Execute all subruns in order
        while len(subrun_list) > 0:

            # Get the next subrun
            current_subrun = subrun_list.pop(0)

            # 1. Call `add` of all normal components
            for component in component_list:
                component.add_to_network(traj, network, current_subrun, subrun_list,
                                         network_dict)

            # 2. Call `add` of all analyser components
            for analyser in analyser_list:
                analyser.add_to_network(traj, network, current_subrun, subrun_list,
                                        network_dict)

            # 3. Call `add` of the network runner itself
            self.add_to_network(traj, network, current_subrun, subrun_list,
                                network_dict)

            # 4. Run the network
            self._logger.info('STARTING subrun `%s` (#%d) lasting %s.' %
                             (current_subrun.v_name, subrun_number, str(current_subrun.f_get())))
            network.run(duration=current_subrun.f_get(), report=self._report,
                              report_period=self._report_period)

            # 5. Call `analyse` of all analyser components
            for analyser in analyser_list:
                analyser.analyse(traj, network, current_subrun, subrun_list,
                                 network_dict)

            # 6. Call `remove` of the network runner itself
            self.remove_from_network(traj, network, current_subrun, subrun_list,
                                     network_dict)

            # 7. Call `remove` for all analyser components
            for analyser in analyser_list:
                analyser.remove_from_network(traj, network, current_subrun, subrun_list,
                                             network_dict)

            # 8. Call `remove` for all normal components
            for component in component_list:
                component.remove_from_network(traj, network, current_subrun, subrun_list,
                                              network_dict)


            subrun_number += 1


class NetworkManager(HasLogger):
    """Manages a BRIAN network experiment and creates the network.

    An experiment consists of

    :param network_runner:  A :class:`~pypet.brian.network.NetworkRunner`

        Special component that handles the execution of several subruns.
        A NetworkRunner can be subclassed to implement the
        :func:`~pypet.brian.network.NetworkComponent.add_parameters` method to add
        :class:`~pypet.brian.parameter.BrianParameter` instances defining the
        order and duration of subruns.

    :param component_list:

        List of :class:`~pypet.brian.network.NetworkComponents` instances to create
        and manage individual parts of a network.
        They are build and added to the network in the order defined in the list.

        :class:`~pypet.brian.network.NetworkComponent` always needs to be sublcassed and
        defines only an abstract interface. For instance, one could create her or his
        own subclass called NeuronGroupComponent that creates NeuronGroups_, Whereas
        a SynapseComponent creates Synapses_ between the before built NeuronGroups_.
        Accordingly, the SynapseComponent instance is listed after
        the NeuronGroupComponent.

        .. _NeuronGroups: http://briansimulator.org/docs/reference-models-and-groups.html

        .. _Synapses: http://briansimulator.org/docs/reference-synapses.html

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
        network, you can set `force_single_core=True`. The NetworkManager will
        do iterative single processing and ignore the ongoing modification of the network
        throughout all runs.

        In case `multiproc=True` for your environment, the setting of `force_single_core`
        is irrelevant and has no effect.

    :param network_constructor:

        If you have a custom network constructor apart from the Brian one,
        pass it here.

    """
    def __init__(self, network_runner, component_list, analyser_list=(),
                 force_single_core=False, network_constructor=None):
        self.components = component_list
        self.network_runner = network_runner
        self.analysers = analyser_list
        self._network_dict = {}
        self._brian_list = []
        self._set_logger()
        self._pre_built = False
        self._pre_run = False
        self._network = None
        self._force_single_core = force_single_core
        if network_constructor is None:
            self._network_constructor = Network
        else:
            self._network_constructor = network_constructor

    def add_parameters(self, traj):
        """Adds parameters for a network simulation.

        Calls :func:`~pypet.brian.network.NetworkComponent.add_parameters` for all components,
        analyser, and the network runner (in this order).

        :param traj:  Trajectory container

        """
        self._logger.info('Adding Parameters of Components')

        for component in self.components:
            component.add_parameters(traj)

        if self.analysers:
            self._logger.info('Adding Parameters of Analysers')

            for analyser in self.analysers:
                analyser.add_parameters(traj)

        self._logger.info('Adding Parameters of Runner')

        self.network_runner.add_parameters(traj)

    def pre_build(self, traj):
        """Pre-builds network components.

        Calls :func:`~pypet.brian.network.NetworkComponent.pre_build` for all components,
        analysers, and the network runner.

        `pre_build` is not automatically called but either needs to be executed manually
        by the user, either calling it directly or by using
        :func:`~pypet.brian.network.NetworkManager.pre_run`.

        This function does not create a `BRIAN network`_, but only it's components.

        .. `BRIAN network`_: http://briansimulator.org/docs/reference-network.html#brian.Network

        :param traj: Trajectory container

        """
        self._logger.info('Pre-Building Components')

        for component in self.components:
            component.pre_build(traj, self._brian_list, self._network_dict)

        if self.analysers:

            self._logger.info('Pre-Building Analysers')

            for analyser in self.analysers:
                analyser.pre_build(traj, self._brian_list, self._network_dict)

        self._logger.info('Pre-Building NetworkRunner')
        self.network_runner.pre_build(traj, self._brian_list, self._network_dict)

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

        for component in self.components:
            component.build(traj, self._brian_list, self._network_dict)

        if self.analysers:

            self._logger.info('Building Analysers')

            for analyser in self.analysers:
                analyser.build(traj, self._brian_list, self._network_dict)

        self._logger.info('Building NetworkRunner')
        self.network_runner.build(traj, self._brian_list, self._network_dict)


    def pre_run_network(self, traj):
        """Starts a network run before the individual run.

        Useful if a network needs an initial run that can be shared by all individual
        experimental runs during parameter exploration.

        Needs to be called by the user. If `pre_run_network` is started by the user,
        :func:`~pypet.brian.network.NetworkManager.pre_build` will be automatically called
        from this function.

        This function will create a new `BRIAN network`_ which is run by
        the :class:`~pypet.brian.network.NetworkRunner` and it's
        :func:`~pypet.brian.network.NetworkRunner.execute_network_pre_run`.

        To see how a network run is structured also take a look at
        :func:`~pypet.brian.network.NetworkRunner.run_network`.

        .. `BRIAN network`_: http://briansimulator.org/docs/reference-network.html#brian.Network

        :param traj: Trajectory container

        """
        self.pre_build(traj)

        self._logger.info('\n------------------------\n'
                          'Pre-Running the Network\n'
                          '------------------------')


        self._network = self._network_constructor(*self._brian_list)
        self.network_runner.execute_network_pre_run(traj, self._network, self._network_dict,
                                                    self.components, self.analysers)

        self._logger.info('\n-----------------------------\n'
                          'Network Simulation successful\n'
                          '-----------------------------')

        self._pre_run = True


    def run_network(self, traj):
        """Top-level simulation function, pass this to the environment

        Performs an individual network run during parameter exploration.

        `run_network` does not need to be called by the user. If the top-level
        `~pypet.brian.network.run_network` method (not this one of the NetworkManager)
        is passed to an :class:`~pypet.environment.Environment` with this NetworkManager,
        `run_network` and :func:`~pypet.brian.network.NetworkManager.build`
        are automatically called for each individual experimental run.

        This function will create a new `BRIAN network`_ in case one was not pre-run.
        The execution of the network run is carried out by
        the :class:`~pypet.brian.network.NetworkRunner` and it's
        :func:`~pypet.brian.network.NetworkRunner.execute_network_run` (also take
        a look at this function's documentation to see the structure of a network run).

        .. `BRIAN network`_: http://briansimulator.org/docs/reference-network.html#brian.Network

        :param traj: Trajectory container

        """

        # Check if the network was pre-built
        if self._pre_built:
            # If yes check for multiprocessing or if a single core processing is forced
            multiproc = traj.f_get('config.environment.%s.multiproc' %
                                   traj.v_environment_name).f_get()
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
                    raise RuntimeError('You cannot run a pre-built network without '
                                       'multiprocessing.\n'
                                       'The network configuration must be copied either by '
                                       'pickling (using a `multiproc=True` and `use_pool=True` in '
                                       'your environment) or by forking ( multiprocessing with '
                                       '`use_pool=False`).\n If your network '
                                       'cannot be pickled use the latter. '
                                       'In order to come close to iterative processing '
                                       'you could use multiprocessing with `ncores=1`. \n'
                                       'If you do not care about messing up initial conditions '
                                       '(i.e. you are debugging) use `force_single_core=True` '
                                       'in your network manager.')
        else:
            clear(True, True)
            reinit()
            self._run_network(traj)

    def _pretty_print_explored_parameters(self, traj):
        print_statement = '\n-------------------\n' +\
                          'Running the Network\n' +\
                          '-------------------\n' +\
                          '      with\n'

        explore_dict = traj.f_get_explored_parameters(copy=False)
        for full_name in explore_dict:
            parameter = explore_dict[full_name]

            print_statement += '%s = %s\n' % (parameter.v_full_name, parameter.f_val_to_str())

        print_statement += '-------------------'

        self._logger.info(print_statement)

    def _run_network(self, traj):
        """Starts a single run carried out by a NetworkRunner.

        Called from the public function :func:`~pypet.brian.network.NetworkManger.run_network`.

        :param traj: Trajectory container

        """
        self.build(traj)

        self._pretty_print_explored_parameters(traj)

        # We need to construct a network object in case one was not pre-run
        if not self._pre_run:

            self._network = self._network_constructor(*self._brian_list)

        # Start the experimental run
        self.network_runner.execute_network_run(traj, self._network, self._network_dict,
                                                self.components, self.analysers)

        self._logger.info('\n-----------------------------\n'
                          'Network Simulation successful\n'
                          '-----------------------------')
