.. _more-on-environment:

============================
More about the Environment
============================

In most use cases you will interact with the :class:`~pypet.environment.Envrionemnt` to
do your numerical simulations.
The environment is your handyman for your numerical experiments, it sets up new trajectories,
keeps log
files and can be used to distribute your simulations onto several cpus.

Note in case you use the environment there is no need to call :func:`~pypet.trajectory.SingleRun.f_store`
for data storage, this will always be called before the runs and at the end of a single Run automatically.

You start your simulations by creating an environment object:

>>> env = Environment(self, trajectory='trajectory',\
                 comment='',\
                 dynamically_imported_classes=None,\
                 log_folder='../log/',\
                 use_hdf5=True,\
                 filename='../experiments.h5',\
                 file_title='experiment')


The first argument `trajectory` can either be a string or a given trajectory object. In case of
a string, a new trajectory with that name is created. You can access the new trajectory
via `v_trajectory` property. If a new trajectory is created, the comment and dynamically imported
classes are added to the trajectory. The argument `dynamically_imported_classes` is important
if you have written your own *parameter* or *result* classes, you can pass these either
as class variables `MyCustomParameterClass` or as strings leading to the classes in your package:
`'mysim.myparameters.MyCustomParameterClass'`. If you have several classes, just put them in
a list `dynamically_imported_classes=[MyCustomParameterClass,MyCustomResultClass]`.
The trajectory needs to know your custom classes in case you want to load a custom class
from disk and the trajectory needs to know how they are built.

The `log_folder` specifies where all log files will be stored.
In the log folder the environment will create a sub-folder with the name of the trajectory where
all txt files will be put.
In there you will find several log files.
The environment will create a major logfile (*main.txt*) incorporating all messages of the
current log level and beyond and
a log file that only contains warnings and errors *warnings_and_errors.txt*.
Moreover, if you use multiprocessing
there will be a log file for every process named *proces_XXXX.txt* with *XXXX* the process
id. If you don't set a log level elsewhere before, the standard level will be *INFO*
(if you have no clue what I am talking about, take a look at the logging_ module).

If you want to use the standard hdf5 storage service provided with this package, set
`use_hdf5=True`. You can specify the name of the hdf5 file and, if it has to be created new,
the file title. If you want to use your own storage service (You don't have an SQL one do you?),
set `use_hdf5=False` and add your custom storage service to the trajectory:

 >>> env.v_trajectory.v_storage_service = MyCustomService(...)

.. _logging: http://docs.python.org/2/library/logging.html

.. _config-added-by-environment:

--------------------------------------
Config Data added by the Environment
--------------------------------------

The environment will add some config data to your trajectory. You can change this data
later on (except for the log folder, that has already been created), to enable multiprocessing
and the ability to continue and resume broken or crashed trajectories.

The following config parameters are added:

* environment.multiproc:

    Whether or not to use multiprocessing. Default is 0 (False). If you use
    multiprocessing, all your data and the tasks you compute
    must be pickable!


* environment.ncores:

      If multiproc is 1 (True), this specifies the number of processes that will be spawned
      to run your experiment. Note if you use QUEUE mode (see below) the queue process
      is not included in this number and will add another extra process for storing.


* environment.wrap_mode:

     If multiproc is 1 (True), specifies how storage to disk is handled via
     the storage service. Since hdf5 is not thread safe, the hdf5 storage service
     needs to wrapped with a helper class to allow the interaction with multiple processes.

     There are two options:

     :const:`pypet.globally.MULTIPROC_MODE_QUEUE`: ('QUEUE')

     Another process for storing the trajectory is spawned. The sub processes
     running the individual single runs will add their results to a
     multiprocessing queue that is handled by an additional process.
     Note that this requires additional memory since single runs
     will be pickled and send over the queue for storage!


     :const:`pypet.globally.MULTIPROC_MODE_LOCK`: ('LOCK')

     Each individual process takes care about storage by itself. Before
     carrying out the storage, a lock is placed to prevent the other processes
     to store data. Accordingly, sometimes this leads to a lot of processes
     waiting until the lock is released.
     Yet, single runs do not need to be pickled before storage!
     'LOCK' is the default choice!

     If you don't want wrapping at all use :const:`pypet.globally.MULTIPROC_MODE_NONE` ('NONE')

     If you have no clue what I am talking about, you might want to take a look at multiprocessing_
     in python to learn more about locks, queues and thread safety and so forth.


* environment.continuable:

    Whether the environment should take special care to allow to resume or continue
    crashed trajectories. Default is 1 (True).
    Everything must be pickable in order to allow
    continuing of trajectories. Assume you run experiments that take
    a lot of time. If during your experiments there is a power failure,
    you can resume your trajectory after the last single run that was still
    successfully stored via your storage service.
    This will create a `.cnt` file in the same folder as your hdf5 file,
    using this you can continue crashed trajectories.
    In order to resume trajectories use
    :func:`~pypet.environment.Environment.f_continue_run`

* hdf5.filename: The hdf5 filename

* hdf5.file_title: The hdf5 file title

* hdf5.XXXXX_overview

        Whether the XXXXXX overview table should be created in your hdf5 file.
        XXXXXX from ['config','parameter','derived_parameter','result','explored_parameter'].
        Default is 1 (True)

        Note that these tables create a lot of overhead, if you want small hdf5 files set
        these values to 0 (False). Most memory is taken by the `result_overview` and
        `derived_parameter_overview`!

* hdf5.explored_parameter_overview_in_runs

        Whether an overview table about the explored parameters is added in each
        single run subgroup.
        Default is 1 (True)

* hdf5.results_per_run

        Expected results you store per run. If you give a good/correct estimate
        storage to hdf5 file is much faster if you want overview tables.

        Default is 0, i.e. the number of results is not estimated!

* hdf5.derived_parameters_per_run

      Analogous to the above.

.. _multiprocessing: http://docs.python.org/2/library/multiprocessing.html

.. _more-on-overview:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Overview Tables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Overview tables give you a nice summary about all *parameters* and *results* you needed and
computed during your simulations. They will be placed at the top-level in your trajectory
group in the hdf5 file. In addition, for every single run there will be a small overview
table about the explored parameter values of that run
(see also :ref:`more-on-storage`).

However, if you have many *runs* and *results* and *derived_parameters*,
I would advice you to switch of the result, derived parameter
and explored parameter overview in each single run. You don't have to do that by hand,
simply use :func:`~pypet.environment.Environment.f_switch_off_large_overview`
or :func:`~pypet.environment.Environment.f_switch_off_all_overview` to disable all tables.

_more-on-duplicate-comments

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Purging duplicate Comments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you add a result with the same name and same comment in every single run, this would create
a lot of overhead. Since the very same comment would be stored in every node in the hdf5 file.
For instance,
during a single run you call `traj.f_add_result('my_result`,42, comment='Mostly harmless!')`
and the result will be renamed to `results.run_00000000.my_result`. After storage
in the node associated with this result in your hdf5 file you will find the comment
`'Mostly harmless!'`.
If you call `traj.f_add_result('my_result',-55, comment='Mostly harmless!')`
in another run again, let's say run_00000001, the name will be mapped to
`results.run_00000001.my_result`. But this time the comment will not be saved to disk,
since `'Mostly harmless!'` is already part of the very first result with the name 'my_result'.
Note that comments will be compared and storage will only be discarded if the strings
are exactly the same.

Furthermore, consider if you reload your data, the result instance `results.run_00000001.my_result`
won't have a comment only the instance `results.run_00000000.my_result`.

If you do not want to purge duplicate comments, set the config parameter
`'config.hdf5.purge_duplicate_comments'` to 0 or False.


.. _more-on-multiprocessing:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Multiprocessing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For a full code example on multiprocessing see :ref:`example-04`

The following code snippet shows how to enable multiprocessing with 4 cpus:

.. code-block:: python

    env = Environment(self, trajectory='trajectory',
                 comment='',
                 dynamically_imported_classes=None,
                 log_folder='../log/',
                 use_hdf5=True,
                 filename='../experiments.h5',
                 file_title='experiment')


    traj = env.v_tracetory

    traj.multiproc = True

    traj.ncores = 4

    {...}

    env.f_run(myjobfunc)



Note that hdf5 is not thread safe, so you cannot use the standard hdf5 storage service out of the
box. However, if you want multiprocessing, the environment will automatically provide wrapper
classes for the hdf5 storage service to allow safe data storage.

There are two different modes that are supported. You can choose between them via setting
`config.environment.wrap_mode`. You can choose between `'QUEUE'` and `'LOCK'`. If you
have your own service that is already thread safe you can also choose `'NONE'` to skip wrapping.

If you chose the `'QUEUE'` mode, there will be an additional process spawned that is the only
one writing to the hdf5 file. Everything that is supposed to be stored is send over a queue to
the process. This has the advantage that your worker processes are only busy with your simulation
and are not
bothered with writing data to a file. More important, they don't spend time waiting for other
processes to release a thread lock to allow file writing.
The disadvantage is that this storage relies a lot on pickling of data, so often your entire
trajectory is send over the queue.

If you chose the `'LOCK'` mode, every process will pace a lock before it opens the hdf5 file
for writing data. Thus, only one process at a time stores data. The advantage is that your data
does not need to be send over a queue over and over again. Yet, your simulations might take longer
since processes have to wait for each other to release locks quite often.

IMPORTANT: In order to allow multiprocessing, all your data and objects of your simulation need
to be serialized with pickle_.
But don't worry, most of the python stuff you use is automatically picklable.

.. _pickle: http://docs.python.org/2/library/pickle.html

.. _more-on-running:

---------------------------------
Running an Experiment
---------------------------------

In order to run an experiment, you need to define a job or a top level function that specifies
your simulation. This function gets as first positional argument the *trajectory*, or to be
more precise a *single run* (:class:`~pypet.trajectory.SingleRun`), and
optionally other positional
and keyword arguments of your choice.

.. code-block:: python

    def myjobfunc(traj,*args,**kwargs)
        #Do some sophisticated simulations with your trajectory
        ...


In order to run this simulation, you need to hand over the function to the environment,
where you can also specify the additional arguments and keyword arguments using
:func:`~pypet.environment.Environment.f_run`:

.. code-block:: python

    env.f_run(myjobfunc,*args,**kwargs)

The argument list `args` and keyword dictionary `kwargs` are directly handed over to the
`myjobfunc` during runtime.

Note that the first postional argument used by `myjobfunc` is not a
full :func:`pypet.trajectory.Trajectory` but only
a `~pypet.trajectory.SingleRun` (also see :ref:`more-on-single-runs`). There is not much
difference to a full *trajectory*. You have slightly less functionality and usually no access
to the fully explored parameters but only to a single parameter space point.

^^^^^^^^^^^^^^^^^^^^^^^^^^^
Resuming an Experiment
^^^^^^^^^^^^^^^^^^^^^^^^^^^

If all of your data is picklable, you can use the config `config.environment.continuable=1`.
This will create a '.cnt' file with the name of your trajectory in the
folder where your final hdf5 file will be placed. The `.cnt` file is your safety net
for data loss due to a computer crash. If for whatever reason your day or week-long
lasting simulation was interrupted, you can resume it
without recomputing already obtained results. Note that this works only if the
hdf5 file is not corrupted and with interruptions due
to computer crashes, like power failure etc. If your
simulations crashed due to errors in your code, there is no way to restore that!

You can resume a crashed trajectory via :func:`~pypet.environment.Environment.f_continue_run`
with the name of the corresponding '.cnt' file.


.. code-block:: python

    env = Environment()


    env.f_continue_run('./experiments/my_traj_2015_10_21_04h29m00s.cnt')