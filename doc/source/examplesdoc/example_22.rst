
.. _example-22:

==============================
Using *pypet* with SAGA-Python
==============================

This example shows how to use *pypet* in combination with `SAGA Python`_.
It shows how to establish an **ssh** connection to a given server (`start_saga.py`) and then

    1. Upload all necessary scripts
    2. Start several batches of trajectories
    3. Merge all trajectories into a single one

There are only a few modification necessary to switch from just using **ssh** to
actually submitting jobs on cluster (like a Sun Grid Engine with ``qsub``), see the
`SAGA Python`_ documentation.

To run the example, you only need to add your server address, user name, password, and
working directory (on the server) to the `start_saga.py` file and then
execute ``python start_saga.py``. `the_task.py` and `merge_trajs`
are used on the server side and you don't need to touch these at all, but they need to
be in the same folder as your `start_saga.py` file.

Download: :download:`start_saga.py <../../../examples/example_22_saga_python/start_saga.py>`

Download: :download:`the_task.py <../../../examples/example_22_saga_python/the_task.py>`

Download: :download:`merge_trajs.py <../../../examples/example_22_saga_python/merge_trajs.py>`


---------------
Start Up Script
---------------

.. literalinclude:: ../../../examples/example_22_saga_python/start_saga.py

-------------------
The Experiment File
-------------------

.. literalinclude:: ../../../examples/example_22_saga_python/the_task.py

----------------------------
Script to merge Trajectories
----------------------------

.. literalinclude:: ../../../examples/example_22_saga_python/merge_trajs.py


.. _SAGA Python: http://saga-python.readthedocs.org/