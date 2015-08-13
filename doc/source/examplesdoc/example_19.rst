
.. _example-19:

=================================================
Using DEAP the evolutionary computation framework
=================================================

Download: :download:`example_19_using_deap.py <../../../examples/example_19_using_deap.py>`

Less overhead version: :download:`example_19b_using_deap_less_overhead.py <../../../examples/example_19b_using_deap_less_overhead.py>`

This shows an example of how to use *pypet* in combination with
the evolutionary computation framework DEAP_.

Note storing during a single run as in the example adds a lot of overhead and only makes sense
if your fitness evaluation takes quite long. There's also an example with less
overhead at the bottom.


.. literalinclude:: ../../../examples/example_19_using_deap.py


^^^^^^^^^^^^^^^^^^^^^
Less Overhead Version
^^^^^^^^^^^^^^^^^^^^^

.. literalinclude:: ../../../examples/example_19b_using_deap_less_overhead.py


.. _DEAP: http://deap.readthedocs.org/