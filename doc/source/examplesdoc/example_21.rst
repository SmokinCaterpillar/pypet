
.. _example-21:

===========================
Using SCOOP multiprocessing
===========================

Download: :download:`example_21_scoop_multiprocessing.py <../../../examples/example_21_scoop_multiprocessing.py>`

Here you learn how to use *pypet* in combination wiht SCOOP_.
If your SCOOP_ framework is configured correctly (see the `SCOOP docs`_ on how to set up
start-up scripts for grid engines and/or multiple hosts), you can easily use
*pypet* in a multi-server or cluster framework.

Start the script via ``python -m scoop example_21_scoop_multiprocessing.py`` to run
*pypet* with SCOOP_.

By the way, if using SCOOP_, the only multiprocessing wrap mode supported is
``'LOCAL'``, i.e. all your data is actually stored
by your main python process and results are collected from all workers.


.. literalinclude:: ../../../examples/example_21_scoop_multiprocessing.py

.. _SCOOP: http://scoop.readthedocs.org/

.. _SCOOP docs: http://scoop.readthedocs.org/en/0.7/usage.html#use-with-a-scheduler
