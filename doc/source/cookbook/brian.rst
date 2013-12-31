======================
Using BRIAN with pypet
======================

I use BRIAN_ a lot for my research. Accordingly, initially I started *pypet*
for easier management of large scale BRIAN_ simulations.
I have written some more specified functionality in order to do this.
All of this can be found in `pypet.brian` sub-package.
The package contains a `parameter.py` file that includes specialized containers
for BRIAN_ data, like the :class:`~pypet.brian.parameter.BrianParameter`,
the :class:`~pypet.brian.parameter.BrianResult` (both for BRIAN Quantities),
the :class:`~pypet.brian.parameter.BrianMonitorResult` (extracts data from any kind of
BRIAN Monitor), and finally
the :class:`~pypet.brian.parameter.BrianDurationParameter`. The latter can be used
in conjunction with the network management system in the `network.py` file within
the `pypet.brian` package.

In the following I want to explain how to use the `network.py` framework to run large
scale simulations. An example of such a large scale simulation can be found in
:ref:`example-11` which is an implementation of the `Litwin-Kumar and Doiron paper`_
from 2012.

----------------------------
The BRIAN network framework
----------------------------

The core concept of the network framework is that simulated spiking neural network are
not in one giant piece but compartmentalize. Networks consist of NeuronGroups_,
Connections_ or Synapses_, Monitors_ and so on and so forth. Thus, it would be neat
if these parts can easily be replaced or augmented without rewriting a whole
simulation. You want to add STDP to your network? Just plug-in an STDP compoment.
You do not want to record anymore from the inhibitory neurons? Just throw away a
recording component.

To abstract this idea, the whole simulation framework evolves around the
:class:`~pypet.brian.network.NetworkComponent` class. This specifies an abstract API
that any component (which you as a user implement) should agree on to make them easy
to replace and communicate with each other.

There are two specialisation of this :class:`~pypet.brian.network.NetworkComponent` API:
The :class:`~pypet.brian.network.NetworkAnalyser` and
the :class:`~pypet.brian.network.NetworkRunner`. Implementations of the former deal with
the analysis of network output. This might range from simply adding and removing Monitors_ to
evaluating the monitor data and computing statistics about the network activity.
An instance of the latter is usually only created once and takes care about the running
of a network simulation.

All these three types of components are managed by the
:class:`~pypet.brian.network.NetworkManager` that also creates `BRIAN networks` and
passes these to the runner.
Conceptually this is depicted in figure below.

.. image:: ../figures/network_managing.png
    :width: 660

-------------------
NetworkComponents
-------------------



.. _BRIAN: http://briansimulator.org/


.. _`Litwin-Kumar and Doiron paper`: http://www.nature.com/neuro/journal/v15/n11/full/nn.3220.html

.. _NeuronGroups: http://briansimulator.org/docs/reference-models-and-groups.html

.. _Connections: http://briansimulator.org/docs/reference-connections.html

.. _Synapses: http://briansimulator.org/docs/reference-synapses.html

.. _Monitors: http://briansimulator.org/docs/reference-monitors.html

.. _`BRIAN networks`: http://briansimulator.org/docs/reference-network.html#brian.Network

