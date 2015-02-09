
.. _example-17:

========================================================
Wrapping an Existing Project (Cellular Automata Inside!)
========================================================

Here you can find out how to wrap *pypet* around an already existing simulation.
The original project (``original.py``) simulates `elementary cellular automata`_.

The code explores different starting conditions and automata rules.
``pypetwrap.py`` shows how to include *pypet* into the project without
changing much of the original code. Basically, the core code of the simulation is left
untouched. Only the *boilerplate* of the main script changes and a short wrapper function
is needed that passes parameters from the *trajectory* to the core simulation.

Moreover, introducing *pypet* allows
much easier exploration of the parameter space. Now exploring different
parameter sets requires no more code changes.

Download: :download:`original.py <../../../examples/example_17_wrapping_an_existing_project/original.py>`

Download: :download:`pypetwrap.py <../../../examples/example_17_wrapping_an_existing_project/pypetwrap.py>`

----------------
Original Project
----------------

.. literalinclude:: ../../../examples/example_17_wrapping_an_existing_project/original.py


-------------
Using *pypet*
-------------

.. literalinclude:: ../../../examples/example_17_wrapping_an_existing_project/pypetwrap.py


.. _`elementary cellular automata`: http://en.wikipedia.org/wiki/Elementary_cellular_automaton