""" Module containing the environment to run experiments.

An :class:`~pypet.environment.Environment` provides an interface to run experiments based on
parameter exploration.

The environment contains and might even create a :class:`~pypet.trajectory.Trajectory`
container which can be filled with parameters and results (see :mod:`pypet.parameter`).
Instance of :class:`~pypet.trajectory.SingleRun` based on this trajectory are
distributed to the user's job function to perform a single run of an experiment.

An `Environment` is the handyman for scheduling, it can be used for multiprocessing and takes
care of organizational issues like logging.

"""

__author__ = 'Robert Meyer'

try:
    import __main__ as main
except ImportError as e:
    main = None
    print(repr(e))
import os
import sys
import logging
import shutil
import multiprocessing as multip
import traceback
import hashlib
import time
import datetime
import pickle


try:
    from sumatra.projects import load_project
    from sumatra.programs import PythonExecutable
except ImportError:
    load_project = None
    PythonExecutable = None

try:
    import dill
except ImportError:
    dill = None

try:
    import psutil
except ImportError:
    psutil = None

try:
    import git
except ImportError:
    git = None

import pypet.compat as compat
from pypet.trajectory import Trajectory
from pypet.storageservice import HDF5StorageService, QueueStorageServiceSender, \
    QueueStorageServiceWriter, LockWrapper, LazyStorageService
import pypet.pypetconstants as pypetconstants
from pypet.gitintegration import make_git_commit
from pypet._version import __version__ as VERSION
from pypet.utils.decorators import deprecated
from pypet.pypetlogging import HasLogger, StreamToLogger
from pypet.utils.helpful_functions import is_debug


def _single_run(args):
    """ Performs a single run of the experiment.

    :param args: List of arguments

        0. The single run object containing all parameters set to the corresponding run index.

        1. Path to log files

        2. Boolean whether to log stdout

        3. A queue object, only necessary in case of multiprocessing in queue mode.

        4. The user's job function

        5. Number of total runs (int)

        6. Whether to use multiprocessing

        7. A queue object to store results into in case a pool is used, otherwise None

        8. The arguments handed to the user's job function (as *args)

        9. The keyword arguments handed to the user's job function (as **kwargs)

        10. Whether to clean up after the run

        11. Path for continue files, `None` if continue is not supported

        12. Whether or not the data should be automatically stored

    :return:

        Results computed by the user's job function which are not stored into the trajectory.
        Returns a tuple of run index and result: ``(traj.v_idx, result)``

    """

    try:
        traj = args[0]
        log_path = args[1]
        log_stdout = args[2]
        queue = args[3]
        runfunc = args[4]
        total_runs = args[5]
        multiproc = args[6]
        result_queue = args[7]
        runparams = args[8]
        kwrunparams = args[9]
        clean_up_after_run = args[10]
        continue_path = args[11]
        automatic_storing = args[12]

        use_pool = result_queue is None

        root = logging.getLogger()
        idx = traj.v_idx

        if multiproc and log_path is not None:

            # In case of multiprocessing we want to have a log file for each individual process.
            process_name = multip.current_process().name.lower().replace('-', '_')

            filename = '%s_%s.txt' % (traj.v_name, process_name)

            filename = log_path + '/' + filename

            handler = logging.FileHandler(filename=filename)
            formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)-8s %(message)s')
            handler.setFormatter(formatter)
            root.addHandler(handler)

            if log_stdout:
                # Also copy standard out and error to the log files
                outstl = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO)
                sys.stdout = outstl

                errstl = StreamToLogger(logging.getLogger('STDERR'), logging.ERROR)
                sys.stderr = errstl

        # Add the queue for storage in case of multiprocessing in queue mode.
        if queue is not None:
            traj.v_storage_service.queue = queue

        root.info('\n===================================\n '
                  'Starting single run #%d of %d '
                  '\n===================================\n' % (idx, total_runs))

        # Measure start time
        traj._set_start_time()

        # Run the job function of the user
        result = runfunc(traj, *runparams, **kwrunparams)

        # Measure time of finishing
        traj._set_finish_time()
        # And store some meta data and all other data if desired
        traj._store_final(store_data=automatic_storing)

        # Make some final adjustments to the single run before termination
        if clean_up_after_run and not multiproc:
            traj._finalize()

        root.info('\n===================================\n '
                  'Finished single run #%d of %d '
                  '\n===================================\n' % (idx, total_runs))

        # Add the index to the result
        result = (traj.v_idx, result)

        if continue_path is not None:
            # Trigger Snapshot
            _trigger_result_snapshot(result, continue_path)

        if multiproc:
            root.removeHandler(handler)

        if not use_pool:
            result_queue.put(result)
        else:
            return result

    except:
        errstr = "\n\n############## ERROR ##############\n" + \
                 "".join(traceback.format_exception(*sys.exc_info())) + "\n"
        logging.getLogger('STDERR').error(errstr)
        raise Exception("".join(traceback.format_exception(*sys.exc_info())))


def _queue_handling(handler, log_path, log_stdout):
    """ Starts running a queue handler and creates a log file for the queue."""

    if log_path is not None:
        # Create a new log file for the queue writer
        filename = 'queue_process.txt'
        filename = log_path + '/' + filename
        root = logging.getLogger()

        h = logging.FileHandler(filename=filename)
        f = logging.Formatter('%(asctime)s %(name)s %(levelname)-8s %(message)s')
        h.setFormatter(f)
        root.addHandler(h)

        if log_stdout:
            # Redirect standard out and error to the file
            outstl = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO)
            sys.stdout = outstl

            errstl = StreamToLogger(logging.getLogger('STDERR'), logging.ERROR)
            sys.stderr = errstl

    # Main job, make the listener to the queue start receiving message for writing to disk.
    handler.run()


def _trigger_result_snapshot(result, continue_path):
    """ Triggers a snapshot of the results for continuing

    :param result: Currently computed result
    :param continue_path: Path to continue folder

    """
    dump_dict = {}
    timestamp = time.time()
    timestamp_str = repr(timestamp).replace('.', '_')
    filename = 'result_%s' % timestamp_str
    extension = '.ncnt'
    dump_filename = os.path.join(continue_path, filename + extension)
    dump_dict['result'] = result
    dump_dict['timestamp'] = timestamp

    dump_file = open(dump_filename, 'wb')
    dill.dump(dump_dict, dump_file, protocol=2)
    dump_file.flush()
    dump_file.close()

    # We rename the file to be certain that the trajectory did not crash during taking
    # the snapshot!
    extension = '.rcnt'
    rename_filename = os.path.join(continue_path, filename + extension)
    shutil.move(dump_filename, rename_filename)


class Environment(HasLogger):
    """ The environment to run a parameter exploration.

    The first thing you usually do is to create and environment object that takes care about
    the running of the experiment. You can provide the following arguments:

    :param trajectory:

        String or trajectory instance. If a string is supplied, a novel
        trajectory is created with that name.
        Note that the comment and the dynamically imported classes (see below) are only considered
        if a novel trajectory is created. If you supply a trajectory instance, these fields
        can be ignored.

    :param add_time: If True the current time is added to the trajectory name if created new.

    :param comment: Comment added to the trajectory if a novel trajectory is created.

    :param dynamically_imported_classes:

          Only considered if a new trajectory is created.
          If you've written custom parameters or results that need to be loaded
          dynamically during runtime, the module containing the class
          needs to be specified here as a list of classes or strings
          naming classes and there module paths.

          For example:
          `dynamically_imported_classes =
          ['pypet.parameter.PickleParameter',MyCustomParameter]`

          If you only have a single class to import, you do not need
          the list brackets:
          `dynamically_imported_classes = 'pypet.parameter.PickleParameter'`

    :param automatic_storing:

        If `True` the trajectory will be stored at the end of the simulation and
        single runs will be stored after their completion.
        Be aware of data loss if you set this to `False` and not
        manually store everything.

    :param log_folder:

        Path to a folder where all log files will be stored. If none is specified the default
        `./logs/` is chosen. The log files will be added to a
        sub-folder with the name of the trajectory and the name of the environment.

    :param log_level:

        The log level, default is `logging.INFO`, If you want to disable logging, simply set
        `log_level = None`.

        Note if you configured the logging module somewhere else with
        a different log-level, the value of this `log_level` is simply ignored. Logging handlers
        to log into files in the `log_folder` will still be generated. To strictly forbid the
        generation of these handlers you have to choose set `log_level=None`.

    :param log_stdout:

        Whether the output of STDOUT and STDERROR should be recorded into the log files.
        Disable if only logging statement should be recorded. Note if you work with an
        interactive console like IPython, it is a good idea to set `log_stdout=False`
        to avoid messing up the console output.

    :param multiproc:

        Whether or not to use multiprocessing. Default is `False`.
        Besides the wrap_mode (see below) that deals with how
        storage to disk is carried out in case of multiprocessing, there
        are two ways to do multiprocessing. By using a fixed pool of
        processes (choose `use_pool=True`, default option) or by spawning an
        individual process for every run and parameter combination (`use_pool=False`).
        The former will only spawn not more than *ncores* processes and all simulation runs are
        sent over to to the pool one after the other.
        This requires all your data to be pickled.

        If your data cannot be pickled (which could be the case for some
        BRIAN networks, for instance) choose `use_pool=False` (also make sure to set
        `continuable=False`). This will also spawn
        at most *ncores* processes at a time, but as soon as a process terminates
        a new one is spawned with the next parameter combination. Be aware that you will
        have as many logfiles in your logfolder as processes were spawned.
        If your simulation returns results besides storing results directly into the trajectory,
        these returned results still need to be pickled.

    :param ncores:

        If multiproc is `True`, this specifies the number of processes that will be spawned
        to run your experiment. Note if you use QUEUE mode (see below) the queue process
        is not included in this number and will add another extra process for storing.

    :param use_pool:

        Whether to use a fixed pool of processes or whether to spawn a new process
        for every run. Use the latter if your data cannot be pickled.

    :param cpu_cap:

        If `multiproc=True` and `use_pool=False` you can specify a maximum cpu utilization between
        0.0 (excluded) and 1.0 (included) as fraction of maximum capacity. If the current cpu
        usage is above the specified level (averaged across all cores),
        pypet will not spawn a new process and wait until
        activity falls below the threshold again. Note that in order to avoid dead-lock at least
        one process will always be running regardless of the current utilization.
        If the threshold is crossed a warning will be issued. The warning won't be repeated as
        long as the threshold remains crossed.

        For example `cpu_cap=0.7`, `ncores=3`, and currently on average 80 percent of your cpu are
        used. Moreover, let's assume that at the moment only 2 processes are
        computing single runs simultaneously. Due to the usage of 80 percent of your cpu,
        pypet will wait until cpu usage drops below (or equal to) 70 percent again
        until it starts a third process to carry out another single run.

        The parameters `memory_cap` and `swap_cap` are analogous. These three thresholds are
        combined to determine whether a new process can be spawned. Accordingly, if only one
        of these thresholds is crossed, no new processes will be spawned.

        To disable the cap limits simply set all three values to 1.0.

        You need the psutil_ package to use this cap feature. If not installed, the cap
        values are simply ignored.

        .. _psutil: http://psutil.readthedocs.org/

    :param memory_cap:

        Cap value of RAM usage. If more RAM than the threshold is currently in use, no new
        processes are spawned.

    :param swap_cap:

        Analogous to `memory_cap` but the swap memory is considered.

    :param wrap_mode:

         If multiproc is 1 (True), specifies how storage to disk is handled via
         the storage service.

         There are two options:

         :const:`~pypet.pypetconstants.WRAP_MODE_QUEUE`: ('QUEUE')

             Another process for storing the trajectory is spawned. The sub processes
             running the individual single runs will add their results to a
             multiprocessing queue that is handled by an additional process.
             Note that this requires additional memory since single runs
             will be pickled and send over the queue for storage!

         :const:`~pypet.pypetconstants.WRAP_MODE_LOCK`: ('LOCK')

             Each individual process takes care about storage by itself. Before
             carrying out the storage, a lock is placed to prevent the other processes
             to store data. Accordingly, sometimes this leads to a lot of processes
             waiting until the lock is released.
             Yet, single runs do not need to be pickled before storage!

         If you don't want wrapping at all use
         :const:`~pypet.pypetconstants.WRAP_MODE_NONE` ('NONE')

    :param clean_up_runs:

        In case of single core processing, whether all results under groups named `run_XXXXXXXX`
        should be removed after the completion of
        the run. Note in case of multiprocessing this happens anyway since the single run
        container will be destroyed after finishing of the process.

        Moreover, if set to `True` after post-processing it is checked if there is still data
        under `run_XXXXXXXX` and this data is removed if the trajectory is expanded.

    :param immediate_postproc:

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

    :param continuable:

        Whether the environment should take special care to allow to resume or continue
        crashed trajectories. Default is `False`.

        You need to install dill_ to use this feature. *dill* will make snapshots
        of your simulation function as well as the passed arguments.
        BE AWARE that dill is still rather experimental!

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

    :param continue_folder:

        The folder where the continue files will be placed. Note that *pypet* will create
        a sub-folder with the name of the environment.

    :param delete_continue:

        If true, *pypet* will delete the continue files after a successful simulation.

    :param use_hdf5:

        Whether or not to use the standard hdf5 storage service, if false the following
        arguments below will be ignored:

    :param filename:

        The name of the hdf5 file. If none is specified the default
        `./hdf5/the_name_of_your_trajectory.hdf5` is chosen. If `filename` contains only a path
        like `filename='./myfolder/', it is changed to
        `filename='./myfolder/the_name_of_your_trajectory.hdf5'`.

    :param file_title: Title of the hdf5 file (only important if file is created new)

    :param encoding:

        Format to encode and decode unicode strings stored to disk.
        The default ``'utf8'`` is highly recommended.

    :param complevel:

        If you use HDF5, you can specify your compression level. 0 means no compression
        and 9 is the highest compression level. See `PyTables Compression`_ for a detailed
        description.

        .. _`PyTables Compression`: http://pytables.github.io/usersguide/optimization.html#compression-issues

    :param complib:

        The library used for compression. Choose between *zlib*, *blosc*, and *lzo*.
        Note that 'blosc' and 'lzo' are usually faster than 'zlib' but it may be the case that
        you can no longer open your hdf5 files with third-party applications that do not rely
        on PyTables.

    :param shuffle:

        Whether or not to use the shuffle filters in the HDF5 library.
        This normally improves the compression ratio.

    :param fletcher32:

        Whether or not to use the *Fletcher32* filter in the HDF5 library.
        This is used to add a checksum on hdf5 data.

    :param pandas_format:

        How to store pandas data frames. Either in 'fixed' ('f') or 'table' ('t') format.
        Fixed format allows fast reading and writing but disables querying the hdf5 data and
        appending to the store (with other 3rd party software other than *pypet*).

    :param pandas_append:

        If format is 'table', `pandas_append=True` allows to modify the tables after storage with
        other 3rd party software. Currently appending is not supported by *pypet* but this
        feature will come soon.

    :param purge_duplicate_comments:

        If you add a result via :func:`~pypet.trajectory.SingleRun.f_add_result` or a derived
        parameter :func:`~pypet.trajectory.SingleRun.f_add_derived_parameter` and
        you set a comment, normally that comment would be attached to each and every instance.
        This can produce a lot of unnecessary overhead if the comment is the same for every
        instance over all runs. If `purge_duplicate_comments=1` than only the comment of the
        first result or derived parameter instance created in a run is stored or comments
        that differ from this first comment.

        For instance, during a single run you call
        `traj.f_add_result('my_result`,42, comment='Mostly harmless!')`
        and the result will be renamed to `results.run_00000000.my_result`. After storage
        in the node associated with this result in your hdf5 file, you will find the comment
        `'Mostly harmless!'` there. If you call
        `traj.f_add_result('my_result',-43, comment='Mostly harmless!')`
        in another run again, let's say run 00000001, the name will be mapped to
        `results.run_00000001.my_result`. But this time the comment will not be saved to disk
        since `'Mostly harmless!'` is already part of the very first result with the name
        'results.run_00000000.my_result'.
        Note that the comments will be compared and storage will only be discarded if the strings
        are exactly the same.

        If you use multiprocessing, the storage service will take care that the comment for
        the result or derived parameter with the lowest run index will be considered regardless
        of the order of the finishing of your runs. Note that this only works properly if all
        comments are the same. Otherwise the comment in the overview table might not be the one
        with the lowest run index.

        You need summary tables (see below) to be able to purge duplicate comments.

        This feature only works for comments in *leaf* nodes (aka Results and Parameters).
        So try to avoid to add comments in *group* nodes within single runs.

    :param summary_tables:

        Whether the summary tables should be created, i.e. the 'derived_parameters_runs_summary',
        and the `results_runs_summary`.

        The 'XXXXXX_summary' tables give a summary about all results or derived parameters.
        It is assumed that results and derived parameters with equal names in individual runs
        are similar and only the first result or derived parameter that was created
        is shown as an example.

        The summary table can be used in combination with `purge_duplicate_comments` to only store
        a single comment for every result with the same name in each run, see above.

    :param small_overview_tables:

        Whether the small overview tables should be created.
        Small tables are giving overview about 'config','parameters',
        'derived_parameters_trajectory', ,
        'results_trajectory','results_runs_summary'.

        Note that these tables create some overhead. If you want very small hdf5 files set
        `small_overview_tables` to False.

    :param large_overview_tables:

        Whether to add large overview tables. This encompasses information about every derived
        parameter, result, and the explored parameter in every single run.
        If you want small hdf5 files, this is the first option to set to false.

    :param results_per_run:

        Expected results you store per run. If you give a good/correct estimate
        storage to hdf5 file is much faster in case you store LARGE overview tables.

        Default is 0, i.e. the number of results is not estimated!

    :param derived_parameters_per_run:

        Analogous to the above.

    :param git_repository:

        If your code base is under git version control you can specify here the path
        (relative or absolute) to the folder containing the `.git` directory as a string.
        Note in order to use this tool you need GitPython_.

        If you set this path the environment will trigger a commit of your code base
        adding all files that are currently under version control.
        Similar to calling `git add -u` and `git commit -m 'My Message'` on the command line.
        The user can specify the commit message, see below. Note that the message
        will be augmented by the name and the comment of the trajectory.
        A commit will only be triggered if there are changes detected within your
        working copy.

        This will also add information about the revision to the trajectory, see below.

        .. _GitPython: http://pythonhosted.org/GitPython/0.3.1/index.html

    :param git_message:

        Message passed onto git command. Only relevant if a new commit is triggered.
        If no changes are detected, the information about the previous commit and the previous
        commit message are added to the trajectory and this user passed message is discarded.

    :param sumatra_project:

        If your simulation is managed by sumatra_, you can specify here the path to the
        *sumatra* root folder. Note that you have to initialise the *sumatra* project at least
        once before via ``smt init MyFancyProjectName``.

        *pypet* will automatically ad ALL parameters to the *sumatra* record.
        If a parameter is explored, the WHOLE range is added instead of the default value.

        *pypet* will add the label and reason (only if provided, see below)
        to your trajectory as config parameters.

        .. _sumatra : http://neuralensemble.org/sumatra/

    :param sumatra_reason:

        You can add an additional reason string that is added to the *sumatra* record.
        Regardless if `sumatra_reason` is empty, the name of the trajectory, the comment
        as well as a list of all explored parameters is added to the *sumatra* record.

        Note that the augmented label is not stored into the trajectory as config
        parameter, but the original one (without the name of the trajectory, the comment,
        and the list of explored parameters) in case it is not the empty string.

    :param sumatra_label:

        The label or name of your sumatra record. Set to `None` if you want sumatra
        to choose a label in form of a timestamp for you.

    :param do_single_runs:

        Whether you intend to actually to compute single runs with the trajectory.
        If you do not intend to do single runs, than set to `False` and the
        environment won't add config information like number of processors to the
        trajectory.

    :param lazy_debug:

        If `lazy_debug=True` and in case you debug your code (aka you use pydevd and
        the expression `'pydevd' in sys.modules` is `True`), the environment will use the
        :class:`~pypet.storageservice.LazyStorageService` instead of the HDF5 one.
        Accordingly, no files are created and your trajectory and results are not saved.
        This allows faster debugging and prevents *pypet* from blowing up your hard drive with
        trajectories that you probably not want to use anyway since you just debug your code.


    The Environment will automatically add some config settings to your trajectory.
    Thus, you can always look up how your trajectory was run. This encompasses most of the above
    named parameters as well as some information about the environment.
    This additional information includes
    a timestamp as well as a SHA-1 hash code that uniquely identifies your environment.
    If you use git integration, the SHA-1 hash code will be the one from your git commit.
    Otherwise the code will be calculated from the trajectory name, the current time, and your
    current pypet version.

    The environment will be named `environment_XXXXXXX_XXXX_XX_XX_XXhXXmXXs`. The first seven
    `X` are the first seven characters of the SHA-1 hash code followed by a human readable
    timestamp.

    All information about the environment can be found in your trajectory under
    `config.environment.environment_XXXXXXX_XXXX_XX_XX_XXhXXmXXs`. Your trajectory could
    potentially be run by several environments due to merging or extending an existing trajectory.
    Thus, you will be able to track how your trajectory was build over time.

    Git information is added to your trajectory as follows:

    * git.commit_XXXXXXX_XXXX_XX_XX_XXh_XXm_XXs.hexsha

        The SHA-1 hash of the commit.
        `commit_XXXXXXX_XXXX_XX_XX_XXhXXmXXs` is mapped to the first seven items of the SHA-1 hash
        and the formatted data of the commit, e.g. `commit_7ef7hd4_2015_10_21_16h29m00s`.

    * git.commit_XXXXXXX_XXXX_XX_XX_XXh_XXm_XXs.name_rev

        String describing the commits hexsha based on the closest reference

    * git.commit_XXXXXXX_XXXX_XX_XX_XXh_XXm_XXs.committed_date

        Commit date as Unix Epoch data

    * git.commit_XXXXXXX_XXXX_XX_XX_XXh_XXm_XXs.message

        The commit message


    """

    def __init__(self, trajectory='trajectory',
                 add_time=True,
                 comment='',
                 dynamically_imported_classes=None,
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
                 summary_tables=True,
                 small_overview_tables=True,
                 large_overview_tables=False,
                 results_per_run=0,
                 derived_parameters_per_run=0,
                 git_repository=None,
                 git_message='',
                 sumatra_project=None,
                 sumatra_reason='',
                 sumatra_label=None,
                 do_single_runs=True,
                 lazy_debug=False):

        # First check if purge settings are valid
        if purge_duplicate_comments and not summary_tables:
            raise ValueError('You cannot purge duplicate comments without having the'
                             ' small overview tables.')

        if git_repository is not None and git is None:
            raise ValueError('You cannot specify a git repository without having '
                             'GitPython. Please install the GitPython package to use '
                             'pypet`s git integration.')

        if continuable and dill is None:
            raise ValueError('Please install `dill` if you want to use the feature to '
                             'continue halted trajectories')

        if load_project is None and sumatra_project is not None:
            raise ValueError('`sumatra` package has not been found, either install '
                             '`sumatra` or set `sumatra_project=None`.')

        if sumatra_label is not None and '.' in sumatra_label:
            raise ValueError('Your sumatra label is not allowed to contain dots.')

        if use_pool and immediate_postproc:
            raise ValueError('You CANNOT perform immediate post-processing if you DO '
                             'use a pool.')

        if wrap_mode == pypetconstants.WRAP_MODE_QUEUE and immediate_postproc:
            raise ValueError(
                'You CANNOT perform immediate post-processing if you DO use wrap mode '
                '`QUEUE`.')

        if (cpu_cap <= 0.0 or cpu_cap > 1.0 or
            memory_cap <= 0.0 or memory_cap > 1.0 or
                swap_cap <= 0.0 or swap_cap > 1.0):
            raise ValueError('Please choose cap values larger than 0.0 '
                             'and smaller or equal to 1.0.')

        check_usage = cpu_cap < 1.0 or memory_cap < 1.0 or swap_cap < 1.0

        if check_usage and psutil is None:
            raise ValueError('You cannot enable monitoring without having '
                             'installed psutil. Please install psutil or set '
                             'cpu_cap, memory_cap, and swap_cap to 1.0')

        self._cpu_cap = cpu_cap
        self._memory_cap = memory_cap
        self._swap_cap = swap_cap
        self._check_usage = check_usage

        self._sumatra_project = sumatra_project
        self._sumatra_reason = sumatra_reason
        self._sumatra_label = sumatra_label

        self._runfunc = None
        self._args = ()
        self._kwargs = {}

        self._postproc = None
        self._postproc_args = ()
        self._postproc_kwargs = {}
        self._immediate_postproc = immediate_postproc
        self._user_pipeline = False

        self._git_repository = git_repository
        self._git_message = git_message

        # Check if a novel trajectory needs to be created.
        if isinstance(trajectory, compat.base_type):
            # Create a new trajectory
            self._traj = Trajectory(trajectory,
                                    add_time=add_time,
                                    dynamically_imported_classes=dynamically_imported_classes,
                                    comment=comment)

            self._timestamp = self.v_trajectory.v_timestamp  # Timestamp of creation
            self._time = self.v_trajectory.v_time  # Formatted timestamp

        else:
            self._traj = trajectory

            # If no new trajectory is created the time of the environment differs
            # from the trajectory and must be computed from the current time.
            init_time = time.time()

            formatted_time = datetime.datetime.fromtimestamp(init_time).strftime(
                '%Y_%m_%d_%Hh%Mm%Ss')

            self._timestamp = init_time

            self._time = formatted_time

        # If no filename is supplied, take the filename from the trajectory's storage service
        if self.v_trajectory.v_storage_service is not None and filename is None:
            self._file_title = self._traj.v_storage_service._file_title
            self._filename = self._traj.v_storage_service._filename
        else:
            # Prepare file names and log folder
            if file_title is None:
                self._file_title = self._traj.v_name
            else:
                self._file_title = file_title

            if filename is None:
                # If no filename is supplied and the filename cannot be extracted from the
                # trajectory, create the default filename
                self._filename = os.path.join(os.getcwd(), 'hdf5', self._traj.v_name + '.hdf5')
            else:
                self._filename = filename

        head, tail = os.path.split(self._filename)
        if not head:
            # If the filename contains no path information,
            # we put it into the current working directory
            self._filename = os.path.join(os.getcwd(), self._filename)

        if not tail:
            self._filename = os.path.join(self._filename, self._traj.v_name + '.hdf5')

        self._use_hdf5 = use_hdf5  # Boolean whether to use hdf5 or not

        # Check if the user wants to use the hdf5 storage service. If yes,
        # add a service to the trajectory
        if self._use_hdf5 and self.v_trajectory.v_storage_service is None:
            self._add_hdf5_storage_service(lazy_debug)

        # In case the user provided a git repository path, a git commit is performed
        # and the environment's hexsha is taken from the commit if the commit was triggered by
        # this particular environment, otherwise a new one is generated
        if self._git_repository is not None:
            new_commit, self._hexsha = make_git_commit(self, self._git_repository,
                                                       self._git_message)
            # Identifier hexsha
        else:
            new_commit = False

        if not new_commit:
            # Otherwise we need to create a novel hexsha
            self._hexsha = hashlib.sha1(compat.tobytetype(self.v_trajectory.v_name +
                                                          str(self.v_trajectory.v_timestamp) +
                                                          str(self.v_timestamp) +
                                                          VERSION)).hexdigest()

        # Create the name of the environment
        short_hexsha = self._hexsha[0:7]
        name = 'environment'
        self._name = name + '_' + str(short_hexsha) + '_' + self._time  # Name of environment

        # The trajectory should know the hexsha of the current environment.
        # Thus, for all runs, one can identify by which environment they were run.
        self._traj._environment_hexsha = self._hexsha
        self._traj._environment_name = self._name

        # If no log folder is provided, create the default log folder
        log_path = None
        if log_level is not None:
            if log_folder is None:
                log_folder = os.path.join(os.getcwd(), 'logs')

        # The actual log folder is a sub-folder with the trajectory name and the environment name
        if log_level is not None:
            log_path = os.path.join(log_folder, self._traj.v_name)
            log_path = os.path.join(log_path, self.v_name)
            # Create the loggers
            self._make_logging_handlers(log_path, log_level, log_stdout)

        if dill is not None:
            # If you do not set this log-level dill will flood any logging file :-(
            logging.getLogger(dill.__name__).setLevel(logging.WARNING)

        self._set_logger()

        self._log_folder = log_folder
        self._log_path = log_path
        self._log_stdout = log_stdout

        self._continuable = continuable

        if self._continuable:
            if continue_folder is None:
                continue_folder = os.path.join(os.getcwd(), 'continue')
            continue_path = os.path.join(continue_folder, self._traj.v_name)

            if not os.path.isdir(continue_path):
                os.makedirs(continue_path)
        else:
            continue_path = None

        self._continue_folder = continue_folder
        self._continue_path = continue_path
        self._delete_continue = delete_continue

        self._multiproc = multiproc
        self._ncores = ncores
        self._wrap_mode = wrap_mode
        # Whether to use a pool of processes
        self._use_pool = use_pool

        # Drop a message if we made a commit. We cannot drop the message directly after the
        # commit, because the logger does not exist at this point, yet.
        if self._git_repository is not None:
            if new_commit:
                self._logger.info('Triggered NEW GIT commit `%s`.' % str(self._hexsha))
            else:
                self._logger.info('No changes detected, added PREVIOUS GIT commit `%s`.' %
                                  str(self._hexsha))

        self._do_single_runs = do_single_runs
        self._automatic_storing = automatic_storing
        self._clean_up_runs = clean_up_runs
        self._deep_copy_data = False  # deep_copy_data # For future reference deep_copy_arguments

        if self._do_single_runs:

            config_name = 'environment.%s.multiproc' % self.v_name
            self._traj.f_add_config(config_name, self._multiproc,
                                    comment='Whether or not to use multiprocessing.').f_lock()

            if self._multiproc:
                config_name = 'environment.%s.use_pool' % self.v_name
                self._traj.f_add_config(config_name, self._use_pool,
                                        comment='Whether to use a pool of processes or '
                                                'spawning individual processes for '
                                                'each run.').f_lock()

                if not self._traj.f_get('config.environment.%s.use_pool' % self.v_name).f_get():
                    config_name = 'environment.%s.cpu_cap' % self.v_name
                    self._traj.f_add_config(config_name, self._cpu_cap,
                                            comment='Maximum cpu usage beyond '
                                                    'which no new processes '
                                                    'are spawned').f_lock()

                    config_name = 'environment.%s.memory_cap' % self.v_name
                    self._traj.f_add_config(config_name, self._memory_cap,
                                            comment='Maximum RAM usage beyond which '
                                                    'no new processes '
                                                    'are spawned').f_lock()

                    config_name = 'environment.%s.swap_cap' % self.v_name
                    self._traj.f_add_config(config_name, self._swap_cap,
                                            comment='Maximum Swap memory usage beyond '
                                                    'which no new '
                                                    'processes are spawned').f_lock()

                config_name = 'environment.%s.ncores' % self.v_name
                self._traj.f_add_config(config_name, self._ncores,
                                        comment='Number of processors in case of '
                                                'multiprocessing').f_lock()

                config_name = 'environment.%s.wrap_mode' % self.v_name
                self._traj.f_add_config(config_name, self._wrap_mode,
                                        comment='Multiprocessing mode (if multiproc),'
                                                ' i.e. whether to use QUEUE'
                                                ' or LOCK or NONE'
                                                ' for thread/process safe storing').f_lock()
            # else:
            # config_name='environment.%s.deep_copy_data' % self._name
            # self._traj.f_add_config(config_name, self._deep_copy_data,
            # comment='Only important for single processing. If data should '
            # 'be copied before the beginning of each run. '
            # 'Uses dill is installed, otherwise pickle.').f_lock()
            #
            # if self._deep_copy_data:
            # if dill is not None:
            # method = 'dill'
            # else:
            # method = 'pickle'
            # config_name='environment.%s.deep_copy_method' % self._name
            # self._traj.f_add_config(config_name, method,
            # comment='Wich method was used for deep copying, either '
            # '`dill` or `pickle`').f_lock()

            config_name = 'environment.%s.clean_up_runs' % self._name
            self._traj.f_add_config(config_name, self._clean_up_runs,
                                    comment='Whether or not results should be removed after the '
                                            'completion of a single run. '
                                            'You are not advised to set this '
                                            'to `False`. Only do it if you know what you are '
                                            'doing.').f_lock()

            config_name = 'environment.%s.continuable' % self._name
            self._traj.f_add_config(config_name, self._continuable,
                                    comment='Whether or not a continue file should'
                                            ' be created. If yes, everything is'
                                            ' handled by `dill`.').f_lock()

        config_name = 'environment.%s.trajectory.name' % self.v_name
        self._traj.f_add_config(config_name, self.v_trajectory.v_name,
                                comment='Name of trajectory').f_lock()

        config_name = 'environment.%s.trajectory.timestamp' % self.v_name
        self._traj.f_add_config(config_name, self.v_trajectory.v_timestamp,
                                comment='Timestamp of trajectory').f_lock()

        config_name = 'environment.%s.timestamp' % self.v_name
        self._traj.f_add_config(config_name, self.v_timestamp,
                                comment='Timestamp of environment creation').f_lock()

        config_name = 'environment.%s.hexsha' % self.v_name
        self._traj.f_add_config(config_name, self.v_hexsha,
                                comment='SHA-1 identifier of the environment').f_lock()

        try:
            config_name = 'environment.%s.script' % self.v_name
            self._traj.f_add_config(config_name, main.__file__,
                                    comment='Name of the executed main script').f_lock()
        except AttributeError:
            pass  # We end up here if we use pypet within an ipython console

        if self._traj.v_version != VERSION:
            config_name = 'environment.%s.version' % self.v_name
            self._traj.f_add_config(config_name, self.v_trajectory.v_version,
                                    comment='Pypet version if it differs from the version'
                                            ' of the trajectory').f_lock()

        if self._traj.v_python != compat.python_version_string:
            config_name = 'environment.%s.python' % self.v_name
            self._traj.f_add_config(config_name, self.v_trajectory.v_python,
                                    comment='Python version if it differs from the version'
                                            ' of the trajectory').f_lock()

        self._traj.config.environment.v_comment = 'Settings for the different environments ' \
                                                  'used to run the experiments'

        # Add HDF5 config in case the user wants the standard service
        if self._use_hdf5:
            if not 'hdf5' in self.v_trajectory.config.f_get_children(copy=False):

                # Print which file we use for storage
                self._logger.info('I will us the hdf5 file `%s`.' % self._filename)

                for table_name in HDF5StorageService.NAME_TABLE_MAPPING.values():
                    self._traj.f_add_config('hdf5.overview.' + table_name,
                                            True,
                                            comment='Whether or not to have an overview '
                                                    'table with that name')

                self._traj.f_add_config('hdf5.overview.explored_parameters_runs', True,
                                        comment='Whether there are overview tables about the '
                                                'explored parameters in each run')

                self._traj.f_add_config('hdf5.purge_duplicate_comments', purge_duplicate_comments,
                                        comment='Whether comments of results and'
                                                ' derived parameters should only'
                                                ' be stored for the very first instance.'
                                                ' Works only if the summary tables are'
                                                ' active.')

                self._traj.f_add_config('hdf5.results_per_run', results_per_run,
                                        comment='Expected number of results per run,'
                                                ' a good guess can increase storage performance')

                self._traj.f_add_config('hdf5.derived_parameters_per_run',
                                        derived_parameters_per_run,
                                        comment='Expected number of derived parameters per run,'
                                                ' a good guess can increase storage performance')

                self._traj.f_add_config('hdf5.complevel', complevel,
                                        comment='Compression Level (0 no compression '
                                                'to 9 highest compression)')

                self._traj.f_add_config('hdf5.complib', complib,
                                        comment='Compression Algorithm')

                self._traj.f_add_config('hdf5.encoding', encoding,
                                        comment='Encoding for unicode characters')

                self._traj.f_add_config('hdf5.fletcher32', fletcher32,
                                        comment='Whether to use fletcher 32 checksum')

                self._traj.f_add_config('hdf5.shuffle', shuffle,
                                        comment='Whether to use shuffle filtering.')

                self._traj.f_add_config('hdf5.pandas_format', pandas_format,
                                        comment='''How to store pandas data frames, either'''
                                                ''' 'fixed' ('f') or 'table' ('t').''')

                self._traj.f_add_config('hdf5.pandas_append', pandas_append,
                                        comment='If pandas frames are stored as tables, one can '
                                                'enable append mode.')

                self._traj.config.hdf5.v_comment = 'Settings for the standard HDF5 storage service'

                self.f_set_summary(summary_tables)
                self.f_set_small_overview(small_overview_tables)
                self.f_set_large_overview(large_overview_tables)
            else:
                self._logger.warning('Your trajectory was already stored with an HDF5 storage '
                                     'service before. I will use the old settings and ignore your '
                                     'current HDF5 settings.')

        # Notify that in case of lazy debuggin we won't record anythin
        if lazy_debug and is_debug():
            self._logger.warning('Using the LazyStorageService, nothing will be saved to disk.')

        self._trajectory_name = self._traj.v_name
        self._logger.info('Environment initialized.')

    @staticmethod
    def _make_logging_handlers(log_path, log_level, log_stdout):

        # Make the log folders, the lowest folder in hierarchy has the trajectory name
        if not os.path.isdir(log_path):
            os.makedirs(log_path)

        # Check if there already exist logging handlers, if so, we assume the user
        # has already set a log  level. If not, we set the log level to INFO
        if len(logging.getLogger().handlers) == 0:
            logging.basicConfig(level=log_level)

        # Add a handler for storing everything to a text file
        f = logging.Formatter(
            '%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s')
        h = logging.FileHandler(filename=log_path + '/main.txt')
        root = logging.getLogger()
        root.addHandler(h)

        # Add a handler for storing warnings and errors to a text file
        h = logging.FileHandler(filename=log_path + '/errors_and_warnings.txt')
        h.setLevel(logging.WARNING)
        root = logging.getLogger()
        root.addHandler(h)

        if log_stdout:
            # Also copy standard out and error to the log files
            outstl = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO)
            sys.stdout = outstl

            errstl = StreamToLogger(logging.getLogger('STDERR'), logging.ERROR)
            sys.stderr = errstl

        for handler in root.handlers:
            handler.setFormatter(f)

    @deprecated('Please use assignment in environment constructor.')
    def f_switch_off_large_overview(self):
        """ Switches off the tables consuming the most memory.

            * Single Run Result Overview

            * Single Run Derived Parameter Overview

            * Explored Parameter Overview in each Single Run


        DEPRECATED: Please pass whether to use the tables to the environment constructor.

        """
        self.f_set_large_overview(0)

    @deprecated('Please use assignment in environment constructor.')
    def f_switch_off_all_overview(self):
        """Switches all tables off.

        DEPRECATED: Please pass whether to use the tables to the environment constructor.

        """
        self.f_set_summary(0)
        self.f_set_small_overview(0)
        self.f_set_large_overview(0)

    @deprecated('Please use assignment in environment constructor.')
    def f_switch_off_small_overview(self):
        """ Switches off small overview tables and switches off `purge_duplicate_comments`.

        DEPRECATED: Please pass whether to use the tables to the environment constructor.

        """
        self.f_set_small_overview(0)

    def f_set_large_overview(self, switch):
        """Switches large overview tables on (`switch=True`) or off (`switch=False`). """
        switch = switch
        self._traj.config.hdf5.overview.results_runs = switch
        self._traj.config.hdf5.overview.derived_parameters_runs = switch
        self._traj.config.hdf5.overview.explored_parameters_runs = switch

    def f_set_summary(self, switch):
        """Switches summary tables on (`switch=True`) or off (`switch=False`). """
        switch = switch
        self._traj.config.hdf5.overview.derived_parameters_runs_summary = switch
        self._traj.config.hdf5.overview.results_runs_summary = switch
        self._traj.config.hdf5.purge_duplicate_comments = switch

    def f_set_small_overview(self, switch):
        """Switches small overview tables on (`switch=True`) or off (`switch=False`). """
        switch = switch
        self._traj.config.hdf5.overview.parameters = switch
        self._traj.config.hdf5.overview.config = switch
        self._traj.config.hdf5.overview.explored_parameters = switch
        self._traj.config.hdf5.overview.derived_parameters_trajectory = switch
        self._traj.config.hdf5.overview.results_trajectory = switch

    def f_continue(self, trajectory_name=None, continue_folder=None):
        """Resumes crashed trajectories.

        :param trajectory_name:

            Name of trajectory to resume, if not specified the name passed to the environment
            is used. Be aware that if `add_time=True` the name you passed to the environment is
            altered and the current date is added.

        :param continue_folder:

            The folder where continue files can be found. Do not pass the name of the sub-folder
            with the trajectory name, but to the name of the parental folder.
            If not specified the continue folder passed to the environment is used.

        :return:

            List of the individual results returned by your run function.

            Returns a LIST OF TUPLES, where first entry is the run idx and second entry
            is the actual result. In case of multiprocessing these are not necessarily
            ordered according to their run index, but ordered according to their finishing time.

            Does not contain results stored in the trajectory!
            In order to access these simply interact with the trajectory object,
            potentially after calling`~pypet.trajectory.Trajectory.f_update_skeleton`
            and loading all results at once with :func:`~pypet.trajectory.f_load`
            or loading manually with :func:`~pypet.trajectory.f_load_items`.

            Even if you use multiprocessing without a pool the results returned by
            `runfunc` still need to be pickled.

        """
        if trajectory_name is None:
            self._trajectory_name = self.v_trajectory.v_name
        else:
            self._trajectory_name = trajectory_name

        if continue_folder is not None:
            self._continue_folder = continue_folder

        return self._execute_runs(None)

    @ property
    def v_trajectory(self):
        """ The trajectory of the Environment"""
        return self._traj

    @property
    def v_hexsha(self):
        """The SHA1 identifier of the environment.

        It is identical to the SHA1 of the git commit.
        If version control is not used, the environment hash is computed from the
        trajectory name, the current timestamp and your current pypet version."""
        return self._hexsha

    @property
    def v_time(self):
        """ Time of the creation of the environment, human readable."""
        return self._time

    @property
    def v_timestamp(self):
        """Time of creation as python datetime float"""
        return self._timestamp

    @property
    def v_name(self):
        """ Name of the Environment"""
        return self._name

    def _add_hdf5_storage_service(self, lazy_debug=False):
        """ Adds the standard HDF5 storage service to the trajectory.

        See also :class:`~pypet.storageservice.HDF5StorageService`.

        """

        if lazy_debug and is_debug():
            self._storage_service = LazyStorageService()
        else:
            self._storage_service = HDF5StorageService(self._filename,
                                                       self._file_title)

        self._traj.v_storage_service = self._storage_service

    def f_add_postprocessing(self, postproc, *args, **kwargs):
        """ Adds a post processing function.

        The environment will call this function via
        ``postproc(traj, result_list, *args, **kwargs)`` after the completion of the
        single runs.

        This function can load parts of the trajectory id needed and add additional results.

        Moreover, the function can be used to trigger an expansion of the trajectory.
        This can be useful if the user has an `optimization` task.

        Either the function calls `f_expand` directly on the trajectory or returns
        an dictionary. If latter `f_expand` is called by the environemnt.

        Note that after expansion of the trajectory, the postprocessing function is called
        again (and aigan for further expansions). Thus, this allows an iterative approach
        to parameter exploration.

        :param postproc:

            The post processing function

        :param args:

            Additional arguments passed to the post-processing function

        :param kwargs:

            Additional keyword arguments passed to the postprocessing function

        :return:

        """

        self._postproc = postproc
        self._postproc_args = args
        self._postproc_kwargs = kwargs

    def f_pipeline(self, pipeline):
        """ You can make *pypet* supervise your whole experiment by defining a pipeline.

        `pipeline` is a function that defines the entire experiment. From pre-processing
        including setting up the trajectory over defining the actual simulation runs to
        post processing.

        The `pipeline` function needs to return TWO tuples with a maximum of three entries each.

        For example:

        ::

            return (runfunc, args, kwargs), (postproc, postproc_args, postproc_kwargs)

        Where `runfunc` is the actual simulation function thet gets passed the trajectory
        container and potentially additional arguments `args` and keyword arguments `kwargs`.
        This will be run by your environment with all parameter combinations.

        `postproc` is a post processing function that handles your computed results.
        The function must accept as arguments the trajectory container, a list of
        results (list of tuples (run idx, result) ) and potentially
        additional arguments `postproc_args` and keyword arguments `postproc_kwargs`.

        As for :func:`~pypet.environment.Environment.f_add_postproc`, this function can
        potentially extend the trajectory.

        If you don't want to apply post-processing, your pipeline function can also simply
        return the run function and the arguments:

        ::

            return runfunc, args, kwargs

        Or

        ::

            return runfunc, args

        Or

        ::

            return runfunc

        ``return runfunc, kwargs`` does NOT work, if you don't want to pass `args` do
        ``return runfunc, (), kwargs``.

        Analogously combinations like

        ::

            return (runfunc, args), (postproc,)

        work as well.

        :param pipeline:

            The pipleine function, taking only a single argument `traj`.
            And returning all functions necessary for your experiment.

        :return:

            List of the individual results returned by `runfunc`.

            Returns a LIST OF TUPLES, where first entry is the run idx and second entry
            is the actual result. In case of multiprocessing these are not necessarily
            ordered according to their run index, but ordered according to their finishing time.

            Does not contain results stored in the trajectory!
            In order to access these simply interact with the trajectory object,
            potentially after calling :func:`~pypet.trajectory.Trajectory.f_update_skeleton`
            and loading all results at once with :func:`~pypet.trajectory.f_load`
            or loading manually with :func:`~pypet.trajectory.f_load_items`.

            Even if you use multiprocessing without a pool the results returned by
            `runfunc` still need to be pickled.

            Results computed from `postproc` are not returned. `postproc` should not
            return any results except dictionaries if the trajectory should be expanded.

        """
        self._user_pipeline = True
        return self._execute_runs(pipeline)

    def f_run(self, runfunc, *args, **kwargs):
        """ Runs the experiments and explores the parameter space.

        :param runfunc: The task or job to do

        :param args: Additional arguments (not the ones in the trajectory) passed to `runfunc`

        :param kwargs:

            Additional keyword arguments (not the ones in the trajectory) passed to `runfunc`

        :return:

            List of the individual results returned by `runfunc`.

            Returns a LIST OF TUPLES, where first entry is the run idx and second entry
            is the actual result. In case of multiprocessing these are not necessarily
            ordered according to their run index, but ordered according to their finishing time.

            Does not contain results stored in the trajectory!
            In order to access these simply interact with the trajectory object,
            potentially after calling`~pypet.trajectory.Trajectory.f_update_skeleton`
            and loading all results at once with :func:`~pypet.trajectory.f_load`
            or loading manually with :func:`~pypet.trajectory.f_load_items`.

            If you use multiprocessing without a pool the results returned by
            `runfunc` still need to be pickled.

        """
        pipeline = lambda traj: ((runfunc, args, kwargs),
                                 (self._postproc, self._postproc_args, self._postproc_kwargs))

        self._user_pipeline = False

        return self._execute_runs(pipeline)

    def _trigger_continue_snapshot(self):
        """ Makes the trajectory continuable in case the user wants that"""
        dump_dict = {}
        dump_filename = os.path.join(self._continue_path, 'environment.ecnt')

        # Store the trajectory before the first runs
        prev_full_copy = self._traj.v_full_copy
        dump_dict['full_copy'] = prev_full_copy
        self._traj.v_full_copy = True
        prev_storage_service = self._traj.v_storage_service
        self._traj.v_storage_service = self._storage_service
        dump_dict['trajectory'] = self._traj
        dump_dict['args'] = self._args
        dump_dict['kwargs'] = self._kwargs
        dump_dict['runfunc'] = self._runfunc
        dump_dict['postproc'] = self._postproc
        dump_dict['postproc_args'] = self._postproc_args
        dump_dict['postproc_kwargs'] = self._postproc_kwargs
        dump_dict['start_timestamp'] = self._start_timestamp

        dump_file = open(dump_filename, 'wb')
        dill.dump(dump_dict, dump_file, protocol=2)
        dump_file.flush()
        dump_file.close()

        self._traj.v_full_copy = prev_full_copy
        self._traj.v_storage_service = prev_storage_service

    def _prepare_sumatra(self):
        """ Prepares a sumatra record"""
        reason = self._sumatra_reason
        if reason:
            reason += ' -- '
        reason += 'Trajectory: `%s`, %s -- Explored Parameters: %s' % \
                  (self._traj.v_name,
                   self._traj.v_comment,
                   str(compat.listkeys(self._traj._explored_parameters)))

        self._logger.info('Preparing sumatra record with reason: %s' % reason)
        self._sumatra_reason = reason
        self._project = load_project(self._sumatra_project)

        if self._traj.f_contains('parameters'):
            param_dict = self._traj.parameters.f_to_dict(fast_access=False)

            for param_name in compat.listkeys(param_dict):
                param = param_dict[param_name]
                if param.f_has_range():
                    param_dict[param_name] = param.f_get_range()
                else:
                    param_dict[param_name] = param.f_get()
        else:
            param_dict = {}

        relpath = os.path.relpath(sys.modules['__main__'].__file__, self._sumatra_project)

        executable = PythonExecutable(path=sys.executable)

        self._record = self._project.new_record(
            parameters=param_dict,
            main_file=relpath,
            executable=executable,
            label=self._sumatra_label,
            reason=reason)

    def _finish_sumatra(self):
        """ Saves a sumatra record"""
        finish_time = self._start_timestamp - self._finish_timestamp
        self._record.duration = finish_time
        self._record.output_data = self._record.datastore.find_new_data(self._record.timestamp)
        self._project.add_record(self._record)
        self._project.save()
        sumatra_label = self._record.label

        config_name = 'sumatra.record_%s.label' % str(sumatra_label)
        if not self._traj.f_contains('config.' + config_name):
            self._traj.f_add_config(config_name, sumatra_label,
                                    comment='The label of the sumatra record')

        if self._sumatra_reason:
            config_name = 'sumatra.record_%s.reason' % str(sumatra_label)
            if not self._traj.f_contains('config.' + config_name):
                self._traj.f_add_config(config_name, self._sumatra_reason,
                                        comment='Reason of sumatra run.')

        self._logger.info('Saved sumatra project with reason: %s' % self._sumatra_reason)

    def _prepare_continue(self):
        """Prepares the continuation of a crashed trajectory"""
        if not self._continuable:
            raise RuntimeError('If you create an environment to continue a run, you need to '
                               'set `continuable=True`.')

        if not self._do_single_runs:
            raise RuntimeError('You cannot continue a run if you did create an environment '
                               'with `do_single_runs=False`.')

        self._continue_path = os.path.join(self._continue_folder, self._trajectory_name)
        cnt_filename = os.path.join(self._continue_path, 'environment.ecnt')
        cnt_file = open(cnt_filename, 'rb')
        continue_dict = dill.load(cnt_file)
        cnt_file.close()
        traj = continue_dict['trajectory']

        # We need to update the information about the trajectory name
        config_name = 'config.environment.%s.trajectory.name' % self.v_name
        if self._traj.f_contains(config_name, shortcuts=False):
            param = self._traj.f_get(config_name, shortcuts=False)
            param.f_unlock()
            param.f_set(traj.v_name)
            param.f_lock()

        config_name = 'config.environment.%s.trajectory.timestamp' % self.v_name
        if self._traj.f_contains(config_name, shortcuts=False):
            param = self._traj.f_get(config_name, shortcuts=False)
            param.f_unlock()
            param.f_set(traj.v_timestamp)
            param.f_lock()

        # Merge the information so that we keep a record about the current environment
        if not traj.config.environment.f_contains(self.v_name, shortcuts=False):
            traj._merge_config(self._traj)
        self._traj = traj

        # User's job function
        self._runfunc = continue_dict['runfunc']
        # Arguments to the user's job function
        self._args = continue_dict['args']
        # Keyword arguments to the user's job function
        self._kwargs = continue_dict['kwargs']
        # Postproc Function
        self._postproc = continue_dict['postproc']
        # Postprog args
        self._postproc_args = continue_dict['postproc_args']
        # Postproc Kwargs
        self._postproc_kwargs = continue_dict['postproc_kwargs']

        old_start_timestamp = continue_dict['start_timestamp']

        # Unpack the trajectory
        self._traj.v_full_copy = continue_dict['full_copy']
        # Load meta data
        self._traj.f_load(load_parameters=pypetconstants.LOAD_NOTHING,
                          load_derived_parameters=pypetconstants.LOAD_NOTHING,
                          load_results=pypetconstants.LOAD_NOTHING,
                          load_other_data=pypetconstants.LOAD_NOTHING)

        # Now we have to reconstruct previous results
        result_tuple_list = []
        full_filename_list = []
        for filename in os.listdir(self._continue_path):
            _, ext = os.path.splitext(filename)

            if ext != '.rcnt':
                continue

            full_filename = os.path.join(self._continue_path, filename)
            cnt_file = open(full_filename, 'rb')
            result_dict = dill.load(cnt_file)
            cnt_file.close()
            result_tuple_list.append((result_dict['timestamp'], result_dict['result']))
            full_filename_list.append(full_filename)

        # Sort according to counter
        result_tuple_list = sorted(result_tuple_list, key=lambda x: x[0])
        result_list = [x[1] for x in result_tuple_list]

        run_indices = [result[0] for result in result_list]
        # Remove incomplete runs and check which result snapshots need to be removed
        cleaned_run_indices = self._traj._remove_incomplete_runs(old_start_timestamp, run_indices)
        cleaned_run_indices_set = set(cleaned_run_indices)

        new_result_list = []
        for idx, result_tuple in enumerate(result_list):
            index = result_tuple[0]
            if index in cleaned_run_indices_set:
                new_result_list.append(result_tuple)
            else:
                os.remove(full_filename_list[idx])

        # Add a config parameter signalling that an experiment was continued, and how many of them
        config_name = 'environment.%s.continued' % self.v_name
        if not config_name in self._traj:
            self._traj.f_add_config(config_name, True,
                                    comment='Added if a crashed trajectory was continued.')

        self._logger.info('I will resume trajectory `%s`.' % self._traj.v_name)

        return new_result_list

    def _prepare_runs(self, pipeline):
        """Prepares the running of an experiment

        :param pipeline:

            A pipeline function that defines the task

        :return:

            The number of runs to be executed

        """

        pip_result = pipeline(self._traj)  # Call the pipeline function

        # Extract the task to do from the pipeline result
        raise_error = False
        if pip_result is None:
            if self._do_single_runs:
                raise RuntimeError('Your pipeline function did return `None`.'
                                   'Accordingly, I assume you just do data analysis. '
                                   'Please create and environment with `do_single_runs=False`.')

            self._logger.info('Your pipeline returned no runfunction, I assume you do some '
                              'sort of data analysis and will skip any single run execution.')
            self._runfunc = None
            return
        elif (len(pip_result) == 2 and
              isinstance(pip_result[0], tuple) and
              isinstance(pip_result[1], tuple)):

            run_tuple = pip_result[0]
            self._runfunc = run_tuple[0]
            if len(run_tuple) > 1:
                self._args = run_tuple[1]
            if len(run_tuple) > 2:
                self._kwargs = run_tuple[2]
            if len(run_tuple) > 3:
                raise_error = True

            postproc_tuple = pip_result[1]
            if len(postproc_tuple) > 0:
                self._postproc = postproc_tuple[0]
            if len(postproc_tuple) > 1:
                self._postproc_args = postproc_tuple[1]
            if len(postproc_tuple) > 2:
                self._postproc_kwargs = postproc_tuple[2]
            if len(run_tuple) > 3:
                raise_error = True

        elif len(pip_result) <= 3:
            self._runfunc = pip_result[0]
            if len(pip_result) > 1:
                self._args = pip_result[1]
            if len(pip_result) > 2:
                self._kwargs = pip_result[2]
        else:
            raise_error = True

        if raise_error:
            raise RuntimeError('Your pipeline result is not understood please return'
                               'a tuple of maximum length 3: ``(runfunc, args, kwargs)`` '
                               'Or return two tuple of maximum length 3: '
                               '``(runfunc, args, kwargs), '
                               '(postproc, postproc_args, postproc_kwargs)')

        if self._runfunc is not None and not self._do_single_runs:
            raise RuntimeError('You cannot make a run if you did create an environment '
                               'with `do_single_runs=False`.')

        # Make some sanity checks if the user wants the standard hdf5 service.
        if self._use_hdf5:
            if ((not self._traj.f_get('results_runs_summary').f_get() or
                    not self._traj.f_get('results_runs_summary').f_get()) and
                    self._traj.f_get('purge_duplicate_comments').f_get()):
                raise RuntimeError('You can only use the reduce comments if you enable '
                                   'the summary tables.')

        if self._continuable and os.listdir(self._continue_path):
            raise RuntimeError('Your continue folder `%s` needs to be empty to allow continuing!')

        if self._user_pipeline:
            self._logger.info('\n************************************************************\n'
                              'STARTING PPREPROCESSING for trajectory\n`%s`'
                              '\n************************************************************\n' %
                              self._traj.v_name)

        # Make some preparations (locking of parameters etc) and store the trajectory
        self._logger.info('I am preparing the Trajectory for the experiment and '
                          'initialise the store.')
        self._traj._prepare_experiment()

        self._logger.info('Initialising the storage for the trajectory.')
        self._traj.f_store(only_init=True)

    def _make_iterator(self, queue, result_queue, start_run_idx):
        """Returns an iterator over all runs for multiprocessing"""
        return ((self._traj._make_single_run(n),
                 self._log_path,
                 self._log_stdout,
                 queue,
                 self._runfunc, len(self._traj),
                 self._multiproc,
                 result_queue,
                 self._args,
                 self._kwargs,
                 self._clean_up_runs,
                 self._continue_path,
                 self._automatic_storing)
                for n in compat.xrange(start_run_idx, len(self._traj))
                if not self._traj.f_is_completed(n))

    def _execute_postproc(self, results):
        """Executes a postprocessing function

        :param results:

            List of tuples containing the run indices and the results

        :return:

            1. Whether to new single runs, since the trajectory was enlarged
            2. Index of next new run
            3. Number of new runs

        """
        repeat = False
        start_run_idx = 0
        new_runs = 0

        old_traj_length = len(self._traj)
        postproc_res = self._postproc(self._traj, results,
                                      *self._postproc_args, **self._postproc_kwargs)

        new_traj_length = len(self._traj)

        if new_traj_length != old_traj_length or isinstance(postproc_res, dict):
            start_run_idx = old_traj_length
            repeat = True

            if isinstance(postproc_res, dict):
                self._traj.f_expand(postproc_res)

            if self._continuable:
                self._logger.warning('Continuing a trajectory AND expanding it during runtime is '
                                     'NOT supported properly, there is no guarantee that this '
                                     'works!')

                self._traj.f_store(only_init=True)

            new_traj_length = len(self._traj)
            new_runs = new_traj_length - old_traj_length

            if self._clean_up_runs:
                self._traj._remove_run_data()

        return repeat, start_run_idx, new_runs

    def _execute_runs(self, pipeline):
        """ Starts the individual single runs.

        Starts runs sequentially or initiates multiprocessing.

        :param pipeline:

            A pipeline function producing the run function the corresponding arguments
            and postprocessing function and arguments

        :return:

            List of tuples, where each tuple contains the run idx and the result.

        """
        self._start_timestamp = time.time()

        if self._sumatra_project is not None:
            self._prepare_sumatra()

        start_run_idx = 0
        expanded_by_postproc = False

        if pipeline is not None:
            results = []
            self._prepare_runs(pipeline)
        else:
            results = self._prepare_continue()

        if self._runfunc is not None:

            config_name = 'environment.%s.start_timestamp' % self.v_name
            if not self._traj.f_contains('config.' + config_name):
                self._traj.f_add_config(config_name, self._start_timestamp,
                                        comment='Timestamp of starting of experiment '
                                                '(when the actual simulation was '
                                                'started (either by calling `f_run`, '
                                                '`f_continue`, or `f_pipeline`).')

            if self._multiproc and self._postproc is not None:
                config_name = 'environment.%s.immediate_postprocessing' % self.v_name
                if not self._traj.f_contains('config.' + config_name):
                    self._traj.f_add_config(config_name, self._immediate_postproc,
                                            comment='Whether to use immediate '
                                                    'postprocessing, only added if '
                                                    'postprocessing was used at all.')

            result_queue = None  # Queue for results of `runfunc` in case of multiproc without pool
            self._storage_service = self._traj.v_storage_service

            if self._continuable:
                self._trigger_continue_snapshot()

            while True:
                if self._multiproc:
                    manager = multip.Manager()

                    if not self._use_pool:
                        # If we spawn a single process for each run, we need an additional queue
                        # for the results of `runfunc`
                        if self._postproc is None:
                            result_queue = manager.Queue(maxsize=len(self._traj))
                        else:
                            result_queue = manager.Queue()

                    # Prepare Multiprocessing
                    if self._wrap_mode == pypetconstants.WRAP_MODE_QUEUE:
                        # For queue mode we need to have a queue in a block of shared memory.
                        queue = manager.Queue()

                        self._logger.info('Starting the Storage Queue!')

                        # Wrap a queue writer around the storage service
                        queue_writer = QueueStorageServiceWriter(self._storage_service, queue)

                        # Start the queue process
                        queue_process = multip.Process(name='QueueProcess', target=_queue_handling,
                                                       args=(queue_writer, self._log_path,
                                                             self._log_stdout))
                        queue_process.start()

                        # Replace the storage service of the trajectory by a sender.
                        # The sender will put all data onto the queue.
                        # The writer from above will receive the data from
                        # the queue and hand it over to
                        # the storage service
                        queue_sender = QueueStorageServiceSender()
                        queue_sender.queue = queue
                        self._traj.v_storage_service = queue_sender

                    elif self._wrap_mode == pypetconstants.WRAP_MODE_LOCK:

                        if self._use_pool:
                            # We need a lock that is shared by all processes.
                            lock = manager.Lock()
                        else:
                            lock = multip.Lock()

                        queue = None

                        # Wrap around the storage service to allow the placement of locks around
                        # the storage procedure.
                        lock_wrapper = LockWrapper(self._storage_service, lock)
                        self._traj.v_storage_service = lock_wrapper

                    elif self._wrap_mode == pypetconstants.WRAP_MODE_NONE:
                        # We assume that storage and loading is multiprocessing safe
                        pass
                    else:
                        raise RuntimeError('The mutliprocessing mode %s, your choice is '
                                           'not supported, use `%s` or `%s`.'
                                           % (self._wrap_mode, pypetconstants.WRAP_MODE_QUEUE,
                                              pypetconstants.WRAP_MODE_LOCK))

                    self._logger.info(
                        '\n************************************************************\n'
                        'STARTING runs of trajectory\n`%s`\nin parallel with %d cores.'
                        '\n************************************************************\n' %
                        (self._traj.v_name, self._ncores))

                    # Create a generator to generate the tasks for multiprocessing
                    iterator = self._make_iterator(queue, result_queue, start_run_idx)

                    if self._use_pool:
                        mpool = multip.Pool(self._ncores)
                        # Let the pool workers do their jobs provided by the generator
                        pool_results = mpool.imap(_single_run, iterator)

                        # Everything is done
                        mpool.close()
                        mpool.join()

                        del mpool

                        # We want to consistently return a list of results not an iterator
                        results.extend([result for result in pool_results])

                    else:

                        if self._check_usage:
                            self._logger.info(
                                'Monitoring usage statistics. I will not spawn new processes '
                                'if one of the following cap thresholds is crossed, '
                                'CPU: %.2f, RAM: %.2f, Swap: %.2f.' %
                                (self._cpu_cap, self._memory_cap, self._swap_cap))
                            psutil.cpu_percent()  # Just for initialisation

                        no_cap = True  # Evaluates if new processes are allowed to be started
                        # or if cap is reached
                        signal_cap = True  # If True cap warning is emitted
                        keep_running = True  # Evaluates to falls if trajectory produces
                        # no more single runs
                        process_dict = {}  # Dict containing all subprocees

                        while len(process_dict) > 0 or keep_running:

                            # First check if some processes did finish their job
                            for pid in compat.listkeys(process_dict):
                                proc = process_dict[pid]

                                # Delete the terminated processes
                                if not proc.is_alive():
                                    process_dict.pop(pid)

                            # Check if caps are reached.
                            # Cap is only checked if there is at least one
                            # process working to prevent deadlock.
                            if self._check_usage and keep_running:
                                no_cap = True
                                if len(process_dict) > 0:
                                    cpu_usage = psutil.cpu_percent() / 100.0
                                    memory_usage = psutil.phymem_usage().percent / 100.0
                                    swap_usage = psutil.swap_memory().percent / 100.0
                                    if cpu_usage > self._cpu_cap:
                                        no_cap = False
                                        if signal_cap:
                                            self._logger.warning(
                                                'Could not start next process immediately.'
                                                'CPU Cap reached, %.2f >= %.2f.' %
                                                (cpu_usage, self._cpu_cap))
                                            signal_cap = False
                                    elif memory_usage > self._memory_cap:
                                        no_cap = False
                                        if signal_cap:
                                            self._logger.warning('Could not start next process '
                                                                 'immediately. Memory Cap '
                                                                 'reached, %.2f >= %.2f.' %
                                                                 (memory_usage, self._memory_cap))
                                            signal_cap = False
                                    elif swap_usage > self._swap_cap:
                                        no_cap = False
                                        if signal_cap:
                                            self._logger.warning('Could not start next process '
                                                                 'immediately. Swap Cap reached, '
                                                                 '%.2f >= %.2f.' %
                                                                 (swap_usage, self._swap_cap))
                                            signal_cap = False

                            # If we have less active processes than self._ncores and there is still
                            # a job to do, add another process
                            if len(process_dict) < self._ncores and keep_running and no_cap:
                                try:
                                    task = next(iterator)
                                    proc = multip.Process(target=_single_run,
                                                          args=(task,))
                                    proc.start()
                                    process_dict[proc.pid] = proc
                                    signal_cap = True
                                except StopIteration:
                                    # All simulation runs have been started
                                    keep_running = False
                                    if self._postproc is not None and self._immediate_postproc:
                                        while not result_queue.empty():
                                            result = result_queue.get()

                                            results.append(result)

                                        self._logger.info(
                                            '\n***********************************'
                                            '*************************\n'
                                            'STARTING IMMEDIATE POSTPROCESSING. '
                                            'for trajectory\n`%s`'
                                            '\n***********************************'
                                            '*************************\n' %
                                            self._traj.v_name)

                                        keep_running, start_run_idx, new_runs = \
                                            self._execute_postproc(results)

                                        if keep_running:
                                            expanded_by_postproc = True
                                            self._logger.info(
                                                '\n********************************'
                                                '****************************\n'
                                                'IMMEDIATE POSTPROCESSING expanded the '
                                                'trajectory and added %d new runs'
                                                '\n********************************'
                                                '****************************\n' %
                                                new_runs
                                            )

                                            iterator = self._make_iterator(queue, result_queue,
                                                                           start_run_idx)
                            time.sleep(0.01)

                        # Get all results from the result queue
                        while not result_queue.empty():
                            result = result_queue.get()

                            results.append(result)

                    # In case of queue mode, we need to signal to the queue writer
                    # that no more data
                    # will be put onto the queue
                    if self._wrap_mode == pypetconstants.WRAP_MODE_QUEUE:
                        self._traj.v_storage_service.send_done()
                        queue_process.join()

                    # Replace the wrapped storage service with the original one
                    # and do some finalization
                    self._traj.v_storage_service = self._storage_service
                    self._traj._finalize()

                    self._logger.info(
                        '\n************************************************************\n'
                        'FINISHED all runs of trajectory\n`%s`\nin parallel with %d cores.'
                        '\n************************************************************\n' %
                        (self._traj.v_name, self._ncores))

                else:
                    if self._deep_copy_data:  # Not supported ATM, here for future reference
                        old_full_copy = self._traj.v_full_copy
                        self._traj.v_full_copy = True
                        deep_copied_data = [self._runfunc,
                                            self._traj, self._args, self._kwargs]
                        if dill is not None:
                            deep_copy_dump = dill.dumps(deep_copied_data)
                        else:
                            deep_copy_dump = pickle.dumps(deep_copied_data)
                        self._traj.v_full_copy = old_full_copy

                    # Single Processing
                    self._logger.info(
                        '\n************************************************************\n'
                        'STARTING runs of trajectory\n`%s`.'
                        '\n************************************************************\n' %
                        self._traj.v_name)

                    # Sequentially run all single runs and append the results to a queue
                    for n in compat.xrange(start_run_idx, len(self._traj)):
                        if not self._traj.f_is_completed(n):

                            if self._deep_copy_data:  # Not supported ATM,
                            # here for future reference
                                if dill is not None:
                                    deep_copied_data = dill.loads(deep_copy_dump)
                                else:
                                    deep_copied_data = pickle.loads(deep_copy_dump)
                                deep_copied_data[1].v_full_copy = old_full_copy
                                result = _single_run((deep_copied_data[1]._make_single_run(n),
                                                      self._log_path,
                                                      self._log_stdout,
                                                      None, deep_copied_data[0],
                                                      len(self._traj),
                                                      self._multiproc,
                                                      None,
                                                      deep_copied_data[2],
                                                      deep_copied_data[3],
                                                      self._clean_up_runs,
                                                      self._continue_path,
                                                      self._automatic_storing))
                            else:
                                result = _single_run((self._traj._make_single_run(n),
                                                      self._log_path,
                                                      self._log_stdout,
                                                      None, self._runfunc,
                                                      len(self._traj),
                                                      self._multiproc,
                                                      None,
                                                      self._args,
                                                      self._kwargs,
                                                      self._clean_up_runs,
                                                      self._continue_path,
                                                      self._automatic_storing))

                            results.append(result)

                    # Do some finalization
                    self._traj._finalize()

                    self._logger.info(
                        '\n************************************************************\n'
                        'FINISHED all runs of trajectory\n`%s`.'
                        '\n************************************************************\n' %
                        self._traj.v_name)

                repeat = False
                if self._postproc is not None:
                    self._logger.info(
                        '\n************************************************************\n'
                        'STARTING POSTPROCESSING for trajectory\n`%s`'
                        '\n************************************************************\n' %
                        self._traj.v_name)

                    repeat, start_run_idx, new_runs = self._execute_postproc(results)

                if not repeat:
                    break
                else:
                    expanded_by_postproc = True
                    self._logger.info(
                        '\n************************************************************\n'
                        '  POSTPROCESSING expanded the trajectory and added %d new runs'
                        '\n************************************************************\n' %
                        new_runs
                    )

        if self._continuable and self._delete_continue:
            # We remove all continue files if the simulation was successfully completed
            shutil.rmtree(self._continue_path)

        if expanded_by_postproc:
            config_name = 'environment.%s.postproc_expand' % self.v_name
            if not self._traj.f_contains('config.' + config_name):
                self._traj.f_add_config(config_name, True,
                                        comment='Added if trajectory was expanded '
                                                'by postprocessing.')

        config_name = 'environment.%s.automatic_storing' % self.v_name
        if not self._traj.f_contains('config.' + config_name):
            self._traj.f_add_config(config_name, self.v_trajectory.v_name,
                                    comment='If trajectory should be stored automatically in the '
                                            'end.').f_lock()
        if self._automatic_storing:
            self._logger.info('\n************************************************************\n'
                              'STARTING FINAL STORING of trajectory\n`%s`'
                              '\n************************************************************\n' %
                              self._traj.v_name)
            self._traj.f_store()
            self._logger.info('\n************************************************************\n'
                              'FINISHED FINAL STORING of trajectory\n`%s`.'
                              '\n************************************************************\n' %
                              self._traj.v_name)

        self._finish_timestamp = time.time()

        findatetime = datetime.datetime.fromtimestamp(self._finish_timestamp)
        startdatetime = datetime.datetime.fromtimestamp(self._start_timestamp)

        self._runtime = str(findatetime - startdatetime)

        conf_list = []
        config_name = 'environment.%s.finish_timestamp' % self.v_name
        if not self._traj.f_contains('config.' + config_name):
            conf1 = self._traj.f_add_config(config_name, self._finish_timestamp,
                                            comment='Timestamp of finishing of an experiment.')
            conf_list.append(conf1)

        config_name = 'environment.%s.runtime' % self.v_name
        if not self._traj.f_contains('config.' + config_name):
            conf2 = self._traj.f_add_config(config_name, self._runtime,
                                            comment='Runtime of whole experiment.')
            conf_list.append(conf2)

        if conf_list:
            self._traj.f_store_items(conf_list)

        # Final check if traj was successfully completed
        self._traj.f_load(load_all=pypetconstants.LOAD_NOTHING)
        all_completed = True
        for run_name in self._traj.f_get_run_names():
            if not self._traj.f_is_completed(run_name):
                all_completed = False
                self._logger.error('Run `%s` did NOT completed!' % run_name)
        if all_completed:
            self._logger.info('All runs of trajectory `%s` were completed succesfully.' %
                              self._traj.v_name)

        if self._sumatra_project is not None:
            self._finish_sumatra()

        return results
