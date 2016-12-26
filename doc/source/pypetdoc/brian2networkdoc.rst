========================
Brian2 Network Framework
========================

.. automodule:: pypet.brian2.network


----------
Quicklinks
----------

These function can directly be called or used by the user.

.. currentmodule:: pypet.brian2.network


.. autosummary::
    :nosignatures:

    NetworkManager.add_parameters
    NetworkManager.pre_run_network
    NetworkManager.pre_build

The private functions of the runner and the manager are also listed below
to allow fast browsing of the source code.

-----------------------------------------------
Functions that can be implemented by a Subclass
-----------------------------------------------

These functions can be implemented in the subclasses:

.. autosummary::
    :nosignatures:

    NetworkComponent.build
    NetworkComponent.add_to_network
    NetworkComponent.remove_from_network
    NetworkComponent.pre_build
    NetworkAnalyser.analyse


--------------
NetworkManager
--------------

.. autoclass:: pypet.brian2.network.NetworkManager
    :members:
    :private-members:
    :special-members:

-------------
NetworkRunner
-------------

.. autoclass:: pypet.brian2.network.NetworkRunner
    :members:
    :private-members:
    :special-members:

----------------
NetworkComponent
----------------

.. autoclass:: pypet.brian2.network.NetworkComponent
    :members:

---------------
NetworkAnalyser
---------------

.. autoclass:: pypet.brian2.network.NetworkAnalyser
    :members: