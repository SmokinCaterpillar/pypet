=======================
Brian Network Framework
=======================

.. automodule:: pypet.brian.network


-----------
Quicklinks
-----------

These function can directly be called or used by the user.

.. currentmodule:: pypet.brian.network


.. autosummary::
    :nosignatures:

    run_network
    NetworkManager.add_parameters
    NetworkManager.pre_run_network
    NetworkManager.pre_build

The private functions of the runner and the manager are also listed below
to allow fast browsing of the source code.

------------------------------------------------
Functions that can be implemented by a Subclass
------------------------------------------------

These functions can be implemented in the subclasses:

.. autosummary::
    :nosignatures:

    NetworkComponent.build
    NetworkComponent.add_to_network
    NetworkComponent.remove_from_network
    NetworkComponent.pre_build
    NetworkAnalyser.analyse

I would suggest in case one subclasses :class:`~pypet.brian.network.NetworkRunner`
to implement its :func:`~pypet.brian.network.NetworkComponent.add_parameters` method
(inherited from  :class:`~pypet.brian.network.NetworkComponent`)
in order to add :class:`~pypet.brian.parameter.BrianDurationParameter` instances to
`traj.parameters.simulation.durations` or `traj.parameters.simulation.pre_durations`
to define the length and order of individual subruns.

For a description of the structure and different phases of an individual simulation run see
:func:`~pypet.brian.network.NetworkManager.run_network`.

------------------------------
Top-Level run_network Function
------------------------------

.. autofunction:: pypet.brian.network.run_network

-----------------------
NetworkManager
-----------------------

.. autoclass:: pypet.brian.network.NetworkManager
    :members:
    :private-members:
    :special-members:

-----------------------
NetworkRunner
-----------------------

.. autoclass:: pypet.brian.network.NetworkRunner
    :members:
    :private-members:
    :special-members:

-----------------------
NetworkComponent
-----------------------

.. autoclass:: pypet.brian.network.NetworkComponent
    :members:

-----------------------
NetworkAnalyser
-----------------------

.. autoclass:: pypet.brian.network.NetworkAnalyser
    :members: