from numpy.oldnumeric.ma import _ptp
from wx._windows_ import new_MDIParentFrame

__author__ = 'Robert Meyer'

__version__ = "$Revision: 70b79ccd671a $"# $Source$

import logging
import tables as pt
import os
import numpy as np
from functools import wraps
from mypet.trajectory import Trajectory,SingleRun
from mypet.parameter import BaseParameter, BaseResult, SimpleResult
from mypet import globally
from collections import Sequence
import mypet.petexceptions as pex


from mypet.parameter import ObjectTable
from pandas import DataFrame, read_hdf


def _attr_equals(ptitem,name,value):
    return name in ptitem._v_attrs and ptitem._v_attrs[name] == value

def _get_from_attrs(ptitem,name):
    if name in ptitem._v_attrs:
        return ptitem._v_attrs[name]
    else:
        return None


class MultiprocWrapper(object):


    def store(self,*args,**kwargs):
        raise NotImplementedError('Implement this!')


class QueueStorageServiceSender(MultiprocWrapper):

    def __init__(self):
        self._queue = None

    def set_queue(self,queue):
        self._queue = queue

    def __getstate__(self):
        result = self.__dict__.copy()
        result['_queue'] = None
        return result

    def store(self,*args,**kwargs):
        self._queue.put(('STORE',args,kwargs))


    def send_done(self):
        self._queue.put(('DONE',[],{}))

class QueueStorageServiceWriter(object):
    def __init__(self, storage_service, queue):
        self._storage_service = storage_service
        self._queue = queue

    def run(self):
        while True:
            msg,args,kwargs = self._queue.get()

            if msg == 'DONE':
                break
            elif msg == 'STORE':
                self._storage_service.store(*args,**kwargs)
            else:
                pass
                #raise RuntimeError('You queued something that was not intended to be queued!')

            self._queue.task_done()

class LockWrapper(MultiprocWrapper):
    def __init__(self,storage_service, lock):
        self._storage_service = storage_service
        self._lock = lock


    def store(self,*args,**kwargs):
        try:
            self._lock.acquire()
            self._storage_service.store(*args,**kwargs)
        except Exception, e:
            raise
        finally:
            if not self._lock == None:
                self._lock.release()




class StorageService(object):



    def store(self,msg,stuff_to_store,trajectoryname,*args,**kwargs):
        raise NotImplementedError('Implement this!')

    def load(self,msg,stuff_to_load,trajectoryname,*args,**kwargs):
        raise NotImplementedError('Implement this!')


class LazyStorageService(StorageService):

    def load(self,*args,**kwargs):
        pass

    def store(self,*args,**kwargs):
        pass

class HDF5StorageService(StorageService):
    ''' General Service to handle the storage of a Trajectory and Parameters
    '''

    ADDROW = 'ADD'
    REMOVEROW = 'REMOVE'
    MODIFYROW = 'MODIFY'


    COLLTYPE ='COLLTYPE'

    COLLLIST = 'COLLLIST'
    COLLTUPLE = 'COLLTUPLE'
    COLLNDARRAY = 'COLLNDARRAY'
    COLLSCALAR = 'COLLSCALAR'
    COLLDICT = 'COLLDICT'


    SCALARTYPE = 'SCALARTYPE'




    TABLENAME_MAPPING = {
        'parameters' : 'parameter_table',
        'config' : 'config_table',
        'derived_parameters' : 'derived_parameter_table',
        'results' : 'result_table',
        'explored_parameters' : 'explored_parameter_table'
    }


    ARRAYPREFIX = 'SRVCARRAY_'
    FORMATTEDCOLPREFIX = 'SRVCCOL_%s_'
    DICTPREFIC = 'SRVCDICT_'

    def __init__(self, filename=None, filetitle='Experiment'):
        self._filename = filename
        self._filetitle = filetitle
        self._trajectoryname = None
        self._hdf5file = None
        self._trajectorygroup = None
        self._logger = logging.getLogger('mypet.storageservice_HDF5StorageService')
        self._lock = None



    def load(self,msg,stuff_to_load,*args,**kwargs):
        try:

            self._srvc_extract_file_information(kwargs)


            args = list(args)

            opened = self._srvc_opening_routine('r')


            if msg == globally.TRAJECTORY:
                self._trj_load_trajectory(msg,stuff_to_load,*args,**kwargs)


            elif msg == globally.RESULT or msg == globally.PARAMETER:
                self._prm_load_parameter_or_result(msg,stuff_to_load,*args,**kwargs)

            elif msg ==globally.LIST:
                self._srvc_load_several_items(stuff_to_load,*args,**kwargs)

            else:
                raise pex.NoSuchServiceError('I do not know how to handle >>%s<<' % msg)

            self._srvc_closing_routine(opened)
        except Exception,e:
            self._srvc_closing_routine(True)
            self._logger.error('Failed loading  >>%s<<' % str(stuff_to_load))
            raise




    def store(self,msg,stuff_to_store,*args,**kwargs):
        try:

            self._srvc_extract_file_information(kwargs)


            args = list(args)


            opened= self._srvc_opening_routine('a',msg)

            if msg == globally.MERGE:

                self._trj_merge_trajectories(*args,**kwargs)

            elif msg == globally.BACKUP:
                self._trj_backup_trajectory(stuff_to_store,*args,**kwargs)

            elif msg == globally.UPDATE_TRAJECTORY:
                self._trj_update_trajectory(stuff_to_store,*args,**kwargs)

            elif msg == globally.TRAJECTORY:

                self._trj_store_trajectory(stuff_to_store,*args,**kwargs)

            elif msg == globally.SINGLERUN:

                self._srn_store_single_run(stuff_to_store,*args,**kwargs)

            elif (msg == globally.RESULT or
                          msg == globally.PARAMETER or
                          msg == globally.UPDATE_PARAMETER or
                          msg == globally.UPDATE_RESULT):
                self._prm_store_parameter_or_result(msg,stuff_to_store,*args,**kwargs)

            elif (msg in [globally.REMOVE_RESULT, globally.REMOVE_PARAMETER]):
                self._prm_remove_parameter_or_result(msg,stuff_to_store,*args,**kwargs)

            elif msg == globally.REMOVE_INCOMPLETE_RUNS:
                self._trj_remove_incomplete_runs(stuff_to_store,*args,**kwargs)

            elif msg == globally.LIST:
                self._srvc_store_several_items(stuff_to_store,*args,**kwargs)

            else:
                raise pex.NoSuchServiceError('I do not know how to handle >>%s<<' % msg)

            self._srvc_closing_routine(opened)

        except Exception,e:
            self._srvc_closing_routine(True)
            self._logger.error('Failed storing >>%s<<' % str(stuff_to_store))
            raise


    def _srvc_load_several_items(self,iterable,*args,**kwargs):
        for input_tuple in iterable:
            msg = input_tuple[0]
            item = input_tuple[1]
            if len(input_tuple) > 2:
                args = input_tuple[2]
            if len(input_tuple) > 3:
                kwargs = input_tuple[3]
            if len(input_tuple)> 4:
                raise RuntimeError('You shall not pass!')

            self.load(msg,item,*args,**kwargs)

    def _srvc_store_several_items(self,iterable,*args,**kwargs):

        for input_tuple in iterable:
            msg = input_tuple[0]
            item = input_tuple[1]
            if len(input_tuple) > 2:
                args = input_tuple[2]
            if len(input_tuple) > 3:
                kwargs = input_tuple[3]
            if len(input_tuple)> 4:
                raise RuntimeError('You shall not pass!')

            self.store(msg,item,*args,**kwargs)

    def _srvc_opening_routine(self,mode,msg=None):

        if self._hdf5file == None:
                if 'a' in mode or 'w' in mode:
                    (path, filename)=os.path.split(self._filename)
                    if not os.path.exists(path):
                        os.makedirs(path)


                    self._hdf5file = pt.openFile(filename=self._filename, mode=mode,
                                                 title=self._filetitle)
                    if not ('/'+self._trajectoryname) in self._hdf5file:
                        if not msg == globally.TRAJECTORY:
                            raise ValueError('Your trajectory cannot be found in the hdf5file, '
                                             'please use >>traj.store()<< before storing anyhting else.')
                        self._hdf5file.createGroup(where='/', name= self._trajectoryname,
                                                   title=self._trajectoryname)


                    self._trajectorygroup = self._hdf5file.get_node('/'+self._trajectoryname)

                elif mode == 'r':
                    ### Fuck Pandas, we have to wait until the next relaese until this is supported:
                    mode = 'a'
                    if not os.path.isfile(self._filename):
                        raise ValueError('Filename ' + self._filename + ' does not exist.')

                    self._hdf5file = pt.openFile(filename=self._filename, mode=mode,
                                                 title=self._filetitle)

                    if isinstance(self._trajectoryname,int):
                        nodelist = self._hdf5file.listNodes(where='/')

                        if (self._trajectoryname >= len(nodelist) or
                                    self._trajectoryname < -len(nodelist)):
                            raise ValueError('Trajectory No. %d does not exists, there are only %d trajectories in %s.'
                            % (self._trajectoryname,len(nodelist),self._filename))

                        self._trajectorygroup = nodelist[self._trajectoryname]
                        self._trajectoryname = self._trajectorygroup._v_name
                    else:
                        if not ('/'+self._trajectoryname) in self._hdf5file:
                            raise ValueError('File %s does not contain trajectory %s.'
                                             % (self._filename, self._trajectoryname))
                        self._trajectorygroup = self._hdf5file.get_node('/'+self._trajectoryname)

                else:
                    raise RuntimeError('You shall not pass!')


                return True
        else:
            return False

    def _srvc_closing_routine(self, closing):
        if closing and self._hdf5file != None and self._hdf5file.isopen:
            self._hdf5file.flush()
            self._hdf5file.close()
            self._hdf5file = None
            self._trajectorygroup = None
            self._trajectoryname = None
            return True
        else:
            return False

    def _srvc_extract_file_information(self,kwargs):
        if 'filename' in kwargs:
            self._filename=kwargs.pop('filename')

        if 'filetitle' in kwargs:
            self._filetitle = kwargs.pop('filetitle')

        if 'trajectoryname' in kwargs:
            self._trajectoryname = kwargs.pop('trajectoryname')





    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        result['_lock'] = None
        return result

    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._logger = logging.getLogger('mypet.storageservice_HDF5StorageService=' +
                                         self._filename)


    ########################### MERGING ###########################################################

    def _trj_backup_trajectory(self,traj, *args, **kwargs):

        self._logger.info('Storing backup of %s.' % traj.get_name())

        mypath, filename = os.path.split(self._filename)
        backup_filename = kwargs.pop('backup_filename','%s/backup_%s_.hdf5' %
                                                       (mypath,traj.get_name()))

        backup_hdf5file = pt.openFile(filename=backup_filename, mode='a', title=backup_filename)
        if ('/'+self._trajectoryname) in backup_hdf5file:
            raise ValueError('I cannot backup  >>%s<< into file >>%s<<, there is already a '
                             'trajectory with that name.' % (traj.get_name(),backup_filename))

        backup_root = backup_hdf5file.root

        self._trajectorygroup._f_copy(newparent=backup_root,recursive=True)

        self._logger.info('Finished backup of %s.' % traj.get_name())

    def _trj_merge_trajectories(self,other_trajectory_name,rename_dict,*args,**kwargs):


        copy_nodes = kwargs.pop('copy_nodes', False)
        delete_trajectory = kwargs.pop('delete_trajectory', False)

        if copy_nodes and delete_trajectory:
            raise ValueError('You want to copy nodes, but delete the old trajectory, this is too '
                             'much overhead, please use copy_nodes = False, '
                             'delete_trajectory = True')


        # other_trajectory_name = other_trajectory.get_fullname()
        if not ('/'+other_trajectory_name) in self._hdf5file:
            raise ValueError('Cannot merge >>%s<< and >>%s<<, because the second trajectory cannot '
                             'be found in my file.')

        for old_name, new_name in rename_dict.iteritems():
            split_name = old_name.split('.')
            old_location = '/'+other_trajectory_name+'/'+'/'.join(split_name)


            split_name = new_name.split('.')
            new_location = '/'+self._trajectoryname+'/'+'/'.join(split_name)

            old_group = self._hdf5file.get_node(old_location)

            for node in old_group:

                if copy_nodes:
                     self._hdf5file.copy_node(where=old_location, newparent=new_location,
                                              name=node._v_name,createparents=True,
                                              recursive = True)
                else:
                    self._hdf5file.move_node(where=old_location, newparent=new_location,
                                             name=node._v_name,createparents=True )


        if delete_trajectory:
             self._hdf5file.remove_node(where='/', name=other_trajectory_name, recursive = True)


    def _trj_update_trajectory(self, traj, *args, **kwargs):

        changed_parameters = kwargs.pop('changed_parameters')
        new_results = kwargs.pop('new_results')

        infotable = getattr(self._trajectorygroup,'info_table')
        insert_dict = self._all_extract_insert_dict(traj,infotable.colnames)
        self._all_add_or_modify_row(traj.get_name(),insert_dict,infotable,0,[],
                                    HDF5StorageService.MODIFYROW)


        for result_name in new_results:
            result = traj.get(result_name)
            self._all_store_param_or_result_table_entry(result,'result_table',
                                                        flags=(HDF5StorageService.ADDROW,
                                                               HDF5StorageService.MODIFYROW))

        for param_name in changed_parameters:
            param = traj.get(param_name)
            self.store(globally.UPDATE_PARAMETER,param,*args,**kwargs)


        run_table = getattr(self._trajectorygroup,'run_table')
        actual_rows = run_table.nrows
        self._trj_fill_run_table_with_dummys(traj,actual_rows)


        for runname in traj.get_run_names():
            run_info = traj.get_run_information(runname)
            run_info['name'] = runname
            id = run_info['id']


            traj.prepare_paramspacepoint(id)
            run_summary=self._srn_add_explored_params(runname,traj._exploredparameters.values())


            run_info['explored_parameter_summary'] = run_summary

            self._all_add_or_modify_row(runname,run_info,run_table,id,[],
                                        flags=(HDF5StorageService.MODIFYROW,))

        traj.restore_default()


    def _trj_remove_incomplete_runs(self,traj,*args,**kwargs):

        self._logger.info('Removing incomplete runs.')
        count = 0
        for runname, info_dict in traj._run_information.iteritems():


            completed = info_dict['completed']

            dparams_group = self._trajectorygroup.derived_parameters
            result_group = self._trajectorygroup.results
            if completed == 0:
                if runname in dparams_group or runname in result_group:
                    self._logger.info('Removing run %s.' % runname)
                    count +=1

                if runname in dparams_group:
                    dparams_group._f_get_child(runname)._f_remove(recursive=True)

                if runname in result_group:
                    result_group._f_get_child(runname)._f_remove(recursive=True)

        self._logger.info('Finished removal of incomplete runs, removed %d runs.' % count)






    ######################## LOADING A TRAJECTORY #################################################

    def _trj_load_trajectory(self,msg, traj, *args, **kwargs):

        ''' Loads a single trajectory from a given file.

        Per default derived parameters and results are not loaded. If the filename is not specified
        the file where the current trajectory is supposed to be stored is taken.

        If the user wants to load results, the actual data is not loaded, only dummy objects
        are created, which must load their data independently. It is assumed that
        results of many simulations are large and should not be loaded all together into memory.

        If as_new the old trajectory is loaded into the new one, only parameters and derived
        trajectory parameters can be loaded
        '''

        as_new = kwargs.get('as_new')
        load_params = kwargs.get('load_params')
        load_derived_params = kwargs.get('load_derived_params')
        load_results = kwargs.get('load_results')

        if not as_new:
            # if not traj.is_empty():
            #     raise TypeError('You cannot load a trajectory from disk into a non-empty one.')
            traj._stored=True

        self._trj_load_meta_data(traj,as_new)




        if (as_new and (load_derived_params != globally.LOAD_NOTHING or load_results !=
                        globally.LOAD_NOTHING)):
            self._logger.warning('You cannot load a trajectory as new and load the derived '
                                 'parameters and results. Only parameters are allowed. I will ignore all derived parameters and results.')
            load_derived_params=globally.LOAD_NOTHING
            load_results=globally.LOAD_NOTHING

        if as_new and load_params != globally.LOAD_DATA:
            self._logger.warning('You cannot load the trajectory as new and not load the data of '
                                 'the parameters. I will load all parameter data.')
            load_params=globally.LOAD_DATA

        self._trj_load_config(traj, load_params)
        self._trj_load_params(traj, load_params)
        self._trj_load_derived_params(traj, load_derived_params)
        self._trj_load_results(traj, load_results)





    def _trj_load_meta_data(self,traj, as_new):


        metatable = self._trajectorygroup.info_table
        metarow = metatable[0]

        if as_new:
            length = metarow['lenght']
            for irun in range(length):
                traj._add_run_info(irun)
        else:
            traj._comment = metarow['comment']
            traj._time = metarow['timestamp']
            traj._formatted_time = metarow['time']
            traj._name = metarow['name']

            single_run_table = getattr(self._trajectorygroup,'run_table')

            for row in single_run_table.iterrows():
                name = row['name']
                id = row['id']
                timestamp = row['timestamp']
                time = row['time']
                completed = row['completed']
                traj._single_run_ids[id] = name
                traj._single_run_ids[name] = id

                info_dict = {}
                info_dict['id'] = id
                info_dict['timestamp'] = timestamp
                info_dict['time'] = time
                info_dict['completed'] = completed
                traj._run_information[name] = info_dict





    def _trj_load_config(self,traj,load_params):
        paramtable = self._trajectorygroup.config_table
        self._trj_load_any_param_or_result_table(globally.PARAMETER,traj,traj._config,paramtable,
                                                 load_params)

    def _trj_load_params(self,traj, load_params):
        paramtable = self._trajectorygroup.parameter_table
        self._trj_load_any_param_or_result_table(globally.PARAMETER,traj,traj._parameters,
                                                 paramtable, load_params)

    def _trj_load_derived_params(self,traj, load_derived_params):
        paramtable = self._trajectorygroup.derived_parameter_table
        self._trj_load_any_param_or_result_table(globally.PARAMETER,traj,traj._derivedparameters,
                                                 paramtable, load_derived_params)

    def _trj_load_results(self,traj, load_results):
        resulttable = self._trajectorygroup.result_table
        self._trj_load_any_param_or_result_table(globally.RESULT,traj,traj._results, resulttable,
                                                 load_results)


    def _trj_load_any_param_or_result_table(self,msg,traj, wheredict, paramtable, load_mode):
        ''' Loads a single parameter from a pytable.

        :param paramtable: The overiew pytable containing all parameters
        '''
        assert isinstance(paramtable,pt.Table)

        # if len(wheredict) != 0:
        #     raise ValueError('You cannot load instances from %s into your trajectory since your trajectory is not empty.'
        #     % paramtable._v_name)

        if (load_mode == globally.LOAD_SKELETON or
        load_mode == globally.LOAD_DATA or
        load_mode == globally.UPDATE_SKELETON):
            colnames = paramtable.colnames

            for row in paramtable.iterrows():
                location = row['location']
                name = row['name']
                fullname = location+'.'+name
                class_name = row['class_name']


                comment = row['comment']


                if fullname in wheredict:
                    if load_mode == globally.UPDATE_SKELETON:
                        continue
                    else:
                        self._logger.warn('Paremeter or Result >>%s<< is already in your '
                                          'trajectory, I am overwriting it.' % fullname)

                new_class = traj._create_class(class_name)
                paraminstance = new_class(fullname,comment=comment)
                assert isinstance(paraminstance, (BaseParameter,BaseResult))


                if 'length' in colnames:
                    size = row['length']
                    if size > 1 and size != len(traj):
                        raise RuntimeError('Your are loading a parameter >>%s<< with length %d, '
                                           'yet your trajectory has lenght %d, something is '
                                           'wrong!' % (fullname,size,len(traj)))
                    elif size > 1:
                        traj._exploredparameters[fullname]=paraminstance
                    elif size == 1:
                        pass
                    else:
                        RuntimeError('You shall not pass!')



                if load_mode == globally.LOAD_DATA:
                    self.load(msg, paraminstance)


                wheredict[fullname]=paraminstance

                traj._nninterface._add_to_nninterface(fullname, paraminstance)



    def _trj_store_meta_data(self,traj):
        ''' Stores general information about the trajectory in the hdf5file.

        The 'info_table' table will contain ththane name of the trajectory, it's timestamp, a comment,
        the length (aka the number of single runs), and if applicable a previous trajectory the
        current one was originally loaded from.
        The name of all derived and normal parameters as well as the results are stored in
        appropriate overview tables.
        Thes include the fullname, the name, the name of the class (e.g. SparseParameter),
        the size (1 for single parameter, >1 for explored parameter arrays).
        In case of a derived parameter or a result, the name of the creator trajectory or run
        and the id (-1 for trajectories) are stored.
        '''


        descriptiondict={'name': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                         'time': pt.StringCol(len(traj.get_time())),
                         'timestamp' : pt.FloatCol(),
                         'comment': pt.StringCol(len(traj.get_comment())),
                         'length':pt.IntCol()}
                         # 'loaded_from' : pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH)}

        infotable = self._all_get_or_create_table(where=self._trajectorygroup, tablename='info_table',
                                               description=descriptiondict)


        insert_dict = self._all_extract_insert_dict(traj,infotable.colnames)
        self._all_add_or_modify_row(traj.get_name(),insert_dict,infotable,[],[],
                                    flags=(HDF5StorageService.ADDROW,HDF5StorageService.MODIFYROW))


        rundescription_dict = {'name': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                         'time': pt.StringCol(len(traj.get_time())),
                         'timestamp' : pt.FloatCol(),
                         'id' : pt.IntCol(),
                         'completed' : pt.IntCol(),
                         'explored_parameter_summary' : pt.StringCol(globally.HDF5_STRCOL_MAX_COMMENT_LENGTH)}

        runtable = self._all_get_or_create_table(where=self._trajectorygroup,
                                                 tablename='run_table',
                                                 description=rundescription_dict)


        self._trj_fill_run_table_with_dummys(traj)



        tostore_dict =  {'config_table':traj._config,
                         'parameter_table':traj._parameters,
                         'derived_parameter_table':traj._derivedparameters,
                         'explored_parameter_table' :traj._exploredparameters,
                         'result_table' : traj._results}

        for key, dictionary in tostore_dict.items():

            paramdescriptiondict={'location': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                  'name': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                  'class_name': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                  'comment': pt.StringCol(globally.HDF5_STRCOL_MAX_COMMENT_LENGTH)}


            if not key == 'result_table':
                paramdescriptiondict.update({'length' : pt.IntCol()})
                paramdescriptiondict.update({'value' :pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH)})


            if key == 'explored_parameter_table':
                paramdescriptiondict.update({'array' : pt.StringCol(globally.HDF5_STRCOL_MAX_COMMENT_LENGTH)})

            paramtable = self._all_get_or_create_table(where=self._trajectorygroup, tablename=key,
                                                       description=paramdescriptiondict)

            paramtable.flush()



    def _trj_fill_run_table_with_dummys(self,traj, start=0):

        runtable = getattr(self._trajectorygroup,'run_table')

        assert isinstance(traj,Trajectory)

        for idx in range(start, len(traj)):
            name = traj.id2run(idx)
            insert_dict = traj.get_run_information(name)
            insert_dict['name']=name
            insert_dict['explored_parameter_summary'] = 'Ich verdiene mir Respekt mit Schweiss und Traenen!'

            self._all_add_or_modify_row('Dummy Row', insert_dict, runtable,[],[],flags=(HDF5StorageService.ADDROW,))

        runtable.flush()


    def _trj_store_trajectory(self, traj,*args,**kwargs):
        ''' Stores a trajectory to the in __init__ specified hdf5file.
        '''

        self._logger.info('Start storing Trajectory %s.' % self._trajectoryname)

        self._trj_store_meta_data(traj)

        self._all_store_dict(globally.UPDATE_PARAMETER,traj._config,*args,**kwargs)
        self._all_store_dict(globally.UPDATE_PARAMETER,traj._parameters,*args,**kwargs)
        self._all_store_dict(globally.UPDATE_RESULT,traj._results,*args,**kwargs)
        self._all_store_dict(globally.UPDATE_PARAMETER,traj._derivedparameters,*args,**kwargs)


        self._logger.info('Finished storing Trajectory.')



    ######################## Storing a Signle Run ##########################################

    def _srn_store_single_run(self,single_run):
        ''' Stores the derived parameters and results of a single run.
        '''

        assert isinstance(single_run,SingleRun)

        traj = single_run._single_run
        n = single_run.get_id()

        self._logger.info('Start storing run %d with name %s.' % (n,single_run.get_name()))




        paramtable = getattr(self._trajectorygroup, 'derived_parameter_table')

        self._all_store_dict(globally.PARAMETER,traj._derivedparameters)


        paramtable = getattr(self._trajectorygroup, 'result_table')

        self._all_store_dict(globally.RESULT,traj._results)

        # For better readability add the explored parameters to the results
        run_summary = self._srn_add_explored_params(single_run.get_name(),single_run._parent_trajectory._exploredparameters.values())
        table = getattr(self._trajectorygroup,'run_table')

        insert_dict = self._all_extract_insert_dict(single_run,table.colnames)
        insert_dict['explored_parameter_summary'] = run_summary
        insert_dict['completed'] = 1


        # unused_parameters = self._srn_get_unused_parameters(single_run)
        # insert_dict['unused_parameters'] = unused_parameters


        self._all_add_or_modify_row(single_run.get_name(),insert_dict,table,n,[],HDF5StorageService.MODIFYROW)


        self._logger.info('Finished storing run %d with name %s' % (n,single_run.get_name()))




    def _srn_add_explored_params(self, runname, paramlist):
        ''' Stores the explored parameters as a Node in the HDF5File under the results nodes for easier comprehension of the hdf5file.
        '''

        paramdescriptiondict={'location': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                'name': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                'class_name': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                'value' :pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH)}

        where = 'results.'+runname
        rungroup = self._all_create_groups(where)


        if not 'explored_parameter_table' in rungroup:
            paramtable = self._hdf5file.createTable(where=rungroup, name='explored_parameter_table',
                                                description=paramdescriptiondict, title='explored_parameter_table')
        else:
            paramtable = getattr(rungroup,'explored_parameter_table')

        runsummary = ''
        paramlist = sorted(paramlist, key= lambda name: name.get_name() + name.get_location())
        for idx,expparam in enumerate(paramlist):
            if idx > 0:
                runsummary = runsummary + ',   '

            valstr = expparam.val2str()
            if len(valstr) >= globally.HDF5_STRCOL_MAX_NAME_LENGTH:
                valstr = valstr[0:globally.HDF5_STRCOL_MAX_NAME_LENGTH-3]
                valstr+='...'
            runsummary = runsummary + expparam.get_name() + ': ' +valstr

            self._all_store_param_or_result_table_entry(expparam, paramtable,
                                                        (HDF5StorageService.ADDROW,
                                                         HDF5StorageService.MODIFYROW))

        return runsummary



    ######################################### Storing a Trajectory and a Single Run #####################
    def _all_store_param_or_result_table_entry(self,param_or_result,tablename_or_table, flags):
        ''' Stores a single overview table.

        Called from _trj_store_meta_data and store_single_run
        '''

        if isinstance(tablename_or_table, str):
            table = getattr(self._trajectorygroup, tablename_or_table)
        elif isinstance(tablename_or_table, pt.Table):
            table = tablename_or_table
        else:
            raise RuntimeError('You shall not pass!')

        assert isinstance(table, pt.Table)

        #check if the instance is already in the table
        location = param_or_result.get_location()
        name = param_or_result.get_name()
        fullname = param_or_result.get_fullname()

        condvars = {'namecol' : table.cols.name, 'locationcol' : table.cols.location,
                    'name' : name, 'location': location}

        condition = """(namecol == name) & (locationcol == location)"""


        colnames = set(table.colnames)

        if HDF5StorageService.REMOVEROW in flags:
            insert_dict={}
        else:
            insert_dict = self._all_extract_insert_dict(param_or_result,colnames)

        self._all_add_or_modify_row(fullname,insert_dict,table,condition,condvars,flags)

    def _all_get_or_create_table(self,where,tablename,description):

        where_node = self._hdf5file.get_node(where)

        if not tablename in where_node:
            table = self._hdf5file.createTable(where=where_node, name=tablename,
                                               description=description, title=tablename)
        else:
            table = where_node._f_get_child(tablename)

        return table

    def _all_add_or_modify_row(self, itemname, insert_dict, table, condition_or_row_index=None, condvars=None, flags=(ADDROW,MODIFYROW)):


        # A row index can be 0 so we have to add this annoying line
        if condition_or_row_index or condition_or_row_index==0:
            if isinstance(condition_or_row_index,str):
                rowiterator = table.where(condition_or_row_index,condvars=condvars)
            else:
                rowiterator = table.iterrows(condition_or_row_index,condition_or_row_index+1)

        else:
            rowiterator = None

        try:
            row = rowiterator.next()
        except:
            row = None


        if ((HDF5StorageService.MODIFYROW in flags or HDF5StorageService.ADDROW in flags) and
                HDF5StorageService.REMOVEROW in flags):
            raise ValueError('You cannot add or modify and remove a row at the same time.')

        if row == None and HDF5StorageService.ADDROW in flags:

            row = table.row

            self._all_insert_into_row(row,insert_dict)

            row.append()

        elif (row != None and HDF5StorageService.MODIFYROW in flags):


            self._all_insert_into_row(row,insert_dict)

            row.update()

        elif row != None and HDF5StorageService.REMOVEROW in flags:
            rownumber = row.nrow
            multiple_entries = False

            try:
                rowiterator.next()
                multiple_entries = True
            except StopIteration:
                pass

            if  multiple_entries:
                 raise RuntimeError('There is something entirely wrong, >>%s<< '
                                    'appears more than once in table %s.'
                                    %(itemname,table._v_name))

            table.remove_row(rownumber)
        else:
            raise RuntimeError('Something is wrong, you might not have found '
                               'a row, or your flags are not set approprialty')

        ## Check if there are 2 entries which should not happen
        multiple_entries = False
        try:
            rowiterator.next()
            multiple_entries = True
        except StopIteration:
            pass
        except AttributeError:
            pass

        if  multiple_entries:
             raise RuntimeError('There is something entirely wrong, >>%s<< '
                                'appears more than once in table %s.'
                                %(itemname,table._v_name))

        ## Check if we added something
        if row == None:
            raise RuntimeError('Could not add or modify entries of >>%s<< in '
                               'table %s' %(itemname,table._v_name))
        table.flush()

    def _all_store_dict(self, msg, data_dict,*args,**kwargs):
        for val in data_dict.itervalues():
            self.store(msg,val,*args,**kwargs)


    def _all_insert_into_row(self, row, insert_dict):

        for key, val in insert_dict.items():
            row[key] = val


    def _all_extract_insert_dict(self,item,colnames):
        insert_dict={}

        if 'length' in colnames:
            insert_dict['length'] = len(item)

        if 'comment' in colnames:
            insert_dict['comment'] = item.get_comment()

        if 'location' in colnames:
            insert_dict['location'] = item.get_location()

        if 'name' in colnames:
            insert_dict['name'] = item.get_name()

        if 'class_name' in colnames:
            insert_dict['class_name'] = item.get_classname()

        if 'value' in colnames:
            valstr = item.val2str()
            if len(valstr) >= globally.HDF5_STRCOL_MAX_NAME_LENGTH:
                valstr = valstr[0:globally.HDF5_STRCOL_MAX_NAME_LENGTH-1]
            insert_dict['value'] = valstr

        if 'creator_name' in colnames:
            insert_dict['creator_name'] = item.get_location().split('.')[1]

        if 'id' in colnames:
            insert_dict['id'] = item.get_id()

        if 'time' in colnames:
            insert_dict['time'] = item.get_time()

        if 'timestamp' in colnames:
            insert_dict['timestamp'] = item.get_timestamp()

        if 'array' in colnames:
            arraystr = str(item.get_array())
            if len(arraystr) >= globally.HDF5_STRCOL_MAX_COMMENT_LENGTH:
                arraystr=arraystr[0:globally.HDF5_STRCOL_MAX_COMMENT_LENGTH]
            insert_dict['array'] = arraystr

        # if 'loaded_from' in colnames:
        #     insert_dict['loaded_from'] = item.loaded_from()




        return insert_dict



    def _all_create_groups(self, key):
        newhdf5group = self._trajectorygroup
        split_key = key.split('.')
        for name in split_key:
            if not name in newhdf5group:
                newhdf5group=self._hdf5file.createGroup(where=newhdf5group, name=name, title=name)
            else:
                newhdf5group = getattr(newhdf5group, name)

        return newhdf5group



    ################# Storing and Loading Parameters ############################################


    def _prm_store_parameter_or_result(self, msg, param,*args,**kwargs):

        where = param.get_location().split('.')[0]
        tablename = HDF5StorageService.TABLENAME_MAPPING[where]

        self._all_store_param_or_result_table_entry(param,tablename,
                                                    flags=(HDF5StorageService.ADDROW,
                                                           HDF5StorageService.MODIFYROW))

        if isinstance(param, BaseParameter) and param.is_array():
            self._all_store_param_or_result_table_entry(param,'explored_parameter_table',
                                                        flags=(HDF5StorageService.ADDROW,
                                                           HDF5StorageService.MODIFYROW))

        fullname = param.get_fullname()
        self._logger.debug('Storing %s.' % fullname)
        store_dict = param._store()


        #self._check_dictionary_structure(store_dict)
        #self._prm_check_info_dict(param, store_dict)

        group= self._all_create_groups(fullname)

        for key, data_to_store in store_dict.items():
            if msg == globally.UPDATE_RESULT and  key in group:
                self._logger.debug('Found %s already in hdf5 node of %s, you are in result update mode so I will ignore it.' %(key, fullname))
                continue
            if isinstance(data_to_store, ObjectTable):
                self._prm_store_into_pytable(msg,key, data_to_store, group, fullname,*args,**kwargs)
            elif msg == globally.UPDATE_PARAMETER and key in group:
                self._logger.debug('Found %s already in hdf5 node of %s, you are in parameter update mode so I will ignore it.' %(key, fullname))
                continue
            elif isinstance(data_to_store, dict):
                self._prm_store_dict_as_table(msg,key, data_to_store, group, fullname,*args,**kwargs)
            elif isinstance(data_to_store,(list,tuple)) or isinstance(data_to_store,globally.PARAMETER_SUPPORTED_DATA):
                self._prm_store_into_array(msg,key, data_to_store, group, fullname,*args,**kwargs)
            elif isinstance(data_to_store, np.ndarray):
                self._prm_store_into_carray(msg,key, data_to_store, group, fullname,*args,**kwargs)
            elif isinstance(data_to_store,DataFrame):
                self._prm_store_data_frame(msg,key, data_to_store, group, fullname,*args,**kwargs)
            else:
                raise AttributeError('I don not know how to store %s of %s. Cannot handle type %s.'%(key,fullname,str(type(data_to_store))))


    def _prm_store_dict_as_table(self, msg, key, data_to_store, group, fullname,*args,**kwargs):

        if key in group:
            raise ValueError('Dictionary >>%s<< already exists in >>%s<<. Appending is not supported (yet).')


        assert isinstance(data_to_store,dict)

        if key in group:
            raise ValueError('Dict >>%s<< already exists in >>%s<<. Appending is not supported (yet).')

        temp_dict={}
        for innerkey, val in data_to_store.iteritems():
            temp_dict[innerkey] =[val]

        objtable = ObjectTable(data=temp_dict)

        self._prm_store_into_pytable(msg,key,objtable,group,fullname)
        self._prm_set_attributes_to_recall_natives(temp_dict,group._f_get_child(key),HDF5StorageService.DICTPREFIC)



    def _prm_store_data_frame(self, msg,  key, data_to_store, group, fullname,*args,**kwargs):

        try:

            if key in group:
                # if msg == globally.UPDATE_PARAMETER:
                #     return

                raise ValueError('DataFrame >>%s<< already exists in >>%s<<. Appending is not supported (yet).')



            assert isinstance(data_to_store,DataFrame)
            assert isinstance(group, pt.Group)

            name = group._v_pathname+'/' +key
            data_to_store.to_hdf(self._filename, name, append=True,data_columns=True)
        except:
            self._logger.error('Failed storing DataFrame >>%s<< of >>%s<<.' %(key,fullname))
            raise




    def _prm_store_into_carray(self, msg, key, data, group, fullname,*args,**kwargs):


        try:
            if key in group:
                # if append_mode == globally.UPDATE_PARAMETER:
                #     return

                raise ValueError('CArray >>%s<< already exists in >>%s<<. Appending is not supported (yet).')




            if isinstance(data, np.ndarray):
                size = data.size
            elif hasattr(data,'__len__'):
                size = len(data)
            else:
                size = 1

            if size == 0:
                self._logger.warning('>>%s<< of >>%s<< is empty, I will skip storing.' %(key,fullname))
                return

            carray=self._hdf5file.create_carray(where=group, name=key,obj=data)
        #carray[:]=data
            self._hdf5file.flush()
        except:
            self._logger.error('Failed storing array >>%s<< of >>%s<<.' % (key, fullname))
            raise


    def _prm_store_into_array(self, msg, key, data, group, fullname,*args,**kwargs):

        #append_mode = kwargs.get('append_mode',None)

        try:
            if key in group:
                # if append_mode == globally.UPDATE_PARAMETER:
                #     return

                raise ValueError('Array >>%s<< already exists in >>%s<<. Appending is not supported (yet).')


            if isinstance(data, np.ndarray):
                size = data.size
            elif hasattr(data,'__len__'):
                size = len(data)
            else:
                size = 1

            if size == 0:
                self._logger.warning('>>%s<< of >>%s<< is empty, I will skip storing.' %(key,fullname))
                return


            array=self._hdf5file.create_array(where=group, name=key,obj=data)
            self._prm_set_attributes_to_recall_natives(data,array,HDF5StorageService.ARRAYPREFIX)


            self._hdf5file.flush()
        except:
            self._logger.error('Failed storing array >>%s<< of >>%s<<.' % (key, fullname))
            raise



    def _prm_set_attributes_to_recall_natives(self, data, ptitem_or_dict, prefix):

            def _set_attribute_to_item_or_dict(item_or_dict, name,val):
                if isinstance(item_or_dict,dict):
                    item_or_dict[name]=val
                else:
                    item_or_dict.set_attr(name,val)

            if isinstance(data,tuple):
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLLTYPE,
                                HDF5StorageService.COLLTUPLE)

            elif isinstance(data,list):
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLLTYPE,
                                HDF5StorageService.COLLLIST)

            elif isinstance(data,np.ndarray):
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLLTYPE,
                                HDF5StorageService.COLLNDARRAY)

            elif isinstance(data, globally.PARAMETER_SUPPORTED_DATA):
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLLTYPE,
                                HDF5StorageService.COLLSCALAR)

                strtype = repr(type(data))

                if not strtype in globally.PARAMETERTYPEDICT:
                    raise TypeError('I do not know how to handel >>%s<< its type is >>%s<<.' %
                                   (str(data),str(type(data))))

                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.SCALARTYPE,strtype)

            elif isinstance(data, dict):
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLLTYPE,
                                HDF5StorageService.COLLDICT)

            else:
                raise TypeError('I do not know how to handel >>%s<< its type is >>%s<<.' %
                                   (str(data),str(type(data))))

            if isinstance(data, (list,tuple,np.ndarray)):
                if len(data) > 0:
                    strtype = repr(type(data[0]))

                    if not strtype in globally.PARAMETERTYPEDICT:
                        raise TypeError('I do not know how to handel >>%s<< its type is '
                                           '>>%s<<.' % (str(data),str(type(data))))

                    _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.SCALARTYPE,strtype)


    def _prm_remove_parameter_or_result(self, msg,param, *args,**kwargs):

        trajectory = kwargs.pop('trajectory')

        if param.get_fullname() in trajectory._exploredparameters:
            raise TypeError('You cannot remove an explored parameter of a trajectory stored '
                            'into an hdf5 file.')


        where = param.get_location().split('.')[0]
        tablename = HDF5StorageService.TABLENAME_MAPPING[where]

        self._all_store_param_or_result_table_entry(param,tablename,
                                                    flags=(HDF5StorageService.REMOVEROW,))

        split_name = param.get_fullname().split('.')
        node_name = split_name.pop()

        where = '/'+self._trajectoryname+'/' + '/'.join(split_name)

        self._hdf5file.remove_node(where=where,name=node_name,recursive=True)

        for irun in reversed(range(len(split_name))):
            where = '/'+self._trajectoryname+'/' + '/'.join(split_name[0:irun])
            node_name = split_name[irun]
            act_group = self._hdf5file.get_node(where=where,name=node_name)
            if len(act_group._v_leaves) + len(act_group._v_groups) == 0:
                self._hdf5file.remove_node(where=where,name=node_name,recursive=True)
            else:
                break

        trajectory._remove_only_from_trajectory(param.get_fullname())

    def _prm_check_info_dict(self,param, store_dict):
        ''' Checks if the storage dictionary contains an appropriate description of the parameter.
        This entry is called info, and should contain only a single
        :param param: The parameter to store
        :param store_dict: the dictionary that describes how to store the parameter
        '''
        if not 'info_table' in store_dict:
            store_dict['info_table']={}

        info_dict = store_dict['info_table']

        test_item = info_dict.itervalues().next()
        if len(test_item)>1:
            raise AttributeError('Your description of the parameter %s, generated by _store and '
                                 'stored into >>info<< has more than a single dictionary in the '
                                 'list.' % param.get_fullname())


        if not 'name' in info_dict:
            info_dict['name'] = [param.get_name()]
        else:
            assert info_dict['name'][0] == param.get_name()

        if not 'location' in info_dict:
            info_dict['location'] = [param.get_location()]
        else:
            assert info_dict['location'][0] == param.get_location()

        # if not 'comment' in info_dict:
        #     info_dict['comment'] = [param.get_comment()]
        # else:
        #     assert info_dict['comment'][0] == param.get_comment()

        if not 'type' in info_dict:
            info_dict['type'] = [str(type(param))]
        else:
            assert info_dict['type'][0] == str(type(param))


        if not 'class_name' in info_dict:
            info_dict['class_name'] = [param.__class__.__name__]
        else:
            assert info_dict['class_name'][0] == param.__class__.__name__




    def _prm_store_into_pytable(self,msg, tablename,data,hdf5group,fullname,*args,**kwargs):


        try:
            if hasattr(hdf5group,tablename):
                table = getattr(hdf5group,tablename)

                if msg == globally.UPDATE_PARAMETER:
                    nstart= table.nrows
                    datasize = data.shape[0]
                    if nstart==datasize:
                        self._logger.debug('There is no new data to the parameter >>%s<<. I will'
                                           'skip storage of table >>%s<<' % (fullname,tablename))
                        return
                else:
                    raise ValueError('Table %s already exists, appending is only supported for '
                                     'parameter merging and appending, please use >>msg= %s<<.' %
                                     (tablename,globally.UPDATE_PARAMETER))

                self._logger.debug('Found table %s in file %s, will append new entries in %s to the table.' %
                                   (tablename,self._filename, fullname))

                ## If the table exists, it already knows what the original data of the input was:
                data_type_dict = {}
            else:
                if msg == globally.UPDATE_PARAMETER:
                    self._logger.debug('Parameter table >>%s<< does not exist, I will create it!' % fullname)

                description_dict, data_type_dict = self._prm_make_description(data,fullname)
                table = self._hdf5file.createTable(where=hdf5group,name=tablename,description=description_dict,
                                                   title=tablename)
                nstart = 0

            assert isinstance(table,pt.Table)
            assert isinstance(data, ObjectTable)


            row = table.row

            datasize = data.shape[0]


            cols = data.columns.tolist()
            for n in range(nstart, datasize):

                for key in cols:

                    row[key] = data[key][n]

                row.append()

            for field_name, type_description in data_type_dict.iteritems():
                table.set_attr(field_name,type_description)

            table.flush()
            self._hdf5file.flush()
        except:
            self._logger.error('Failed storing table >>%s<< of >>%s<<.' %(tablename,fullname))
            raise



    def _prm_make_description(self, data, fullname):
        ''' Returns a dictionary that describes a pytbales row.
        '''
        def _convert_lists_and_tuples(series_of_data):
            ## If the first data item is a list, the rest must be as well, since
            # data has to be homogeneous
            if isinstance(series_of_data[0], (list,tuple)):
                for idx,item in enumerate(series_of_data):
                    series_of_data[idx] = np.array(item)

        descriptiondict={}
        original_data_type_dict={}

        for key, val in data.iteritems():

            self._prm_set_attributes_to_recall_natives(val[0],original_data_type_dict,
                            HDF5StorageService.FORMATTEDCOLPREFIX % key)


            _convert_lists_and_tuples(val)

            col = self._prm_get_table_col(key, val, fullname)

            # if col is None:
            #     raise TypeError('Entry %s of %s cannot be translated into pytables column' % (key,fullname))

            descriptiondict[key]=col

        return descriptiondict, original_data_type_dict


    def _prm_get_table_col(self, key, column, fullname):
        ''' Creates a pytables column instance.

        The type of column depends on the type of parameter entry.
        '''

        try:
            val = column[0]

            ## We do not want to loose int_
            if type(val) is int:
                return pt.IntCol()

            if isinstance(val,str):
                itemsize = int(self._prm_get_longest_stringsize(column))
                return pt.StringCol(itemsize)

            if isinstance(val, np.ndarray):
                if np.issubdtype(val.dtype,np.str):
                    itemsize = int(self._prm_get_longest_stringsize(column))
                    return pt.StringCol(itemsize,shape=val.shape)
                else:
                    return pt.Col.from_dtype(np.dtype((val.dtype,val.shape)))
            else:
                return pt.Col.from_dtype(np.dtype(type(val)))
        except Exception:
            self._logger.error('Failure in storing >>%s<< of Parameter/Result >>%s<<. Its type was >>%s<<.' % (key,fullname,str(type(val))))
            raise




    def _prm_get_longest_stringsize(self, string_list):
        ''' Returns the longest stringsize for a string entry across data.
        '''
        maxlength = 1

        for stringar in string_list:
            if not isinstance(stringar,np.ndarray):
                stringar = np.array([stringar])
            for string in stringar:
                maxlength = max(len(string),maxlength)

        # Make the string Col longer than needed in order to allow later on slightly large strings
        return maxlength*1.5



    def _prm_load_parameter_or_result(self, msg, param, *args,**kwargs):

        load_only = None
        if msg == globally.RESULT:
            load_only = kwargs.get('load_only',None)



        fullname = param.get_fullname()

        self._logger.debug('Loading %s' % fullname)

        try:
            hdf5group = eval('self._trajectorygroup.'+fullname)
        except Exception, e:
            raise AttributeError('Parameter or Result %s cannot be found in the hdf5file %s and trajectory %s'
                                 % (fullname,self._filename,self._trajectoryname))

        load_dict = {}
        for leaf in hdf5group:
            if not load_only is None:
                self._logger.debug('I am in load only mode, I will only lode %s, if I can find this data in result >>%s<<.'
                                   % (str(load_only),fullname))

                if not leaf._v_name in load_only:
                    continue

            if isinstance(leaf,pt.Table) and _attr_equals(leaf,
                                                          HDF5StorageService.DICTPREFIC+HDF5StorageService.COLLTYPE,
                                                          HDF5StorageService.COLLDICT):
                self._prm_read_dictionary(leaf, load_dict)
            elif isinstance(leaf, pt.Table):
                self._prm_read_table(leaf, load_dict)
            elif isinstance(leaf, (pt.CArray,pt.Array)):
                self._prm_read_array(leaf, load_dict)
            elif isinstance(leaf, pt.Group):
                self._prm_read_frame(leaf, load_dict)
            else:
                raise TypeError('Cannot load %s, do not understand the hdf5 file structure of %s.' %(fullname,str(leaf)))


        param._load(load_dict)

    def _prm_read_dictionary(self, leaf, load_dict):
        temp_dict={}
        self._prm_read_table(leaf,temp_dict)
        key =leaf._v_name
        temp_table = temp_dict[key]
        temp_dict = temp_table.to_dict('list')

        innder_dict = {}
        load_dict[key] = innder_dict
        for innerkey, vallist in temp_dict.items():
            innder_dict[innerkey] = vallist[0]


    def _prm_read_frame(self,group,load_dict):
        name = group._v_name
        pathname = group._v_pathname
        dataframe = read_hdf(self._filename,pathname,mode='r')
        load_dict[name] = dataframe

    def _prm_read_table(self,table,load_dict):
        ''' Reads a non-nested Pytables table column by column.

        :type table: pt.Table
        :type load_dict:
        :return:
        '''

        table_name = table._v_name

        for colname in table.colnames:
            col = table.col(colname)
            data_list=list(col)

            prefix = HDF5StorageService.FORMATTEDCOLPREFIX % colname
            for idx,data in enumerate(data_list):
                data,type_changed = self._prm_recall_native_type(data,table,prefix)
                if type_changed:
                    data_list[idx] = data
                else:
                    break

            if table_name in load_dict:
                load_dict[table_name][colname] = data_list
            else:
                load_dict[table_name] = ObjectTable(data={colname:data_list})


    def _prm_read_array(self, array, load_dict):

        #assert isinstance(carray,pt.CArray)
        array_name = array._v_name

        result = array.read()
        result, dummy = self._prm_recall_native_type(result,array,HDF5StorageService.ARRAYPREFIX)

        load_dict[array._v_name]=result



    def _prm_recall_native_type(self,data,ptitem,prefix):
            ## Numpy Scalars are converted to numpy arrays, but we want to retrieve tha numpy scalar
            # as it was
            typestr = _get_from_attrs(ptitem,prefix+HDF5StorageService.SCALARTYPE)
            type_changed = False

            if _attr_equals(ptitem, prefix+HDF5StorageService.COLLTYPE, HDF5StorageService.COLLSCALAR):
                if isinstance(data,np.ndarray):
                    data = np.array([data])[0]
                    type_changed = True


                if not typestr is None:
                    if not typestr == repr(type(data)):
                        data = globally.PARAMETERTYPEDICT[typestr](data)
                        type_changed = True


            elif (_attr_equals(ptitem, prefix+HDF5StorageService.COLLTYPE, HDF5StorageService.COLLTUPLE) or
                    _attr_equals(ptitem, prefix+HDF5StorageService.COLLTYPE, HDF5StorageService.COLLLIST)):

                if isinstance(data,np.ndarray):
                    type_changed=True

                data = list(data)

                if len(data)>0:
                    first_item = data[0]
                else:
                    first_item = None

                if not first_item is None:
                    if not typestr == repr(type(data)):
                        for idx,item in enumerate(data):
                            data[idx] = globally.PARAMETERTYPEDICT[typestr](item)
                            type_changed = True



                if _attr_equals(ptitem, prefix+HDF5StorageService.COLLTYPE, HDF5StorageService.COLLTUPLE):
                    data = tuple(data)
                    type_changed = True

            return data, type_changed






