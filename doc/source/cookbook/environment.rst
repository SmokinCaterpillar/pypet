
.. _more-on-environment:

==========================
More about the Environment
==========================

-----------------------
Creating an Environment
-----------------------

In most use cases you will interact with the :class:`~pypet.environment.Environment` to
do your numerical simulations.
The environment is your handyman for your numerical experiments, it sets up new trajectories,
keeps log files and can be used to distribute your simulations onto several CPUs.


You start your simulations by creating an environment object:

>>> env = Environment(trajectory='trajectory', comment='A useful comment')

You can pass the following arguments. Note usually you only have to change very few of these
because most of the time the default settings are sufficient.

* ``trajectory``

    The first argument ``trajectory`` can either be a string or a given trajectory object. In case of
    a string, a new trajectory with that name is created. You can access the new trajectory
    via ``trajectory`` property. If a new trajectory is created,
    the comment and dynamically imported classes are added to the trajectory.

* ``add_time``

    Whether the current time in format XXXX_XX_XX_XXhXXmXXs is added to the trajectory name if
    the trajectory is newly created.

* ``comment``

    The comment that will be added to a newly created trajectory.

* ``dynamic_imports``

    Only considered if a new trajectory is created.

    The argument ``dynamic_imports`` is important
    if you have written your own *parameter* or *result* classes, you can pass these either
    as class variables ``MyCustomParameterClass`` or as strings leading to the classes in your package:
    ``'mysim.myparameters.MyCustomParameterClass'``. If you have several classes, just put them in
    a list ``dynamic_imports=[MyCustomParameterClass, MyCustomResultClass]``.
    In case you want to load a custom class
    from disk and the trajectory needs to know how they are built.

    It is **VERY important**, that every class name is **UNIQUE**. So you should not have
    two classes named ``'MyCustomParameterClass'`` in two different python modules!
    The identification of the class is based only on its name and not its path in your packages.

* ``wildcard_functions``

    Dictionary of wildcards like `$` and corresponding functions that are called upon
    finding such a wildcard. For example, to replace the `$` aka `crun` wildcard,
    you can pass the following: ``wildcard_functions = {('$', 'crun'): myfunc}``.

    Your wildcard function `myfunc` must return a unique run name as a function of
    a given integer run index. Moreover, your function must also return a unique
    *dummy* name for the run index being `-1`.

    Of course, you can define your
    own wildcards like `wildcard_functions = {('$mycard', 'mycard'): myfunc)}.
    These are not required to return a unique name for each run index, but can be used
    to group runs into buckets by returning the same name for several run indices.
    Yet, all wildcard functions need to return a dummy name for the index `-1`.

    You may also want to take a look at :ref:`more-on-wildcards`.

* ``automatic_storing``

    If ``True`` the trajectory will be stored at the end of the simulation and
    single runs will be stored after their completion.
    Be aware of data loss if you set this to ``False`` and not
    manually store everything.

* ``log_config``

    Can be path to a logging `.ini` file specifying the logging configuration.
    For an example of such a file see :ref:`more-on-logging`.
    Can also be a dictionary that is accepted by the built-in logging module.
    Set to `None` if you don't want *pypet* to configure logging.

    If not specified, the default settings are used. Moreover, you can manually tweak the
    default settings without creating a new `ini` file.
    Instead of the `log_config` parameter, pass a ``log_folder``,
    a list of `logger_names` and corresponding `log_levels` to fine grain
    the loggers to which the default settings apply.

    For example:

    ``log_folder='logs', logger_names='('pypet', 'MyCustomLogger'), log_levels=(logging.ERROR, logging.INFO)``

    You can further disable multiprocess logging via setting ``log_multiproc=False``.

* ``log_stdout``

    Whether the output of ``stdout`` and ``stderr`` should be recorded into the log files.
    Disable if only logging statement should be recorded. Note if you work with an
    interactive console like *IPython*, it is a good idea to set ``log_stdout=False``
    to avoid messing up the console output.

* ``report_progress``

    If progress of runs and an estimate of the remaining time should be shown.
    Can be `True` or `False` or a triple ``(10, 'pypet', logging.Info)`` where the first number
    is the percentage and update step of the resulting progressbar and
    the second one is a corresponding logger name with which the progress should be logged.
    If you use `'print'`, the `print` statement is used instead. The third value
    specifies the logging level (level of logging statement *not* a filter)
    with which the progress should be logged.

    Note that the progress is based on finished runs. If you use the `QUEUE` wrapping
    in case of multiprocessing and if storing takes long, the estimate of the remaining
    time might not be very accurate.

* ``multiproc``

    ``multiproc`` specifies whether or not to use multiprocessing
    (take a look at :ref:`more-on-multiprocessing`). Default is ``False``.

* ``ncores``

    If ``multiproc`` is ``True``, this specifies the number of processes that will be spawned
    to run your experiment. Note if you use ``'QUEUE'`` mode (see below) the queue process
    is not included in this number and will add another extra process for storing.
    If you have psutil_ installed, you can set `ncores=0` to let psutil_ determine
    the number of CPUs available.

* ``use_scoop``

    If python should be used in a SCOOP_ framework to distribute runs amond a cluster
    or multiple servers. If so you need to start your script via
    ``python -m scoop my_script.py``. Currently, SCOOP_ only works with
    ``'LOCAL'`` ``wrap_mode`` (see below).

* ``use_pool``

    If you choose multiprocessing you can specify whether you want to spawn a new
    process for every run or if you want a fixed pool of processes to carry out your
    computation.

    When to use a fixed pool of processes or when to spawn a new process
    for every run? Use the former if you perform many runs (50k and more)
    which are inexpensive in terms of memory and runtime.
    Be aware that everything you use must be picklable.
    Use the latter for fewer runs (50k and less) and which are longer lasting
    and more expensive runs (in terms of memory consumption).
    In case your operating system allows forking, your data does not need to be
    picklable.
    If you choose ``use_pool=False`` you can also make use of the `cap` values,
    see below.

* ``freeze_input``

    Can be set to ``True`` if the run function as well as all additional arguments
    are immutable. This will prevent the trajectory from getting pickled again and again.
    Thus, the run function, the trajectory as well as all arguments are passed to the pool
    or SCOOP_ workers at initialisation.
    Works also under :func:`~pypet.environment.Environment.run_map`.
    In this case the iterable arguments are, of course, not frozen but passed for every run.

* ``timeout``

    Timeout parameter in seconds passed on to SCOOP_ and ``'NETLOCK'`` wrapping.
    Leave `None` for no timeout. After `timeout` seconds SCOOP_ will assume
    that a single run failed and skip waiting for it.
    Moreover, if using ``'NETLOCK'`` wrapping, after `timeout` seconds
    a lock is automatically released and again
    available for other waiting processes.

* ``cpu_cap``

    If ``multiproc=True`` and ``use_pool=False`` you can specify a maximum CPU utilization between
    0.0 (excluded) and 100.0 (included) as fraction of maximum capacity. If the current CPU
    usage is above the specified level (averaged across all cores),
    *pypet* will not spawn a new process and wait until
    activity falls below the threshold again. Note that in order to avoid dead-lock at least
    one process will always be running regardless of the current utilization.
    If the threshold is crossed a warning will be issued. The warning won't be repeated as
    long as the threshold remains crossed.

    For example let us assume you chose ``cpu_cap=70.0``, ``ncores=3``,
    and currently on average 80 percent of your CPU are
    used. Moreover, at the moment only 2 processes are
    computing single runs simultaneously. Due to the usage of 80 percent of your CPU,
    *pypet* will wait until CPU usage drops below (or equal to) 70 percent again
    until it starts a third process to carry out another single run.

    The parameters ``memory_cap`` and ``swap_cap`` are analogous. These three thresholds are
    combined to determine whether a new process can be spawned. Accordingly, if only one
    of these thresholds is crossed, no new processes will be spawned.

    To disable the cap limits simply set all three values to 100.0.

    You need the psutil_ package to use this cap feature. If not installed and you
    choose cap values different from 100.0 a ValueError is thrown.

* ``memory_cap``

    Cap value of RAM usage. If more RAM than the threshold is currently in use, no new
    processes are spawned. Can also be a tuple ``(limit, memory_per_process)``,
    first value is the cap value (between 0.0 and 100.0),
    second one is the estimated memory per process in mega bytes (MB).
    If an estimate is given a new process is not started if
    the threshold would be crossed including the estimate.

* ``swap_cap``

    Analogous to ``cpu_cap`` but the swap memory is considered.

* ``niceness``

    If you are running on a UNIX based system or you have psutil_ (under Windows) installed,
    you can choose a niceness value to prioritize the child processes executing the
    single runs in case you use multiprocessing.
    Under Linux these usually range from 0 (highest priority)
    to 19 (lowest priority). For Windows values check the psutil_ homepage.
    Leave ``None`` if you don't care about niceness.
    Under Linux the `niceness`` value is a minimum value, if the OS decides to
    nice your program (maybe you are running on a server) *pypet* does not try to
    decrease the `niceness` again.

* ``wrap_mode``

    If ``multiproc`` is ``True``, specifies how storage to disk is handled via
    the storage service. Since PyTables HDF5 is not thread safe, the HDF5 storage service
    needs to be wrapped with a helper class to allow the interaction with multiple processes.

    There are a few options:

    :const:`pypet.pypetconstants.MULTIPROC_MODE_QUEUE`: ('QUEUE')

        Another process for storing the trajectory is spawned. The sub processes
        running the individual single runs will add their results to a
        multiprocessing queue that is handled by an additional process.

    :const:`pypet.pypetconstants.MULTIPROC_MODE_LOCK`: ('LOCK')

        Each individual process takes care about storage by itself. Before
        carrying out the storage, a lock is placed to prevent the other processes
        to store data. Allows loading of data during runs.

    :const:`~pypet.pypetconstants.WRAP_MODE_LOCK`: ('PIPE)

        Experimental mode based on a single pipe. Is faster than ``'QUEUE'`` wrapping
        but data corruption may occur, does not work under Windows
        (since it relies on forking).

    :const:`~pypet.pypetconstant.WRAP_MODE_LOCAL` ('LOCAL')

        Data is not stored during the single runs but after they completed.
        Storing is only performed locally in the main process.

        Note that removing data during a single run has no longer an effect on memory
        whatsoever, because there are references kept for all data
        that is supposed to be stored.

    :const:`~pypet.pypetconstant.WRAP_MODE_NETLOCK` ('NETLOCK')

        Similar to 'LOCK' but locks can be shared across a network.
        Sharing is established by running a lock server that
        distributes locks to the individual processes.
        Can be used with SCOOP_ if all hosts have access to
        a shared home directory.
        Allows loading of data during runs.

    :const:`~pypet.pypetconstant.WRAP_MODE_NETQUEUE` ('NETQUEUE')

        Similar to 'QUEUE' but data can be shared across a network.
        Sharing is established by running a queue server that
        distributes locks to the individual processes.

    If you don't want wrapping at all use
    :const:`pypet.pypetconstants.MULTIPROC_MODE_NONE` ('NONE').

    If you have no clue what I am talking about, you might want to take a look at multiprocessing_
    in python to learn more about locks, queues and thread safety and so forth.

* ``queue_maxsize``

    Maximum size of the Storage Queue, in case of ``'QUEUE'`` wrapping.
    ``0`` means infinite, ``-1`` (default) means the educated guess of ``2 * ncores``.

* ``port``

    Port to be used by lock server in case of ``'NETLOCK'`` wrapping.
    Can be a single integer as well as a tuple ``(7777, 9999)`` to specify
    a range of ports from which to pick a random one.
    Leave `None` for using pyzmq's default range.
    In case automatic determining of the host's IP address fails,
    you can also pass the full address (including the protocol and
    the port) of the host in the network like ``'tcp://127.0.0.1:7777'``.

* ``param gc_interval``

    Interval (in runs or storage operations) with which ``gc.collect()``
    should be called in case of the ``'LOCAL'``, ``'QUEUE'``, or ``'PIPE'`` wrapping.
    Leave ``None`` for never.

    In case of ``'LOCAL'`` wrapping ``1`` means after every run ``2``
    after every second run, and so on. In case of ``'QUEUE'`` or ``'PIPE''`` wrapping
    ``1`` means after every store operation,
    ``2`` after every second store operation, and so on.
    Only calls ``gc.collect()`` in the main (if ``'LOCAL'`` wrapping)
    or the queue/pipe process. If you need to garbage collect data within your single runs,
    you need to manually call ``gc.collect()``.

    Usually, there is no need to set this parameter since the Python garbage collection
    works quite nicely and schedules collection automatically.

* ``clean_up_runs``

    In case of single core processing, whether all results under ``results.runs.run_XXXXXXXX``
    and ``derived_parameters.runs.run_XXXXXXXX`` should be removed after the completion of
    the run. Note in case of multiprocessing this happens anyway since the trajectory
    container will be destroyed after finishing of the process.

    Moreover, if set to ``True`` after post-processing run data is also cleaned up.

* ``immediate_postproc``

    If you use post- and multiprocessing, you can immediately start analysing the data
    as soon as the trajectory runs out of tasks, i.e. is fully explored but the final runs
    are not completed. Thus, while executing the last batch of parameter space points,
    you can already analyse the finished runs. This is especially helpful if you perform some
    sort of adaptive search within the parameter space.

    The difference to normal post-processing is that you do not have to wait until all
    single runs are finished, but your analysis already starts while there are still
    runs being executed. This can be a huge time saver especially if your simulation time
    differs a lot between individual runs. Accordingly, you don't have to wait for a very
    long run to finish to start post-processing.

    Note that after the execution of the final run, your post-processing routine will
    be called again as usual.

    **IMPORTANT**: If you use immediate post-processing, the results that are passed to
    your post-processing function are not sorted by their run indices but by finishing time!

* ``resumable``

    Whether the environment should take special care to allow to resume or continue
    crashed trajectories. Default is ``False``.

    You need to install dill_ to use this feature. dill_ will make snapshots
    of your simulation function as well as the passed arguments.
    **Be aware** that dill_ is still rather experimental!

    Assume you run experiments that take a lot of time.
    If during your experiments there is a power failure,
    you can resume your trajectory after the last single run that was still
    successfully stored via your storage service.

    The environment will create several `.ecnt` and `.rcnt` files in a folder that you specify
    (see below).
    Using this data you can continue crashed trajectories.

    In order to resume trajectories use :func:`~pypet.environment.Environment.resume`.

    Your individual single runs must be completely independent of one
    another to allow continuing to work. Thus, they should **not** be based on shared data
    that is manipulated during runtime (like a multiprocessing manager list)
    in the positional and keyword arguments passed to the run function.

    If you use postprocessing, the expansion of trajectories and continuing of trajectories
    is *not* supported properly. There is no guarantee that both work together.


    .. _dill: https://pypi.python.org/pypi/dill

* ``resume_folder``

    The folder where the resume files will be placed. Note that *pypet* will create
    a sub-folder with the name of the environment.

* ``delete_resume``

    If true, *pypet* will delete the resume files after a successful simulation.

* ``storage_service``

    Pass a given storage service or a class constructor
    (default is :class:`~pypet.storageservice.HDF5StorageService`)
    if you want the environment to create
    the service for you. The environment will pass
    additional keyword arguments you provide directly to the constructor.
    If the trajectory already has a service attached,
    the one from the trajectory will be used. For the additional keyword arguments,
    see below.

* ``git_repository``

    If your code base is under git version control you can specify the path
    (relative or absolute) to
    the folder containing the `.git` directory. See also :ref:`more-on-git`.

* ``git_message``

    Message passed onto git command.

* ``git_fail``

    If `True` the program fails instead of triggering a commit if there are not committed
    changes found in the code base. In such a case a `GitDiffError` is raised.

* ``do_single_runs``

    Whether you intend to actually to compute single runs with the trajectory.
    If you do not intend to carry out single runs (probably because you loaded an old trajectory
    for data analysis), than set to ``False`` and the
    environment won't add config information like number of processors to the
    trajectory.

* ``graceful_exit``

    If ``True`` hitting CTRL+C (i.e.sending SIGINT) will not terminate the program
    immediately. Instead, active single runs will be finished and stored before
    shutdown. Hitting CTRL+C twice will raise a KeyboardInterrupt as usual.

* ``lazy_debug``

    If ``lazy_debug=True`` and in case you debug your code (aka you use *pydevd* and
    the expression ``'pydevd' in sys.modules`` is ``True``), the environment will use the
    :class:`~pypet.storageservice.LazyStorageService` instead of the HDF5 one.
    Accordingly, no files are created and your trajectory and results are not saved.
    This allows faster debugging and prevents *pypet* from blowing up your hard drive with
    trajectories that you probably not want to use anyway since you just debug your code.


If you use the standard :class:`~pypet.storageservice.HDF5StorageService`
you can pass the following additional keyword arguments to the environment.
These are handed over to the service:

* ``filename``

    The name of the hdf5 file. If none is specified, the default
    `./hdf5/the_name_of_your_trajectory.hdf5` is chosen. If ``filename`` contains only a path
    like ``filename='./myfolder/'``, it is changed to
    ``filename='./myfolder/the_name_of_your_trajectory.hdf5'``.

* ``file_title``

    Title of the hdf5 file (only important if file is created new)

* ``overwrite_file``

    If the file already exists it will be overwritten. Otherwise
    the trajectory will simply be added to the file and already
    existing trajectories are not deleted.

* ``encoding``

    Encoding for unicode characters. The default ``'utf8'`` is highly recommended.

* ``complevel``

    You can specify your compression level. 0 means no compression
    and 9 is the highest compression level. By default the level is set to 9 to reduce the
    size of the resulting HDF5 file.
    See `PyTables Compression`_ for a detailed explanation.

* ``complib``

    The library used for compression. Choose between *zlib*, *blosc*, and *lzo*.
    Note that 'blosc' and 'lzo' are usually faster than 'zlib' but it may be the case that
    you can no longer open your hdf5 files with third-party applications that do not rely
    on PyTables.

* ``shuffle``

    Whether or not to use the shuffle filters in the HDF5 library.
    This normally improves the compression ratio.

* ``fletcher32``

    Whether or not to use the *Fletcher32* filter in the HDF5 library.
    This is used to add a checksum on hdf5 data.

* ``pandas_format``

    How to store pandas data frames. Either in 'fixed' ('f') or 'table' ('t') format.
    Fixed format allows fast reading and writing but disables querying the hdf5 data and
    appending to the store (with other 3rd party software other than *pypet*).

* ``purge_duplicate_comments``

    If you add a result via :func:`~pypet.naturalnaming.ResultGroup.f_add_result` or a derived
    parameter :func:`~pypet.naturalnaming.DerivedParameterGroup.f_add_derived_parameter` and
    you set a comment, normally that comment would be attached to each and every instance.
    This can produce a lot of unnecessary overhead if the comment is the same for every
    result over all runs. If ``hdf5.purge_duplicate_comments=True`` than only the comment of the
    first result or derived parameter instance created is stored, or comments
    that differ from this first comment. You might want to take a look at
    :ref:`more-on-duplicate-comments`.

* ``summary_tables``

    Whether summary tables should be created.
    These give overview about 'derived_parameters_runs_summary', and 'results_runs_summary'.
    They give an example about your results by listing the very first computed result.
    If you want to ``purge_duplicate_comments`` you will need the ``summary_tables``.
    You might want to check out :ref:`more-on-overview`.

* ``small_overview_tables``

    Whether the small overview tables should be created.
    Small tables are giving overview about 'config', 'parameters', 'derived_parameters_trajectory',
    'results_trajectory'.

* ``large_overview_tables``

    Whether to add large overview tables. These encompass information about every derived
    parameter and result and the explored parameters in every single run.
    If you want small HDF5 files set to ``False`` (default).

* ``results_per_run``

    Expected results you store per run. If you give a good/correct estimate,
    storage to HDF5 file is much faster in case you want ``large_overview_tables``.

    Default is 0, i.e. the number of results is not estimated!

* ``derived_parameters_per_run``

    Analogous to the above.

Finally, you can also pass properties of the trajectory, like ``v_auto_load=True``
(you can leave the prefix ``v_``, i.e. ``auto_load`` works, too).
Thus, you can change the settings of the trajectory immediately.


.. _GitPython: http://pythonhosted.org/GitPython/0.3.1/index.html

.. _logging: http://docs.python.org/2/library/logging.html

.. _multiprocessing: http://docs.python.org/2/library/multiprocessing.html

.. _`PyTables Compression`: http://pytables.github.io/usersguide/optimization.html#compression-issues


.. _config-added-by-environment:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Config Data added by the Environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Environment will automatically add some config settings to your trajectory.
Thus, you can always look up how your trajectory was run. This encompasses many of the above named
parameters as well as some information about the environment. This additional information includes
a timestamp and a SHA-1 hash code that uniquely identifies your environment.
If you use git integration (:ref:`more-on-git`), the SHA-1 hash code will be the one from
your git commit.
Otherwise the code will be calculated from the trajectory name, the current time, and your
current *pypet* version.

The environment will be named `environment_XXXXXXX_XXXX_XX_XX_XXhXXmXXs`. The first seven
`X` are the first seven characters of the SHA-1 hash code followed by a human readable
timestamp.

All information about the environment can be found in your trajectory under
``config.environment.environment_XXXXXXX_XXXX_XX_XX_XXhXXmXXs``. Your trajectory could
potentially be run by several environments due to merging or extending an existing trajectory.
Thus, you will be able to track how your trajectory was built over time.


.. _more-on-logging:

-------
Logging
-------

*pypet* comes with a full fledged logging environment.

Per default the environment will created loggers_ and stores all logged messages
to log files. This can include also everything written to the standard stream ``stdout``,
like ``print`` statements, for instance. In order to log print statements set
``log_stdout=True``. ``log_stdout`` can also be a tuple: ``('mylogger', 10)``,
specifying a logger name as well as a log-level.
The log-level defines with what level ``stdout`` is logged, it is *not* a filter.

Note that you should always disable this feature
in case you use an interactive
console like *IPython*. Otherwise your console output will be garbled.

After your experiments are finished you can disable logging to files via
:func:`~pypet.environment.Environment.disable_logging`. This also restores the
standard stream.

You can tweak the standard logging settings via passing the following arguments to the environment.
`log_folder` specifies a folder where all log-files are stored. `logger_names` is a list
of logger names to which the standard settings apply. `log_levels` is a list of levels
with which the specified loggers should be logged.
You can further disable multiprocess logging via setting ``log_multiproc=False``.

.. code-block:: python

    import logging
    from pypet import Environment

    env =  Environment(trajectory='mytraj',
                     log_folder = './logs/',
                     logger_nmes = ('pypet', 'MyCustomLogger'),
                     log_levels=(logging.ERROR, logging.INFO),
                     log_stdout=True,
                     log_multiproc=False,
                     multiproc=True,
                     ncores=4)



Furthermore, if the standard settings don't suite you at all,
you can fine grain logging via a logging config file passed via ``log_config='/test/ini.'``.
This file has to follow the `logging configurations`_ of the logging module.

Additionally, if you create file handlers you can use the following wildcards in the filenames
which are replaced during runtime:

    :const:`~pypet.pypetconstants.LOG_ENV` ($env) is replaces by the name of the
    trajectory`s environment.

    :const:`~pypet.pypetconstants.LOG_TRAJ` ($traj) is replaced by the name of the
    trajectory.

    :const:`~pypet.pypetconstants.LOG_RUN` ($run) is replaced by the name of the current
    run.

    :const:`~pypet.pypetconstants.LOG_SET` ($set) is replaced by the name of the current
    run set.

    :const:`~pypet.pypetconstants.LOG_PROC` ($proc) is replaced by the name fo the
    current process and its process id.

    :const:`~pypet.pypetconstant.LOG_HOST` ($host) is replaced by the network name of the
    current host (note that dots (.)  in the hostname are replaced by minus (-))

Note that in contrast to the standard logging package, *pypet* will automatically create
folders for your log-files if these don't exist.

You can further specify settings for multiprocessing logging which will overwrite your current
settings within each new process. To specify settings only used for multiprocessing,
simply append `multiproc_` to the sections of the `.ini` file.

An example logging `ini` file including multiprocessing is given below.

Download: :download:`default.ini <../../../pypet/logging/default.ini>`

.. literalinclude:: ../../../pypet/logging/default.ini


Furthermore, an environment can also be used as a context manager such that logging
is automatically disabled in the end:

.. code-block:: python

    import logging
    from pypet import Environment

    with Environment(trajectory='mytraj',
                     log_config='DEFAULT,
                     log_stdout=True) as env:
        traj = env.trajectory

        # do your complex experiment...

This is equivalent to:

.. code-block:: python

    import logging
    from pypet import Environment

    env = Environment(trajectory='mytraj',
                      log_config='DEFAULT'
                      log_stdout=True)
    traj = env.trajectory

    # do your complex experiment...

    env.disable_logging()


.. _loggers: https://docs.python.org/2/library/logging.html

.. _`logging configurations`: https://docs.python.org/2/library/logging.config.html#logging-config-fileformat


.. _more-on-multiprocessing:

---------------
Multiprocessing
---------------

For an  example on multiprocessing see :ref:`example-04`.

The following code snippet shows how to enable multiprocessing with 4 CPUs, a pool, and a queue.

.. code-block:: python

    env = Environment(self, trajectory='trajectory',
                 filename='../experiments.h5',
                 multiproc=True,
                 ncores=4,
                 use_pool=True,
                 wrap_mode='QUEUE')

Setting ``use_pool=True`` will create a pool of ``ncores`` worker processes which perform your
simulation runs.

**IMPORTANT**: Python multiprocessing does not work well with multi-threading of openBLAS_.
If your simulation relies on openBLAS, you need to make sure that multi-threading is
disabled.
For disabling set the environment variables ``OPENBLAS_NUM_THREADS=1`` and
``OMP_NUM_THREADS=1`` before starting python and using *pypet*.
For instance, numpy and matplotlib (!) use openBLAS to solve linear algebra operations.
If your simulation relies on these packages, make sure the environment variables are changed
appropriately. Otherwise your program might crash or get stuck in an infinite loop.

**IMPORTANT**: In order to allow multiprocessing with a pool (or in general under **Windows**),
all your data and objects of your
simulation need to be serialized with pickle_.
But don't worry, most of the python stuff you use is automatically *picklable*.

If you come across the situation that your data cannot be pickled (which is the case
for some BRIAN networks, for example), don't worry either. Set ``use_pool=False``
(and also ``continuable=False``) and for every simulation run
*pypet* will spawn an entirely new subprocess.
The data is than passed to the subprocess by forking on OS level and not by pickling.
However, this only works under **Linux**. If you use **Windows** and choose ``use_pool=False``
you still need to rely on pickle_ because **Windows** does not support forking of python processes.

Besides, as a general rule of thumb when to use ``use_pool`` or don't:
Use the former if you perform many runs (50k and more)
which are in terms of memory and runtime inexpensive.
Use **no** pool (``use_pool=False``) for fewer runs (50k and less) and which are longer lasting
and more expensive runs (in terms of memory consumption).
In case your operating system allows forking, your data does not need to be
picklable.
Furthermore, if your trajectory contains many parameters and
you want to avoid that your trajectory
gets pickled over and over again you can set ``freeze_input=True``.
The trajectory, the run function as well as the
all additional function arguments are passed to the multiprocessing pool at
initialization. Be aware that the run function as well as the the additional arguments must be
immutable, otherwise your individual runs are no longer independent. In case you use
:func:`~pypet.environment.Environment.run_map` (see below), additional arguments are not frozen
but passed for every run.


Moreover, if you **enable** multiprocessing and **disable** pool usage,
besides the maximum number of utilized processors ``ncores``,
you can specify usage cap levels with ``cpu_cap``, ``memory_cap``,
and ``swap_cap`` as fractions of the maximum capacity.
Values must be chosen larger than 0.0 and smaller or equal to 100.0. If any of these thresholds is
crossed no new processes will be started by *pypet*. For instance, if you want to use 3 cores
aka ``ncores=3`` and set a memory cap of ``memory_cap=90.`` and let's assume that currently only
2 processes are started with currently 95 percent of you RAM are occupied.
Accordingly, *pypet* will not start the third process until RAM usage drops again below
(or equal to) 90 percent.

In addition, (only) the ``memory_cap`` argument can alternatively be a tuple with two entries:
``(cap, memory_per_process)``. First entry is the cap value between 0.0 and 100.0 and the second
one is the estimated memory per process in mega-bytes (MB). If you specify such an estimate,
starting a new process is suspended if the threshold would be reached including the estimated
memory.

Moreover, to prevent dead-lock *pypet* will regardless of the cap values always start at
least one process.
To disable the cap levels, simply set all three to 100.0 (which is default, anyway).
*pypet* does not check if the processes themselves obey the cap limit. Thus,
if one of the process that computes your single runs needs more RAM/Swap or CPU power than the cap
value, this is its very own problem.
The process will **not** be terminated by *pypet*. The process will only cause *pypet* to not start
new processes until the utilization falls below the threshold again.
In order to use this cap feature, you need the psutil_ package.

In addition to the cap values, you can also choose the ``niceness`` of your multiprocessing
processes. If your operating system supports ``nice`` (Linux, MacOS) natively, this feature
works even without the psutil_ package. Priority values under Linux usually range from 0 (highest)
to 19 (lowest), for Windows values see the psutil_ documentation.
Low priority processes will be given less CPU time, so they are *nice* to other processes.
Nicing works with ``use_pool`` as well. Leave ``None`` if you don't care about niceness.

Note that HDF5 is not thread safe, so you cannot use the standard HDF5 storage service out of the
box. However, if you want multiprocessing, the environment will automatically provide wrapper
classes for the HDF5 storage service to allow safe data storage.
There are a couple different modes that are supported. You can choose between them via setting
``wrap_mode``. You can select between ``'QUEUE'``, ``'LOCK'``, ``'PIPE'``,
``'LOCAL'``,``'NETLOCK'``, and ``'NETQUEUE'`` wrapping. If you
have your own service that is already thread safe you can also choose ``'NONE'`` to skip wrapping.

If you chose the ``'QUEUE'`` mode, there will be an additional process spawned that is the only
one writing to the HDF5 file. Everything that is supposed to be stored is send over a queue to
the process. This has the advantage that your worker processes are only busy with your simulation
and are not bothered with writing data to a file.
More important, they don't spend time waiting for other
processes to release a thread lock to allow file writing.
The disadvantages are that you can only store but not load data and
storage relies a lot on pickling of data, so often your entire
trajectory is send over the queue. Moreover, in case of ``'QUEUE'`` wrapping you can
choose the ``queue_maxsize`` of elements that can be put on the queue. To few means that
your worker processes may need to wait until they can put more data on the queue.
To many could blow up your memory in cases the single runs are actually faster than the storage
of the data. ``0`` means a queue of infinite size. Default is ``-1`` meaning *pypet*
makes a conservative estimate of twice te number of processes (i.e. ``2 * ncores``).
This doesn't sound a lot. However, keep in mind that a single element on the queue might already
be quite large like the entire data gathered in a single run.

If you chose the ``'LOCK'`` mode, every process will place a lock before it opens the HDF5 file
for writing data. Thus, only one process at a time stores data. The advantages are the
possibility to load data and that your data
does not need to be send over a queue over and over again. Yet, your simulations may take longer
since processes have to wait often for each other to release locks.

``'PIPE'`` wrapping is a rather experimental mode where all processes feed their data into
a shared `multiprocessing pipe`_. This can be much faster than a queue. However, no
data integrity checks are made. So there's no guarantee that all you data is really saved.
Use this if you go for many runs that just produce small results, and use it carefully.
Since this mode relies on forking of processes, it cannot be used under Windows.

``'LOCAL'`` wrapping means that all data is kept and feed back to your local main process as
soon as a single run is completed. Your data is then stored by your main process.
This wrap mode can be useful if you use *pypet* with SCOOP_ (see also :ref:`pypet-and-scoop`)
in a cluster environment and your workers are distributed over a network.
Note that freeing data with ``f_empty()`` during a single run has no effect
on your memory because the local wrapper will keep references to all data
until the single run is completed.

``'NETLOCK'`` wrapping is similar to ``'LOCK'`` wrapping but locks can be
shared across a computer network. Lock distribution is established by
a server process that listens at a particular ``port`` for lock requests.
The server locks and releases locks accordingly.
Like regular ``'LOCK'`` wrapping
it allows to load data during the runs. This wrap mode can be used with
SCOOP_ if all hosts have access to a shared home directory.
``'NETLOCK'`` wrapping requires an installation of pyzmq_.
However, installing SCOOP_ will automatically install pyzmq_
if it is missing.

``'NETQUEUE'`` wrapping is similar to ``'QUEUE'`` wrapping but data
can be shared across a computer network. Data is collected by a server process that listens
at a particular ``port``. As above this wrap mode can be used with SCOOP_ and requires pyzmq_.

Finally, there also exists a lightweight multiprocessing environment
:class:`~pypet.environment.MultiprocContext`. It allows to use trajectories in a
multiprocess safe setting without the need of a full :class:`~pypet.environment.Environment`.
For instance, you might use this if you also want to analyse the trajectory with
multiprocessing. You can find an example here: :ref:`example-16`.


.. _pickle: http://docs.python.org/2/library/pickle.html

.. _psutil: http://psutil.readthedocs.org/

.. _multiprocessing pipe: https://docs.python.org/2/library/multiprocessing.html#multiprocessing.Pipe

.. _pyzmq: https://zeromq.github.io/pyzmq/


.. _pypet-and-scoop:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Multiprocessing with a Cluster or a Multi-Server Framework
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

*pypet* can be used on computing clusters as well as multiple servers sharing a
home directory via SCOOP_.

Simply create your environment as follows

.. code-block:: python

    env = Environment(multiproc=True,
                      use_scoop=True
                      wrap_mode='LOCAL')


and start your script via ``python -m scoop my_script.py``.
If using SCOOP_, the only multiprocessing wrap modes currently supported are
``'LOCAL'``, ``'NETLOCK'``, and ``'NETQUEUE'``. That is in the former case
all your data is actually stored by your local main python process and
results are collected from all workers. ``'NETLOCK'`` means locks are shared across
the computer network to allow only one process to write data at a time.
Lastly, ``'NETQUEUE'`` starts queue process that collects data stores it.

In case SCOOP_ is configured correctly, you can easily use
*pypet* in a multi-server or cluster framework. :ref:`example-21` shows how to
combine *pypet* and SCOOP_. For instance, if you have multiple servers sharing the
same home directory you can distribute your runs on all of them via
``python -m scoop --hostfile hosts -vv -n 16 my_script.py`` to start 16 workers on your ``hosts``
which is a file specifying the servers to use. It has the format

   | some_host 10
   | 130.148.250.11
   | another_host 4

with the name or IP of the host followed by the number of workers you want to launch (optional).

To use *pypet* and SCOOP_ on a computing cluster one additional needs a bash start-up script.
For instance, for a sun grid engine (SGE), the bash script might look like the following:

    | #!/bin/bash
    | #$ -l h_rt=3600
    | #$ -N mysimulation
    | #$ -pe mp 4
    | #$ -cwd
    |
    | # Launch the simulation with SCOOP
    | python -m scoop -vv mysimulation.py

Most important is the ``-pe`` parallel environment flag to let the computer grid
and SCOOP know how many workers to spawn (here 4).
Other options may be parameters like ``-l h_rt`` defining the maximum runtime,
``-N`` assigning a name, or ``-cwd`` using the the current folder as the working directory.
The particular options depend on your cluster environment and
requirements of the grid provider. This job script, let's name it ``mybash.sh``,
can be submitted via

    $ qsub mybash.sh

Accordingly, the simulation ``mysimulation.py`` gets queued and eventually executed
in parallel on the computer grid as soon as resources are available.

See also the `SCOOP docs`_ and the `example start up scripts`_
on how to set up multiple hosts and scripts for other grid engines.

To avoid overhead of re-pickling the trajectory,
SCOOP_ mode also supports setting ``freeze_input=True`` (see :ref:`more-on-multiprocessing`).

Moreover, you can also use *pypet* with `SAGA Python`_ to manually schedule your experiments
on a cluster environment. :ref:`example-22` shows how to submit batches of experiments
and later on merge the trajectories from each experiment into one.


.. _SCOOP docs: http://scoop.readthedocs.org/en/0.7/usage.html#how-to-launch-scoop-programs

.. _SCOOP: https://scoop.readthedocs.org/

.. _SAGA Python: http://saga-python.readthedocs.org/

.. _example start up scripts: https://github.com/soravux/scoop/tree/master/examples/submit_files

.. _shared constants: http://scoop.readthedocs.org/en/latest/_modules/scoop/shared.html


.. _more-on-git:

---------------
Git Integration
---------------

The environment can make use of version control. If you manage your code with
git_, you can trigger automatic commits with the environment to get a proper snapshot
of the code you actually use. This ensures that your experiments are repeatable.
In order to use the feature of git integration, you additionally need GitPython_.

To trigger an automatic commit simply pass the arguments ``git_repository`` and ``git_message``
to the :class:`~pypet.environment.Environment` constructor. ``git_repository``
specifies the path to the folder containing the `.git` directory. ``git_message`` is optional
and adds the corresponding message to the commit. Note that the message will always be
augmented with some short information about the trajectory you are running.
The commit SHA-1 hash and some other information about the commit will be added to the
config subtree of your trajectory, so you can easily recall that commit from git later on.

The automatic commit functionality will only commit changes in files that are currently tracked by
your git repository, it will **not** add new files.
So make sure to put new files into your repository before running
an experiment. Moreover, a commit will only be triggered if your working copy contains
changes. If there are no changes detected, information about the previous commit will be
added to the trajectory.
By the way, the autocommit function is similar to calling
``$ git add -u`` and ``$ git commit -m 'Some Message'``
in your console.

If you want git version control but no automatic commits of your code base in case of changes,
you can pass the option `git_fail=True` to the environment. Instead of triggering a new
commit in case of changed code, the program will throw a ``GitDiffError``.


.. _git: http://git-scm.com/


.. _more-on-sumatra:

-------------------
Sumatra Integration
-------------------

The environment can make use of a Sumatra_ experimental lab-book.

Just pass the argument ``sumatra_project`` - which should specify the path to your root
sumatra folder - to the :class:`~pypet.environment.Environment` constructor.
You can additionally pass a ``sumatra_reason``, a string describing the
reason for you sumatra simulation. *pypet* will automatically add the name, comment, and
the names of all explored parameters to the reason.
You can also pick a ``sumatra_label``,
set this to ``None`` if you want Sumatra to pick a label for you.
Moreover, *pypet* automatically adds all parameters to the sumatra record. The explored parameters
are added with their full range instead of the default values.

In contrast to the automatic git commits (see above),
which are done as soon as the environment is created, a sumatra record is only created and
stored if you actually perform single runs. Hence, records are stored if you use one of following
three functions:
:func:`~pypet.environment.Environment.run`, or :func:`~pypet.environment.Environment.pipeline`,
or :func:`~pypet.environment.Environment.resume` and your simulation succeeds and does
not crash.


.. _more-on-overview:

--------------------
HDF5 Overview Tables
--------------------

The :class:`~pypet.storageservice.HDF5StorageService` creates summarizing information
about your trajectory that can be found in the ``overview`` group within your HDF5 file.
These overview tables give you a nice summary about all *parameters* and
*results* you needed and computed during your simulations.

The following tables are created depending of your choice of ``large_overview_tables``
and ``small_overview_tables``:

* An `info` table listing general information about your trajectory (needed internally)

* A `runs` table summarizing the single runs (needed internally)

* An `explorations` table listing only the names of explored parameters (needed internally)

* The branch tables:

    `parameters_overview`

        Containing all parameters, and some information about comments, length etc.

    `config_overview`,

        As above, but config parameters

    `results_overview`

        All results  to reduce memory size only a short value
        summary and the name is given. Per default this table is switched off, to enable it
        pass ``large_overview_tables=True`` to your environment.


    `results_summary`

        Only the very first result with a particular **comment** is listed. For instance,
        if you create the result 'my_result' in all with the comment
        ``'Contains my important data'``. Only the very first result having this comment is
        put into the summary table.

        If you use this table, you can purge duplicate comments,
        see :ref:`more-on-duplicate-comments`.

    `derived_parameters_overview`

    `derived_parameters_summary`

        Both are analogous to the result overviews above

* The `explored_parameters_overview` overview table showing the explored parameter ranges

**IMPORTRANT**: Be aware that *overview* and *summary* tables are **only** for eye-balling of data.
You should **never** rely on data in these tables because it might be truncated or outdated.
Moreover, the size of these tables is restricted to 1000 entries. If you add more
parameters or results, these are no longer listed in the *overview* tables.
Finally, deleting or merging information does not affect the overview tables.
Thus, deleted data remains in the table and is not removed. Again, the overview
tables are unreliable and their only purpose is to provide a quick glance at your data
for eye-balling.


.. _more-on-duplicate-comments:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
HDF5 Purging of Duplicate Comments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Adding a result with the same comment in every single run, may create
a lot of overhead. Since the very same comment would be stored in every node in the HDF5 file.
To get rid of this overhead use the option ``purge_duplicate_comments=True`` and
``summary_tables=True``.

For instance, during a single run you call
``traj.f_add_result('my_result', 42, comment='Mostly harmless!')``
and the result will be renamed to ``results.runs.run_00000000.my_result``. After storage
of the result into your HDF5 file, you will find the comment
``'Mostly harmless!'`` in the corresponding HDF5 group node.
If you call ``traj.f_add_result('my_result',-55, comment='Mostly harmless!')``
in another run again, let's say run_00000001, the name will be mapped to
``results.runs.run_00000001.my_result``. But this time the comment will not be saved to disk,
since ``'Mostly harmless!'`` is already part of the very first result with the name 'my_result'.

Furthermore, if you reload your data from the example above,
the result instance ``results.runs.run_00000001.my_result``
won't have a comment only the instance ``results.runs.run_00000000.my_result``.

**IMPORTANT**: If you use multiprocessing, the comment of the first result that was stored
is used. Since runs are performed synchronously there is no guarantee that the comment
of the result with the lowest run index is kept.

**IMPORTANT** Purging of duplicate comments requires overview tables. Since there are no
overview tables for *group* nodes, this feature does not work for comments in *group* nodes.
So try to avoid to adding the same comments over and over again in *group* nodes
within single runs.


.. _more-on-config:

-------------------
Using a Config File
-------------------

You are not limited to specify the logging environment within an `.ini` file.
You can actually specify all settings of the environment and already add some basic parameters
or config data yourself. Simply pass ``config='my_config_file.ini`` to the environment.
If your `.ini` file encompasses logging settings, you don't have to pass another ``log_config``.

Anything found in an `environment`, `trajectory` or `storage_service` section is directly
passed to the environment constructor.
Yet, you can still specify other setting of the environment. Settings passed to the constructor
directly take precedence over settings specified in the ini file.

Anything found under `parameters` or `config` is added to the trajectory as
parameter or config data.


An example `ini` file including logging can be found below.

Download: :download:`environment_config.ini <../../../pypet/logging/env_config_test.ini>`

.. literalinclude:: ../../../pypet/logging/env_config_test.ini

Example usage:

.. code-block:: python

     env = Environment(config='path/to/my_config.ini',
                       multiproc = False # This will set multiproc to `False` regardless of the
                       # setting within the `my_config.ini` file.
                       )


.. _more-on-running:

---------------------
Running an Experiment
---------------------

In order to run an experiment, you need to define a job or a top level function that specifies
your simulation. This function gets as first positional argument the:
:class:`~pypet.trajectory.Trajectory` container (see :ref:`more-on-trajectories`),
and optionally other positional and keyword arguments of your choice.

.. code-block:: python

    def myjobfunc(traj, *args, **kwargs)
        # Do some sophisticated simulations with your trajectory
        ...
        return 'fortytwo'


In order to run this simulation, you need to hand over the function to the environment.
You can also specify the additional arguments and keyword arguments using
:func:`~pypet.environment.Environment.run`:

.. code-block:: python

    env.run(myjobfunc, *args, **kwargs)

The argument list ``args`` and keyword dictionary ``kwargs`` are directly handed over to the
``myjobfunc`` during runtime.

The :func:`~pypet.environment.Environment.run` will return a list of tuples.
Whereas the first tuple entry is the index of the corresponding run and the second entry
of the tuple is the result returned by your run function.
For the example above this would simply always be
the string ``'fortytwo'``, i.e. ``((0, 'fortytwo'), (1, 'fortytwo'),...)``.
These will always be in order of the run indices even in case of multiprocessing.
The only exception to this rule is if you use immediate postprocessing
(see :ref:`more-about-postproc`) where results are in order of finishing time.

using :func:`~pypet.environment.Environment.run` all ``args`` and ``kwargs`` are supposed to
be static, that is all of them are passed to every function call.
If you need to pass different values to each function call of your job function use
:func:`~pypet.environment.Environment.run_map`, where each entry in ``args`` and
``kwargs`` needs to be an iterable (list, tuple, iterator, generator etc.). Hence,
the contents of each iterable are passed one after the other to your job function.
For instance, assuming besides the trajectory your job function takes
3 arguments (here passed as 2 positional and 1 keyword argument):

.. code-block:: python

    def myjobfunc(traj, arg1, arg2, arg3):
        # do stuff

        ...

    env.run(myjobfunc, range(5), ['a','b','c','d','e'], arg3=[5,4,3,2,1])

Thus, the first run of your job function will be started with the arguments
``0`` (from ``range``) ``'a'`` (from the list) and ``arg3=5`` (from the other list).
Accordingly the second run gets passed ``1, 'b', arg3=4``.


^^^^^^^^^^^^^
Graceful Exit
^^^^^^^^^^^^^

Sometimes you might need to stop your experiments via ``CTRL-C``. If you did choose
``graceful_exit=True`` when creating an environment, ``CTRL-C`` won't kill your
program immediately but *pypet* will try to exit gracefully. That is *pypet* will finish
the currently active runs and wait until their results have been returned.
Hitting ``CTRL+C`` twice will, of course, immediately kill your program.

By default ``graceful_exit`` is ``False`` because it does not work in all python contexts.
For instance, ``graceful_exit`` does not work with IPython notebooks.
If in doubt, just try it out.


.. _more-about-postproc:

----------------------
Adding Post-Processing
----------------------

You can add a post-processing function that is called after the execution of all the single
runs via :func:`~pypet.environment.Environment.add_postprocessing`.

Your post processing function must accept the trajectory container as the first argument,
a list of tuples (containing the run indices and results, normally in order of indices
unless you use ``immediate_postproc``, see below), and arbitrary positional and
keyword arguments. In order to pass arbitrary arguments to your post-processing function,
simply pass these first to :func:`~pypet.environment.Environment.add_postprocessing`.

For example:

.. code-block:: python

    def mypostprocfunc(traj, result_list, extra_arg1, extra_arg2):
        # do some postprocessing here
        ...

Whereas in your main script you can call

.. code-block:: python

    env.add_postproc(mypostprocfunc, 42, extra_arg2=42.5)


which will later on pass ``42`` as ``extra_arg1`` and ``42.4`` as ``extra_arg2``. It is the
very same principle as before for your run function.
The post-processing function will be called after the completion of all single runs.

Moreover, please note that your trajectory usually does **not** contain the data computed
during the single runs, since this has been removed after the single runs to save RAM.
If your post-processing needs access to this data, you can simply load it via one of
the many loading functions (:func:`~pypet.naturalnaming.NNGroupNode.f_load_child`,
:func:`~pypet.trajectory.Trajectory.f_load_item`,
:func:`~pypet.naturalnaming.NNGroupNode.f_load`) or even turn on :ref:`more-on-auto-loading`.

Note that your post-processing function should **not** return any results, since these
will simply be lost. However, there is one particular result that can be returned,
see below.


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Expanding your Trajectory via Post-Processing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If your post-processing function expands the trajectory via
:func:`~pypet.trajectory.Trajectory.f_expand` or if your post-processing function returns
a dictionary of lists that can be interpreted to expand the trajectory,
*pypet* will start the single runs again and explore the expanded trajectory.
Of course, after this expanded exploration, your post-processing function will be
called again. Likewise, you could potentially expand again, and after the next expansion
post-processing will be executed again (and again, and again, and again, I guess you get it).
Thus, you can use post-processing for an adaptive search within your parameter space.

**IMPORTANT**: All changes you apply to your trajectory,
like setting auto-loading or changing fast
access, are propagated to the new single runs. So try to undo all changes before finishing
the post-processing if you plan to trigger new single runs.

Moreover, your post-processing function can return more than a dictionary,
it can return up to five elements.

    1. dictionary for further exploration

    2. New ``args`` tuple that is passed to subsequent calls to your job function.
    Potentially these have to be iterables in case you used
    :func:`~pypet.environment.Environment.run_map`.

    3. New ``kwargs`` dictionary that is passed as keyword arguments to
    subsequent calls to your job function.
    Potentially these have to be iterables in case you used
    :func:`~pypet.environment.Environment.run_map`.

    4. New ``args`` for the next call to your post-proc function

    5. New ``kwargs`` for the next call to your post-proc function.


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Expanding your Trajectory and using Multiprocessing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you use multiprocessing and you want to adaptively expand your trajectory, it can
be a waste of precious time to wait until all runs have finished.
Accordingly, you can set the argument ``immediate_postproc`` to ``True`` when you create
your environment. Then your post-processing function is called as soon as *pypet* runs
out of jobs for single runs. Thus, you can expand your trajectory while the last batch
of single runs is still being executed.

To emphasize this a bit more and to not be misunderstood: Your post-processing function is **not**
called as soon as a single run finishes and the first result is available but as soon as there
are **no more** single runs available to start new processes.
Still, that does not mean you have to wait
until *all* single runs are finished (as for normal post-processing),
but you can already add new single runs to the trajectory
while the final *n* runs are still being executed. Where *n* is determined by the number of cores
(``ncores``) and probably the *cap values* you have chosen (see :ref:`more-on-multiprocessing`).

*pypet* will **not** start a new process for your post-processing. Your post-processing function
is executed in the main process (this makes writing actual post-processing functions much easier
because you don't have to wrap your head around dead-locks).
Accordingly, post-processing should be rather quick in comparison to your single runs, otherwise
post-processing will become the bottleneck in your parallel simulations.

**IMPORTANT**: If you use immediate post-processing, the results that are passed to
your post-processing function are not sorted by their run indices but by finishing time!


----------------------------
Using an Experiment Pipeline
----------------------------

Your numerical experiments usually work like the following: You add some parameters to
your trajectory, you mark a few of these for exploration, and you pass your main function
to the environment via :func:`~pypet.environment.Environment.run`. Accordingly, this
function will be executed with all parameter combinations. Maybe you want some post-processing
in the end and that's about it. However, sometimes even the addition of parameters can be
fairly complex. Thus, you want this part under the supervision of an environment, too.
For instance, because you have a Sumatra_ lab-book and adding of parameters should also account as
runtime.
Thus, to have your entire experiment and not only the exploration of the parameter space
managed by *pypet* you can use the :func:`~pypet.environment.Environment.pipeline`
function, see also :ref:`example-13`.

You have to pass a so called *pipeline* function to
:func:`~pypet.environment.Environment.pipeline` that defines your entire experiment.
Accordingly, your pipeline function is only allowed to take a single parameter,
that is the trajectory container.
Next, your pipeline function can fill in some parameters and do some pre-processing.
Afterwards your pipeline function needs to return the run function, the corresponding arguments
and potentially a post-processing function with arguments.
To be more precise your pipeline function needs to return two tuples with at most 3 entries each,
for example:

.. code-block:: python

    def myjobfunc(traj, extra_arg1, extra_arg2, extra_arg3)
        # do some sophisticated simulation stuff
        solve_p_equals_np(traj, extra_arg1)
        disproof_spock(traj, extra_arg2, extra_arg3)
        ...

    def mypostproc(traj, postproc_arg1, postproc_arg2, postproc_arg3)
        # do some analysis here
        ...

        exploration_dict={'ncards' : [100, 200]}

        if maybe_i_should_explore_more_cards:
            return exploration_dict
        else
            return None

    def mypipeline(traj):
        # add some parameters
        traj.f_add_parameter('poker.ncards', 7, comment='Usually we play 7-card-stud')
        ...
        # Explore the trajectory
        traj.f_explore({'ncards': range(42)})

        # Finally return the tuples
        args = (myarg1, myarg2) # myargX can be anything form ints to strings to complex objects
        kwargs = {'extra_arg3': myarg3}
        postproc_args = (some_other_arg1,) # Check out the comma here! Important to make it a tuple
        postproc_kwargs = {'postproc_arg2' : some_other_arg2,
                           'postproc_arg3' : some_other_arg3}
        return (myjobfunc, args, kwargs), (mypostproc, postproc_args, postproc_kwargs)


The first entry of the first tuple is you run or top-level execution function, followed by
a list or tuple defining the positional arguments and, thirdly, a dictionary defining the
keyword arguments. The second tuple has to contain the post-processing function and positional
arguments and keyword arguments. If you do not have any positional arguments pass an
empty tuple ``()``, if you do not have any keyword arguments pass an empty dictionary ``{}``.

If you do not need postprocessing at all, your pipeline function can simply return
the run function followed by the positional and keyword arguments:

.. code-block:: python

    def mypipeline(traj):
        #...
        return myjobfunc, args, kwargs


.. _more-on-optimization:

----------------------
Parameter Optimization
----------------------

Since *pypet* offers iterative post-processing and
the ability to :func:`~pypet.trajectory.Trajectory.f_expand`
trajectories, you can iteratively explore the parameter space.
*pypet* does **not** provide built-in parameter optimization methods.
However, *pypet* can be easily combined with frameworks like the evolutionary
algorithms toolbox DEAP_ for adaptive parameter optimization.
:ref:`example-19` shows how you can integrate *pypet* and DEAP_.

.. _DEAP: http://deap.readthedocs.org/en/


.. _more-on-continuing:

-------------------------------------------
Continuing or Resuming a Crashed Experiment
-------------------------------------------

In order to use this feature you need dill_.
Careful, dill_ is rather experimental and still in alpha status!

If all of your data can be handled by dill_,
you can use the config parameter ``resumable=True`` passed
to the :class:`~pypet.environment.Environment` constructor.
This will create a resume directory (name specified by you via ``resume_folder``)
and a sub-folder with the name of the trajectory. This folder is your safety net
for data loss due to a computer crash. If for whatever reason your day or week-long
lasting simulation was interrupted, you can resume it
without recomputing already obtained results. Note that this works only if the
HDF5 file is not corrupted and for interruptions due
to computer crashes, like power failure etc. If your
simulations crashed due to errors in your code, there is no way to restore that!

You can resume a crashed trajectory via :func:`~pypet.environment.Environment.resume`
with the name of the resume folder (not the subfolder) and the name of the trajectory:

.. code-block:: python

    env = Environment(continuable=True)

    env.resume(trajectory_name='my_traj_2015_10_21_04h29m00s',
                            resume_folder='./experiments/resume/')


The neat thing here is, that you create a novel environment for the continuation. Accordingly,
you can set different environmental settings, like changing the number of cores, etc.
You *cannot* change any HDF5 settings or even change the whole storage service.

When does continuing not work?

Continuing does **not** work with ``'QUEUE'`` or ``'PIPE'`` wrapping in case of multiprocessing.

Moreover, continuing will **not** work if your top-level simulation function
or the arguments passed to your simulation function are altered between individual runs.
For instance, if you use multiprocessing
and you want to write computed data into a shared data list
(like ``multiprocessing.Manager().list()``, see :ref:`example-12`),
these changes will be lost and cannot be captured by the resume snapshots.

A work around here would be to not manipulate the arguments but pass these values as results
of your top-level simulation function. Everything that is returned by your top-level function
will be part of the snapshots and can be reconstructed after a crash.

Continuing *might not* work if you use post-processing that expands the trajectory.
Since you are not limited in how you manipulate the trajectory within your post-processing,
there are potentially many side effects that remain undetected by the resume snapshots.
You can try to use both together, but there is **no** guarantee whatsoever that continuing a
crashed trajectory and post-processing with expanding will work together.


.. _sumatra: http://neuralensemble.org/sumatra/

.. _openBLAS: http://www.openblas.net/


-----------
Manual Runs
-----------

You are not obliged to use a trajectory with an environment. If you still want the
distinction between single runs but manually schedule them, take a look at
the :func:`pypet.utils.decorators.manual_run` decorator. An example of how to use it
is given here :ref:`example-20`.


.. _wrap-project:

------------------------------------------
Combining *pypet* with an Existing Project
------------------------------------------

If you already have a rather evolved simulator yourself, there are ways
to combine it with *pypet* instead of starting from scratch. Usually,
the only thing you need is a wrapper function that passes parameters
from the :class:`~pypet.trajectory.Trajectory` to your simulator and puts
your results back into it. Finally, you need some boilerplate like code to
create an :class:`~pypet.environment.Environment`, add some parameters and exploration,
and start the wrapping function instead of your simulation directly.
A full fledged example is given here: :ref:`example-17`.
Or take this script for instance where ``my_simulator`` is your original simulation:

.. code-block:: python

    from pypet import Environment


    def my_simulator(a,b,c):
        # Do some serious stuff and compute a `result`
        result = 42  # What else?
        return result


    def my_pypet_wrapper(traj):
        result = my_simulator(traj.a, traj.b, traj.c)
        traj.f_add_result('my_result', result, comment='Result from `my_simulator`')


    def main():
        # Boilerplate main code:

        # Create the environment
        env = Environment()
        traj = env.traj

        # Now add the parameters and some exploration
        traj.f_add_parameter('a', 0)
        traj.f_add_parameter('b', 0)
        traj.f_add_parameter('c', 0)
        traj.f_explore({'a': [1,2,3,4,5]})

        # Run your wrapping function instead of your simulator
        env.run(my_pypet_wrapper)


    if __name__ == '__main__':
        # Let's make the python evangelists happy and encapsulate
        # the main function as you always should ;-)
        main()