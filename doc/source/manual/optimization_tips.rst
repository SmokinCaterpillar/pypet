
.. _optimization-tips:

=================
Optimization Tips
=================

------------------------------------
Group your Results into Buckets/Sets
------------------------------------

HDF5 has a hard time managing nodes with more than 20,000 children.
Accordingly, file I/O and reading or writing data can become very inefficient
if one of your trajectory groups has more than 20,000 children.
For instance, this may happen to you if you explore many runs.

Suppose in every run you add the following result:

    >>> traj.f_add_result('some_group.$.z', 42, comment='Universal answer.')

If this line is executed in each of your, let's say 100,000 runs, the node ``some_group``
will have at least 100k children. Hence, storage and loading becomes extremely slow.

The simplest way around this problem is to group your results into buckets using the
``'$set'`` wildcard, see also :ref:`more-on-wildcards`. Accordingly, your result addition becomes:

    >>> traj.f_add_result('some_group.$set.$.z', 42, comment='Universal answer.')

Hence, even running 100k runs, `some_group` has only 100 children, each having only 1000 children
themselves.


-----------------
Huge Explorations
-----------------

Yet, this approach will still fall short in case you have parameter exploration of more than
1,000,000 runs, because loading meta-data of your trajectory may already take more than
a minute. And this can be annoying. In case of such huge explorations, I would
advise you to tailor your parameter space and split it among several individual trajectories.


---------------------
Collect Small Results
---------------------

In case you compute only small results during your runs, like a single value,
but you do this quite often (100k+), it might be more convenient to return
the result instead of storing it into the trajectory directly.
As a consequence, you can collect these single values later on during the
post-processing phase and store all of them together into a single result.
This has also been done for the estimated firing rate in the :ref:`tutorial`.


-------------------------
Many and Fast Single Runs
-------------------------

In case you perform many single runs and milliseconds matter, use a pool (``use_pool=True``) in
combination with a queue (``wrap_mode='QUEUE'``, see :ref:`more-on-multiprocessing`) or the even
faster - but potentially unreliable - method of using a shared pipe (``wrape_mode='PIPE'``).
Moreover, to avoid re-pickling of unnecessary data of your trajectory,
store and remove all data that is not needed during single runs.

For instance, if you don't really need config data during the runs, use the following
**before** calling the environment's :func:`~pypet.environment.Environment.run` function:

.. code-block:: python

    traj.f_store()
    traj.config.f_remove(recursive=True)


This may save a couple of milliseconds each run because
the config data no longer needs to be pickled and send over the queue for storage.

Moreover, you can further avoid unnecessary pickling for the pool and SCOOP_ by setting
``freeze_input=True``.
Accordingly, the trajectory, your target function, and all additional arguments are passed
to each pool or SCOOP_ process at initialisation and not for each run individually. However,
in order to use this feature, you must make sure that neither your target function nor the
additional arguments are mutated over the course of your runs.
In case you use SCOOP_, try do avoid running many batches of experiments
in one go with ``freeze_input=True`` because memory consumption of all the SCOOP_ workers
may increase with every batch, see also :ref:`pypet-and-scoop`.

.. _SCOOP: http://scoop.readthedocs.org/
