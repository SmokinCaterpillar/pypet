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

import os
import sys
import logging
try:
    import cPickle as pickle
except ImportError:
    import pickle
import multiprocessing as multip
import traceback
import hashlib
import time
import datetime

from pypet.utils.mplogging import StreamToLogger
from pypet.trajectory import Trajectory, SingleRun
from pypet.storageservice import HDF5StorageService, QueueStorageServiceSender,\
    QueueStorageServiceWriter, LockWrapper
from  pypet import pypetconstants
from pypet.gitintegration import make_git_commit
from pypet import __version__ as VERSION
from pypet.utils.decorators import deprecated


def _single_run(args):
    """ Performs a single run of the experiment.

    :param args: List of arguments

        0. The single run object containing all parameters set to the corresponding run index.

        1. Path to log files

        2. A queue object, only necessary in case of multiprocessing in queue mode.

        3. The user's job function

        4. Number of total runs (int)

        5. Whether to use multiprocessing or not (bool)

        6. The arguments handed to the user's job function (as *args)

        7. The keyword arguments handed to the user's job function (as **kwargs)

    :return: Results computed by the user's job function which are not stored into the trajectory

    """

    try:
        traj=args[0] 
        log_path=args[1] 
        queue=args[2]
        runfunc=args[3] 
        total_runs = args[4]
        multiproc = args[5]
        runparams = args[6]
        kwrunparams = args[7]
    
        assert isinstance(traj, SingleRun)
        root = logging.getLogger()
        idx = traj.v_idx

        if multiproc:
            
            # In case of multiprocessing we want to have a log file for each individual process.
            pid = os.getpid()
            filename = 'process_%s.txt' % str(pid)
            filename=log_path+'/'+filename
            exists = os.path.isfile(filename)

            # If the file does not exist we need to create it and create a handler that logs
            # all messages into the file.
            if not exists:

                h=logging.FileHandler(filename=filename)
                f = logging.Formatter('%(asctime)s %(name)s %(levelname)-8s %(message)s')
                h.setFormatter(f)
                root.addHandler(h)

                # Also copy standard out and error to the log files
                outstl = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO)
                sys.stdout = outstl

                errstl = StreamToLogger(logging.getLogger('STDERR'), logging.ERROR)
                sys.stderr = errstl


        ## Add the queue for storage in case of multiprocessing in queue mode.
        if queue is not None:
            traj.v_storage_service.queue = queue
    
        root.info('\n===================================\n '
                  'Starting single run #%d of %d '
                  '\n===================================\n' % (idx,total_runs))

        # Measure start time
        traj._set_start_time()

        # Run the job function of the user
        result =runfunc(traj,*runparams,**kwrunparams)

        # Measure time of finishing
        traj._set_finish_time()


        root.info('Evoke Storing (Either storing directly or sending trajectory to queue)')
        # Store the single run
        traj.f_store()

        # Make some final adjustments to the single run before termination
        traj._finalize()

        root.info('\n===================================\n '
                  'Finished single run #%d of %d '
                  '\n===================================\n' % (idx,total_runs))

        return result

    except:
        errstr = "\n\n############## ERROR ##############\n"+"".join(traceback.format_exception(*sys.exc_info()))+"\n"
        logging.getLogger('STDERR').error(errstr)
        raise Exception("".join(traceback.format_exception(*sys.exc_info())))

def _queue_handling(handler,log_path):
    """ Starts running a queue handler and creates a log file for the queue."""

    # Create a new log file for the queue writer
    filename = 'queue_process.txt'
    filename=log_path+'/'+filename
    root = logging.getLogger()

    h=logging.FileHandler(filename=filename)
    f = logging.Formatter('%(asctime)s %(name)s %(levelname)-8s %(message)s')
    h.setFormatter(f)
    root.addHandler(h)

    #Redirect standard out and error to the file
    outstl = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO)
    sys.stdout = outstl

    errstl = StreamToLogger(logging.getLogger('STDERR'), logging.ERROR)
    sys.stderr = errstl

    # Main job, make the listener to the queue start receiving message for writing to disk.
    handler.run()

class Environment(object):
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

    :param log_folder:

        Path to a folder where all log files will be stored. If none is specified the default
        `./logs/` is chosen. The log files will be added to a
        sub-folder with the name of the trajectory.

    :param multiproc:

        Whether or not to use multiprocessing. Default is 0 (False). If you use
        multiprocessing, all your data and the tasks you compute must be picklable!

    :param ncores:

        If multiproc is 1 (True), this specifies the number of processes that will be spawned
        to run your experiment. Note if you use QUEUE mode (see below) the queue process
        is not included in this number and will add another extra process for storing.

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

         If you don't want wrapping at all use :const:`~pypet.pypetconstants.WRAP_MODE_NONE` ('NONE')


    :param continuable:

        Whether the environment should take special care to allow to resume or continue
        crashed trajectories. Default is 1 (True).
        Everything must be picklable in order to allow continuing of trajectories.

        Assume you run experiments that take a lot of time.
        If during your experiments there is a power failure,
        you can resume your trajectory after the last single run that was still
        successfully stored via your storage service.

        The environment will create a `.cnt` file in the same folder as your hdf5 file,
        using this you can continue crashed trajectories.
        If you do not use hdf5 files or the hdf5 storage service, the `.cnt` file is placed
        into the log folder.

        In order to resume trajectories use :func:`~pypet.environment.Environment.f_continue_run`.

    :param use_hdf5:

        Whether or not to use the standard hdf5 storage service, if false the following
        arguments below will be ignored:

    :param filename:

        The name of the hdf5 file. If none is specified the default './hdf5/experiment.hdf5'
        is chosen.

    :param file_title: Title of the hdf5 file (only important if file is created new)

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

    :param small_overview_tables:

        Whether the small overview tables should be created.
        Small tables are giving overview about 'config','parameters',
        'derived_parameters_trajectory', 'derived_parameters_runs_summary',
        'results_trajectory','results_runs_summary'.

        Note that these tables create some overhead. If you want very small hdf5 files set
        `small_overview_tables` to False.

        The 'XXXXXX_summary' tables give a summary about all results or derived parameters.
        It is assumed that results and derived parameters with equal names in individual runs
        are similar and only the first result or derived parameter that was created
        is shown as an example.

        The summary table can be used in combination with `purge_duplicate_comments` to only store
        a single comment for every result with the same name in each run, see above.

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

        This will also add information about the revision to the trajectory, see below.

    :param git_message:

        Message passed onto git command.

    .. _GitPython: http://pythonhosted.org/GitPython/0.3.1/index.html


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
                 log_folder=None,
                 multiproc=False,
                 ncores=1,
                 wrap_mode=pypetconstants.WRAP_MODE_LOCK,
                 continuable=1,
                 use_hdf5=True,
                 filename=None,
                 file_title=None,
                 purge_duplicate_comments=True,
                 small_overview_tables=True,
                 large_overview_tables=True,
                 results_per_run=0,
                 derived_parameters_per_run=0,
                 git_repository = None,
                 git_message=''):


        # First check if purge settings are valid
        if purge_duplicate_comments and not small_overview_tables:
            raise RuntimeError('You cannot purge duplicate comments without having the'
                               ' small overview tables.')


        self._git_repository = git_repository
        self._git_message=git_message

        # Check if a novel trajectory needs to be created.
        if isinstance(trajectory,str):
            # Create a new trajectory
            self._traj = Trajectory(trajectory,
                                    add_time=add_time,
                                    dynamically_imported_classes=dynamically_imported_classes,
                                    comment=comment)

            self._timestamp = self.v_trajectory.v_timestamp # Timestamp of creation
            self._time = self.v_trajectory.v_time # Formatted timestamp

        else:

            self._traj = trajectory

            # If no new trajectory is created the time of the environment differs from the trajectory
            # and must be computed from the current time.
            init_time = time.time()

            formatted_time = datetime.datetime.fromtimestamp(init_time).strftime('%Y_%m_%d_%Hh%Mm%Ss')

            self._timestamp = init_time

            self._time = formatted_time

        # If no filename is supplied, take the filename from the trajectory's storage service
        if self.v_trajectory.v_storage_service is not None and filename is None:
            self._file_title=self._traj.v_storage_service._file_title
            self._filename=self._traj.v_storage_service._filename
        else:
            # Prepare file names and log folder
            if file_title is None:
                self._file_title = self._traj.v_name
            else:
                self._file_title = file_title

            if filename is None:
                # If no filename is supplied and the filename cannot be extracted from the
                # trajectory, create the default filename
                self._filename = os.path.join(os.getcwd(),'hdf5','experiment.hdf5')
            else:
                self._filename=filename

        head, tail = os.path.split(self._filename)
        if not head:
            # If the filename contains no path information,
            # we put it into the current working directory
            self._filename = os.path.join(os.getcwd(),self._filename)

        if not tail:
            raise ValueError('You need to specify a filename not just a path.')

        self._use_hdf5 = use_hdf5 # Boolean whether to use hdf5 or not

        # Check if the user wants to use the hdf5 storage service. If yes,
        # add a service to the trajectory
        if self._use_hdf5 and self.v_trajectory.v_storage_service is None:
            self._add_hdf5_storage_service()

        # In case the user provided a git repository path, a git commit is performed
        # and the environment's hexsha is taken from the commit
        if self._git_repository is not None:
            self._hexsha=make_git_commit(self,self._git_repository, self._git_message) # Identifier
            # hexsha
        else:
            # Otherwise we need to create a novel hexsha
            self._hexsha=hashlib.sha1(self.v_trajectory.v_name +
                                      str(self.v_trajectory.v_timestamp) +
                                      str(self.v_timestamp) +
                                      VERSION).hexdigest()

        # Create the name of the environment
        short_hexsha= self._hexsha[0:7]
        name = 'environment'
        self._name = name+'_'+str(short_hexsha)+'_'+self._time # Name of environment

        # The trajectory should know the hexsha of the current environment.
        # Thus, for all runs, one can identify by which environment they were run.
        self._traj._environment_hexsha=self._hexsha

        # If no log folder is provided, create the default log folder
        if log_folder is None:
            log_folder = os.path.join(os.getcwd(), 'logs')

        # The actual log folder is a sub-folder with the trajectory name
        log_path = os.path.join(log_folder,self._traj.v_name)
        self._log_path = log_path

        # Create the loggers
        self._make_logger(log_path)


        # Add config values to the trajectory
        config_name='environment.%s.ncores' % self.v_name
        self._traj.f_add_config(config_name,ncores,
                                comment='Number of processors in case of multiprocessing')

        config_name='environment.%s.multiproc' % self.v_name
        self._traj.f_add_config(config_name, multiproc,
                                comment= 'Whether or not to use multiprocessing. If yes'
                                         ' than everything must be pickable.')

        config_name='environment.%s.wrap_mode' % self.v_name
        self._traj.f_add_config(config_name,wrap_mode,
                                    comment ='Multiprocessing mode (if multiproc),'
                                             ' i.e. whether to use QUEUE'
                                             ' or LOCK or NONE'
                                             ' for thread/process safe storing')

        config_name='environment.%s.timestamp' % self.v_name
        self._traj.f_add_config(config_name,self.v_timestamp,
                                    comment ='Timestamp of environment creation')

        config_name='environment.%s.hexsha' % self.v_name
        self._traj.f_add_config(config_name,self.v_hexsha,
                                    comment ='SHA-1 identifier of the environment')

        config_name='environment.%s.continuable' % self._name
        self._traj.f_add_config(config_name, continuable,
                                comment='Whether or not a continue file should'
                                        ' be created. If yes, everything must be'
                                        ' picklable.')

        if self._traj.v_version != VERSION:
            config_name='environment.%s.version' % self.v_name
            self._traj.f_add_config(config_name,self.v_trajectory.v_version,
                                    comment ='Pypet version if it differs from the version'
                                             ' of the trajectory')

        config_name='environment.%s.trajectory.name' % self.v_name
        self._traj.f_add_config(config_name,self.v_trajectory.v_name,
                                    comment ='Name of trajectory')

        config_name='environment.%s.trajectory.timestamp' % self.v_name
        self._traj.f_add_config(config_name,self.v_trajectory.v_timestamp,
                                    comment ='Timestamp of trajectory')

        # Add HDF5 config in case the user wants the standard service
        if self._use_hdf5 and not self.v_trajectory.v_stored:
            for config_name, table_name in HDF5StorageService.NAME_TABLE_MAPPING.items():

                self._traj.f_add_config(config_name,1,comment='Whether or not to have an overview '
                                                                  'table with that name')


            self._traj.f_add_config('hdf5.overview.explored_parameters_runs',1,
                                        comment='Whether there are overview tables about the '
                                                'explored parameters in each run')


            self._traj.f_add_config('hdf5.purge_duplicate_comments',int(purge_duplicate_comments),
                                                comment='Whether comments of results and'
                                                        ' derived parameters should only'
                                                        ' be stored for the very first instance.'
                                                        ' Works only if the summary tables are'
                                                        ' active.')



            self._traj.f_add_config('hdf5.results_per_run', int(results_per_run),
                                        comment='Expected number of results per run,'
                                            ' a good guess can increase storage performance')


            self._traj.f_add_config('hdf5.derived_parameters_per_run', int(derived_parameters_per_run),
                                        comment='Expected number of derived parameters per run,'
                                            ' a good guess can increase storage performance')


            if not small_overview_tables:
                self.f_switch_off_small_overview()
            if not large_overview_tables:
                self.f_switch_off_large_overview()


        self._logger.info('Environment initialized.')


    def _make_logger(self,log_path):

        # Make the log folders, the lowest folder in hierarchy has the trajectory name
        if not os.path.isdir(log_path):
            os.makedirs(log_path)

        # Check if there already exist logging handlers, if so, we assume the user
        # has already set a log  level. If not, we set the log level to INFO
        if len(logging.getLogger().handlers)==0:
            logging.basicConfig(level=logging.INFO)

        # Add a handler for storing everything to a text file
        f = logging.Formatter('%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s')
        h=logging.FileHandler(filename=log_path+'/main.txt')
        root = logging.getLogger()
        root.addHandler(h)

        # Add a handler for storing warnings and errors to a text file
        h=logging.FileHandler(filename=log_path+'/warnings_and_errors.txt')
        h.setLevel(logging.WARNING)
        root = logging.getLogger()
        root.addHandler(h)

        # Also copy standard out and error to the log files
        outstl = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO)
        sys.stdout = outstl

        errstl = StreamToLogger(logging.getLogger('STDERR'), logging.ERROR)
        sys.stderr = errstl

        for handler in root.handlers:
            handler.setFormatter(f)
        self._logger = logging.getLogger('pypet.environment.Environment=%s' % self.v_name)

    @deprecated('Please use assignment in environment constructor.')
    def f_switch_off_large_overview(self):
        """ Switches off the tables consuming the most memory.

            * Single Run Result Overview

            * Single Run Derived Parameter Overview

            * Explored Parameter Overview in each Single Run


        DEPRECATED: Please pass whether to use the tables to the environment constructor.

        """
        self._traj.config.hdf5.overview.results_runs=0
        self._traj.config.hdf5.overview.derived_parameters_runs = 0
        self._traj.config.hdf5.overview.explored_parameters_runs = 0

    @deprecated('Please use assignment in environment constructor.')
    def f_switch_off_all_overview(self):
        """Switches all tables off.

        DEPRECATED: Please pass whether to use the tables to the environment constructor.

        """
        self.f_switch_off_small_overview()
        self.f_switch_off_large_overview()

    @deprecated('Please use assignment in environment constructor.')
    def f_switch_off_small_overview(self):
        """ Switches off small overview tables and switches off `purge_duplicate_comments`.

        DEPRECATED: Please pass whether to use the tables to the environment constructor.

        """
        self._traj.config.hdf5.overview.parameters = 0
        self._traj.config.hdf5.overview.config=0
        self._traj.config.hdf5.overview.explored_parameters=0
        self._traj.config.hdf5.overview.derived_parameters_trajectory=0
        self._traj.config.hdf5.overview.derived_parameters_runs_summary=0
        self._traj.config.hdf5.overview.results_trajectory=0
        self._traj.config.hdf5.overview.results_runs_summary=0
        self._traj.config.hdf5.purge_duplicate_comments=0


    def f_continue_run(self, continue_file):
        """ Resumes crashed trajectories by supplying the '.cnt' file."""

        # Unpack the stored data
        continue_dict = pickle.load(open(continue_file,'rb'))
        # User's job function
        runfunc = continue_dict['runfunc']
        # Arguments to the user's job function
        args = continue_dict['args']
        # Keyword arguments to the user's job function
        kwargs = continue_dict['kwargs']
        # Unpack the trajectory
        self._traj = continue_dict['trajectory']
        self._traj.v_full_copy = continue_dict['full_copy']
        # Load meta data
        self._traj.f_load(load_parameters=pypetconstants.LOAD_NOTHING,
             load_derived_parameters=pypetconstants.LOAD_NOTHING,
             load_results=pypetconstants.LOAD_NOTHING)


        # Remove incomplete runs
        self._traj._remove_incomplete_runs()

        # Check how many runs are about to be done
        count = 0
        for run_dict in self._traj.f_get_run_information(copy=False).itervalues():
            if not run_dict['completed']:
                count +=1

        # Add a config parameter signalling that an experiment was continued, and how many of them
        config_name='environment.%s.continued_runs' % self.v_name
        if not config_name in self._traj:
            self._traj.f_add_config(config_name, count,
                                    comment ='Added if a crashed trajectory was continued.')

        # Resume the experiment
        self._do_runs(runfunc,*args,**kwargs)




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


    def _add_hdf5_storage_service(self):
        """ Adds the standard HDF5 storage service to the trajectory.

        See also :class:`~pypet.storageservice.HDF5StorageService`.

        """
        self._storage_service = HDF5StorageService(self._filename,
                                                 self._file_title )

        self._traj.v_storage_service=self._storage_service

    def f_run(self, runfunc, *args,**kwargs):
        """ Runs the experiments and explores the parameter space.

        :param runfunc: The task or job to do

        :param args: Additional arguments (not the ones in the trajectory) passed to runfunc

        :param kwargs: Additional keyword arguments (not the ones in the trajectory) passed to runfunc

        :return:

                Iterable over the results returned by runfunc.

                Does not iterate over results stored in the trajectory!
                In order to do that simply interact with the trajectory object, potentially after
                calling`~pypet.trajectory.Trajectory.f_update_skeleton` and loading all results
                at once with :func:`~pypet.trajectory.f_load` or loading manually with
                :func:`~pypet.trajectory.f_load_items`.

        """

        # Make some sanity checks if the user wants the standard hdf5 service.
        if self._use_hdf5:
            if ( (not self._traj.f_get('results_runs_summary').f_get() or
                        not self._traj.f_get('results_runs_summary').f_get()) and
                    self._traj.f_get('purge_duplicate_comments').f_get()):
                    raise RuntimeError('You can only use the reduce comments if you enable '
                                       'the summary tables.')

        # Check how many runs are about to be done
        count = 0
        for run_dict in self._traj.f_get_run_information(copy=False).itervalues():
            if not run_dict['completed']:
                count +=1

        # Add the amount to be run to the trajectory
        config_name='environment.%s.normal_runs' % self.v_name
        if not config_name in self._traj:
            self._traj.f_add_config(config_name, count,
                                    comment ='Added if trajectory was explored normally and not continued.')

        # Make some preparations (locking of parameters etc) and store the trajectory
        self._traj._prepare_experiment()
        self._traj.f_store()

        # Make the trajectory continuable in case the user wants that
        continuable = self._traj.f_get('config.environment.continuable').f_get()
        if continuable:

            dump_dict ={}
            # Put the file into the hdf5 file folder. If no hdf5 files are used, put it into
            # the log folder.
            if self._use_hdf5:
                filename = self._filename
                dump_folder= os.path.split(filename)[0]
                dump_filename=os.path.join(dump_folder,self._traj.v_name+'.cnt')
            else:
                dump_filename = os.path.join(self._log_path,self._traj.v_name+'.cnt')

            # Store all relevant info into a dictionary and pickle it.
            prev_full_copy = self._traj.v_full_copy
            dump_dict['full_copy'] = prev_full_copy
            dump_dict['runfunc'] = runfunc
            dump_dict['args'] = args
            dump_dict['kwargs'] = kwargs
            self._traj.v_full_copy=True
            dump_dict['trajectory'] = self._traj

            pickle.dump(dump_dict,open(dump_filename,'wb'),protocol=2)

            self._traj.v_full_copy=prev_full_copy

        # Start the runs
        self._do_runs(runfunc,*args,**kwargs)


    def _do_runs(self, runfunc, *args, **kwargs):
        """ Starts the individual single runs.

        Starts runs sequentially or initiates multiprocessing.

        :param runfunc: The user's job
        :param args: Arguments handed to the job
        :param kwargs: Keyword arguments handed to the job

        :return: Iterable over the results of the individual runs

        """
        log_path = self._log_path
        multiproc = self._traj.f_get('config.environment.multiproc').f_get()
        mode = self._traj.f_get('config.environment.wrap_mode').f_get()

        self._storage_service = self._traj.v_storage_service

        if multiproc and mode != pypetconstants.WRAP_MODE_NONE:
            # Prepare Multiprocessing
            if mode == pypetconstants.WRAP_MODE_QUEUE:
                # For queue mode we need to have a queue in a block of shared memory.
                # Accordingly wee need a Multiprocessing Manager.
                manager = multip.Manager()
                queue = manager.Queue()
                self._logger.info('Starting the Storage Queue!')

                # Wrap a queue writer around the storage service
                queue_writer = QueueStorageServiceWriter(self._storage_service,queue)

                # Start the queue process
                queue_process = multip.Process(name='QueueProcess',target=_queue_handling, args=(queue_writer,log_path))
                queue_process.start()

                # Replace the storage service of the trajectory by a sender.
                # The sender will put all data onto the queue.
                # The writer from above will receive the data from the queue and hand it over to
                # the storage service
                queue_sender = QueueStorageServiceSender()
                queue_sender.queue=queue
                self._traj.v_storage_service=queue_sender

            elif mode == pypetconstants.WRAP_MODE_LOCK:
                # We need a lock that is shared by all processes.
                # Accordingly, we use the Multiprocessing Manager.
                manager = multip.Manager()
                lock = manager.Lock()
                queue = None

                # Wrap around the storage service to allow the placement of locks around
                # the storage procedure.
                lock_wrapper = LockWrapper(self._storage_service,lock)
                self._traj.v_storage_service=lock_wrapper

            else:
                raise RuntimeError('The mutliprocessing mode %s, your choice is '
                                   'not supported, use `%s` or `%s`.'
                                    %(mode,pypetconstants.WRAP_MODE_QUEUE,
                                      pypetconstants.WRAP_MODE_LOCK))

            # Create a pool of `ncores` processes
            ncores =  self._traj.f_get('config.ncores').f_get()
            mpool = multip.Pool(ncores)

            self._logger.info('\n************************************************************\n'
                              '************************************************************\n'
                              'STARTING runs of trajectory\n`%s`\nin parallel with %d cores.'
                              '\n************************************************************\n'
                              '************************************************************\n' %
                              (self._traj.v_name, ncores))

            # Create a generator to generate the tasks for the mp-pool
            iterator = ((self._traj._make_single_run(n), log_path, queue, runfunc, len(self._traj),
                         multiproc, args, kwargs) for n in xrange(len(self._traj))
                                                            if not self._traj.f_is_completed(n))


            # Let the pool workers do their jobs provided by the generator
            results = mpool.imap(_single_run,iterator)

            # Everything is done
            mpool.close()
            mpool.join()

            # In case of queue mode, we need to signal to the queue writer that no more data
            # will be put onto the queue
            if mode == pypetconstants.WRAP_MODE_QUEUE:
                self._traj.v_storage_service.send_done()
                queue_process.join()

            # That's about it!
            mpool.terminate()

            # Replace the wrapped storage service with the original one and do some finalization
            self._traj.v_storage_service=self._storage_service
            self._traj._finalize()

            self._logger.info('\n************************************************************\n'
                              '************************************************************\n'
                              'FINISHED all runs of trajectory\n`%s`\nin parallel with %d cores.'
                              '\n************************************************************\n'
                              '************************************************************\n' %
                              (self._traj.v_name, ncores))

            return results
        else:
            # Single Processing
            self._logger.info('\n************************************************************\n'
                              '************************************************************\n'
                              'STARTING runs of trajectory\n`%s`.'
                              '\n************************************************************\n'
                              '************************************************************\n' %
                              self._traj.v_name)

            # Sequentially run all single runs and append the results to a queue
            results = [_single_run((self._traj._make_single_run(n),log_path,None,runfunc,
                                    len(self._traj),multiproc,args,kwargs)) for n in xrange(len(self._traj))
                                    if not self._traj.f_is_completed(n)]

            # Do some finalization
            self._traj._finalize()

            self._logger.info('\n************************************************************\n'
                              '************************************************************\n'
                              'FINISHED all runs of trajectory\n`%s`.'
                              '\n************************************************************\n'
                              '************************************************************\n' %
                              self._traj.v_name)

            return results
                
