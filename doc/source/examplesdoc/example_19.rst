
.. _example-19:

=================================================
Using DEAP the evolutionary computation framework
=================================================

Download: :download:`example_19_using_deap.py <../../../examples/example_19_using_deap.py>`

Less overhead version: :download:`example_19b_using_deap_less_overhead.py <../../../examples/example_19b_using_deap_less_overhead.py>`

Less overhead and *post-processing* version: :download:`example_19c_using_deap_with_post_processing.py <../../../examples/example_19c_using_deap_with_post_processing.py>`


This shows an example of how to use *pypet* in combination with
the evolutionary computation framework DEAP_.

Note storing during a single run as in the example adds a lot of overhead and only makes sense
if your fitness evaluation takes quite long. There's also an example with less
overhead at the middle section.

Moreover, if you are interested in using DEAP_ in a post-processing scheme
(:ref:`more-about-postproc`), at the very bottom you can find an example using
post-processing.


.. literalinclude:: ../../../examples/example_19_using_deap.py


^^^^^^^^^^^^^^^^^^^^^
Less Overhead Version
^^^^^^^^^^^^^^^^^^^^^

.. literalinclude:: ../../../examples/example_19b_using_deap_less_overhead.py


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Less Overhead and Post-Processing Version
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. literalinclude:: ../../../examples/example_19c_using_deap_with_post_processing.py


.. _DEAP: http://deap.readthedocs.org/