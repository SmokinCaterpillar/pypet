
.. _example-04:

===================================
04 Multiprocessing
===================================

This code snippet shows how to use multiprocessing with a queue.
In order to use the lock based multiprocessing one simply needs to make the following change:

    `traj.envrionment.wrap_mode=globally.WRAP_MODE_LOCK`.

.. literalinclude:: ../../../examples/example_04_multiprocessing.py

