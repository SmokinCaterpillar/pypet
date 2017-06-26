""" Module containing the environment to run experiments.

An :class:`~pypet.environment.Environment` provides an interface to run experiments based on
parameter exploration.

The environment contains and might even create a :class:`~pypet.trajectory.Trajectory`
container which can be filled with parameters and results (see :mod:`pypet.parameter`).
Instance of this trajectory are distributed to the user's job function to perform a single run
of an experiment.

An `Environment` is the handyman for scheduling, it can be used for multiprocessing and takes
care of organizational issues like logging.

"""

__author__ = 'Robert Meyer'

try:
    import __main__ as main
except ImportError as exc:
    main = None  # We can end up here in an interactive IPython console
import os
import sys
import logging
import shutil
import multiprocessing as multip
import traceback
import hashlib
import time
import datetime
import inspect

try:
    from sumatra.projects import load_project
    from sumatra.programs import PythonExecutable
except ImportError:
    load_project = None
    PythonExecutable = None

try:
    import dill
    # If you do not set this log-level dill will flood any log file :-(
    logging.getLogger(dill.__name__).setLevel(logging.WARNING)
except ImportError:
    dill = None

try:
    import psutil
except ImportError:
    psutil = None

try:
    import scoop
    from scoop import futures, shared
except ImportError:
    scoop = None

try:
    import git
except ImportError:
    git = None

try:
    import zmq
except ImportError:
    zmq = None

from pypet.pypetlogging import LoggingManager, HasLogger, simple_logging_config
from pypet.trajectory import Trajectory
from pypet.storageservice import HDF5StorageService, LazyStorageService
from pypet.utils.mpwrappers import QueueStorageServiceWriter, LockWrapper, \
    PipeStorageServiceSender, PipeStorageServiceWriter, ReferenceWrapper, \
    ReferenceStore, QueueStorageServiceSender, LockerServer, LockerClient, \
    ForkAwareLockerClient, TimeOutLockerServer, QueuingClient, QueuingServer, \
    ForkAwareQueuingClient
from pypet.utils.siginthandling import sigint_handling
from pypet.utils.gitintegration import make_git_commit
from pypet._version import __version__ as VERSION
from pypet.utils.decorators import deprecated, kwargs_api_change, prefix_naming
from pypet.utils.helpful_functions import is_debug, result_sort, format_time, port_to_tcp, \
    racedirs
from pypet.utils.storagefactory import storage_factory
from pypet.utils.configparsing import parse_config
from pypet.parameter import Parameter
import pypet.pypetconstants as pypetconstants


def _pool_single_run(kwargs):
    """Starts a pool single run and passes the storage service"""
    wrap_mode = kwargs['wrap_mode']
    traj = kwargs['traj']
    traj.v_storage_service = _pool_single_run.storage_service
    if wrap_mode == pypetconstants.WRAP_MODE_LOCAL:
        # Free references from previous runs
        traj.v_storage_service.free_references()
    return _sigint_handling_single_run(kwargs)


def _frozen_pool_single_run(kwargs):
    """Single run wrapper for the frozen pool, makes a single run and passes kwargs"""
    idx = kwargs.pop('idx')
    frozen_kwargs = _frozen_pool_single_run.kwargs
    frozen_kwargs.update(kwargs)  # in case of `run_map`
    # we need to update job's args and kwargs
    traj = frozen_kwargs['traj']
    traj.f_set_crun(idx)
    return _sigint_handling_single_run(frozen_kwargs)


def _configure_pool(kwargs):
    """Configures the pool and keeps the storage service"""
    _pool_single_run.storage_service = kwargs['storage_service']
    _configure_niceness(kwargs)
    _configure_logging(kwargs, extract=False)


def _configure_frozen_pool(kwargs):
    """Configures the frozen pool and keeps all kwargs"""
    _frozen_pool_single_run.kwargs = kwargs
    _configure_niceness(kwargs)
    _configure_logging(kwargs, extract=False)
    # Reset full copy to it's old value
    traj = kwargs['traj']
    traj.v_full_copy = kwargs['full_copy']


def _process_single_run(kwargs):
    """Wrapper function that first configures logging and starts a single run afterwards."""
    _configure_niceness(kwargs)
    _configure_logging(kwargs)
    result_queue = kwargs['result_queue']
    result = _sigint_handling_single_run(kwargs)
    result_queue.put(result)
    result_queue.close()


def _configure_frozen_scoop(kwargs):
    """Wrapper function that configures a frozen SCOOP set up.

    Deletes of data if necessary.

    """
    def _delete_old_scoop_rev_data(old_scoop_rev):
        if old_scoop_rev is not None:
            try:
                elements = shared.elements
                for key in elements:
                    var_dict = elements[key]
                    if old_scoop_rev in var_dict:
                        del var_dict[old_scoop_rev]
                logging.getLogger('pypet.scoop').debug('Deleted old SCOOP data from '
                                                       'revolution `%s`.' % old_scoop_rev)
            except AttributeError:
                logging.getLogger('pypet.scoop').error('Could not delete old SCOOP data from '
                                                       'revolution `%s`.' % old_scoop_rev)
    scoop_rev = kwargs.pop('scoop_rev')
    # Check if we need to reconfigure SCOOP
    try:
        old_scoop_rev = _frozen_scoop_single_run.kwargs['scoop_rev']
        configured = old_scoop_rev == scoop_rev
    except (AttributeError, KeyError):
        old_scoop_rev = None
        configured = False
    if not configured:
        _frozen_scoop_single_run.kwargs = shared.getConst(scoop_rev, timeout=424.2)
        frozen_kwargs = _frozen_scoop_single_run.kwargs
        frozen_kwargs['scoop_rev'] = scoop_rev
        frozen_kwargs['traj'].v_full_copy = frozen_kwargs['full_copy']
        if not scoop.IS_ORIGIN:
            _configure_niceness(frozen_kwargs)
            _configure_logging(frozen_kwargs, extract=False)
        _delete_old_scoop_rev_data(old_scoop_rev)
        logging.getLogger('pypet.scoop').info('Configured Worker %s' % str(scoop.worker))


def _frozen_scoop_single_run(kwargs):
    try:
        _configure_frozen_scoop(kwargs)
        idx = kwargs.pop('idx')
        frozen_kwargs = _frozen_scoop_single_run.kwargs
        frozen_kwargs.update(kwargs)
        traj = frozen_kwargs['traj']
        traj.f_set_crun(idx)
        return _single_run(frozen_kwargs)
    except Exception:
        scoop.logger.exception('ERROR occurred during a single run!')
        raise


def _scoop_single_run(kwargs):
    """Wrapper function for scoop, that does not configure logging"""
    try:
        try:
            is_origin = scoop.IS_ORIGIN
        except AttributeError:
            # scoop is not properly started, i.e. with `python -m scoop...`
            # in this case scoop uses default `map` function, i.e.
            # the main process
            is_origin = True
        if not is_origin:
            # configure logging and niceness if not the main process:
            _configure_niceness(kwargs)
            _configure_logging(kwargs)
        return _single_run(kwargs)
    except Exception:
        scoop.logger.exception('ERROR occurred during a single run!')
        raise


def _configure_logging(kwargs, extract=True):
    """Requests the logging manager to configure logging.

    :param extract:

        If naming data should be extracted from the trajectory

    """
    try:
        logging_manager = kwargs['logging_manager']
        if extract:
            logging_manager.extract_replacements(kwargs['traj'])
        logging_manager.make_logging_handlers_and_tools(multiproc=True)
    except Exception as exc:
        sys.stderr.write('Could not configure logging system because of: %s' % repr(exc))
        traceback.print_exc()


def _configure_niceness(kwargs):
    """Sets niceness of a process"""
    niceness = kwargs['niceness']
    if niceness is not None:
        try:
            try:
                current = os.nice(0)
                if niceness - current > 0:
                    # Under Linux you cannot decrement niceness if set elsewhere
                    os.nice(niceness-current)
            except AttributeError:
                # Fall back on psutil under Windows
                psutil.Process().nice(niceness)
        except Exception as exc:
            sys.stderr.write('Could not configure niceness because of: %s' % repr(exc))
            traceback.print_exc()

def _sigint_handling_single_run(kwargs):
    """Wrapper that allow graceful exits of single runs"""
    try:
        graceful_exit = kwargs['graceful_exit']

        if graceful_exit:
            sigint_handling.start()
            if sigint_handling.hit:
                result = (sigint_handling.SIGINT, None)
            else:
                result = _single_run(kwargs)
                if sigint_handling.hit:
                    result = (sigint_handling.SIGINT, result)
            return result
        return _single_run(kwargs)

    except:
        # Log traceback of exception
        pypet_root_logger = logging.getLogger('pypet')
        pypet_root_logger.exception('ERROR occurred during a single run! ')
        raise


def _single_run(kwargs):
    """ Performs a single run of the experiment.

    :param kwargs: Dict of arguments

        traj: The trajectory containing all parameters set to the corresponding run index.

        runfunc: The user's job function

        runargs: The arguments handed to the user's job function (as *args)

        runkwargs: The keyword arguments handed to the user's job function (as **kwargs)

        clean_up_after_run: Whether to clean up after the run

        automatic_storing: Whether or not the data should be automatically stored

        result_queue: A queue object to store results into in case a pool is used, otherwise None

    :return:

        Results computed by the user's job function which are not stored into the trajectory.
        Returns a nested tuple of run index and result and run information:
        ``((traj.v_idx, result), run_information_dict)``

    """
    pypet_root_logger = logging.getLogger('pypet')
    traj = kwargs['traj']
    runfunc = kwargs['runfunc']
    runargs = kwargs['runargs']
    kwrunparams = kwargs['runkwargs']
    clean_up_after_run = kwargs['clean_up_runs']
    automatic_storing = kwargs['automatic_storing']
    wrap_mode = kwargs['wrap_mode']

    idx = traj.v_idx
    total_runs = len(traj)

    pypet_root_logger.info('\n=========================================\n '
              'Starting single run #%d of %d '
              '\n=========================================\n' % (idx, total_runs))

    # Measure start time
    traj.f_start_run(turn_into_run=True)

    # Run the job function of the user
    result = runfunc(traj, *runargs, **kwrunparams)

    # Store data if desired
    if automatic_storing:
        traj.f_store()

    # Add the index to the result and the run information
    if wrap_mode == pypetconstants.WRAP_MODE_LOCAL:
        result = ((traj.v_idx, result),
                   traj.f_get_run_information(traj.v_idx, copy=False),
                   traj.v_storage_service.references)
        traj.v_storage_service.free_references()
    else:
        result = ((traj.v_idx, result),
                   traj.f_get_run_information(traj.v_idx, copy=False))

    # Measure time of finishing
    traj.f_finalize_run(store_meta_data=False,
                        clean_up=clean_up_after_run)

    pypet_root_logger.info('\n=========================================\n '
              'Finished single run #%d of %d '
              '\n=========================================\n' % (idx, total_runs))

    return result


def _wrap_handling(kwargs):
    """ Starts running a queue handler and creates a log file for the queue."""
    _configure_logging(kwargs, extract=False)
    # Main job, make the listener to the queue start receiving message for writing to disk.
    handler=kwargs['handler']
    graceful_exit = kwargs['graceful_exit']
    # import cProfile as profile
    # profiler = profile.Profile()
    # profiler.enable()
    if graceful_exit:
        sigint_handling.start()
    handler.run()
    # profiler.disable()
    # profiler.dump_stats('./queue.profile2')


@prefix_naming
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

    :param dynamic_imports:

          Only considered if a new trajectory is created.
          If you've written custom parameters or results that need to be loaded
          dynamically during runtime, the module containing the class
          needs to be specified here as a list of classes or strings
          naming classes and there module paths.

          For example:
          `dynamic_imports =
          ['pypet.parameter.PickleParameter', MyCustomParameter]`

          If you only have a single class to import, you do not need
          the list brackets:
          `dynamic_imports = 'pypet.parameter.PickleParameter'`

    :param wildcard_functions:

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

    :param automatic_storing:

        If `True` the trajectory will be stored at the end of the simulation and
        single runs will be stored after their completion.
        Be aware of data loss if you set this to `False` and not
        manually store everything.

    :param log_config:

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

    :param log_stdout:

        Whether the output of ``stdout`` should be recorded into the log files.
        Disable if only logging statement should be recorded. Note if you work with an
        interactive console like *IPython*, it is a good idea to set ``log_stdout=False``
        to avoid messing up the console output.

        Can also be a tuple: ('mylogger', 10), specifying a logger name as well as a log-level.
        The log-level defines with what level `stdout` is logged, it is *not* a filter.

    :param report_progress:

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

    :param multiproc:

        Whether or not to use multiprocessing. Default is ``False``.
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

        If multiproc is ``True``, this specifies the number of processes that will be spawned
        to run your experiment. Note if you use QUEUE mode (see below) the queue process
        is not included in this number and will add another extra process for storing.
        If you have *psutil* installed, you can set `ncores=0` to let *psutil* determine
        the number of CPUs available.

    :param use_scoop:

        If python should be used in a SCOOP_ framework to distribute runs amond a cluster
        or multiple servers. If so you need to start your script via
        ``python -m scoop my_script.py``. Currently, SCOOP_ only works with
        ``'LOCAL'`` ``wrap_mode`` (see below).

        .. _SCOOP: http://scoop.readthedocs.org/

    :param use_pool:

        Whether to use a fixed pool of processes or whether to spawn a new process
        for every run. Use the former if you perform many runs (50k and more)
        which are in terms of memory and runtime inexpensive.
        Be aware that everything you use must be picklable.
        Use the latter for fewer runs (50k and less) and which are longer lasting
        and more expensive runs (in terms of memory consumption).
        In case your operating system allows forking, your data does not need to be
        picklable.
        If you choose ``use_pool=False`` you can also make use of the `cap` values,
        see below.

    :param freeze_input:

        Can be set to ``True`` if the run function as well as all additional arguments
        are immutable. This will prevent the trajectory from getting pickled again and again.
        Thus, the run function, the trajectory, as well as all arguments are passed to the pool
        or SCOOP workers at initialisation. Works also under `run_map`.
        In this case the iterable arguments are, of course, not frozen but passed for every run.

    :param timeout:

        Timeout parameter in seconds passed on to SCOOP_ and ``'NETLOCK'`` wrapping.
        Leave `None` for no timeout. After `timeout` seconds SCOOP_ will assume
        that a single run failed and skip waiting for it.
        Moreover, if using ``'NETLOCK'`` wrapping, after `timeout` seconds
        a lock is automatically released and again
        available for other waiting processes.

    :param cpu_cap:

        If `multiproc=True` and `use_pool=False` you can specify a maximum cpu utilization between
        0.0 (excluded) and 100.0 (included) as fraction of maximum capacity. If the current cpu
        usage is above the specified level (averaged across all cores),
        *pypet* will not spawn a new process and wait until
        activity falls below the threshold again. Note that in order to avoid dead-lock at least
        one process will always be running regardless of the current utilization.
        If the threshold is crossed a warning will be issued. The warning won't be repeated as
        long as the threshold remains crossed.

        For example `cpu_cap=70.0`, `ncores=3`, and currently on average 80 percent of your cpu are
        used. Moreover, let's assume that at the moment only 2 processes are
        computing single runs simultaneously. Due to the usage of 80 percent of your cpu,
        *pypet* will wait until cpu usage drops below (or equal to) 70 percent again
        until it starts a third process to carry out another single run.

        The parameters `memory_cap` and `swap_cap` are analogous. These three thresholds are
        combined to determine whether a new process can be spawned. Accordingly, if only one
        of these thresholds is crossed, no new processes will be spawned.

        To disable the cap limits simply set all three values to 100.0.

        You need the psutil_ package to use this cap feature. If not installed and you
        choose cap values different from 100.0 a ValueError is thrown.

    :param memory_cap:

        Cap value of RAM usage. If more RAM than the threshold is currently in use, no new
        processes are spawned. Can also be a tuple ``(limit, memory_per_process)``,
        first value is the cap value (between 0.0 and 100.0),
        second one is the estimated memory per process in mega bytes (MB).
        If an estimate is given a new process is not started if
        the threshold would be crossed including the estimate.

    :param swap_cap:

        Analogous to `cpu_cap` but the swap memory is considered.

    :param niceness:

        If you are running on a UNIX based system or you have psutil_ (under Windows) installed,
        you can choose a niceness value to prioritize the child processes executing the
        single runs in case you use multiprocessing.
        Under Linux these usually range from 0 (highest priority)
        to 19 (lowest priority). For Windows values check the psutil_ homepage.
        Leave ``None`` if you don't care about niceness.
        Under Linux the `niceness`` value is a minimum value, if the OS decides to
        nice your program (maybe you are running on a server) *pypet* does not try to
        decrease the `niceness` again.

    :param wrap_mode:

         If multiproc is ``True``, specifies how storage to disk is handled via
         the storage service.

         There are a few options:

         :const:`~pypet.pypetconstants.WRAP_MODE_QUEUE`: ('QUEUE')

             Another process for storing the trajectory is spawned. The sub processes
             running the individual single runs will add their results to a
             multiprocessing queue that is handled by an additional process.
             Note that this requires additional memory since the trajectory
             will be pickled and send over the queue for storage!

         :const:`~pypet.pypetconstants.WRAP_MODE_LOCK`: ('LOCK')

             Each individual process takes care about storage by itself. Before
             carrying out the storage, a lock is placed to prevent the other processes
             to store data. Accordingly, sometimes this leads to a lot of processes
             waiting until the lock is released.
             Allows loading of data during runs.

         :const:`~pypet.pypetconstants.WRAP_MODE_PIPE`: ('PIPE)

            Experimental mode based on a single pipe. Is faster than ``'QUEUE'`` wrapping
            but data corruption may occur, does not work under Windows
            (since it relies on forking).

         :const:`~pypet.pypetconstant.WRAP_MODE_LOCAL` ('LOCAL')

            Data is not stored during the single runs but after they completed.
            Storing is only performed in the main process.

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
         :const:`~pypet.pypetconstants.WRAP_MODE_NONE` ('NONE')

    :param queue_maxsize:

        Maximum size of the Storage Queue, in case of ``'QUEUE'`` wrapping.
        ``0`` means infinite, ``-1`` (default) means the educated guess of ``2 * ncores``.

    :param port:

        Port to be used by lock server in case of ``'NETLOCK'`` wrapping.
        Can be a single integer as well as a tuple ``(7777, 9999)`` to specify
        a range of ports from which to pick a random one.
        Leave `None` for using pyzmq's default range.
        In case automatic determining of the host's IP address fails,
        you can also pass the full address (including the protocol and
        the port) of the host in the network like ``'tcp://127.0.0.1:7777'``.

    :param gc_interval:

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

    :param clean_up_runs:

        In case of single core processing, whether all results under groups named `run_XXXXXXXX`
        should be removed after the completion of
        the run. Note in case of multiprocessing this happens anyway since the single run
        container will be destroyed after finishing of the process.

        Moreover, if set to ``True`` after post-processing it is checked if there is still data
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

        In case you use immediate postprocessing, the storage service of your trajectory is still
        multiprocessing safe (except when using the wrap_mode ``'LOCAL'``).
        Accordingly, you could even use multiprocessing in your immediate post-processing phase
        if you dare, like use a multiprocessing pool_, for instance.

        Note that after the execution of the final run, your post-processing routine will
        be called again as usual.

        **IMPORTANT**: If you use immediate post-processing, the results that are passed to
        your post-processing function are not sorted by their run indices but by finishing time!

        .. _pool: https://docs.python.org/2/library/multiprocessing.html

    :param resumable:

        Whether the environment should take special care to allow to resume or continue
        crashed trajectories. Default is ``False``.

        You need to install dill_ to use this feature. *dill* will make snapshots
        of your simulation function as well as the passed arguments.
        BE AWARE that dill is still rather experimental!

        Assume you run experiments that take a lot of time.
        If during your experiments there is a power failure,
        you can resume your trajectory after the last single run that was still
        successfully stored via your storage service.

        The environment will create several `.ecnt` and `.rcnt` files in a folder that you specify
        (see below).
        Using this data you can resume crashed trajectories.

        In order to resume trajectories use :func:`~pypet.environment.Environment.resume`.

        Be aware that your individual single runs must be completely independent of one
        another to allow continuing to work. Thus, they should **NOT** be based on shared data
        that is manipulated during runtime (like a multiprocessing manager list)
        in the positional and keyword arguments passed to the run function.

        If you use post-processing, the expansion of trajectories and continuing of trajectories
        is NOT supported properly. There is no guarantee that both work together.


        .. _dill: https://pypi.python.org/pypi/dill

    :param resume_folder:

        The folder where the resume files will be placed. Note that *pypet* will create
        a sub-folder with the name of the environment.

    :param delete_resume:

        If true, *pypet* will delete the resume files after a successful simulation.

    :param storage_service:

        Pass a given storage service or a class constructor (default ``HDF5StorageService``)
        if you want the environment to create
        the service for you. The environment will pass the
        additional keyword arguments you pass directly to the constructor.
        If the trajectory already has a service attached,
        the one from the trajectory will be used.

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

    :param git_fail:

        If `True` the program fails instead of triggering a commit if there are not committed
        changes found in the code base. In such a case a `GitDiffError` is raised.

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
        If you do not intend to do single runs, than set to ``False`` and the
        environment won't add config information like number of processors to the
        trajectory.

    :param graceful_exit:

        If ``True`` hitting CTRL+C (i.e.sending SIGINT) will not terminate the program
        immediately. Instead, active single runs will be finished and stored before
        shutdown. Hitting CTRL+C twice will raise a KeyboardInterrupt as usual.

    :param lazy_debug:

        If ``lazy_debug=True`` and in case you debug your code (aka you use pydevd and
        the expression ``'pydevd' in sys.modules`` is ``True``), the environment will use the
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
    current *pypet* version.

    The environment will be named `environment_XXXXXXX_XXXX_XX_XX_XXhXXmXXs`. The first seven
    `X` are the first seven characters of the SHA-1 hash code followed by a human readable
    timestamp.

    All information about the environment can be found in your trajectory under
    `config.environment.environment_XXXXXXX_XXXX_XX_XX_XXhXXmXXs`. Your trajectory could
    potentially be run by several environments due to merging or extending an existing trajectory.
    Thus, you will be able to track how your trajectory was built over time.

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

    Moreover, if you use the standard ``HDF5StorageService`` you can pass the following keyword
    arguments in ``**kwargs``:

    :param filename:

        The name of the hdf5 file. If none is specified the default
        `./hdf5/the_name_of_your_trajectory.hdf5` is chosen. If `filename` contains only a path
        like `filename='./myfolder/', it is changed to
        `filename='./myfolder/the_name_of_your_trajectory.hdf5'`.

    :param file_title: Title of the hdf5 file (only important if file is created new)

    :param overwrite_file:

        If the file already exists it will be overwritten. Otherwise,
        the trajectory will simply be added to the file and already
        existing trajectories are **not** deleted.

    :param encoding:

        Format to encode and decode unicode strings stored to disk.
        The default ``'utf8'`` is highly recommended.

    :param complevel:

        You can specify your compression level. 0 means no compression
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

    :param purge_duplicate_comments:

        If you add a result via :func:`~pypet.naturalnaming.ResultGroup.f_add_result` or a derived
        parameter :func:`~pypet.naturalnaming.DerivedParameterGroup.f_add_derived_parameter` and
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
        'results_trajectory', 'results_runs_summary'.

        Note that these tables create some overhead. If you want very small hdf5 files set
        `small_overview_tables` to False.

    :param large_overview_tables:

        Whether to add large overview tables. This encompasses information about every derived
        parameter, result, and the explored parameter in every single run.
        If you want small hdf5 files set to ``False`` (default).

    :param results_per_run:

        Expected results you store per run. If you give a good/correct estimate
        storage to hdf5 file is much faster in case you store LARGE overview tables.

        Default is 0, i.e. the number of results is not estimated!

    :param derived_parameters_per_run:

        Analogous to the above.

    Finally, you can also pass properties of the trajectory, like ``v_with_links=True``
    (you can leave the prefix ``v_``, i.e. ``with_links`` works, too).
    Thus, you can change the settings of the trajectory immediately.

    .. _psutil: http://psutil.readthedocs.org/

    """

    @parse_config
    @kwargs_api_change('delete_continue', 'delete_resume')
    @kwargs_api_change('continue_folder', 'resume_folder')
    @kwargs_api_change('continuable', 'resumable')
    @kwargs_api_change('freeze_pool_input', 'freeze_input')
    @kwargs_api_change('use_hdf5', 'storage_service')
    @kwargs_api_change('dynamically_imported_classes', 'dynamic_imports')
    @kwargs_api_change('pandas_append')
    @simple_logging_config
    def __init__(self, trajectory='trajectory',
                 add_time=False,
                 comment='',
                 dynamic_imports=None,
                 wildcard_functions=None,
                 automatic_storing=True,
                 log_config=pypetconstants.DEFAULT_LOGGING,
                 log_stdout=False,
                 report_progress = (5, 'pypet', logging.INFO),
                 multiproc=False,
                 ncores=1,
                 use_scoop=False,
                 use_pool=False,
                 freeze_input=False,
                 timeout=None,
                 cpu_cap=100.0,
                 memory_cap=100.0,
                 swap_cap=100.0,
                 niceness=None,
                 wrap_mode=pypetconstants.WRAP_MODE_LOCK,
                 queue_maxsize=-1,
                 port=None,
                 gc_interval=None,
                 clean_up_runs=True,
                 immediate_postproc=False,
                 resumable=False,
                 resume_folder=None,
                 delete_resume=True,
                 storage_service=HDF5StorageService,
                 git_repository=None,
                 git_message='',
                 git_fail=False,
                 sumatra_project=None,
                 sumatra_reason='',
                 sumatra_label=None,
                 do_single_runs=True,
                 graceful_exit=False,
                 lazy_debug=False,
                 **kwargs):

        if git_repository is not None and git is None:
            raise ValueError('You cannot specify a git repository without having '
                             'GitPython. Please install the GitPython package to use '
                             'pypet`s git integration.')

        if resumable and dill is None:
            raise ValueError('Please install `dill` if you want to use the feature to '
                             'resume halted trajectories')

        if load_project is None and sumatra_project is not None:
            raise ValueError('`sumatra` package has not been found, either install '
                             '`sumatra` or set `sumatra_project=None`.')

        if sumatra_label is not None and '.' in sumatra_label:
            raise ValueError('Your sumatra label is not allowed to contain dots.')

        if wrap_mode == pypetconstants.WRAP_MODE_NETLOCK and zmq is None:
            raise ValueError('You need to install `zmq` for `NETLOCK` wrapping.')

        if (use_pool or use_scoop) and immediate_postproc:
            raise ValueError('You CANNOT perform immediate post-processing if you DO '
                             'use a pool or scoop.')

        if use_pool and use_scoop:
            raise ValueError('You can either `use_pool` or `use_scoop` or none of both, '
                             'but not both together')

        if use_scoop and scoop is None:
            raise ValueError('Cannot use `scoop` because it is not installed.')

        if (wrap_mode not in (pypetconstants.WRAP_MODE_NONE,
                              pypetconstants.WRAP_MODE_LOCAL,
                              pypetconstants.WRAP_MODE_LOCK,
                              pypetconstants.WRAP_MODE_NETLOCK) and
                                resumable):
            raise ValueError('Continuing trajectories does only work with '
                             '`LOCK`, `NETLOCK` or `LOCAL`wrap mode.')

        if resumable and not automatic_storing:
            raise ValueError('Continuing only works with `automatic_storing=True`')

        if use_scoop and wrap_mode not in (pypetconstants.WRAP_MODE_LOCAL,
                                           pypetconstants.WRAP_MODE_NONE,
                                           pypetconstants.WRAP_MODE_NETLOCK,
                                           pypetconstants.WRAP_MODE_NETQUEUE):
            raise ValueError('SCOOP mode only works with `LOCAL`, `NETLOCK` or '
                             '`NETQUEUE` wrap mode!')

        if niceness is not None and not hasattr(os, 'nice') and psutil is None:
            raise ValueError('You cannot set `niceness` if your operating system does not '
                             'support the `nice` operation. Alternatively you can install '
                             '`psutil`.')

        if freeze_input and not use_pool and not use_scoop:
            raise ValueError('You can only use `freeze_input=True` if you either use '
                             'a pool or SCOOP.')

        if not isinstance(memory_cap, tuple):
            memory_cap = (memory_cap, 0.0)

        if (cpu_cap <= 0.0 or cpu_cap > 100.0 or
            memory_cap[0] <= 0.0 or memory_cap[0] > 100.0 or
                swap_cap <= 0.0 or swap_cap > 100.0):
            raise ValueError('Please choose cap values larger than 0.0 '
                             'and smaller or equal to 100.0.')

        check_usage = cpu_cap < 100.0 or memory_cap[0] < 100.0 or swap_cap < 100.0

        if check_usage and psutil is None:
            raise ValueError('You cannot enable monitoring without having '
                             'installed psutil. Please install psutil or set '
                             'cpu_cap, memory_cap, and swap_cap to 100.0')

        if ncores == 0 and psutil is None:
            raise ValueError('You cannot set `ncores=0` for auto detection of CPUs if you did not '
                             'installed psutil. Please install psutil or '
                             'set `ncores` manually.')

        if port is not None and wrap_mode not in (pypetconstants.WRAP_MODE_NETLOCK,
                                                  pypetconstants.WRAP_MODE_NETQUEUE):
            raise ValueError('You can only specify a port for the `NETLOCK` wrapping.')

        if use_scoop and graceful_exit:
            raise ValueError('You cannot exit gracefully using SCOOP.')

        unused_kwargs = set(kwargs.keys())

        self._logging_manager = LoggingManager(log_config=log_config,
                                               log_stdout=log_stdout,
                                               report_progress=report_progress)
        self._logging_manager.check_log_config()
        self._logging_manager.add_null_handler()
        self._set_logger()

        self._map_arguments = False
        self._stop_iteration = False  # Marker to cancel
        # iteration in case of Keyboard interrupt
        self._graceful_exit = graceful_exit

        # Helper attributes defined later on
        self._start_timestamp = None
        self._finish_timestamp = None
        self._runtime = None

        self._cpu_cap = cpu_cap
        self._memory_cap = memory_cap
        if psutil is not None:
            # Total memory in MB
            self._total_memory = psutil.virtual_memory().total / 1024.0 / 1024.0
            # Estimated memory needed by each process as ratio
            self._est_per_process = self._memory_cap[1] / self._total_memory * 100.0
        self._swap_cap = swap_cap
        self._check_usage = check_usage
        self._last_cpu_check = 0.0
        self._last_cpu_usage = 0.0
        if self._check_usage:
            # For initialisation
            self._estimate_cpu_utilization()
        self._niceness = niceness

        self._sumatra_project = sumatra_project
        self._sumatra_reason = sumatra_reason
        self._sumatra_label = sumatra_label
        self._loaded_sumatatra_project = None
        self._sumatra_record = None

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
        self._git_fail = git_fail

        # Check if a novel trajectory needs to be created.
        if isinstance(trajectory, str):
            # Create a new trajectory
            self._traj = Trajectory(trajectory,
                                    add_time=add_time,
                                    dynamic_imports=dynamic_imports,
                                    wildcard_functions=wildcard_functions,
                                    comment=comment)

            self._timestamp = self.trajectory.v_timestamp  # Timestamp of creation
            self._time = self.trajectory.v_time  # Formatted timestamp
        else:
            self._traj = trajectory
            # If no new trajectory is created the time of the environment differs
            # from the trajectory and must be computed from the current time.
            init_time = time.time()
            formatted_time = format_time(init_time)
            self._timestamp = init_time
            self._time = formatted_time

        # In case the user provided a git repository path, a git commit is performed
        # and the environment's hexsha is taken from the commit if the commit was triggered by
        # this particular environment, otherwise a new one is generated
        if self._git_repository is not None:
            new_commit, self._hexsha = make_git_commit(self, self._git_repository,
                                                       self._git_message, self._git_fail)
            # Identifier hexsha
        else:
            new_commit = False

        if not new_commit:
            # Otherwise we need to create a novel hexsha
            self._hexsha = hashlib.sha1((self.trajectory.v_name +
                                                       str(self.trajectory.v_timestamp) +
                                                       str(self.timestamp) +
                                                           VERSION).encode('utf-8')).hexdigest()

        # Create the name of the environment
        short_hexsha = self._hexsha[0:7]
        name = 'environment'
        self._name = name + '_' + str(short_hexsha) + '_' + self._time  # Name of environment

        # The trajectory should know the hexsha of the current environment.
        # Thus, for all runs, one can identify by which environment they were run.
        self._traj._environment_hexsha = self._hexsha
        self._traj._environment_name = self._name

        self._logging_manager.extract_replacements(self._traj)
        self._logging_manager.remove_null_handler()
        self._logging_manager.make_logging_handlers_and_tools()

        # Drop a message if we made a commit. We cannot drop the message directly after the
        # commit, because the logging files do not exist yet,
        # and we want this commit to be tracked
        if self._git_repository is not None:
            if new_commit:
                self._logger.info('Triggered NEW GIT commit `%s`.' % str(self._hexsha))
            else:
                self._logger.info('No changes detected, added PREVIOUS GIT commit `%s`.' %
                                  str(self._hexsha))

        # Create the storage service
        if storage_service is True: # to allow compatibility with older python versions, i.e. old
            # keyword use_hdf5
            storage_service = HDF5StorageService
        if self._traj.v_storage_service is not None:
            # Use the service of the trajectory
            self._logger.info('Found storage service attached to Trajectory. Will use '
                              'this storage service.')
            self._storage_service = self.trajectory.v_storage_service
        else:
            # Create a new service
            self._storage_service, unused_factory_kwargs = storage_factory(storage_service,
                                                                        self._traj, **kwargs)
            unused_kwargs = unused_kwargs - (set(kwargs.keys()) - unused_factory_kwargs)

        if lazy_debug and is_debug():
            self._storage_service = LazyStorageService()

        self._traj.v_storage_service = self._storage_service

        # Create resume path if desired
        self._resumable = resumable

        if self._resumable:
            if resume_folder is None:
                resume_folder = os.path.join(os.getcwd(), 'resume')
            resume_path = os.path.join(resume_folder, self._traj.v_name)
        else:
            resume_path = None

        self._resume_folder = resume_folder
        self._resume_path = resume_path
        self._delete_resume = delete_resume

        # Check multiproc
        self._multiproc = multiproc
        if ncores == 0:
            # Let *pypet* detect CPU count via psutil
            ncores = psutil.cpu_count()
            self._logger.info('Determined CPUs automatically, found `%d` cores.' % ncores)
        self._ncores = ncores
        if queue_maxsize == -1:
            # Educated guess of queue size
            queue_maxsize = 2 * ncores
        self._queue_maxsize = queue_maxsize
        if wrap_mode is None:
            # None cannot be used in HDF5 files, accordingly we need a string representation
            wrap_mode = pypetconstants.WRAP_MODE_NONE
        self._wrap_mode = wrap_mode
        # Whether to use a pool of processes
        self._use_pool = use_pool
        self._use_scoop = use_scoop
        self._freeze_input = freeze_input
        self._gc_interval = gc_interval
        self._multiproc_wrapper = None # The wrapper Service

        self._do_single_runs = do_single_runs
        self._automatic_storing = automatic_storing
        self._clean_up_runs = clean_up_runs

        if (wrap_mode == pypetconstants.WRAP_MODE_NETLOCK and
                not isinstance(port, str)):
                url = port_to_tcp(port)
                self._logger.info('Determined lock-server URL automatically, it is `%s`.' % url)
        else:
            url = port
        self._url = url
        self._timeout = timeout
        # self._deep_copy_data = False  # deep_copy_data # For future reference deep_copy_arguments

        # Notify that in case of lazy debuggin we won't record anythin
        if lazy_debug and is_debug():
            self._logger.warning('Using the LazyStorageService, nothing will be saved to disk.')

        # Current run index to avoid quadratic runtime complexity in case of re-running
        self._current_idx = 0

        self._trajectory_name = self._traj.v_name
        for kwarg in list(unused_kwargs):
            try:
                val = kwargs[kwarg]
                self._traj.f_set_properties(**{kwarg: val})
                self._logger.info('Set trajectory property `%s` to `%s`.' % (kwarg, str(val)))
                unused_kwargs.remove(kwarg)
            except AttributeError:
                pass
        if len(unused_kwargs) > 0:
            raise ValueError('You passed keyword arguments to the environment that you '
                                 'did not use. The following keyword arguments were ignored: '
                                 '`%s`' % str(unused_kwargs))

        # Add all config data to the environment
        self._add_config()

        self._logger.info('Environment initialized.')

    def _add_config(self):
        # Add config data to the trajectory
        if self._do_single_runs:
            # Only add parameters if we actually want single runs to be performed
            config_name = 'environment.%s.multiproc' % self.name
            self._traj.f_add_config(Parameter, config_name, self._multiproc,
                                    comment='Whether or not to use multiprocessing.').f_lock()

            if self._multiproc:
                config_name = 'environment.%s.use_pool' % self.name
                self._traj.f_add_config(Parameter, config_name, self._use_pool,
                                        comment='Whether to use a pool of processes or '
                                                'spawning individual processes for '
                                                'each run.').f_lock()

                config_name = 'environment.%s.use_scoop' % self.name
                self._traj.f_add_config(Parameter, config_name, self._use_scoop,
                                        comment='Whether to use scoop to launch single '
                                                'runs').f_lock()

                if self._niceness is not None:
                    config_name = 'environment.%s.niceness' % self.name
                    self._traj.f_add_config(Parameter, config_name, self._niceness,
                                        comment='Niceness value of child processes.').f_lock()

                if self._use_pool:
                    config_name = 'environment.%s.freeze_input' % self.name
                    self._traj.f_add_config(Parameter, config_name, self._freeze_input,
                                        comment='If inputs to each run are static and '
                                                'are not mutated during each run, '
                                                'can speed up pool running.').f_lock()

                elif self._use_scoop:
                    pass
                else:
                    config_name = 'environment.%s.cpu_cap' % self.name
                    self._traj.f_add_config(Parameter, config_name, self._cpu_cap,
                                            comment='Maximum cpu usage beyond '
                                                    'which no new processes '
                                                    'are spawned.').f_lock()

                    config_name = 'environment.%s.memory_cap' % self.name
                    self._traj.f_add_config(Parameter, config_name, self._memory_cap,
                                            comment='Tuple, first entry: Maximum RAM usage beyond '
                                                    'which no new processes are spawned; '
                                                    'second entry: Estimated usage per '
                                                    'process in MB. 0 if not estimated.').f_lock()

                    config_name = 'environment.%s.swap_cap' % self.name
                    self._traj.f_add_config(Parameter, config_name, self._swap_cap,
                                            comment='Maximum Swap memory usage beyond '
                                                    'which no new '
                                                    'processes are spawned').f_lock()

                    config_name = 'environment.%s.immediate_postprocessing' % self.name
                    self._traj.f_add_config(Parameter, config_name, self._immediate_postproc,
                                            comment='Whether to use immediate '
                                                    'postprocessing.').f_lock()

                config_name = 'environment.%s.ncores' % self.name
                self._traj.f_add_config(Parameter, config_name, self._ncores,
                                        comment='Number of processors in case of '
                                                'multiprocessing').f_lock()

                config_name = 'environment.%s.wrap_mode' % self.name
                self._traj.f_add_config(Parameter, config_name, self._wrap_mode,
                                        comment='Multiprocessing mode (if multiproc),'
                                                ' i.e. whether to use QUEUE'
                                                ' or LOCK or NONE'
                                                ' for thread/process safe storing').f_lock()

                if (self._wrap_mode == pypetconstants.WRAP_MODE_QUEUE or
                                self._wrap_mode == pypetconstants.WRAP_MODE_PIPE):
                    config_name = 'environment.%s.queue_maxsize' % self.name
                    self._traj.f_add_config(Parameter, config_name, self._queue_maxsize,
                                        comment='Maximum size of Storage Queue/Pipe in case of '
                                                'multiprocessing and QUEUE/PIPE wrapping').f_lock()

                if self._wrap_mode == pypetconstants.WRAP_MODE_NETLOCK:
                    config_name = 'environment.%s.url' % self.name
                    self._traj.f_add_config(Parameter, config_name, self._url,
                                        comment='URL of lock distribution server, including '
                                                'protocol and port.').f_lock()

                if self._wrap_mode == pypetconstants.WRAP_MODE_NETLOCK or self._use_scoop:
                    config_name = 'environment.%s.timeout' % self.name
                    timeout = self._timeout
                    if timeout is None:
                        timeout = -1.0
                    self._traj.f_add_config(Parameter, config_name, timeout,
                                        comment='Timout for scoop and NETLOCK, '
                                                '-1.0 means no timeout.').f_lock()

                if (self._gc_interval and
                        (self._wrap_mode == pypetconstants.WRAP_MODE_LOCAL or
                            self._wrap_mode == pypetconstants.WRAP_MODE_QUEUE or
                                self._wrap_mode == pypetconstants.WRAP_MODE_PIPE)):
                    config_name = 'environment.%s.gc_interval' % self.name
                    self._traj.f_add_config(Parameter, config_name, self._gc_interval,
                                        comment='Intervals with which ``gc.collect()`` '
                                                'is called.').f_lock()


            config_name = 'environment.%s.clean_up_runs' % self._name
            self._traj.f_add_config(Parameter, config_name, self._clean_up_runs,
                                    comment='Whether or not results should be removed after the '
                                            'completion of a single run. '
                                            'You are not advised to set this '
                                            'to `False`. Only do it if you know what you are '
                                            'doing.').f_lock()

            config_name = 'environment.%s.resumable' % self._name
            self._traj.f_add_config(Parameter, config_name, self._resumable,
                                    comment='Whether or not resume files should '
                                            'be created. If yes, everything is '
                                            'handled by `dill`.').f_lock()

            config_name = 'environment.%s.graceful_exit' % self._name
            self._traj.f_add_config(Parameter, config_name, self._graceful_exit,
                                    comment='Whether or not to allow graceful handling '
                                            'of `SIGINT` (`CTRL+C`).').f_lock()

        config_name = 'environment.%s.trajectory.name' % self.name
        self._traj.f_add_config(Parameter, config_name, self.trajectory.v_name,
                                comment='Name of trajectory').f_lock()

        config_name = 'environment.%s.trajectory.timestamp' % self.name
        self._traj.f_add_config(Parameter, config_name, self.trajectory.v_timestamp,
                                comment='Timestamp of trajectory').f_lock()

        config_name = 'environment.%s.timestamp' % self.name
        self._traj.f_add_config(Parameter, config_name, self.timestamp,
                                comment='Timestamp of environment creation').f_lock()

        config_name = 'environment.%s.hexsha' % self.name
        self._traj.f_add_config(Parameter, config_name, self.hexsha,
                                comment='SHA-1 identifier of the environment').f_lock()

        config_name = 'environment.%s.automatic_storing' % self.name
        if not self._traj.f_contains('config.' + config_name):
            self._traj.f_add_config(Parameter, config_name, self._automatic_storing,
                                    comment='If trajectory should be stored automatically in the '
                                            'end.').f_lock()

        try:
            config_name = 'environment.%s.script' % self.name
            self._traj.f_add_config(Parameter, config_name, main.__file__,
                                    comment='Name of the executed main script').f_lock()
        except AttributeError:
            pass  # We end up here if we use pypet within an ipython console

        for package_name, version in pypetconstants.VERSIONS_TO_STORE.items():
            config_name = 'environment.%s.versions.%s' % (self.name, package_name)
            self._traj.f_add_config(Parameter, config_name, version,
                                    comment='Particular version of a package or distribution '
                                            'used during experiment. N/A if package could not '
                                            'be imported.').f_lock()

        self._traj.config.environment.v_comment = 'Settings for the different environments ' \
                                                  'used to run the experiments'

    def __repr__(self):
        """String representation of environment"""
        repr_string = '<%s %s for Trajectory %s>' % (self.__class__.__name__, self.name,
                                          self.trajectory.v_name)
        return repr_string

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disable_logging()

    def disable_logging(self, remove_all_handlers=True):
        """Removes all logging handlers and stops logging to files and logging stdout.

        :param remove_all_handlers:

            If `True` all logging handlers are removed.
            If you want to keep the handlers set to `False`.

        """
        self._logging_manager.finalize(remove_all_handlers)

    @kwargs_api_change('continue_folder', 'resume_folder')
    def resume(self, trajectory_name=None, resume_folder=None):
        """Resumes crashed trajectories.

        :param trajectory_name:

            Name of trajectory to resume, if not specified the name passed to the environment
            is used. Be aware that if `add_time=True` the name you passed to the environment is
            altered and the current date is added.

        :param resume_folder:

            The folder where resume files can be found. Do not pass the name of the sub-folder
            with the trajectory name, but to the name of the parental folder.
            If not specified the resume folder passed to the environment is used.

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
            self._trajectory_name = self.trajectory.v_name
        else:
            self._trajectory_name = trajectory_name

        if resume_folder is not None:
            self._resume_folder = resume_folder

        return self._execute_runs(None)

    @property
    def trajectory(self):
        """ The trajectory of the Environment"""
        return self._traj

    @property
    def traj(self):
        """ Equivalent to env.trajectory"""
        return self.trajectory

    @property
    def current_idx(self):
        """The current run index that is the next one to be executed.

        Can be set manually to make the environment consider old non-completed ones.

        """
        return self._current_idx

    @current_idx.setter
    def current_idx(self, idx):
        self._current_idx = idx

    @property
    def hexsha(self):
        """The SHA1 identifier of the environment.

        It is identical to the SHA1 of the git commit.
        If version control is not used, the environment hash is computed from the
        trajectory name, the current timestamp and your current *pypet* version."""
        return self._hexsha

    @property
    def time(self):
        """ Time of the creation of the environment, human readable."""
        return self._time

    @property
    def timestamp(self):
        """Time of creation as python datetime float"""
        return self._timestamp

    @property
    def name(self):
        """ Name of the Environment"""
        return self._name

    def add_postprocessing(self, postproc, *args, **kwargs):
        """ Adds a post processing function.

        The environment will call this function via
        ``postproc(traj, result_list, *args, **kwargs)`` after the completion of the
        single runs.

        This function can load parts of the trajectory id needed and add additional results.

        Moreover, the function can be used to trigger an expansion of the trajectory.
        This can be useful if the user has an `optimization` task.

        Either the function calls `f_expand` directly on the trajectory or returns
        an dictionary. If latter `f_expand` is called by the environment.

        Note that after expansion of the trajectory, the post-processing function is called
        again (and again for further expansions). Thus, this allows an iterative approach
        to parameter exploration.

        Note that in case post-processing is called after all runs have been executed,
        the storage service of the trajectory is no longer multiprocessing safe.
        If you want to use multiprocessing in your post-processing you can still
        manually wrap the storage service with the :class:`~pypet.environment.MultiprocessWrapper`.

        In case you use **immediate** postprocessing, the storage service of your trajectory
        is still multiprocessing safe (except when using the wrap_mode ``'LOCAL'``).
        Accordingly, you could even use multiprocessing in your immediate post-processing phase
        if you dare, like use a multiprocessing pool_, for instance.

        You can easily check in your post-processing function if the storage service is
        multiprocessing safe via the ``multiproc_safe`` attribute, i.e.
        ``traj.v_storage_service.multiproc_safe``.

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

    def pipeline(self, pipeline):
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
        self._map_arguments = False
        return self._execute_runs(pipeline)

    def pipeline_map(self, pipeline):
        """Creates a pipeline with iterable arguments"""
        self._user_pipeline = True
        self._map_arguments = True
        return self._execute_runs(pipeline)

    def run(self, runfunc, *args, **kwargs):
        """ Runs the experiments and explores the parameter space.

        :param runfunc: The task or job to do

        :param args: Additional arguments (not the ones in the trajectory) passed to `runfunc`

        :param kwargs:

            Additional keyword arguments (not the ones in the trajectory) passed to `runfunc`

        :return:

            List of the individual results returned by `runfunc`.

            Returns a LIST OF TUPLES, where first entry is the run idx and second entry
            is the actual result. They are always ordered according to the run index.

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
        self._map_arguments = False
        return self._execute_runs(pipeline)

    def run_map(self, runfunc, *iter_args, **iter_kwargs):
        """Calls runfunc with different args and kwargs each time.

        Similar to `:func:`~pypet.environment.Environment.run`
        but all ``iter_args`` and ``iter_kwargs`` need to be iterables,
        iterators, or generators that return new arguments for each run.

        """
        if len(iter_args) == 0 and len(iter_kwargs) == 0:
            raise ValueError('Use `run` if you don`t have any other arguments.')
        pipeline = lambda traj: ((runfunc, iter_args, iter_kwargs),
                                 (self._postproc, self._postproc_args, self._postproc_kwargs))

        self._user_pipeline = False
        self._map_arguments = True
        return self._execute_runs(pipeline)

    def _trigger_resume_snapshot(self):
        """ Makes the trajectory continuable in case the user wants that"""
        dump_dict = {}
        dump_filename = os.path.join(self._resume_path, 'environment.ecnt')

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
        """ Prepares a sumatra record """
        reason = self._sumatra_reason
        if reason:
            reason += ' -- '

        if self._traj.v_comment:
            commentstr = ' (`%s`)' % self._traj.v_comment
        else:
            commentstr = ''

        reason += 'Trajectory %s%s -- Explored Parameters: %s' % \
                  (self._traj.v_name,
                   commentstr,
                   str(list(self._traj._explored_parameters.keys())))

        self._logger.info('Preparing sumatra record with reason: %s' % reason)
        self._sumatra_reason = reason
        self._loaded_sumatatra_project = load_project(self._sumatra_project)

        if self._traj.f_contains('parameters', shortcuts=False):
            param_dict = self._traj.parameters.f_to_dict(fast_access=False)

            for param_name in list(param_dict.keys()):
                param = param_dict[param_name]
                if param.f_has_range():
                    param_dict[param_name] = param.f_get_range()
                else:
                    param_dict[param_name] = param.f_get()
        else:
            param_dict = {}

        relpath = os.path.relpath(sys.modules['__main__'].__file__, self._sumatra_project)

        executable = PythonExecutable(path=sys.executable)

        self._sumatra_record = self._loaded_sumatatra_project.new_record(
            parameters=param_dict,
            main_file=relpath,
            executable=executable,
            label=self._sumatra_label,
            reason=reason)

    def _finish_sumatra(self):
        """ Saves a sumatra record """

        finish_time = self._start_timestamp - self._finish_timestamp
        self._sumatra_record.duration = finish_time
        self._sumatra_record.output_data = self._sumatra_record.datastore.find_new_data(
                                                                self._sumatra_record.timestamp)
        self._loaded_sumatatra_project.add_record(self._sumatra_record)
        self._loaded_sumatatra_project.save()
        sumatra_label = self._sumatra_record.label

        config_name = 'sumatra.record_%s.label' % str(sumatra_label)
        conf_list = []
        if not self._traj.f_contains('config.' + config_name):
            conf1 = self._traj.f_add_config(Parameter, config_name, str(sumatra_label),
                                    comment='The label of the sumatra record')
            conf_list.append(conf1)

        if self._sumatra_reason:
            config_name = 'sumatra.record_%s.reason' % str(sumatra_label)
            if not self._traj.f_contains('config.' + config_name):
                conf2 = self._traj.f_add_config(Parameter, config_name,
                                                str(self._sumatra_reason),
                                                comment='Reason of sumatra run.')
                conf_list.append(conf2)

        if self._automatic_storing and conf_list:
            self._traj.f_store_items(conf_list)

        self._logger.info('Saved sumatra project record with reason: '
                          '%s' % str(self._sumatra_reason))

    def _prepare_resume(self):
        """ Prepares the continuation of a crashed trajectory """
        if not self._resumable:
            raise RuntimeError('If you create an environment to resume a run, you need to '
                               'set `continuable=True`.')

        if not self._do_single_runs:
            raise RuntimeError('You cannot resume a run if you did create an environment '
                               'with `do_single_runs=False`.')

        self._resume_path = os.path.join(self._resume_folder, self._trajectory_name)
        cnt_filename = os.path.join(self._resume_path, 'environment.ecnt')
        cnt_file = open(cnt_filename, 'rb')
        resume_dict = dill.load(cnt_file)
        cnt_file.close()
        traj = resume_dict['trajectory']

        # We need to update the information about the trajectory name
        config_name = 'config.environment.%s.trajectory.name' % self.name
        if self._traj.f_contains(config_name, shortcuts=False):
            param = self._traj.f_get(config_name, shortcuts=False)
            param.f_unlock()
            param.f_set(traj.v_name)
            param.f_lock()

        config_name = 'config.environment.%s.trajectory.timestamp' % self.name
        if self._traj.f_contains(config_name, shortcuts=False):
            param = self._traj.f_get(config_name, shortcuts=False)
            param.f_unlock()
            param.f_set(traj.v_timestamp)
            param.f_lock()

        # Merge the information so that we keep a record about the current environment
        if not traj.config.environment.f_contains(self.name, shortcuts=False):
            traj._merge_config(self._traj)
        self._traj = traj

        # User's job function
        self._runfunc = resume_dict['runfunc']
        # Arguments to the user's job function
        self._args = resume_dict['args']
        # Keyword arguments to the user's job function
        self._kwargs = resume_dict['kwargs']
        # Postproc Function
        self._postproc = resume_dict['postproc']
        # Postprog args
        self._postproc_args = resume_dict['postproc_args']
        # Postproc Kwargs
        self._postproc_kwargs = resume_dict['postproc_kwargs']

        # Unpack the trajectory
        self._traj.v_full_copy = resume_dict['full_copy']
        # Load meta data
        self._traj.f_load(load_parameters=pypetconstants.LOAD_NOTHING,
                          load_derived_parameters=pypetconstants.LOAD_NOTHING,
                          load_results=pypetconstants.LOAD_NOTHING,
                          load_other_data=pypetconstants.LOAD_NOTHING)

        # Now we have to reconstruct previous results
        result_list = []
        full_filename_list = []
        for filename in os.listdir(self._resume_path):
            _, ext = os.path.splitext(filename)

            if ext != '.rcnt':
                continue

            full_filename = os.path.join(self._resume_path, filename)
            cnt_file = open(full_filename, 'rb')
            result_list.append(dill.load(cnt_file))
            cnt_file.close()
            full_filename_list.append(full_filename)

        new_result_list = []
        for result_tuple in result_list:
            run_information = result_tuple[1]
            self._traj._update_run_information(run_information)
            new_result_list.append(result_tuple[0])
        result_sort(new_result_list)

        # Add a config parameter signalling that an experiment was resumed, and how many of them
        config_name = 'environment.%s.resumed' % self.name
        if not config_name in self._traj:
            self._traj.f_add_config(Parameter, config_name, True,
                                    comment='Added if a crashed trajectory was continued.')

        self._logger.info('I will resume trajectory `%s`.' % self._traj.v_name)

        return new_result_list

    def _prepare_runs(self, pipeline):
        """Prepares the running of an experiment

        :param pipeline:

            A pipeline function that defines the task

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
            # Extract the run and post-processing functions and arguments
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

        if self._resumable:
            racedirs(self._resume_path)
            if os.listdir(self._resume_path):
                raise RuntimeError('Your resume folder `%s` needs '
                                   'to be empty to allow continuing!' % self._resume_path)

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

    def _show_progress(self, n, total_runs):
        """Displays a progressbar"""
        self._logging_manager.show_progress(n, total_runs)

    def _make_kwargs(self, **kwargs):
        """Creates the keyword arguments for the single run handling"""
        result_dict = {'traj': self._traj,
                       'logging_manager': self._logging_manager,
                       'runfunc': self._runfunc,
                       'runargs': self._args,
                       'runkwargs': self._kwargs,
                       'clean_up_runs': self._clean_up_runs,
                       'automatic_storing': self._automatic_storing,
                       'wrap_mode': self._wrap_mode,
                       'niceness': self._niceness,
                       'graceful_exit': self._graceful_exit}
        result_dict.update(kwargs)
        if self._multiproc:
            if self._use_pool or self._use_scoop:
                if self._use_scoop:
                    del result_dict['graceful_exit']
                if self._freeze_input:
                    # Remember the full copy setting for the frozen input to
                    # change this back once the trajectory is received by
                    # each process
                    result_dict['full_copy'] = self.traj.v_full_copy
                    if self._map_arguments:
                        del result_dict['runargs']
                        del result_dict['runkwargs']
                else:
                    result_dict['clean_up_runs'] = False
                    if self._use_pool:
                        # Needs only be deleted in case of using a pool but necessary for scoop
                        del result_dict['logging_manager']
                        del result_dict['niceness']
            else:
                result_dict['clean_up_runs'] = False
        return result_dict

    def _make_index_iterator(self, start_run_idx):
        """Returns an iterator over the run indices that are not completed"""
        total_runs = len(self._traj)
        for n in range(start_run_idx, total_runs):
            self._current_idx = n + 1
            if self._stop_iteration:
                self._logger.debug('I am stopping new run iterations now!')
                break
            if not self._traj._is_completed(n):
                self._traj.f_set_crun(n)
                yield n
            else:
                self._logger.debug('Run `%d` has already been completed, I am skipping it.' % n)

    def _make_iterator(self, start_run_idx, copy_data=False, **kwargs):
        """ Returns an iterator over all runs and yields the keyword arguments """
        if (not self._freeze_input) or (not self._multiproc):
            kwargs = self._make_kwargs(**kwargs)

        def _do_iter():
            if self._map_arguments:

                self._args = tuple(iter(arg) for arg in self._args)
                for key in list(self._kwargs.keys()):
                    self._kwargs[key] = iter(self._kwargs[key])

                for idx in self._make_index_iterator(start_run_idx):
                    iter_args = tuple(next(x) for x in self._args)
                    iter_kwargs = {}
                    for key in self._kwargs:
                        iter_kwargs[key] = next(self._kwargs[key])
                    kwargs['runargs'] = iter_args
                    kwargs['runkwargs'] = iter_kwargs
                    if self._freeze_input:
                        # Frozen pool needs current run index
                        kwargs['idx'] = idx
                    if copy_data:
                        copied_kwargs = kwargs.copy()
                        if not self._freeze_input:
                            copied_kwargs['traj'] = self._traj.f_copy(copy_leaves='explored',
                                                                  with_links=True)
                        yield copied_kwargs
                    else:
                        yield kwargs
            else:
                for idx in self._make_index_iterator(start_run_idx):
                    if self._freeze_input:
                        # Frozen pool needs current run index
                        kwargs['idx'] = idx
                    if copy_data:
                        copied_kwargs = kwargs.copy()
                        if not self._freeze_input:
                            copied_kwargs['traj'] = self._traj.f_copy(copy_leaves='explored',
                                                                  with_links=True)
                        yield copied_kwargs
                    else:
                        yield kwargs
        return _do_iter()

    def _execute_postproc(self, results):
        """ Executes a postprocessing function

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

        # Do some finalization
        self._traj._finalize(store_meta_data=True)

        old_traj_length = len(self._traj)
        postproc_res = self._postproc(self._traj, results,
                                      *self._postproc_args, **self._postproc_kwargs)

        if postproc_res is None:
            pass
        elif isinstance(postproc_res, dict):
            if postproc_res:
                self._traj.f_expand(postproc_res)
        elif isinstance(postproc_res, tuple):
            expand_dict = postproc_res[0]
            if len(postproc_res) > 1:
                self._args = postproc_res[1]
            if len(postproc_res) > 2:
                self._kwargs = postproc_res[2]
            if len(postproc_res) > 3:
                self._postproc_args = postproc_res[3]
            if len(postproc_res) > 4:
                self._postproc_kwargs = postproc_res[4]
            if expand_dict:
                self._traj.f_expand(expand_dict)
        else:
            self._logger.error('Your postproc result `%s` was not understood.' % str(postproc_res))

        new_traj_length = len(self._traj)

        if new_traj_length != old_traj_length:
            start_run_idx = old_traj_length
            repeat = True

            if self._resumable:
                self._logger.warning('Continuing a trajectory AND expanding it during runtime is '
                                     'NOT supported properly, there is no guarantee that this '
                                     'works!')

            self._traj.f_store(only_init=True)

            new_traj_length = len(self._traj)
            new_runs = new_traj_length - old_traj_length

        return repeat, start_run_idx, new_runs

    def _estimate_cpu_utilization(self):
        """Estimates the cpu utilization within the last 500ms"""
        now = time.time()
        if now - self._last_cpu_check >= 0.5:
            try:
                self._last_cpu_usage = psutil.cpu_percent()
                self._last_cpu_check = now
            except (psutil.NoSuchProcess, ZeroDivisionError):
                pass  # psutil sometimes produces ZeroDivisionErrors, has been fixed in newer
                # Versions but we want to support older as well
        return self._last_cpu_usage

    def _estimate_memory_utilization(self, process_dict):
        """Estimates memory utilization to come if process was started"""
        n_processes = len(process_dict)
        total_utilization = psutil.virtual_memory().percent
        sum = 0.0
        for proc in process_dict.values():
            try:
                sum += psutil.Process(proc.pid).memory_percent()
            except (psutil.NoSuchProcess, ZeroDivisionError):
                pass
        curr_all_processes = sum
        missing_utilization = max(0.0, n_processes * self._est_per_process - curr_all_processes)
        estimated_utilization = total_utilization
        estimated_utilization += missing_utilization
        estimated_utilization += self._est_per_process
        return estimated_utilization

    def _execute_runs(self, pipeline):
        """ Starts the individual single runs.

        Starts runs sequentially or initiates multiprocessing.

        :param pipeline:

            A pipeline function producing the run function the corresponding arguments
            and postprocessing function and arguments

        :return:

            List of tuples, where each tuple contains the run idx and the result.

        """
        if self._start_timestamp is None:
            self._start_timestamp = time.time()

        if self._map_arguments and self._resumable:
            raise ValueError('You cannot use `run_map` or `pipeline_map` in combination '
                             'with continuing option.')

        if self._sumatra_project is not None:
            self._prepare_sumatra()

        if pipeline is not None:
            results = []
            self._prepare_runs(pipeline)
        else:
            results = self._prepare_resume()

        if self._runfunc is not None:
            self._traj._run_by_environment = True
            if self._graceful_exit:
                sigint_handling.start()
            try:
                self._inner_run_loop(results)
            finally:
                self._traj._run_by_environment = False
                self._stop_iteration = False
                if self._graceful_exit:
                    sigint_handling.finalize()

        self._add_wildcard_config()

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
        config_name = 'environment.%s.start_timestamp' % self.name
        if not self._traj.f_contains('config.' + config_name):
            conf1 = self._traj.f_add_config(Parameter, config_name, self._start_timestamp,
                                    comment='Timestamp of starting of experiment '
                                            '(when the actual simulation was '
                                            'started (either by calling `run`, '
                                            '`resume`, or `pipeline`).')
            conf_list.append(conf1)

        config_name = 'environment.%s.finish_timestamp' % self.name
        if not self._traj.f_contains('config.' + config_name):
            conf2 = self._traj.f_add_config(Parameter, config_name, self._finish_timestamp,
                                            comment='Timestamp of finishing of an experiment.')
        else:
            conf2 = self._traj.f_get('config.' + config_name)
            conf2.f_unlock()
            conf2.f_set(self._finish_timestamp)
        conf_list.append(conf2)

        config_name = 'environment.%s.runtime' % self.name
        if not self._traj.f_contains('config.' + config_name):
            conf3 = self._traj.f_add_config(Parameter, config_name, self._runtime,
                                            comment='Runtime of whole experiment.')
        else:
            conf3 = self._traj.f_get('config.' + config_name)
            conf3.f_unlock()
            conf3.f_set(self._runtime)
        conf_list.append(conf3)

        if self._automatic_storing:
            self._traj.f_store_items(conf_list, store_data=pypetconstants.OVERWRITE_DATA)

        if hasattr(self._traj.v_storage_service, 'finalize'):
            # Finalize the storage service if this is supported
            self._traj.v_storage_service.finalize()

        incomplete = []
        for run_name in self._traj.f_get_run_names():
            if not self._traj._is_completed(run_name):
                incomplete.append(run_name)
        if len(incomplete) > 0:
            self._logger.error('Following runs of trajectory `%s` '
                               'did NOT complete: `%s`' % (self._traj.v_name,
                                                           ', '.join(incomplete)))
        else:
            self._logger.info('All runs of trajectory `%s` were completed successfully.' %
                              self._traj.v_name)

        if self._sumatra_project is not None:
            self._finish_sumatra()

        return results

    def _add_wildcard_config(self):
        """Adds config data about the wildcard functions"""
        for idx, pair in enumerate(self._traj._wildcard_functions.items()):
            wildcards, wc_function = pair
            for jdx, wildcard in enumerate(wildcards):
                config_name = ('environment.%s.wildcards.function_%d.wildcard_%d' %
                                (self.name, idx, jdx))
                if not self._traj.f_contains('config.' + config_name):
                    self._traj.f_add_config(Parameter, config_name, wildcard,
                                    comment='Wildcard symbol for the wildcard function').f_lock()
            if hasattr(wc_function, '__name__'):
                config_name = ('environment.%s.wildcards.function_%d.name' %
                                (self.name, idx))
                if not self._traj.f_contains('config.' + config_name):
                    self._traj.f_add_config(Parameter, config_name, wc_function.__name__,
                                    comment='Nme of wildcard function').f_lock()
            if wc_function.__doc__:
                config_name = ('environment.%s.wildcards.function_%d.doc' %
                                (self.name, idx))
                if not self._traj.f_contains('config.' + config_name):
                    self._traj.f_add_config(Parameter, config_name, wc_function.__doc__,
                                    comment='Docstring of wildcard function').f_lock()
            try:
                source = inspect.getsource(wc_function)
                config_name = ('environment.%s.wildcards.function_%d.source' %
                            (self.name, idx))
                if not self._traj.f_contains('config.' + config_name):
                    self._traj.f_add_config(Parameter, config_name, source,
                                comment='Source code of wildcard function').f_lock()
            except Exception:
                pass  # We cannot find the source, just leave it

    def _inner_run_loop(self, results):
        """Performs the inner loop of the run execution"""
        start_run_idx = self._current_idx
        expanded_by_postproc = False

        self._storage_service = self._traj.v_storage_service
        self._multiproc_wrapper = None

        if self._resumable:
            self._trigger_resume_snapshot()

        self._logger.info(
            '\n************************************************************\n'
            'STARTING runs of trajectory\n`%s`.'
            '\n************************************************************\n' %
            self._traj.v_name)

        while True:

            if self._multiproc:
                expanded_by_postproc = self._execute_multiprocessing(start_run_idx, results)
            else:
                # Create a generator to generate the tasks
                iterator = self._make_iterator(start_run_idx)

                n = start_run_idx
                total_runs = len(self._traj)
                # Signal start of progress calculation
                self._show_progress(n - 1, total_runs)
                for task in iterator:
                    result = _sigint_handling_single_run(task)
                    n = self._check_result_and_store_references(result, results,
                                                                        n, total_runs)

            repeat = False
            if self._postproc is not None:
                self._logger.info('Performing POSTPROCESSING')

                repeat, start_run_idx, new_runs = self._execute_postproc(results)

            if not repeat:
                break
            else:
                expanded_by_postproc = True
                self._logger.info('POSTPROCESSING expanded the trajectory and added %d new runs' %
                                  new_runs)

        # Do some finalization
        self._traj._finalize(store_meta_data=True)

        self._logger.info(
                    '\n************************************************************\n'
                    'FINISHED all runs of trajectory\n`%s`.'
                    '\n************************************************************\n' %
                    self._traj.v_name)

        if self._resumable and self._delete_resume:
            # We remove all resume files if the simulation was successfully completed
            shutil.rmtree(self._resume_path)

        if expanded_by_postproc:
            config_name = 'environment.%s.postproc_expand' % self.name
            if not self._traj.f_contains('config.' + config_name):
                self._traj.f_add_config(Parameter, config_name, True,
                                        comment='Added if trajectory was expanded '
                                                'by postprocessing.')

    def _get_results_from_queue(self, result_queue, results, n, total_runs):
        """Extract all available results from the queue and returns the increased n"""
        # Get all results from the result queue
        while not result_queue.empty():
            result = result_queue.get()
            n = self._check_result_and_store_references(result, results, n, total_runs)
        return n

    def _check_result_and_store_references(self, result, results, n, total_runs):
        """Checks for SIGINT and if reference wrapping and stores references."""
        if result[0] == sigint_handling.SIGINT:
            self._stop_iteration = True
            result = result[1]  # If SIGINT result is a nested tuple
        if result is not None:
            if self._wrap_mode == pypetconstants.WRAP_MODE_LOCAL:
                self._multiproc_wrapper.store_references(result[2])
            self._traj._update_run_information(result[1])
            results.append(result[0])
            if self._resumable:
                # [0:2] to not store references
                self._trigger_result_snapshot(result[0:2])
        self._show_progress(n, total_runs)
        n += 1
        return n

    def _trigger_result_snapshot(self, result):
        """ Triggers a snapshot of the results for continuing

        :param result: Currently computed result

        """
        timestamp = result[1]['finish_timestamp']
        timestamp_str = repr(timestamp).replace('.', '_')
        filename = 'result_%s' % timestamp_str
        extension = '.ncnt'
        dump_filename = os.path.join(self._resume_path, filename + extension)

        dump_file = open(dump_filename, 'wb')
        dill.dump(result, dump_file, protocol=2)
        dump_file.flush()
        dump_file.close()

        # We rename the file to be certain that the trajectory did not crash during taking
        # the snapshot!
        extension = '.rcnt'
        rename_filename = os.path.join(self._resume_path, filename + extension)
        shutil.move(dump_filename, rename_filename)

    def _execute_multiprocessing(self, start_run_idx, results):
        """Performs multiprocessing and signals expansion by postproc"""
        n = start_run_idx
        total_runs = len(self._traj)
        expanded_by_postproc = False

        if (self._wrap_mode == pypetconstants.WRAP_MODE_NONE or
                self._storage_service.multiproc_safe):
            self._logger.info('I assume that your storage service is multiprocessing safe.')
        else:
            use_manager = (self._wrap_mode == pypetconstants.WRAP_MODE_QUEUE or
                           self._immediate_postproc)

            self._multiproc_wrapper = MultiprocContext(self._traj,
                               self._wrap_mode,
                               full_copy=None,
                               manager=None,
                               use_manager=use_manager,
                               lock=None,
                               queue=None,
                               queue_maxsize=self._queue_maxsize,
                               port=self._url,
                               timeout=self._timeout,
                               gc_interval=self._gc_interval,
                               log_config=self._logging_manager.log_config,
                               log_stdout=self._logging_manager.log_stdout,
                               graceful_exit=self._graceful_exit)

            self._multiproc_wrapper.start()
        try:

            if self._use_pool:

                self._logger.info('Starting Pool with %d processes' % self._ncores)

                if self._freeze_input:
                    self._logger.info('Freezing pool input')

                    init_kwargs = self._make_kwargs()

                    # To work under windows we must allow the full-copy now!
                    # Because windows does not support forking!
                    pool_full_copy = self._traj.v_full_copy
                    self._traj.v_full_copy = True

                    initializer = _configure_frozen_pool
                    target = _frozen_pool_single_run
                else:
                    # We don't want to pickle the storage service
                    pool_service = self._traj.v_storage_service
                    self._traj.v_storage_service = None

                    init_kwargs = dict(logging_manager=self._logging_manager,
                                       storage_service=pool_service,
                                       niceness=self._niceness)
                    initializer = _configure_pool
                    target = _pool_single_run

                try:
                    iterator = self._make_iterator(start_run_idx)
                    mpool = multip.Pool(self._ncores, initializer=initializer,
                                        initargs=(init_kwargs,))
                    pool_results = mpool.imap(target, iterator)

                    # Signal start of progress calculation
                    self._show_progress(n - 1, total_runs)
                    for result in pool_results:
                        n = self._check_result_and_store_references(result, results,
                                                                    n, total_runs)

                    # Everything is done
                    mpool.close()
                    mpool.join()
                finally:
                    if self._freeze_input:
                        self._traj.v_full_copy = pool_full_copy
                    else:
                        self._traj.v_storage_service = pool_service


                self._logger.info('Pool has joined, will delete it.')
                del mpool
            elif self._use_scoop:
                self._logger.info('Starting SCOOP jobs')

                if self._freeze_input:
                    self._logger.info('Freezing SCOOP input')

                    if not hasattr(_frozen_scoop_single_run, 'kwargs'):
                        _frozen_scoop_single_run.kwargs = {}

                    scoop_full_copy = self._traj.v_full_copy
                    self._traj.v_full_copy = True
                    init_kwargs = self._make_kwargs()

                    scoop_rev = self.name + '_' + str(time.time()).replace('.','_')
                    shared.setConst(**{scoop_rev: init_kwargs})

                    iterator = self._make_iterator(start_run_idx,
                                                   copy_data=True,
                                                   scoop_rev=scoop_rev)

                    target = _frozen_scoop_single_run
                else:
                    iterator = self._make_iterator(start_run_idx,
                                                   copy_data=True)
                    target = _scoop_single_run

                try:
                    if scoop.IS_RUNNING:
                        scoop_results = futures.map(target, iterator, timeout=self._timeout)
                    else:
                        self._logger.error('SCOOP is NOT running, I will use Python`s map '
                                             'function. To activate scoop, start your script via '
                                             '`python -m scoop your_script.py`.')
                        scoop_results = map(target, iterator)

                    # Signal start of progress calculation
                    self._show_progress(n - 1, total_runs)
                    for result in scoop_results:
                        n = self._check_result_and_store_references(result, results,
                                                                    n, total_runs)
                finally:
                    if self._freeze_input:
                        self._traj.v_full_copy = scoop_full_copy
            else:
                # If we spawn a single process for each run, we need an additional queue
                # for the results of `runfunc`
                if self._immediate_postproc:
                    maxsize = 0
                else:
                    maxsize = total_runs

                start_result_length = len(results)
                result_queue = multip.Queue(maxsize=maxsize)

                # Create a generator to generate the tasks for multiprocessing
                iterator = self._make_iterator(start_run_idx, result_queue=result_queue)

                self._logger.info('Starting multiprocessing with at most '
                                  '%d processes running at the same time.' % self._ncores)

                if self._check_usage:
                    self._logger.info(
                        'Monitoring usage statistics. I will not spawn new processes '
                        'if one of the following cap thresholds is crossed, '
                        'CPU: %.1f %%, RAM: %.1f %%, Swap: %.1f %%.' %
                        (self._cpu_cap, self._memory_cap[0], self._swap_cap))


                keep_running = True  # Evaluates to false if trajectory produces
                # no more single runs
                process_dict = {}  # Dict containing all subprocees

                # For the cap values, we lazily evaluate them
                cpu_usage_func = lambda: self._estimate_cpu_utilization()
                memory_usage_func = lambda: self._estimate_memory_utilization(process_dict)
                swap_usage_func = lambda: psutil.swap_memory().percent
                signal_cap = True  # If True cap warning is emitted
                max_signals = 10  # Maximum number of warnings, after that warnings are
                # no longer signaled

                # Signal start of progress calculation
                self._show_progress(n - 1, total_runs)

                while len(process_dict) > 0 or keep_running:
                    # First check if some processes did finish their job
                    for pid in list(process_dict.keys()):
                        proc = process_dict[pid]

                        # Delete the terminated processes
                        if not proc.is_alive():
                            proc.join()
                            del process_dict[pid]
                            del proc

                    # Check if caps are reached.
                    # Cap is only checked if there is at least one
                    # process working to prevent deadlock.
                    no_cap = True
                    if self._check_usage and self._ncores > len(process_dict) > 0:
                        for cap_name, cap_function, threshold in (
                                            ('CPU Cap', cpu_usage_func, self._cpu_cap),
                                            ('Memory Cap', memory_usage_func, self._memory_cap[0]),
                                            ('Swap Cap', swap_usage_func, self._swap_cap)):
                            cap_value = cap_function()
                            if cap_value > threshold:
                                no_cap = False
                                if signal_cap:
                                    if cap_name == 'Memory Cap':
                                        add_on_str = ' [including estimate]'
                                    else:
                                        add_on_str = ''
                                    self._logger.warning('Could not start next process '
                                                         'immediately [currently running '
                                                         '%d process(es)]. '
                                                         '%s reached, '
                                                         '%.1f%% >= %.1f%%%s.' %
                                                         (len(process_dict), cap_name,
                                                          cap_value, threshold,
                                                          add_on_str))
                                    signal_cap = False
                                    max_signals -= 1
                                    if max_signals == 0:
                                        self._logger.warning('Maximum number of cap warnings '
                                                             'reached. I will no longer '
                                                             'notify about cap violations, '
                                                             'but cap values are still applied '
                                                             'silently in background.')
                                break  # If one cap value is reached we can skip the rest

                    # If we have less active processes than
                    # self._ncores and there is still
                    # a job to do, add another process
                    if len(process_dict) < self._ncores and keep_running and no_cap:
                        try:
                            task = next(iterator)
                            proc = multip.Process(target=_process_single_run,
                                                  args=(task,))
                            proc.start()
                            process_dict[proc.pid] = proc

                            signal_cap = max_signals > 0  # Only signal max_signals times
                        except StopIteration:
                            # All simulation runs have been started
                            keep_running = False
                            if self._postproc is not None and self._immediate_postproc:

                                if self._wrap_mode == pypetconstants.WRAP_MODE_LOCAL:
                                    reference_service = self._traj._storage_service
                                    self._traj.v_storage_service = self._storage_service
                                try:
                                    self._logger.info('Performing IMMEDIATE POSTPROCESSING.')
                                    keep_running, start_run_idx, new_runs = \
                                        self._execute_postproc(results)
                                finally:
                                    if self._wrap_mode == pypetconstants.WRAP_MODE_LOCAL:
                                        self._traj._storage_service = reference_service

                                if keep_running:
                                    expanded_by_postproc = True
                                    self._logger.info('IMMEDIATE POSTPROCESSING expanded '
                                              'the trajectory and added %d '
                                              'new runs' % new_runs)

                                    n = start_run_idx
                                    total_runs = len(self._traj)
                                    iterator = self._make_iterator(start_run_idx,
                                                                   result_queue=result_queue)
                            if not keep_running:
                                self._logger.debug('All simulation runs have been started. '
                                                   'No new runs will be started. '
                                                   'The simulation will finish after the still '
                                                   'active runs completed.')
                    else:
                        time.sleep(0.001)

                    # Get all results from the result queue
                    n = self._get_results_from_queue(result_queue, results, n, total_runs)

                # Finally get all results from the result queue once more and finalize the queue
                self._get_results_from_queue(result_queue, results, n, total_runs)
                result_queue.close()
                result_queue.join_thread()
                del result_queue

                result_sort(results, start_result_length)
        finally:
            # Finalize the wrapper
            if self._multiproc_wrapper is not None:
                self._multiproc_wrapper.finalize()
                self._multiproc_wrapper = None

        return expanded_by_postproc


@prefix_naming
class MultiprocContext(HasLogger):
    """ A lightweight environment that allows the usage of multiprocessing.

    Can be used if you don't want a full-blown :class:`~pypet.environment.Environment` to
    enable multiprocessing or if you want to implement your own custom multiprocessing.

    This Wrapper tool will take a trajectory container and take care that the storage
    service is multiprocessing safe. Supports the ``'LOCK'`` as well as the ``'QUEUE'`` mode.
    In case of the latter an extra queue process is created if desired.
    This process will handle all storage requests and write data to the hdf5 file.

    Not that in case of ``'QUEUE'`` wrapping data can only be stored not loaded, because
    the queue will only be read in one direction.

    :param trajectory:

        The trajectory which storage service should be wrapped

    :param wrap_mode:

        There are four options:

         :const:`~pypet.pypetconstants.WRAP_MODE_QUEUE`: ('QUEUE')

             If desired another process for storing the trajectory is spawned.
             The sub processes running the individual trajectories will add their results to a
             multiprocessing queue that is handled by an additional process.
             Note that this requires additional memory since data
             will be pickled and send over the queue for storage!

         :const:`~pypet.pypetconstants.WRAP_MODE_LOCK`: ('LOCK')

             Each individual process takes care about storage by itself. Before
             carrying out the storage, a lock is placed to prevent the other processes
             to store data. Accordingly, sometimes this leads to a lot of processes
             waiting until the lock is released.
             Yet, data does not need to be pickled before storage!

         :const:`~pypet.pypetconstants.WRAP_MODE_PIPE`: ('PIPE)

            Experimental mode based on a single pipe. Is faster than ``'QUEUE'`` wrapping
            but data corruption may occur, does not work under Windows
            (since it relies on forking).

         :const:`~pypet.pypetconstant.WRAP_MODE_LOCAL` ('LOCAL')

            Data is not stored in spawned child processes, but data needs to be
            retunred manually in terms of *references* dictionaries (the ``reference`` property
            of the ``ReferenceWrapper`` class)..
            Storing is only performed in the main process.

            Note that removing data during a single run has no longer an effect on memory
            whatsoever, because there are references kept for all data
            that is supposed to be stored.

    :param full_copy:

        In case the trajectory gets pickled (sending over a queue or a pool of processors)
        if the full trajectory should be copied each time (i.e. all parameter points) or
        only a particular point. A particular point can be chosen beforehand with
        :func:`~pypet.trajectory.Trajectory.f_set_crun`.

        Leave ``full_copy=None`` if the setting from the passed trajectory should be used.
        Otherwise ``v_full_copy`` of the trajectory is changed to your chosen value.

    :param manager:

        You can pass an optional multiprocessing manager here,
        if you already have instantiated one.
        Leave ``None`` if you want the wrapper to create one.

    :param use_manager:

        If your lock and queue should be created with a manager or if wrapping should be
        created from the multiprocessing module directly.

        For example: ``multiprocessing.Lock()`` or via a manager
        ``multiprocessing.Manager().Lock()``
        (if you specified a manager, this manager will be used).

        The former is usually faster whereas the latter is more flexible and can
        be used in an environment where fork is not available, for instance.

    :param lock:

        You can pass a multiprocessing lock here, if you already have instantiated one.
        Leave ``None`` if you want the wrapper to create one in case of ``'LOCK'`` wrapping.

    :param queue:

        You can pass a multiprocessing queue here, if you already instantiated one.
        Leave ``None`` if you want the wrapper to create one in case of ''`QUEUE'`` wrapping.

    :param queue_maxsize:

        Maximum size of queue if created new. 0 means infinite.

    :param port:

        Port to be used by lock server in case of ``'NETLOCK'`` wrapping.
        Can be a single integer as well as a tuple ``(7777, 9999)`` to specify
        a range of ports from which to pick a random one.
        Leave `None` for using pyzmq's default range.
        In case automatic determining of the host's ip address fails,
        you can also pass the full address (including the protocol and
        the port) of the host in the network like ``'tcp://127.0.0.1:7777'``.

    :param timeout:

        Timeout for a NETLOCK wrapping in seconds. After ``timeout``
        seconds a lock is automatically released and free for other
        processes.

    :param gc_interval:

        Interval (in runs or storage operations) with which ``gc.collect()``
        should be called in case of the ``'LOCAL'``, ``'QUEUE'``, or ``'PIPE'`` wrapping.
        Leave ``None`` for never.

        ``1`` means after every storing, ``2`` after every second storing, and so on.
        Only calls ``gc.collect()`` in the main (if ``'LOCAL'`` wrapping)
        or the queue/pipe process. If you need to garbage collect data within your single runs,
        you need to manually call ``gc.collect()``.

        Usually, there is no need to set this parameter since the Python garbage collection
        works quite nicely and schedules collection automatically.

    :param log_config:

        Path to logging config file or dictionary to configure logging for the
        spawned queue process. Thus, only considered if the queue wrap mode is chosen.

    :param log_stdout:

        If stdout of the queue process should also be logged.

    :param graceful_exit:

        Hitting Ctrl+C won't kill a server process unless hit twice.

    For an usage example see :ref:`example-16`.

    """
    def __init__(self, trajectory,
                 wrap_mode=pypetconstants.WRAP_MODE_LOCK,
                 full_copy=None,
                 manager=None,
                 use_manager=True,
                 lock=None,
                 queue=None,
                 queue_maxsize=0,
                 port=None,
                 timeout=None,
                 gc_interval=None,
                 log_config=None,
                 log_stdout=False,
                 graceful_exit=False):

        self._set_logger()

        self._manager = manager
        self._traj = trajectory
        self._storage_service = self._traj.v_storage_service
        self._queue_process = None
        self._pipe_process = None
        self._lock_wrapper = None
        self._queue_wrapper = None
        self._reference_wrapper = None
        self._wrap_mode = wrap_mode
        self._queue = queue
        self._queue_maxsize = queue_maxsize
        self._pipe = queue
        self._max_buffer_size = queue_maxsize
        self._lock = lock
        self._lock_process = None
        self._port = port
        self._timeout = timeout
        self._use_manager = use_manager
        self._logging_manager = None
        self._gc_interval = gc_interval
        self._graceful_exit = graceful_exit

        if (self._wrap_mode == pypetconstants.WRAP_MODE_QUEUE or
                        self._wrap_mode == pypetconstants.WRAP_MODE_PIPE or
                            self._wrap_mode == pypetconstants.WRAP_MODE_NETLOCK or
                                self._wrap_mode == pypetconstants.WRAP_MODE_NETQUEUE):
            self._logging_manager = LoggingManager(log_config=log_config,
                                                   log_stdout=log_stdout)
            self._logging_manager.extract_replacements(self._traj)
            self._logging_manager.check_log_config()

        if full_copy is not None:
            self._traj.v_full_copy=full_copy

    @property
    def lock(self):
        return self._lock

    @property
    def queue(self):
        return self._queue

    @property
    def pipe(self):
        return self._pipe

    @property
    def queue_wrapper(self):
        return self._queue_wrapper

    @property
    def reference_wrapper(self):
        return self._reference_wrapper

    @property
    def lock_wrapper(self):
        return self._lock_wrapper

    @property
    def pipe_wrapper(self):
        return self._pipe_wrapper

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finalize()

    def store_references(self, references):
        """In case of reference wrapping, stores data.

        :param references: References dictionary from a ReferenceWrapper.

        :param gc_collect: If ``gc.collect`` should be called.

        :param n:

            Alternatively if ``gc_interval`` is set, a current index can be passed.
            Data is stored in case ``n % gc_interval == 0``.

        """
        self._reference_store.store_references(references)

    def start(self):
        """Starts the multiprocess wrapping.

        Automatically called when used as context manager.
        """
        self._do_wrap()

    def _do_wrap(self):
        """ Wraps a Storage Service """

        # First take care that the storage is initialised
        self._traj.f_store(only_init=True)
        if self._wrap_mode == pypetconstants.WRAP_MODE_QUEUE:
            self._prepare_queue()
        elif self._wrap_mode == pypetconstants.WRAP_MODE_LOCK:
            self._prepare_lock()
        elif self._wrap_mode == pypetconstants.WRAP_MODE_PIPE:
            self._prepare_pipe()
        elif self._wrap_mode == pypetconstants.WRAP_MODE_LOCAL:
            self._prepare_local()
        elif self._wrap_mode == pypetconstants.WRAP_MODE_NETLOCK:
            self._prepare_netlock()
        elif self._wrap_mode == pypetconstants.WRAP_MODE_NETQUEUE:
            self._prepare_netqueue()
        else:
            raise RuntimeError('The mutliprocessing mode %s, your choice is '
                                           'not supported, use %s`, `%s`, %s, `%s`, or `%s`.'
                                           % (self._wrap_mode, pypetconstants.WRAP_MODE_QUEUE,
                                              pypetconstants.WRAP_MODE_LOCK,
                                              pypetconstants.WRAP_MODE_PIPE,
                                              pypetconstants.WRAP_MODE_LOCAL,
                                              pypetconstants.WRAP_MODE_NETLOCK))

    def _prepare_local(self):
        reference_wrapper = ReferenceWrapper()
        self._traj.v_storage_service = reference_wrapper
        self._reference_wrapper = reference_wrapper
        self._reference_store = ReferenceStore(self._storage_service, self._gc_interval)

    def _prepare_netlock(self):
        """ Replaces the trajectory's service with a LockWrapper """
        if not isinstance(self._port, str):
            url = port_to_tcp(self._port)
            self._logger.info('Determined Server URL: `%s`' % url)
        else:
            url = self._port

        if self._lock is None:
            if hasattr(os, 'fork'):
                self._lock = ForkAwareLockerClient(url)
            else:
                self._lock = LockerClient(url)

        if self._timeout is None:
            lock_server = LockerServer(url)
        else:
            lock_server = TimeOutLockerServer(url, self._timeout)
            self._logger.info('Using timeout aware lock server.')

        self._lock_process = multip.Process(name='LockServer', target=_wrap_handling,
                                            args=(dict(handler=lock_server,
                                                       logging_manager=self._logging_manager,
                                                       graceful_exit=self._graceful_exit),))
        # self._lock_process = threading.Thread(name='LockServer', target=_wrap_handling,
        #                                       args=(dict(handler=lock_server,
        #                                       logging_manager=self._logging_manager),))

        self._lock_process.start()
        self._lock.start()
        # Wrap around the storage service to allow the placement of locks around
        # the storage procedure.
        lock_wrapper = LockWrapper(self._storage_service, self._lock)
        self._traj.v_storage_service = lock_wrapper
        self._lock_wrapper = lock_wrapper

    def _prepare_lock(self):
        """ Replaces the trajectory's service with a LockWrapper """
        if self._lock is None:
            if self._use_manager:
                if self._manager is None:
                    self._manager = multip.Manager()
                # We need a lock that is shared by all processes.
                self._lock = self._manager.Lock()
            else:
                self._lock = multip.Lock()

        # Wrap around the storage service to allow the placement of locks around
        # the storage procedure.
        lock_wrapper = LockWrapper(self._storage_service, self._lock)
        self._traj.v_storage_service = lock_wrapper
        self._lock_wrapper = lock_wrapper

    def _prepare_pipe(self):
        """ Replaces the trajectory's service with a queue sender and starts the queue process.

        """
        if self._pipe is None:
            self._pipe = multip.Pipe(True)
        if self._lock is None:
            self._lock = multip.Lock()

        self._logger.info('Starting the Storage Pipe!')
        # Wrap a queue writer around the storage service
        pipe_handler = PipeStorageServiceWriter(self._storage_service, self._pipe[0],
                                                max_buffer_size=self._max_buffer_size)

        # Start the queue process
        self._pipe_process = multip.Process(name='PipeProcess', target=_wrap_handling,
                                             args=(dict(handler=pipe_handler,
                                                        logging_manager=self._logging_manager,
                                                        graceful_exit=self._graceful_exit),))
        self._pipe_process.start()

        # Replace the storage service of the trajectory by a sender.
        # The sender will put all data onto the pipe.
        # The writer from above will receive the data from
        # the pipe and hand it over to
        # the storage service
        self._pipe_wrapper = PipeStorageServiceSender(self._pipe[1], self._lock)
        self._traj.v_storage_service = self._pipe_wrapper

    def _prepare_queue(self):
        """ Replaces the trajectory's service with a queue sender and starts the queue process.

        """
        if self._queue is None:
            if self._use_manager:
                if self._manager is None:
                    self._manager = multip.Manager()
                self._queue = self._manager.Queue(maxsize=self._queue_maxsize)
            else:
                self._queue = multip.Queue(maxsize=self._queue_maxsize)

        self._logger.info('Starting the Storage Queue!')
        # Wrap a queue writer around the storage service
        queue_handler = QueueStorageServiceWriter(self._storage_service, self._queue,
                                                  self._gc_interval)

        # Start the queue process
        self._queue_process = multip.Process(name='QueueProcess', target=_wrap_handling,
                                             args=(dict(handler=queue_handler,
                                                        logging_manager=self._logging_manager,
                                                        graceful_exit=self._graceful_exit),))
        self._queue_process.start()

        # Replace the storage service of the trajectory by a sender.
        # The sender will put all data onto the queue.
        # The writer from above will receive the data from
        # the queue and hand it over to
        # the storage service
        self._queue_wrapper = QueueStorageServiceSender(self._queue)
        self._traj.v_storage_service = self._queue_wrapper

    def _prepare_netqueue(self):
        """ Replaces the trajectory's service with a queue sender and starts the queue process.

        """
        self._logger.info('Starting Network Queue!')

        if not isinstance(self._port, str):
            url = port_to_tcp(self._port)
            self._logger.info('Determined Server URL: `%s`' % url)
        else:
            url = self._port

        if self._queue is None:
            if hasattr(os, 'fork'):
                self._queue = ForkAwareQueuingClient(url)
            else:
                self._queue = QueuingClient(url)

        # Wrap a queue writer around the storage service
        queuing_server_handler = QueuingServer(url,
                                               self._storage_service,
                                               self._queue_maxsize,
                                               self._gc_interval)

        # Start the queue process
        self._queue_process = multip.Process(name='QueuingServerProcess', target=_wrap_handling,
                                             args=(dict(handler=queuing_server_handler,
                                                        logging_manager=self._logging_manager,
                                                        graceful_exit=self._graceful_exit),))
        self._queue_process.start()
        self._queue.start()

        # Replace the storage service of the trajectory by a sender.
        # The sender will put all data onto the queue.
        # The writer from above will receive the data from
        # the queue and hand it over to
        # the storage service
        self._queue_wrapper = QueueStorageServiceSender(self._queue)
        self._traj.v_storage_service = self._queue_wrapper

    def finalize(self):
        """ Restores the original storage service.

        If a queue process and a manager were used both are shut down.

        Automatically called when used as context manager.

        """
        if (self._wrap_mode == pypetconstants.WRAP_MODE_QUEUE and
                    self._queue_process is not None):
            self._logger.info('The Storage Queue will no longer accept new data. '
                              'Hang in there for a little while. '
                              'There still might be some data in the queue that '
                              'needs to be stored.')
            # We might have passed the queue implicitly,
            # to be sure we add the queue here again
            self._traj.v_storage_service.queue = self._queue
            self._traj.v_storage_service.send_done()
            self._queue_process.join()
            if hasattr(self._queue, 'join'):
                self._queue.join()
            if hasattr(self._queue, 'close'):
                self._queue.close()
            if hasattr(self._queue, 'join_thread'):
                self._queue.join_thread()
            self._logger.info('The Storage Queue has joined.')

        elif (self._wrap_mode == pypetconstants.WRAP_MODE_PIPE and
                    self._pipe_process is not None):
            self._logger.info('The Storage Pipe will no longer accept new data. '
                              'Hang in there for a little while. '
                              'There still might be some data in the pipe that '
                              'needs to be stored.')
            self._traj.v_storage_service.conn = self._pipe[1]
            self._traj.v_storage_service.send_done()
            self._pipe_process.join()
            self._pipe[1].close()
            self._pipe[0].close()
        elif (self._wrap_mode == pypetconstants.WRAP_MODE_NETLOCK and
                self._lock_process is not None):
            self._lock.send_done()
            self._lock.finalize()
            self._lock_process.join()
        elif (self._wrap_mode == pypetconstants.WRAP_MODE_NETQUEUE and
                self._queue_process is not None):
            self._queue.send_done()
            self._queue.finalize()
            self._queue_process.join()

        if self._manager is not None:
            self._manager.shutdown()

        self._manager = None
        self._queue_process = None
        self._queue = None
        self._queue_wrapper = None
        self._lock = None
        self._lock_wrapper = None
        self._lock_process = None
        self._reference_wrapper = None
        self._pipe = None
        self._pipe_process = None
        self._pipe_wrapper = None
        self._logging_manager = None

        self._traj._storage_service = self._storage_service

    def __del__(self):
        self.finalize()
