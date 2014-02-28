
====================
Naming Convention
====================

To avoid confusion with natural naming scheme and the functionality provided by the trajectory,
parameters, and so on, I followed the idea by PyTables to use prefixes:
`f_` for functions and `v_` for python variables/attributes/properties.

For instance, given a result instance `res`, `res.v_comment` is the object's comment attribute and
`res.f_set(mydata=42)` is the function for adding data to the result container.
Whereas `res.mydata` might refer to a data item named `mydata` added by the user.


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
for data storage, this will always be called before the runs and at the end of a
single run automatically.

You start your simulations by creating an environment object:

>>> env = Environment(trajectory='trajectory',
                 add_time=True,
                 comment='',
                 dynamically_imported_classes=None,
                 log_folder=None,
                 multiproc=False,
                 ncores=1,
                 wrap_mode=pypetconstants.WRAP_MODE_LOCK,
                 continuable=1,
                 use_hdf5=True,
                 filename=None,
                 file_title=None,
                 purge_duplicate_comments=True,
                 summary_tables=True,
                 small_overview_tables=True,
                 large_overview_tables=True,
                 results_per_run=0,
                 derived_parameters_per_run=0,
                 git_repository = None,
                 git_message=''):

You can pass the following arguments:

* `trajectory`

    The first argument `trajectory` can either be a string or a given trajectory object. In case of
    a string, a new trajectory with that name is created. You can access the new trajectory
    via `v_trajectory` property. If a new trajectory is created, the comment and dynamically imported
    classes are added to the trajectory.

* `add_time`

    Whether the current time in format XXXX_XX_XX_XXhXXmXXs is added to the trajectory name if
    the trajectory is newly created.

* `comment`

    The comment that will be added to a newly created trajectory.

* `dynamically_imported_classes`

    The argument `dynamically_imported_classes` is important
    if you have written your own *parameter* or *result* classes, you can pass these either
    as class variables `MyCustomParameterClass` or as strings leading to the classes in your package:
    `'mysim.myparameters.MyCustomParameterClass'`. If you have several classes, just put them in
    a list `dynamically_imported_classes=[MyCustomParameterClass,MyCustomResultClass]`.
    The trajectory needs to know your custom classes in case you want to load a custom class
    from disk and the trajectory needs to know how they are built.

    It is **VERY important**, that every class name is **UNIQUE**. So you should not have
    two classes named `'MyCustomParameterClass'` in two different python modules!
    The identification of the class is based only on its name and not its path in your packages.

* `multiproc`

    `multiproc` specifies whether or not to use multiprocessing
    (take a look at :ref:`more-on-multiprocessing`). Default is 0 (False).

* `ncores`

    If `multiproc` is 1 (True), this specifies the number of processes that will be spawned
    to run your experiment. Note if you use `'QUEUE'` mode (see below) the queue process
    is not included in this number and will add another extra process for storing.

* `use_pool`

    If you choose multiprocessing you can specify whether you want to spawn a new
    process for every run or if you want a fixed pool of processes to carry out your
    computation.

    If you use a pool, all your data and the tasks you compute must be picklable!
    If you never heard about pickling or object serialization, you might want to take a loot at the
    pickle_ module.

    Thus, if your simulation data cannot be pickled (which is the case for some BRIAN networks,
    for instance), choose `use_pool=False` and continuable=`False` (see below).
    Be aware that you will have an individual logfile for every process you spawn.

* `wrap_mode`

     If `multiproc` is 1 (True), specifies how storage to disk is handled via
     the storage service. Since HDF5 is not thread safe, the HDF5 storage service
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

* `continuable`

    Whether the environment should take special care to allow to resume or continue
    crashed trajectories. Default is 1 (True).
    Everything must be picklable in order to allow
    continuing of trajectories (take a look at :ref:`more-on-continuing`).
    In order to resume trajectories use
    :func:`~pypet.environment.Environment.f_continue_run`.

* `log_folder`

    The `log_folder` specifies where all log files will be stored.
    The environment will create a sub-folder with the name of the trajectory where
    all txt files will be put.
    The environment will create a major logfile (*main.txt*) incorporating all messages of the
    current log level and beyond and
    a log file that only contains warnings and errors *warnings_and_errors.txt*.

    Moreover, if you use multiprocessing and a pool,
    there will be a log file for every process named *proces_XXXX.txt* with *XXXX* the process
    id containing all log messages produced by the corresponding process. Moreover,
    you will find a *process_XXXX_runs.txt* file where you can see which individual runs were
    actually carried out by the process.

    In case you want multiprocessing without a pool of workers, there will be a logfile
    for each individual run called *run_XXXXXXXX.txt*.

    If you don't set a log level elsewhere before, the standard level will be *INFO*
    (if you have no clue what I am talking about, take a look at the logging_ module).

* `use_hdf5`:

    If you want to use the standard HDF5 storage service provided with this package, set
    `use_hdf5=True`. You can specify the name of the HDF5 file and, if it has to be created new,
    the file title. If you want to use your own storage service (You don't have an SQL one do you?),
    set `use_hdf5=False` and add your custom storage service directly to the trajectory:

    >>> env.v_trajectory.v_storage_service = MyCustomService(...)

* `filename`

    The name of the hdf5 file. If none is specified the default
    `./hdf5/the_name_of_your_trajectory.hdf5` is chosen. If `filename` contains only a path
    like `filename='./myfolder/', it is changed to
    `filename='./myfolder/the_name_of_your_trajectory.hdf5'`.

* `file_title`

    Title of the hdf5 file (only important if file is created new)

* `complevel`

    If you use HDF5, you can specify your compression level. 0 means no compression
    and 9 is the highest compression level. By default the level is set to 9 to reduce the
    size of the resulting HDF5 file.
    See `PyTables Compression`_ for a detailed explanation.

* `complib`

    The library used for compression

* `purge_duplicate_comments`

    If you add a result via :func:`pypet.trajectory.SingleRun.f_add_result` or a derived
    parameter :func:`pypet.trajectory.SingleRun.f_add_derived_parameter` and
    you set a comment, normally that comment would be attached to each and every instance.
    This can produce a lot of unnecessary overhead if the comment is the same for every
    result over all runs. If `hdf5.purge_duplicate_comments=1` than only the comment of the
    first result or derived parameter instance created is stored, or comments
    that differ from this first comment. You might want to take a look at
    :ref:`more-on-duplicate-comments`.

* `summary_tables`

    Whether summary tables should be created.
    These give overview about 'derived_parameters_runs_summary', and 'results_runs_summary'.
    They give an example about your results by listing the very first computed result.
    If you want to `purge_duplicate_comments` you will need the `summary_tables`.
    You might want to check out :ref:`more-on-overview`.

* `small_overview_tables`

    Whether the small overview tables should be created.
    Small tables are giving overview about 'config','parameters','derived_parameters_trajectory',
    'results_trajectory'.

* `large_overview_tables`

    Whether to add large overview tables. This encompasses information about every derived
    parameter and result and the explored parameters in every single run.
    If you want small HDF5 files, this is the first option to set to False.

* `results_per_run`

    Expected results you store per run. If you give a good/correct estimate
    storage to HDF5 file is much faster in case you store LARGE overview tables.

    Default is 0, i.e. the number of results is not estimated!

* `derived_parameters_per_run`

    Analogous to the above.

* `git_repository`

    If your code base is under git version control you can specify the path
    (relative or absolute) to
    the folder containing the `.git` directory. See also :ref:`more-on-git`.

* `git_message`

    Message passed onto git command.

* `lazy_debug`

    If `lazy_debug=True` and in case you debug your code (aka the built-in variable `__debug__`
    is set to `True` by python), the environment will use the
    :class:`~pypet.storageservice.LazyStorageService` instead of the HDF5 one.
    Accordingly, no files are created and your trajectory and results are not saved.
    This allows faster debugging and prevents *pypet* from blowing up your hard drive with
    trajectories that you probably not want to use anyway since you just debug your code.


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
`config.environment.environment_XXXXXXX_XXXX_XX_XX_XXhXXmXXs`. Your trajectory could
potentially be run by several environments due to merging or extending an existing trajectory.
Thus, you will be able to track how your trajectory was build over time.


.. _more-on-overview:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Overview Tables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Overview tables give you a nice summary about all *parameters* and *results* you needed and
computed during your simulations. They will be placed under the subgroup
`overview` at the top-level in your trajectory group in the HDF5 file.
In addition, for every single run there will be a small overview
table about the explored parameter values of that run.

The following tables are created:

* An `info` table listing general information about your trajectory

* A `runs` table summarizing the single runs

* The instance tables:

    `parameters`

        Containing all parameters, and some information about comments, length etc.

    `config`,

        As above, but config parameters

    `results_runs`

        All results of all individual runs, to reduce memory size only a short value
        summary and the name is given.


    `results_runs_summary`

        Only the very first result with a particular name is listed. For instance
        if you create the result 'my_result' in all runs only the result of `run_00000000`
        is listed with detailed information.

        If you use this table, you can purge duplicate comments,
        see :ref:`more-on-duplicate-comments`.

    `results_trajectroy`

        All results created directly with the trajectory and not within single runs

    `derived_parameters_trajectory`

    `derived_parameters_runs`

    `derived_parameters_runs_summary`

        All three are analogous to the result overviews above

* The `explored_parameters` overview about your parameters explored in the single runs

* In each subtree *results.run_XXXXXXXX* there will be another explored parameter table summarizing
  the values in each run.

However, if you have many *runs* and *results* and *derived_parameters*,
I would advice you to switch of the result, derived parameter
and explored parameter overview in each single run. These tables are switched off if you
pass `large_overview_tables=False` as a parameter at environment construction (see above).


.. _more-on-duplicate-comments:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Purging duplicate Comments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you added a result with the same name and same comment in every single run, this would create
a lot of overhead. Since the very same comment would be stored in every node in the HDF5 file.
For instance,
during a single run you call `traj.f_add_result('my_result', 42, comment='Mostly harmless!')`
and the result will be renamed to `results.run_00000000.my_result`. After storage
in the node associated with this result in your HDF5 file, you will find the comment
`'Mostly harmless!'`.
If you call `traj.f_add_result('my_result',-55, comment='Mostly harmless!')`
in another run again, let's say run_00000001, the name will be mapped to
`results.run_00000001.my_result`. But this time the comment will not be saved to disk,
since `'Mostly harmless!'` is already part of the very first result with the name 'my_result'.
Note that comments will be compared and storage will only be discarded if the strings
are exactly the same. Moreover, the comment will only be compared to the comment of the very
first result, if all comments are equal except for the very first one, all of these equal comments
will be stored!

In order to allow the purge of duplicate comments you need the `summary` overview tables.

Furthermore, consider if you reload your data from the example above,
the result instance `results.run_00000001.my_result`
won't have a comment only the instance `results.run_00000000.my_result`.

**IMPORTANT**: If you use multiprocessing, the storage service will take care that the comment for
the result or derived parameter with the lowest run index will be considered, regardless
of the order of the finishing of your runs. Note that this only works properly if all
comments are the same. Otherwise the comment in the overview table might not be the one
with the lowest run index. Moreover, if you merge trajectories (see ref:`more-on-merging`)
there is no support for purging comments in the other trajectory.
All comments of the other trajectory's results and derived parameters will be kept and
merged into your current one.

**IMPORTANT** Purging of duplicate comments rqeuires overview tables. Since there are no
overview tables for *group* nodes, this feature does not work for comments in *group* nodes,
only in *leaf* nodes (aka results and parameters)!
So try to avoid to add comments in *group* nodes within single runs.

If you do not want to purge duplicate comments, set the config parameter
`'purge_duplicate_comments'` to 0 or `False`.


.. _more-on-multiprocessing:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Multiprocessing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For an  example on multiprocessing see :ref:`example-04`.

The following code snippet shows how to enable multiprocessing with 4 cpus, a pool, and a queue.

.. code-block:: python

    env = Environment(self, trajectory='trajectory',
                 comment='',
                 dynamically_imported_classes=None,
                 log_folder='../log/',
                 use_hdf5=True,
                 filename='../experiments.h5',
                 file_title='experiment',
                 multiproc=True,
                 ncores=4,
                 use_pool=True,
                 wrap_mode='QUEUE')

Setting `use_pool=True` will create a pool of `ncores` worker processes which perform your
simulation runs.

IMPORTANT: In order to allow multiprocessing with a pool, all your data and objects of your
simulation need to be serialized with pickle_.
But don't worry, most of the python stuff you use is automatically *picklable*.

If you come across the situation that your data cannot be pickled (which is the case
for some BRIAN networks, for example), don't worry either. Set `use_pool=False`
(and also `continuable=False`) and for every simulation run
*pypet* will spawn an entirely new subprocess.
The data is than passed to the subprocess by inheritance and not by pickling.

Note that HDF5 is not thread safe, so you cannot use the standard HDF5 storage service out of the
box. However, if you want multiprocessing, the environment will automatically provide wrapper
classes for the HDF5 storage service to allow safe data storage.

There are two different modes that are supported. You can choose between them via setting
`wrap_mode`. You can choose between `'QUEUE'` and `'LOCK'`. If you
have your own service that is already thread safe you can also choose `'NONE'` to skip wrapping.

If you chose the `'QUEUE'` mode, there will be an additional process spawned that is the only
one writing to the HDF5 file. Everything that is supposed to be stored is send over a queue to
the process. This has the advantage that your worker processes are only busy with your simulation
and are not bothered with writing data to a file.
More important, they don't spend time waiting for other
processes to release a thread lock to allow file writing.
The disadvantage is that this storage relies a lot on pickling of data, so often your entire
trajectory is send over the queue.

If you chose the `'LOCK'` mode, every process will pace a lock before it opens the HDF5 file
for writing data. Thus, only one process at a time stores data. The advantage is that your data
does not need to be send over a queue over and over again. Yet, your simulations might take longer
since processes have to wait for each other to release locks quite often.


.. _pickle: http://docs.python.org/2/library/pickle.html


.. _more-on-git:

^^^^^^^^^^^^^^^^
Git Integration
^^^^^^^^^^^^^^^^

The environment can make use of version control. If you manage your code with
git_ you can trigger automatic commits with the environment to get a proper snapshot
of the code you actually use. This ensures that your experiments are repeatable!
In order to use the feature of git integration you additionally need GitPython_.

To trigger an automatic commit simply pass the arguments `git_repository` and `git_message`
to the :class:`~pypet.environment.Environment` constructor. `git_repository`
specifies the path to the folder containing the `.git` directory. `git_message` is optional
and adds the corresponding message to the commit. Note that the message will always be
augmented with some short information about the trajectory you are running.

The commit SHA-1 hash and some other information about the commit will be added to the
config subtree of your trajectory, so you can easily recall that commit from git later on.

The automatic commit will only commit changes in files that are currently tracked by
your git repository, it will **NOT** add new files.
So make sure that if you create new files you put them into your repository before running
an experiment.

The autocommit function is similar to calling `$ git add -u` and `$ git commit -m 'Some Message'`
in your linux console!


.. _git: http://git-scm.com/

.. _GitPython: http://pythonhosted.org/GitPython/0.3.1/index.html


.. _more-on-running:

---------------------------------
Running an Experiment
---------------------------------

In order to run an experiment, you need to define a job or a top level function that specifies
your simulation. This function gets as first positional argument the *trajectory*, or to be
more precise a *single run*
(see :ref:`more-on-trajectories` and :class:`~pypet.trajectory.SingleRun`),
and optionally other positional and keyword arguments of your choice.

.. code-block:: python

    def myjobfunc(traj,*args,**kwargs)
        #Do some sophisticated simulations with your trajectory
        ...


In order to run this simulation, you need to hand over the function to the environment,
where you can also specify the additional arguments and keyword arguments using
:func:`~pypet.environment.Environment.f_run`:

.. code-block:: python

    env.f_run(myjobfunc, *args, **kwargs)

The argument list `args` and keyword dictionary `kwargs` are directly handed over to the
`myjobfunc` during runtime.

Note that the first postional argument used by `myjobfunc` is not a
full :class:`pypet.trajectory.Trajectory` but only
a `~pypet.trajectory.SingleRun` (also see :ref:`more-on-single-runs`). There is not much
difference to a full *trajectory*. You have slightly less functionality and usually no access
to the fully explored parameters but only to a single parameter space point.

.. _more-on-continuing:

^^^^^^^^^^^^^^^^^^^^^^^^^^^
Resuming an Experiment
^^^^^^^^^^^^^^^^^^^^^^^^^^^

If all of your data is picklable, you can use the config parameter `continuable=1` passed
to the :class:`~pypet.environment.Environment` constructor.
This will create a '.cnt' file with the name of your trajectory in the
folder where your final HDF5 file will be placed. The `.cnt` file is your safety net
for data loss due to a computer crash. If for whatever reason your day or week-long
lasting simulation was interrupted, you can resume it
without recomputing already obtained results. Note that this works only if the
hdf5 file is not corrupted and for interruptions due
to computer crashes, like power failure etc. If your
simulations crashed due to errors in your code, there is no way to restore that!

You can resume a crashed trajectory via :func:`~pypet.environment.Environment.f_continue_run`
with the name of the corresponding '.cnt' file.

.. code-block:: python

    env = Environment()

    env.f_continue_run('./experiments/my_traj_2015_10_21_04h29m00s.cnt')