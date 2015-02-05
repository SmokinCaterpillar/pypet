
.. _example-17:

========================================================
Wrapping an Existing Project (Cellular Automata Inside!)
========================================================

Here you can find how to wrap pypet around an already existing simulation.
The original project (``original.py``) simulates `elementary cellular automata`_.

The code explores different starting conditions and automata rules.
``pypetwrap.py`` shows how to include *pypet* into the project without
changing much of the original code. Moreover, introducing *pypet* allows
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