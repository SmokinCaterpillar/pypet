


.. _more-on-environment:

============================
More about the Environment
============================

-----------------------------
Constructing an Environment
-----------------------------

In most use cases you will interact with the :class:`~pypet.environment.Environment` to
do your numerical simulations.
The environment is your handyman for your numerical experiments, it sets up new trajectories,
keeps log files and can be used to distribute your simulations onto several cpus.

Note in case you use the environment there is no need to call
:func:`~pypet.trajectory.Trajectory.f_store`
for data storage, this will always be called at the end of the simulation and at the end of a
single run automatically (unless you set ``automatic_storing`` to ``False``).
Yet, be aware that if you add any custom data during a single run not under a group named
`run_XXXXXXXX` this data will not
be immediately saved after the completion of the run. In case of multiprocessing this data will be
lost if not manually stored.

You start your simulations by creating an environment object:

>>> env = Environment(trajectory='trajectory',
                 add_time=True,
                 comment='',
                 dynamic_imports=None,
                 automatic_storing=True,
                 log_folder=None,
                 log_level=logging.INFO,
                 log_stdout=True,
                 multiproc=False,
                 ncores=1,
                 use_pool=False,
                 cpu_cap=1.0,
                 memory_cap=1.0,
                 swap_cap=1.0,
                 wrap_mode=pypetconstants.WRAP_MODE_LOCK,
                 clean_up_runs=True,
                 immediate_postproc=False,
                 deep_copy_data=False,
                 continuable=False,
                 continue_folder=None,
                 delete_continue=True,
                 use_hdf5=True,
                 filename=None,
                 file_title=None,
                 encoding='utf8',
                 complevel=9,
                 complib='zlib',
                 shuffle=True,
                 fletcher32=False,
                 pandas_format='fixed',
                 pandas_append=False,
                 purge_duplicate_comments=True,
                 summary_tables = True,
                 small_overview_tables=True,
                 large_overview_tables=False,
                 results_per_run=0,
                 derived_parameters_per_run=0,
                 git_repository = None,
                 git_message='',
                 sumatra_project=None,
                 sumatra_reason = '',
                 sumatra_label = None,
                 do_single_runs=True,
                 lazy_debug=False):

You can pass the following arguments. Note usually you only have to change very few of these
because most of the time the default settings are sufficient.

* ``trajectory``

    The first argument ``trajectory`` can either be a string or a given trajectory object. In case of
    a string, a new trajectory with that name is created. You can access the new trajectory
    via ``v_trajectory`` property. If a new trajectory is created, the comment and dynamically imported
    classes are added to the trajectory.

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
    a list ``dynamic_imports=[MyCustomParameterClass,MyCustomResultClass]``.
    The trajectory needs to know your custom classes in case you want to load a custom class
    from disk and the trajectory needs to know how they are built.

    It is **VERY important**, that every class name is **UNIQUE**. So you should not have
    two classes named ``'MyCustomParameterClass'`` in two different python modules!
    The identification of the class is based only on its name and not its path in your packages.

* automatic_storing

    If ``True`` the trajectory will be stored at the end of the simulation and
    single runs will be stored after their completion.
    Be aware of data loss if you set this to ``False`` and not
    manually store everything.


* ``log_folder``

    The ``log_folder`` specifies where all log files will be stored.
    The environment will create a sub-folder with the name of the trajectory and the name
    of the environment where all txt files will be put.
    The environment will create a major logfile (*main.txt*) incorporating all messages of the
    current log level and beyond and
    a log file that only contains warnings and errors *errors_and_warnings.txt*.

    Moreover, if you use multiprocessing,
    there will be a log file for every single run and process named
    *run_XXXXXXXX_process_YYYY.txt* with *XXXXXXXX* the run id and *YYYYY* the process
    id. It contains all log messages produced by the corresponding process within the single run.

    If you don't want the logging message stored to the file system set to ``None``-

    If you don't set a log level elsewhere before, the standard level will be *INFO*
    (if you have no clue what I am talking about, take a look at the logging_ module).

* ``logger_names``

    List or tuple of logger names to which the logging settings apply.
    Default is root ``('',)``, i.e.  all logging messages are logged to the folder
    specified above. For instance, if you only want *pypet* to save messages created by itself
    and not by your own loggers use ``logger_names='(pypet,)'``. If you only
    want to store message from your custom loggers, you could pass the names of your
    loggers, like ``logger_names=('MyCustomLogger1', 'MyCustomLogger2', ...)``.
    Or, for example, if you only want to store messages from
    ``stdout`` and ``stderr`` set ``logger_names`` to ``('STDOUT','STDERR')``.

* ``log_levels``

    List or tuple of log levels with the same length as ``logger_names``.
    If the length is 1 and ``loger_names`` has more than 1 entry,
    the log level is used for all loggers.

    Default is level ``(logging.INFO,)``.
    If you choose ``(logging.DEBUG,)`` more verbose statements will be displayed.
    Set to ``None`` if you don't want to set log-levels or if you already
    specified log-levels somewhere else.

* ``log_stdout``

    Whether the output of STDOUT and STDERROR should be recorded into the log files.
    Disable if only logging statement should be recorded. Note if you work with an
    interactive console like IPython, it is a good idea to set ``log_stdout=False``
    to avoid messing up the console output.

* ``multiproc``

    ``multiproc`` specifies whether or not to use multiprocessing
    (take a look at :ref:`more-on-multiprocessing`). Default is 0 (False).

* ``ncores``

    If ``multiproc`` is ``True``, this specifies the number of processes that will be spawned
    to run your experiment. Note if you use ``'QUEUE'`` mode (see below) the queue process
    is not included in this number and will add another extra process for storing.

* ``use_pool``

    If you choose multiprocessing you can specify whether you want to spawn a new
    process for every run or if you want a fixed pool of processes to carry out your
    computation.

    If you use a pool, all your data and the tasks you compute must be picklable!
    If you never heard about pickling or object serialization, you might want to take a loot at the
    pickle_ module.

    Thus, if your simulation data cannot be pickled (which is the case for some BRIAN networks,
    for instance), choose ``use_pool=False`` and continuable=``False`` (see below).

* ``cpu_cap``

    If ``multiproc=True`` and ``use_pool=False`` you can specify a maximum cpu utilization between
    0.0 (excluded) and 1.0 (included) as fraction of maximum capacity. If the current cpu
    usage is above the specified level (averaged across all cores),
    *pypet* will not spawn a new process and wait until
    activity falls below the threshold again. Note that in order to avoid dead-lock at least
    one process will always be running regardless of the current utilization.
    If the threshold is crossed a warning will be issued. The warning won't be repeated as
    long as the threshold remains crossed.

    For example let us assume you chose``cpu_cap=0.7``, ``ncores=3``,
    and currently on average 80 percent of your cpu are
    used. Moreover, at the moment only 2 processes are
    computing single runs simultaneously. Due to the usage of 80 percent of your cpu,
    *pypet* will wait until cpu usage drops below (or equal to) 70 percent again
    until it starts a third process to carry out another single run.

    The parameters ``memory_cap`` and ``swap_cap`` are analogous. These three thresholds are
    combined to determine whether a new process can be spawned. Accordingly, if only one
    of these thresholds is crossed, no new processes will be spawned.

    To disable the cap limits simply set all three values to 1.0.

    You need the psutil_ package to use this cap feature. If not installed, the cap
    values are simply ignored.

* ``memory_cap``

    Cap value of RAM usage. If more RAM than the threshold is currently in use, no new
    processes are spawned.

* ``swap_cap``

    Analogous to ``memory_cap`` but the swap memory is considered.

* ``wrap_mode``

     If ``multiproc`` is ``True``, specifies how storage to disk is handled via
     the storage service. Since PyTables HDF5 is not thread safe, the HDF5 storage service
     needs to be wrapped with a helper class to allow the interaction with multiple processes.

     There are two options:

     :const:`pypet.pypetconstants.MULTIPROC_MODE_QUEUE`: ('QUEUE')

     Another process for storing the trajectory is spawned. The sub processes
     running the individual single runs will add their results to a
     multiprocessing queue that is handled by an additional process.


     :const:`pypet.pypetconstants.MULTIPROC_MODE_LOCK`: ('LOCK')

     Each individual process takes care about storage by itself. Before
     carrying out the storage, a lock is placed to prevent the other processes
     to store data.

     If you don't want wrapping at all use :const:`pypet.pypetconstants.MULTIPROC_MODE_NONE` ('NONE')

     If you have no clue what I am talking about, you might want to take a look at multiprocessing_
     in python to learn more about locks, queues and thread safety and so forth.

* ``clean_up_runs``

    In case of single core processing, whether all results under ``results.runs.run_XXXXXXXX``
    and ``derived_parameters.runs.run_XXXXXXXX`` should be removed after the completion of
    the run. Note in case of multiprocessing this happens anyway since the single run
    container will be destroyed after finishing of the process.

    Moreover, if set to ``True`` after post-processing it is checked if there is still data
    under ``results.runs`` and ``derived_parameters.runs`` and this data is removed if
    the trajectory is expanded.

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

* ``continuable``

    Whether the environment should take special care to allow to resume or continue
    crashed trajectories. Default is ``False``.

    You need to install dill_ to use this feature. dill_ will make snapshots
    of your simulation function as well as the passed arguments.
    BE AWARE that dill_ is still rather experimental!

    Assume you run experiments that take a lot of time.
    If during your experiments there is a power failure,
    you can resume your trajectory after the last single run that was still
    successfully stored via your storage service.

    The environment will create several `.ecnt` and `.rcnt` files in a folder that you specify
    (see below).
    Using this data you can continue crashed trajectories.

    In order to resume trajectories use :func:`~pypet.environment.Environment.f_continue`.

    Be aware that your individual single runs must be completely independent of one
    another to allow continuing to work. Thus, they should **NOT** be based on shared data
    that is manipulated during runtime (like a multiprocessing manager list)
    in the positional and keyword arguments passed to the run function.

    If you use postprocessing, the expansion of trajectories and continuing of trajectories
    is NOT supported properly. There is no guarantee that both work together.


    .. _dill: https://pypi.python.org/pypi/dill


* ``continue_folder``

    The folder where the continue files will be placed. Note that *pypet* will create
    a sub-folder with the name of the environment.

* ``delete_continue``

    If true, *pypet* will delete the continue files after a successful simulation.

* `storage_service``

    Pass a given storage service or a class constructor (default ``HDF5StorageService``)
    if you want the environment to create
    the service for you. The environment will pass the
    additional keyword arguments you pass directly to the constructor.
    If the trajectory already has a service attached,
    the one from the trajectory will be used. For the additional keyword arguments,
    see below.

* ``git_repository``

    If your code base is under git version control you can specify the path
    (relative or absolute) to
    the folder containing the `.git` directory. See also :ref:`more-on-git`.

* ``git_message``

    Message passed onto git command.

* ``do_single_runs``

    Whether you intend to actually to compute single runs with the trajectory.
    If you do not intend to carry out single runs (probably because you loaded an old trajectory
    for data analysis), than set to ``False`` and the
    environment won't add config information like number of processors to the
    trajectory.

* ``lazy_debug``

    If ``lazy_debug=True`` and in case you debug your code (aka you use *pydevd* and
    the expression ``'pydevd' in sys.modules`` is ``True``), the environment will use the
    :class:`~pypet.storageservice.LazyStorageService` instead of the HDF5 one.
    Accordingly, no files are created and your trajectory and results are not saved.
    This allows faster debugging and prevents *pypet* from blowing up your hard drive with
    trajectories that you probably not want to use anyway since you just debug your code.

If you use the standard ``HDF5StorageService`` you can pass the following additional
keyword arguments to the environment. These are handed over to the service:

* ``filename``

    The name of the hdf5 file. If none is specified the default
    `./hdf5/the_name_of_your_trajectory.hdf5` is chosen. If ``filename`` contains only a path
    like ``filename='./myfolder/'``, it is changed to
    ``filename='./myfolder/the_name_of_your_trajectory.hdf5'``.

* ``file_title``

    Title of the hdf5 file (only important if file is created new)

* ``new_file``

    If the file already exists it will be overwritten. Otherwise
    the trajectory will simply be added to the file and already
    existing trajectories are not deleted.

* ``encoding``

    Encoding for unicode characters. The default ``'utf8'`` is highly recommended.

* ``complevel``

    If you use HDF5, you can specify your compression level. 0 means no compression
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

* ``pandas_append``

    If format is 'table', ``pandas_append=True`` allows to modify the tables after storage with
    other 3rd party software. Currently appending is not supported by *pypet* but this
    feature will come soon.

* ``purge_duplicate_comments``

    If you add a result via :func:`pypet.trajectory.SingleRun.f_add_result` or a derived
    parameter :func:`pypet.trajectory.SingleRun.f_add_derived_parameter` and
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
    Small tables are giving overview about 'config','parameters','derived_parameters_trajectory',
    'results_trajectory'.

* ``large_overview_tables``

    Whether to add large overview tables. This encompasses information about every derived
    parameter and result and the explored parameters in every single run.
    If you want small HDF5 files, this is the first option to set to False.

* ``results_per_run``

    Expected results you store per run. If you give a good/correct estimate
    storage to HDF5 file is much faster in case you store LARGE overview tables.

    Default is 0, i.e. the number of results is not estimated!

* ``derived_parameters_per_run``

    Analogous to the above.


.. _GitPython: http://pythonhosted.org/GitPython/0.3.1/index.html

.. _logging: http://docs.python.org/2/library/logging.html

.. _multiprocessing: http://docs.python.org/2/library/multiprocessing.html

.. _`PyTables Compression`: http://pytables.github.io/usersguide/optimization.html#compression-issues

.. _config-added-by-environment:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Config Data added by the Environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Environment will automatically add some config settings to your trajectory.
Thus, you can always look up how your trajectory was run. This encompasses many of the above named
parameters as well as some information about the environment. This additional information includes
a timestamp and a SHA-1 hash code that uniquely identifies your environment.
If you use git integration (:ref:`more-on-git`), the SHA-1 hash code will be the one from your git commit.
Otherwise the code will be calculated from the trajectory name, the current time, and your
current pypet version.

The environment will be named `environment_XXXXXXX_XXXX_XX_XX_XXhXXmXXs`. The first seven
`X` are the first seven characters of the SHA-1 hash code followed by a human readable
timestamp.

All information about the environment can be found in your trajectory under
``config.environment.environment_XXXXXXX_XXXX_XX_XX_XXhXXmXXs``. Your trajectory could
potentially be run by several environments due to merging or extending an existing trajectory.
Thus, you will be able to track how your trajectory was build over time.


.. _more-on-overview:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Overview Tables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Overview tables give you a nice summary about all *parameters* and *results* you needed and
computed during your simulations. They will be placed under the subgroup
``overview`` at the top-level in your trajectory group in the HDF5 file.
In addition, for every single run there will be a small overview
table about the explored parameter values of that run.

The following tables are created:

* An `info` table listing general information about your trajectory

* A `runs` table summarizing the single runs

* The branch tables:

    `parameters`

        Containing all parameters, and some information about comments, length etc.

    `config`,

        As above, but config parameters

    `results_runs`

        All results of all individual runs, to reduce memory size only a short value
        summary and the name is given. Per default this table is switched off, to enable it
        pass ``large_overview_tables=True`` to your environment.


    `results_runs_summary`

        Only the very first result with a particular name is listed. For instance
        if you create the result 'my_result' in all runs only the result of `run_00000000`
        is listed with detailed information.

        If you use this table, you can purge duplicate comments,
        see :ref:`more-on-duplicate-comments`.

    `results_trajectory`

        All results created not within single runs

    `derived_parameters_trajectory`

    `derived_parameters_runs`

    `derived_parameters_runs_summary`

        All three are analogous to the result overviews above

* The `explored_parameters` overview about your parameters explored in the single runs.

* In each subtree *results.run_XXXXXXXX* there will be another explored parameter table summarizing
  the values in each run.
  Per default these tables are switched off, to enable it pass ``large_overview_tables=True``
  to your environment.


.. _more-on-duplicate-comments:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Purging duplicate Comments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you added a result with the same name and same comment in every single run, this would create
a lot of overhead. Since the very same comment would be stored in every node in the HDF5 file.
For instance,
during a single run you call ``traj.f_add_result('my_result', 42, comment='Mostly harmless!')``
and the result will be renamed to ``results.runs.run_00000000.my_result``. After storage
in the node associated with this result in your HDF5 file, you will find the comment
``'Mostly harmless!'``.
If you call ``traj.f_add_result('my_result',-55, comment='Mostly harmless!')``
in another run again, let's say run_00000001, the name will be mapped to
``results.runs.run_00000001.my_result``. But this time the comment will not be saved to disk,
since ``'Mostly harmless!'`` is already part of the very first result with the name 'my_result'.
Note that comments will be compared and storage will only be discarded if the strings
are exactly the same. Moreover, the comment will only be compared to the comment of the very
first result, if all comments are equal except for the very first one, all of these equal comments
will be stored!

In order to allow the purge of duplicate comments you need the `summary` overview tables.

Furthermore, if you reload your data from the example above,
the result instance ``results.runs.run_00000001.my_result``
won't have a comment only the instance ``results.runs.run_00000000.my_result``.

**IMPORTANT**: If you use multiprocessing, the storage service will take care that the comment for
the result or derived parameter with the lowest run index will be considered, regardless
of the order of the finishing of your runs. Note that this only works properly if all
comments are the same. Otherwise the comment in the overview table might not be the one
with the lowest run index. Moreover, if you merge trajectories (see ref:`more-on-merging`)
there is no support for purging comments in the other trajectory.
All comments of the other trajectory's results and derived parameters will be kept and
merged into your current one.

**IMPORTANT** Purging of duplicate comments requires overview tables. Since there are no
overview tables for *group* nodes, this feature does not work for comments in *group* nodes,
only in *leaf* nodes (aka results and parameters)!
So try to avoid to add comments in *group* nodes within single runs.

If you do not want to purge duplicate comments, set the config parameter
``'purge_duplicate_comments'`` to 0 or ``False``.


.. _more-on-multiprocessing:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Multiprocessing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For an  example on multiprocessing see :ref:`example-04`.

The following code snippet shows how to enable multiprocessing with 4 cpus, a pool, and a queue.

.. code-block:: python

    env = Environment(self, trajectory='trajectory',
                 comment='',
                 dynamic_imports=None,
                 log_folder='../log/',
                 use_hdf5=True,
                 filename='../experiments.h5',
                 file_title='experiment',
                 multiproc=True,
                 ncores=4,
                 use_pool=True,
                 wrap_mode='QUEUE')

Setting ``use_pool=True`` will create a pool of ``ncores`` worker processes which perform your
simulation runs.

**IMPORTANT**: In order to allow multiprocessing with a pool, all your data and objects of your
simulation need to be serialized with pickle_.
But don't worry, most of the python stuff you use is automatically *picklable*.

If you come across the situation that your data cannot be pickled (which is the case
for some BRIAN networks, for example), don't worry either. Set ``use_pool=False``
(and also ``continuable=False``) and for every simulation run
*pypet* will spawn an entirely new subprocess.
The data is than passed to the subprocess by forking on OS level and not by pickling.

Moreover, if you **ENABLE** multiprocessing and **DISABLE** pool usage, besides the maximum number of
utilized processors ``ncores``, you can specify usage cap levels with ``cpu_cap``, ``memory_cap``,
and ``swap_cap`` as fractions of the maximum capacity.
Values must be chosen larger than 0.0 and smaller or equal to 1.0. If any of these thresholds is
crossed no new processes will be started by *pypet*. For instance, if you want to use 3 cores
aka ``ncores=3`` and set a memory cap of ``memory_cap=0.9`` and let's assume that currently only
2 processes are started. Moreover, let's say currently 95 percent of you RAM are occupied.
Accordingly, *pypet* will *NOT* start the third process until RAM usage drops again below
(or equal to) 90 percent.

Be aware that all three thresholds are combined. So if just one of them is crossed, *pypet*
will refuse to start new processes. Moreover, to prevent dead-lock *pypet* will regardless
of the cap values always start at least one process.

To disable the cap levels, simply set all three to 1.0 (which is default, anyway).

**IMPORTANT**: *pypet* does not check if the processes themselves obey the cap limit. Thus,
if one of the process that computes your single runs needs more RAM/Swap or CPU power than the cap
value, this is its very own problem.
The process will **NOT** be terminated by *pypet*. The process will only cause *pypet* to not start
new processes until the utilization falls below the threshold again.

**IMPORTANT**: In order to use this cap feature you need the psutil_ package. If
psutil_ is not installed, the cap values are simply ignored.

Note that HDF5 is not thread safe, so you cannot use the standard HDF5 storage service out of the
box. However, if you want multiprocessing, the environment will automatically provide wrapper
classes for the HDF5 storage service to allow safe data storage.

There are two different modes that are supported. You can choose between them via setting
``wrap_mode``. You can choose between ``'QUEUE'`` and ``'LOCK'``. If you
have your own service that is already thread safe you can also choose ``'NONE'`` to skip wrapping.

If you chose the ``'QUEUE'`` mode, there will be an additional process spawned that is the only
one writing to the HDF5 file. Everything that is supposed to be stored is send over a queue to
the process. This has the advantage that your worker processes are only busy with your simulation
and are not bothered with writing data to a file.
More important, they don't spend time waiting for other
processes to release a thread lock to allow file writing.
The disadvantage is that this storage relies a lot on pickling of data, so often your entire
trajectory is send over the queue.

If you chose the ``'LOCK'`` mode, every process will pace a lock before it opens the HDF5 file
for writing data. Thus, only one process at a time stores data. The advantage is that your data
does not need to be send over a queue over and over again. Yet, your simulations might take longer
since processes have to wait for each other to release locks quite often.


.. _pickle: http://docs.python.org/2/library/pickle.html

.. _psutil: http://psutil.readthedocs.org/

.. _more-on-git:

^^^^^^^^^^^^^^^^
Git Integration
^^^^^^^^^^^^^^^^

The environment can make use of version control. If you manage your code with
git_ you can trigger automatic commits with the environment to get a proper snapshot
of the code you actually use. This ensures that your experiments are repeatable!
In order to use the feature of git integration you additionally need GitPython_.

To trigger an automatic commit simply pass the arguments ``git_repository`` and ``git_message``
to the :class:`~pypet.environment.Environment` constructor. `git_repository`
specifies the path to the folder containing the `.git` directory. ``git_message`` is optional
and adds the corresponding message to the commit. Note that the message will always be
augmented with some short information about the trajectory you are running.

The commit SHA-1 hash and some other information about the commit will be added to the
config subtree of your trajectory, so you can easily recall that commit from git later on.

The automatic commit will only commit changes in files that are currently tracked by
your git repository, it will **NOT** add new files.
So make sure that if you create new files to put them into your repository before running
an experiment. Moreover, a commit will only be triggered if your working copy contains
changes. If there are no changes detected, information about the previous commit will be
added to the trajectory.

The autocommit function is similar to calling ``$ git add -u`` and ``$ git commit -m 'Some Message'``
in your linux console!


.. _git: http://git-scm.com/

.. _GitPython: http://pythonhosted.org/GitPython/0.3.1/index.html

.. _more-on-sumatra:

^^^^^^^^^^^^^^^^^^^^
Sumatra Integration
^^^^^^^^^^^^^^^^^^^^

The environment can make use of a Sumatra_ experimental lab-book.

Just pass the argument ``sumatra_project`` which should specify the path to your root
sumatra folder to the :class:`~pypet.environment.Environment` constructor.
You can additionally pass a ``sumatra_reason``, a string describing the
reason for you sumatra simulation. *pypet* will automatically add the name, comment, and
the names of all explored parameters to the reason.
You can also pick a ``sumatra_label`` (string),
set this to ``None`` if you want Sumatra to pick a label for you.


Note in contrast to the automatic git commits (see above)
which are done as soon as the environment is created, a sumatra record is only created and
stored if you actually perform single runs. So if you use one of the three:
:func:`~pypet.environment.Environment.f_run`, or :func:`~pypet.environment.Environment.f_pipline`,
or :func:`~pypet.environment.Environment.f_continue` and your simulation succeeds and does
not crash.

*pypet* automatically adds all parameters to the sumatra record. The explored parameters
are added with their full range instead of the default values.

.. _more-on-running:

---------------------------------
Running an Experiment
---------------------------------

In order to run an experiment, you need to define a job or a top level function that specifies
your simulation. This function gets as first positional argument the :
:class:`~pypet.trajectory.Trajectory` container,
or to be more precise a :class:`~pypet.trajectory.SingleRun` container
(see :ref:`more-on-trajectories` and :class:`~pypet.trajectory.SingleRun`),
and optionally other positional and keyword arguments of your choice.

.. code-block:: python

    def myjobfunc(traj, *args, **kwargs)
        #Do some sophisticated simulations with your trajectory
        ...
        return 'fortytwo'


In order to run this simulation, you need to hand over the function to the environment,
where you can also specify the additional arguments and keyword arguments using
:func:`~pypet.environment.Environment.f_run`:

.. code-block:: python

    env.f_run(myjobfunc, *args, **kwargs)

The argument list ``args`` and keyword dictionary ``kwargs`` are directly handed over to the
``myjobfunc`` during runtime.

The :func:`~pypet.environment.Environment.f_run` will return a list of tuples.
Whereas the first tuple entry is the index of the corresponding run and the second entry
of the tuple
is the result returned by your run function (for the example above this would simply always be
the string ``'fortytwo'``). In case you use multiprocessing these tuples are **NOT** in the order
of the run indices but in the order of their finishing time!


.. _more-about-postproc:

-----------------------------
Adding Post-Processing
-----------------------------

You can add a post-processing function that should be called after the execution of all the single
runs via :func:`pypet.environment.Environment.f_add_postproc`.

Your post processing function must accept the trajectory container as the first argument,
a list of tuples (containing the run indices and results) and arbitrary positional and
keyword arguments. In order to pass arbitrary arguments to your post-processing function,
simply pass these first ot the :func:`pypet.environment.Environment.f_add_postproc`.

For example:

.. code-block:: python

    def mypostprocfunc(traj, result_list, extra_arg1, extra_arg2):
        # do some postprocessing here
        ...

Whereas in your main script you can call

.. code-block:: python

    env.f_add_postproc(mypostprocfunc, 42, extra_arg2=42.5)


which will later on pass ``42`` as ``extra_arg1`` and ``42.4`` as ``extra_arg2``. It is the
very same principle as before for your run function.
The post-processing function will be called after the completion of all single runs.

Moreover, please note that your trajectory will **NOT** contain the data computed
during the single runs, since this has been removed after the single runs to save RAM.
If your post-processing needs access to this data, you can simply load it via one of
the many loading functions (:func:`~pypet.naturalnaming.NNGroupNode.f_load_child`,
:func:`~pypet.naturalnaming.NNGroupNode.f_load_item`) or even turn on auto-loading.

Note that your post-processing function should **NOT** return any results, since these
will simply be lost. However, there is one particular result that can be returned,
see below.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Expanding your Trajectory via Post-Processing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If your post-processing function expands the trajectory via
:func:`~pypet.trajectory.Trajectory.f_expand` or if your post-processing function returns
a dictionary of lists that can be interpreted to expand the trajectory,
*pypet* will start the single runs again and explore the expanded trajectory.
Of course, after this expanded exploration, your post-processing function will be
called again. Likewise, you could potentially expand again, and after the next expansion
post-processing will be executed again (and again, and again, and again, I guess you get it).

Thus, you can use post-processing for an adaptive search within your parameter space.

**IMPORTANT**: All changes you apply to your trajectory, like setting auto-loading or changing fast
access will be propagated to the new single runs. So try to undo all changes before finishing
the post-processing if you plan to trigger new single runs.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Expanding your Trajectory and using Multiprocessing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you use multiprocessing and you want to adaptively expand your trajectory, it can
be a waste of precious time to wait until all runs have finished.
Accordingly, you can set the argument ``immediate_postproc`` to ``True`` when you create
your environment. Then your post-processing function is called as soon as *pypet* runs
out of jobs for single runs. Thus, you can expand your trajectory while the last batch
of single runs is still being executed.

To emphasize this a bit more and to not be misunderstood: Your post-processing function is **NOT**
called as soon as a single run finishes and the first result is available but as soon as there
are **no more** single runs available to start new processes!
Still, that does not mean you have to wait
until *ALL* single runs are finished (as for normal post-processing),
but you can already add new single runs to the trajectory
while the final `n` runs are still being executed. Where `n` is determined by the number of cores
(``ncores``) and probably the *cap values* you have chosen (see :ref:`more-on-multiprocessing`).

*pypet* will *NOT* start a new process for your post-processing. Your post-processing function
is executed in the main process (this makes writing actual post-processing functions much easier
because you don't have to wrap your head around dead-locks).

Accordingly, post-processing should be rather quick in comparison to your single runs, otherwise
post-processing will become the bottleneck in your parallel simulations.

----------------------------
Using a Experiment Pipeline
----------------------------

Usually, your numerical experiments work like the following: You add some parameters to
your trajectory, you mark a few of these for exploration, and you pass your main function
to the environment via :func:`~pypet.environment.Environment.f_run`. Accordingly, this
function will be executed with all parameter combinations. Maybe you want some post-processing
in the end and that's about it. However, sometimes even the addition of parameters can be
fairly complex or you want this part under the supervision of an environment, too.
For instance, because you have a Sumatra_ lab-book and adding of parameters should also account as
runtime.

Thus, to have your entire experiment and not only the exploration of the parameter space
managed by *pypet* you can use the :func:`~pypet.environment.Environment.f_pipeline`
function, see also :ref:`example-13`.

You have to pass a so called *pipeline* function to
:func:`~pypet.environment.Environment.f_pipeline` that defines your entire experiment.

Your pipeline function is only allowed to take a single parameter, that is the trajectory
container. Next, your pipeline function can fill in some parameters and do some pre-processing.

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
        traj.f_explore({'ncards' : range(42)})

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

.. _more-on-continuing:

--------------------------------------------
Continuing or Resuming a Crashed Experiment
--------------------------------------------

In order to use this feature you need dill_.

BE AWARE that *dill* is rather experimental and still in alpha status!

If all of your data can be handled by dill (probably anything),
you can use the config parameter ``continuable=True`` passed
to the :class:`~pypet.environment.Environment` constructor.

This will create a continue directory (name specified by you) and a sub-folder with the name
ot the trajectory. This folder is your safety net
for data loss due to a computer crash. If for whatever reason your day or week-long
lasting simulation was interrupted, you can resume it
without recomputing already obtained results. Note that this works only if the
HDF% file is not corrupted and for interruptions due
to computer crashes, like power failure etc. If your
simulations crashed due to errors in your code, there is no way to restore that!

You can resume a crashed trajectory via :func:`~pypet.environment.Environment.f_continue`
with the name of the continue folder (not the subfolder) and the name of the trajectory:

.. code-block:: python

    env = Environment(continuable=True)

    env.f_continue(trajectory_name = my_traj_2015_10_21_04h29m00s,
                            continue_folder = './experiments/continue/')


The neat thing here is, that you create a novel environment for the continuation. Accordingly,
you can set different environmental settings, like changing the number of cores, etc.
You CANNOT change any HDF5 settings or even change the whole storage service.

When does continuing NOT work?

Continuing will **NOT** work if your top-level simulation function or the arguments passed to your
simulation function are altered between individual runs. For instance, if you use multiprocessing
and you want to write computed data into a shared data list
(like ``multiprocessing.Manager().list()``, see :ref:`example-12`),
these changes will be lost and cannot be captured by the continue snapshots.

A work around here would be to not manipulate the arguments but pass these values as results
of your top-level simulation function. Everything that is returned by your top-level function
will be part of the snapshots and can be reconstructed after a crash.

Continuing *might not* work if you use post-processing that expands the trajectory.
Since you are not limited in how you manipulate the trajectory within your post-processing,
there are potentially many side effects that remain undetected by the continue snapshots.
You can try to use both together, but there is **NO** guarantee whatsoever that continuing a
crashed trajectory and post-processing with expanding will work together.



.. _dill: https://pypi.python.org/pypi/dill

.. _sumatra: http://neuralensemble.org/sumatra/