
.. _example-04:

===============
Multiprocessing
===============

Download: :download:`example_04_multiprocessing.py <../../../examples/example_04_multiprocessing.py>`

This code snippet shows how to use multiprocessing with locks.
In order to use the queue based multiprocessing one simply needs to make the following change
for the environment creation:

    ``wrap_mode=pypetconstants.WRAP_MODE_QUEUE``.

.. literalinclude:: ../../../examples/example_04_multiprocessing.py

