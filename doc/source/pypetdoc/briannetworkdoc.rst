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
:func:`pypeet.brian.network.NetworkManager.run_network`.

-----------------------
NetworkManager
-----------------------

.. autoclass:: pypet.brian.network.NetworkManager
    :members:

-----------------------
NetworkRunner
-----------------------

.. autoclass:: pypet.brian.network.NetworkRunner
    :members:

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