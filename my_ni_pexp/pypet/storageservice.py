from numpy.oldnumeric.ma import _ptp
from wx._windows_ import new_MDIParentFrame

__author__ = 'Robert Meyer'

__version__ = "$Revision: 70b79ccd671a $"# $Source$

import logging
import tables as pt
import os
import numpy as np
from pypet import globally
import pypet.petexceptions as pex


from pypet.parameter import ObjectTable
from pandas import DataFrame, read_hdf





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


    def load(self,*args,**kwargs):
        try:
            self._lock.acquire()
            self._storage_service.load(*args,**kwargs)
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

    ADD_ROW = 'ADD'
    REMOVE_ROW = 'REMOVE'
    MODIFY_ROW = 'MODIFY'


    COLL_TYPE ='COLL_TYPE'

    COLL_LIST = 'COLL_LIST'
    COLL_TUPLE = 'COLL_TUPLE'
    COLL_NDARRAY = 'COLL_NDARRAY'
    COLL_MATRIX = 'COLL_MATRIX'
    COLL_SCALAR = 'COLL_SCALAR'
    COLL_DICT = 'COLL_DICT'


    SCALAR_TYPE = 'SCALAR_TYPE'

    ### Overview Table constants
    CONFIG = 'config'
    PARAMETERS = 'parameters'
    RESULTS = 'results'
    EXPLORED_PARAMETERS = 'explored_parameters'
    DERIVED_PARAMETERS = 'derived_parameters'

    TABLE_NAME_MAPPING = {

        PARAMETERS : 'parameter_table',
        CONFIG : 'config_table',
        DERIVED_PARAMETERS : 'derived_parameter_table',
        RESULTS : 'result_table',
        EXPLORED_PARAMETERS : 'explored_parameter_table'

    }


    ### Storing Data Constants
    STORAGE_TYPE= 'SRVC_STORE'

    ARRAY = 'ARRAY'
    CARRAY = 'CARRAY'
    EARRAY = 'EARRAY' # not supported yet
    VLARRAY = 'VLARRAY' # not supported yet
    DICT = 'DICT'
    TABLE = 'TABLE'
    FRAME = 'FRAME'

    TYPE_FLAG_MAPPING = {

        ObjectTable : TABLE,
        list:ARRAY,
        tuple:ARRAY,
        dict: DICT,
        np.ndarray:CARRAY,
        np.matrix:CARRAY,
        DataFrame : FRAME


    }

    for item in globally.PARAMETER_SUPPORTED_DATA:
        TYPE_FLAG_MAPPING[item]=ARRAY


    FORMATTED_COLUMN_PREFIX = 'SRVC_COLUMN_%s_'
    DATA_PREFIX = 'SRVC_DATA_'


    # ANNOTATION CONSTANTS
    ANNOTATION_PREFIX = 'SRVC_AN_'
    ANNOTATED ='SRVC_ANNOTATED'


    # Stuff necessary to construct parameters and result

    INIT_PREFIX = 'SRVC_INIT_'
    CLASS_NAME = INIT_PREFIX+'CLASS_NAME'
    COMMENT = INIT_PREFIX+'COMMENT'
    LENGTH = INIT_PREFIX+'LENGTH'
    # DETERMINES WHETHER
    LEAF = 'SRVC_LEAF'



    def __init__(self, filename=None, file_title='Experiment'):
        self._filename = filename
        self._file_title = file_title
        self._trajectory_name = None
        self._trajectory_index = None
        self._hdf5file = None
        self._trajectory_group = None
        self._logger = logging.getLogger('my_ni_pexp.storageservice_HDF5StorageService')




    def load(self,msg,stuff_to_load,*args,**kwargs):
        try:

            self._srvc_extract_file_information(kwargs)


            args = list(args)

            opened = self._srvc_opening_routine('r')


            if msg == globally.TRAJECTORY:
                self._trj_load_trajectory(msg,stuff_to_load,*args,**kwargs)


            elif msg == globally.LEAF:
                self._prm_load_parameter_or_result(stuff_to_load,*args,**kwargs)

            elif msg ==globally.LIST:
                self._srvc_load_several_items(stuff_to_load,*args,**kwargs)

            elif (msg == globally.GROUP):
                self._node_load_node(stuff_to_load,*args,**kwargs)

            elif msg == globally.TREE:
                self._tree_load_tree(stuff_to_load,*args,**kwargs)

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

            elif msg == globally.SINGLE_RUN:

                self._srn_store_single_run(stuff_to_store,*args,**kwargs)

            elif msg in (globally.LEAF, globally.UPDATE_LEAF):
                self._prm_store_parameter_or_result(msg,stuff_to_store,*args,**kwargs)

            elif msg == globally.REMOVE:
                self._all_remove_parameter_or_result(stuff_to_store,*args,**kwargs)

            elif msg == globally.GROUP:
                self._node_store_node(stuff_to_store,*args,**kwargs)

            elif msg == globally.REMOVE_INCOMPLETE_RUNS:
                self._trj_remove_incomplete_runs(stuff_to_store,*args,**kwargs)

            elif msg == globally.TREE:
                self._tree_store_tree(stuff_to_store,*args,**kwargs)

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
                                                 title=self._file_title)
                    if not ('/'+self._trajectory_name) in self._hdf5file:
                        if not msg == globally.TRAJECTORY:
                            raise ValueError('Your trajectory cannot be found in the hdf5file, '
                                             'please use >>traj.store()<< before storing anyhting else.')
                        self._hdf5file.createGroup(where='/', name= self._trajectory_name,
                                                   title=self._trajectory_name)


                    self._trajectory_group = self._hdf5file.get_node('/'+self._trajectory_name)

                elif mode == 'r':
                    
                    if not self._trajectory_name is None and not self._trajectory_index is None:
                    
                        raise ValueError('Please specify either a name of a trajectory or an index'
                                     'but not both at the same time.')
                    
                    ### Fuck Pandas, we have to wait until the next relaese until this is supported:
                    mode = 'a'
                    if not os.path.isfile(self._filename):
                        raise ValueError('Filename ' + self._filename + ' does not exist.')

                    self._hdf5file = pt.openFile(filename=self._filename, mode=mode,
                                                 title=self._file_title)

                    if not self._trajectory_index is None:
                        
                        nodelist = self._hdf5file.listNodes(where='/')

                        if (self._trajectory_index >= len(nodelist) or
                                    self._trajectory_index  < -len(nodelist)):
                            raise ValueError('Trajectory No. %d does not exists, there are only '
                                             '%d trajectories in %s.'
                                            % (self._trajectory_name,len(nodelist),self._filename))

                        self._trajectory_group = nodelist[self._trajectory_index]
                        self._trajectory_name = self._trajectory_group._v_name
                        
                    elif not self._trajectory_name is None:
                        
                        if not ('/'+self._trajectory_name) in self._hdf5file:
                            raise ValueError('File %s does not contain trajectory %s.'
                                             % (self._filename, self._trajectory_name))
                        self._trajectory_group = self._hdf5file.get_node('/'+self._trajectory_name)
                    else:
                        raise ValueError('Please specify a name of a trajectory to load or its'
                                         'index, otherwise I cannot open one.')

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
            self._trajectory_group = None
            self._trajectory_name = None
            self._trajectory_index=None
            return True
        else:
            return False

    def _srvc_extract_file_information(self,kwargs):
        if 'filename' in kwargs:
            self._filename=kwargs.pop('filename')

        if 'file_title' in kwargs:
            self._file_title = kwargs.pop('file_title')

        if 'trajectory_name' in kwargs:
            self._trajectory_name = kwargs.pop('trajectory_name')

        if 'trajectory_index' in kwargs:
            self._trajectory_index = kwargs.pop('trajectory_index')





    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        result['_lock'] = None
        return result

    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._logger = logging.getLogger('my_ni_pexp.storageservice_HDF5StorageService=' +
                                         self._filename)


    ########################### MERGING ###########################################################

    def _trj_backup_trajectory(self,traj, backup_filename=None):

        self._logger.info('Storing backup of %s.' % traj.v_name)

        mypath, filename = os.path.split(self._filename)

        if backup_filename is None:
            backup_filename ='%s/backup_%s_.hdf5' % (mypath,traj.v_name)

        backup_hdf5file = pt.openFile(filename=backup_filename, mode='a', title=backup_filename)
        
        if ('/'+self._trajectory_name) in backup_hdf5file:
            
            raise ValueError('I cannot backup  >>%s<< into file >>%s<<, there is already a '
                             'trajectory with that name.' % (traj.v_name,backup_filename))

        backup_root = backup_hdf5file.root

        self._trajectory_group._f_copy(newparent=backup_root,recursive=True)

        self._logger.info('Finished backup of %s.' % traj.v_name)

    def _trj_merge_trajectories(self,other_trajectory_name,rename_dict,copy_nodes=True,
                                delete_trajectory=False):


        if copy_nodes and delete_trajectory:
            raise ValueError('You want to copy nodes, but delete the old trajectory, this is too '
                             'much overhead, please use copy_nodes = False, '
                             'delete_trajectory = True')


        # other_trajectory_name = other_trajectory.v_full_name
        if not ('/'+other_trajectory_name) in self._hdf5file:
            raise ValueError('Cannot merge >>%s<< and >>%s<<, because the second trajectory cannot '
                             'be found in my file.')

        for old_name, new_name in rename_dict.iteritems():
            split_name = old_name.split('.')
            old_location = '/'+other_trajectory_name+'/'+'/'.join(split_name)


            split_name = new_name.split('.')
            new_location = '/'+self._trajectory_name+'/'+'/'.join(split_name)

            old_group = self._hdf5file.get_node(old_location)



            for node in old_group:

                if copy_nodes:
                     self._hdf5file.copy_node(where=old_location, newparent=new_location,
                                              name=node._v_name,createparents=True,
                                              recursive = True)


                else:
                    self._hdf5file.move_node(where=old_location, newparent=new_location,
                                             name=node._v_name,createparents=True )

            old_group._v_attrs._f_copy(where = self._hdf5file.get_node(new_location))


        if delete_trajectory:
             self._hdf5file.remove_node(where='/', name=other_trajectory_name, recursive = True)


    def _trj_update_trajectory(self, traj,changed_parameters,new_results):

        # changed_parameters = kwargs.pop('changed_parameters')
        # new_results = kwargs.pop('new_results')
        # changed_groups = kwargs.pop('changed_nodes')

        infotable = getattr(self._trajectory_group,'info_table')
        insert_dict = self._all_extract_insert_dict(traj,infotable.colnames)
        self._all_add_or_modify_row(traj.v_name,insert_dict,infotable,index=0,
                                    flags=(HDF5StorageService.MODIFY_ROW,))




        ## We only add the table entries, since we can f_merge via the hdf5 storage service
        for result_name in new_results:
            result = traj.f_get(result_name)
            tablename='result_table'
            table = getattr(self._trajectory_group,tablename)
            self._all_store_param_or_result_table_entry(result,table,
                                                        flags=(HDF5StorageService.ADD_ROW,
                                                               HDF5StorageService.MODIFY_ROW))
        ### Store the parameters
        for param_name in changed_parameters:
            param = traj.f_get(param_name)
            self.store(globally.UPDATE_LEAF,param)

        # ### Store the changed groups
        # for group_node in changed_groups:
        #     self.store(globally.GROUP,group_node)

        run_table = getattr(self._trajectory_group,'run_table')
        actual_rows = run_table.nrows
        self._trj_fill_run_table_with_dummys(traj,actual_rows)


        for run_name in traj.f_get_run_names():
            run_info = traj.f_get_run_information(run_name)
            run_info['name'] = run_name
            idx = run_info['idx']


            traj.f_prepare_parameter_space_point(idx)
            run_summary=self._srn_add_explored_params(run_name,traj._explored_parameters.values())


            run_info['parameter_summary'] = run_summary

            self._all_add_or_modify_row(run_name,run_info,run_table,index=idx,
                                        flags=(HDF5StorageService.MODIFY_ROW,))

        traj.f_restore_default()


    def _trj_remove_incomplete_runs(self,traj,*args,**kwargs):

        self._logger.info('Removing incomplete runs.')
        count = 0
        for run_name, info_dict in traj._run_information.iteritems():


            completed = info_dict['completed']

            dparams_group = self._trajectory_group.derived_parameters
            result_group = self._trajectory_group.results
            if completed == 0:
                if run_name in dparams_group or run_name in result_group:
                    self._logger.info('Removing run %s.' % run_name)
                    count +=1

                if run_name in dparams_group:
                    dparams_group._f_get_child(run_name)._f_remove(recursive=True)

                if run_name in result_group:
                    result_group._f_get_child(run_name)._f_remove(recursive=True)

        self._logger.info('Finished removal of incomplete runs, removed %d runs.' % count)






    ######################## LOADING A TRAJECTORY #################################################

    def _trj_load_trajectory(self,msg, traj, as_new, load_params,load_derived_params,load_results):

        ''' Loads a single trajectory from a given file.

        Per default derived parameters and results are not loaded. If the filename is not specified
        the file where the current trajectory is supposed to be stored is taken.

        If the user wants to load results, the actual data is not loaded, only dummy objects
        are created, which must load their data independently. It is assumed that
        results of many simulations are large and should not be loaded all together into memory.

        If as_new the old trajectory is loaded into the new one, only parameters and derived
        trajectory parameters can be loaded
        '''

        # as_new = kwargs.pop('as_new')
        # load_params = kwargs.pop('load_parameters')
        # load_derived_params = kwargs.pop('load_derived_parameters')
        # load_results = kwargs.pop('load_results')

        if not as_new:
            # if not traj.f_is_empty():
            #     raise TypeError('You cannot f_load a trajectory from disk into a non-_empty one.')
            traj._stored=True

        self._trj_load_meta_data(traj,as_new)
        self._ann_load_annotations(traj,self._trajectory_group)





        if (as_new and (load_derived_params != globally.LOAD_NOTHING or load_results !=
                        globally.LOAD_NOTHING)):
            raise ValueError('You cannot load a trajectory as new and load the derived '
                                 'parameters and results. Only parameters are allowed.')


        if as_new and load_params != globally.LOAD_DATA:
            raise ValueError('You cannot load the trajectory as new and not load the data of '
                                 'the parameters.')


        self._ann_load_annotations(traj,self._trajectory_group)

        for what,loading in ( ('config',load_params),('parameters',load_params),
                             ('derived_parameters',load_derived_params),
                             ('results',load_results) ):

            if loading != globally.LOAD_NOTHING:
                self._trj_load_sub_branch(traj,traj,what,self._trajectory_group,loading)




    def _trj_load_meta_data(self,traj, as_new):


        metatable = self._trajectory_group.info_table
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

            single_run_table = getattr(self._trajectory_group,'run_table')

            for row in single_run_table.iterrows():
                name = row['name']
                id = row['idx']
                timestamp = row['timestamp']
                time = row['time']
                completed = row['completed']
                summary=row['parameter_summary']
                traj._single_run_ids[id] = name
                traj._single_run_ids[name] = id

                info_dict = {}
                info_dict['idx'] = id
                info_dict['timestamp'] = timestamp
                info_dict['time'] = time
                info_dict['completed'] = completed
                info_dict['name'] = name
                info_dict['parameter_summary'] = summary
                traj._run_information[name] = info_dict



    def _trj_load_sub_branch(self,traj,traj_node,branch_name,hdf5_group,load_data):

        split_names = branch_name.split('.')

        leaf_name = split_names.pop()

        for name in split_names:

            hdf5_group = getattr(hdf5_group,name)


            if not name in traj:
                traj_node=traj_node._nn_interface._add_from_group_name(traj_node,name)
                load_annotations = True
            else:
                traj_node=traj_node._children[name]

            if load_annotations or load_data in [globally.LOAD_SKELETON,globally.LOAD_DATA]:
                self._ann_load_annotations(traj_node,hdf5_group)

        hdf5_group = getattr(hdf5_group,leaf_name)
        self._tree_load_recursively(traj,traj_node,hdf5_group,load_data)



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
                         'time': pt.StringCol(len(traj.v_time)),
                         'timestamp' : pt.FloatCol(),
                         'comment':  pt.StringCol(globally.HDF5_STRCOL_MAX_COMMENT_LENGTH),
                         'length':pt.IntCol()}
                         # 'loaded_from' : pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH)}

        infotable = self._all_get_or_create_table(where=self._trajectory_group, tablename='info_table',
                                               description=descriptiondict)


        insert_dict = self._all_extract_insert_dict(traj,infotable.colnames)
        self._all_add_or_modify_row(traj.v_name,insert_dict,infotable,
                                    flags=(HDF5StorageService.ADD_ROW,HDF5StorageService.MODIFY_ROW))


        rundescription_dict = {'name': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                         'time': pt.StringCol(len(traj.v_time)),
                         'timestamp' : pt.FloatCol(),
                         'idx' : pt.IntCol(),
                         'completed' : pt.IntCol(),
                         'parameter_summary' : pt.StringCol(globally.HDF5_STRCOL_MAX_COMMENT_LENGTH)}

        runtable = self._all_get_or_create_table(where=self._trajectory_group,
                                                 tablename='run_table',
                                                 description=rundescription_dict)


        self._trj_fill_run_table_with_dummys(traj)

        self._ann_store_annotations(traj,self._trajectory_group)


        tostore_dict =  {'config_table':traj._config,
                         'parameter_table':traj._parameters,
                         'derived_parameter_table':traj._derived_parameters,
                         'explored_parameter_table' :traj._explored_parameters,
                         'result_table' : traj._results}

        for key, dictionary in tostore_dict.items():

            paramdescriptiondict={'location': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                  'name': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                  'class_name': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                  'comment': pt.StringCol(globally.HDF5_STRCOL_MAX_COMMENT_LENGTH),
                                  'value' :pt.StringCol(globally.HDF5_STRCOL_MAX_COMMENT_LENGTH)}


            if not key == 'result_table':
                paramdescriptiondict.update({'length' : pt.IntCol()})


            if key == 'explored_parameter_table':
                paramdescriptiondict.update({'array' : pt.StringCol(globally.HDF5_STRCOL_MAX_COMMENT_LENGTH)})

            paramtable = self._all_get_or_create_table(where=self._trajectory_group, tablename=key,
                                                       description=paramdescriptiondict)

            paramtable.flush()



    def _trj_fill_run_table_with_dummys(self,traj, start=0):

        runtable = getattr(self._trajectory_group,'run_table')

        #assert isinstance(traj,Trajectory)

        for idx in range(start, len(traj)):
            name = traj.f_idx_to_run(idx)
            insert_dict = traj.f_get_run_information(name)

            self._all_add_or_modify_row('Dummy Row', insert_dict, runtable,flags=(HDF5StorageService.ADD_ROW,))

        runtable.flush()


    def _trj_store_trajectory(self, traj):
        ''' Stores a trajectory to the in __init__ specified hdf5file.
        '''

        self._logger.info('Start storing Trajectory %s.' % self._trajectory_name)

        self._trj_store_meta_data(traj)


        self._ann_store_annotations(traj,self._trajectory_group)

        self._tree_store_recursively(globally.LEAF,traj.config,self._trajectory_group)
        ## If we extended a trajectory we want to call update in any case
        self._tree_store_recursively(globally.UPDATE_LEAF,traj.parameters,self._trajectory_group)
        self._tree_store_recursively(globally.LEAF,traj.derived_parameters,self._trajectory_group)
        self._tree_store_recursively(globally.LEAF,traj.results,self._trajectory_group)


        self._logger.info('Finished storing Trajectory.')






    def _trj_store_sub_branch(self,msg,traj_node,branch_name,hdf5_group):

        split_names = branch_name.split('.')


        leaf_name = split_names.pop()

        for name in split_names:


            traj_node = traj_node._children[name]

            if not hasattr(hdf5_group,name):
                hdf5_group=self._hdf5file.create_group(where=hdf5_group,name=name)
            else:
                hdf5_group=getattr(hdf5_group,name)

            self._ann_store_annotations(traj_node,hdf5_group)

        traj_node = traj_node._children[leaf_name]

        self._tree_store_recursively(msg,traj_node,hdf5_group)

    ########################  Storing Sub Trees ###########################################

    def _tree_load_recursively(self,traj, parent_traj_node, hdf5group,
                              load_data=globally.UPDATE_SKELETON, recursive=True):

        path_name = parent_traj_node.v_full_name
        name = hdf5group._v_name

        if not name in parent_traj_node._children and load_data==globally.LOAD_ANNOTATIONS:
            return

        is_leaf = self._all_get_from_attrs(hdf5group,HDF5StorageService.LEAF)

        if is_leaf:

            if path_name=='':
                full_name=name
            else:
                full_name = '%s.%s' % (path_name,name)


            in_trajectory =  name in parent_traj_node._children
            if in_trajectory:
                instance=parent_traj_node._children[name]

                if load_data == globally.UPDATE_SKELETON :
                    return

                if (not instance.f_is_empty()
                    and load_data == globally.UPDATE_DATA):
                    return

                if load_data == globally.LOAD_ANNOTATIONS:
                    self._ann_load_annotations(instance,node=hdf5group)
                    return


            if not in_trajectory or load_data==globally.LOAD_DATA:
                class_name = self._all_get_from_attrs(hdf5group,HDF5StorageService.CLASS_NAME)
                comment = self._all_get_from_attrs(hdf5group,HDF5StorageService.COMMENT)


                length = self._all_get_from_attrs(hdf5group,HDF5StorageService.LENGTH)

                if not length is None and length >1 and length != len(traj):
                        raise RuntimeError('Something is completely odd. Yo load parameter'
                                               ' >>%s<< of length %d into a trajectory of length'
                                               ' %d. They should be equally long!'  %
                                               (full_name,length,len(traj)))

                class_constructor = traj._create_class(class_name)
                instance = class_constructor(name,comment=comment)

                parent_traj_node._nn_interface._add_from_leaf_instance(parent_traj_node,instance)
                self._ann_load_annotations(instance,node=hdf5group)



            if load_data in [globally.LOAD_DATA, globally.UPDATE_DATA]:
                self._prm_load_parameter_or_result(instance,_hdf5_group=hdf5group)
        else:

            if not name in parent_traj_node._children:
                new_traj_node = parent_traj_node._nn_interface._add_from_group_name(
                                                                            parent_traj_node, name)
                newly_created = True
            else:
                new_traj_node = parent_traj_node._children[name]
                newly_created=False

            if (load_data in [globally.LOAD_DATA, globally.LOAD_SKELETON,globally.LOAD_ANNOTATIONS] or
                                            newly_created):

                self._ann_load_annotations(new_traj_node,node=hdf5group)

            if recursive:
                for new_hdf5group in hdf5group._f_iter_nodes(classname='Group'):
                    self._tree_load_recursively(traj,new_traj_node,new_hdf5group,load_data)


    def _tree_store_recursively(self,msg, traj_node, parent_hdf5_group, recursive = True):


        name = traj_node.v_name

        if not hasattr(parent_hdf5_group,name):
            new_hdf5_group = self._hdf5file.create_group(where=parent_hdf5_group,name=name)
            msg = globally.UPDATE_LEAF
        else:
            new_hdf5_group = getattr(parent_hdf5_group,name)


        if traj_node.v_leaf:

            self._prm_store_parameter_or_result(msg, traj_node, _hdf5_group=new_hdf5_group)

        else:
            self._node_store_node(traj_node,_hdf5_group=new_hdf5_group)

            if recursive:
                for child in traj_node._children.itervalues():

                    self._tree_store_recursively(msg,child,new_hdf5_group)

    def _tree_store_tree(self,traj_node,recursive):
        location = traj_node.v_location

        hdf5_location = location.replace('.','/')

        try:
            parent_hdf5_node = self._hdf5file.get_node(where=self._trajectory_group,name=hdf5_location)
        except pt.NoSuchNodeError:
            self._logger.error('Cannot store >>%s<< the parental hdf5 node with path >>%s<< does '
                               'not exist! Store the parental node first!' %
                               (traj_node.v_name,hdf5_location))
            raise

        self._tree_store_recursively(globally.LEAF,traj_node,parent_hdf5_node,recursive)

    def _tree_load_tree(self,parent_traj_node,child_name,recursive,load_data,trajectory):

        if parent_traj_node.f_is_root():
            full_child_name = child_name
        else:
            full_child_name = parent_traj_node.v_full_name+'.'+child_name

        hdf5_node_name =full_child_name.replace('.','/')

        try:
            hdf5_node = self._hdf5file.get_node(where=self._trajectory_group,name = hdf5_node_name)
        except pt.NoSuchNodeError:
            self._logger.error('Cannot load >>%s<< the hdf5 node >>%s<< does not exist!'
                                % (child_name,hdf5_node_name))

            raise

        self._tree_load_recursively(trajectory,parent_traj_node,hdf5_node,load_data,recursive)




    ######################## Storing a Signle Run ##########################################

    def _srn_store_single_run(self,single_run,*args,**kwargs):
        ''' Stores the derived parameters and results of a single run.
        '''

        #assert isinstance(single_run,SingleRun)

        idx = single_run.v_idx

        self._logger.info('Start storing run %d with name %s.' % (idx,single_run.v_name))

        for branch in ('results','derived_parameters'):
            branch_name = branch +'.'+single_run.v_name
            if branch_name in single_run:
                self._trj_store_sub_branch(globally.LEAF,single_run,
                                           branch_name,self._trajectory_group)

        # For better readability add the explored parameters to the results
        run_summary = self._srn_add_explored_params(single_run.v_name,
                                                    single_run._explored_parameters.values())

        table = getattr(self._trajectory_group,'run_table')

        insert_dict = self._all_extract_insert_dict(single_run,table.colnames)
        insert_dict['parameter_summary'] = run_summary
        insert_dict['completed'] = 1


        # unused_parameters = self._srn_get_unused_parameters(single_run)
        # insert_dict['unused_parameters'] = unused_parameters


        self._all_add_or_modify_row(single_run, insert_dict, table,
                                    index=idx,flags=(HDF5StorageService.MODIFY_ROW,))


        self._logger.info('Finished storing run %d with name %s' % (idx,single_run.v_name))



    def _srn_add_explored_params(self, name, paramlist):
        ''' Stores the explored parameters as a Node in the HDF5File under the results nodes for easier comprehension of the hdf5file.
        '''

        paramdescriptiondict={'location': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                'name': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                'class_name': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                'value' :pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH)}

        where = 'results.'+name


        where = where.replace('.','/')
        add_table =where in self._trajectory_group
        if add_table:
            rungroup = getattr(self._trajectory_group,where)


            if not 'explored_parameter_table' in rungroup:
                paramtable = self._hdf5file.createTable(where=rungroup, name='explored_parameter_table',
                                                    description=paramdescriptiondict, title='explored_parameter_table')
            else:
                paramtable = getattr(rungroup,'explored_parameter_table')

        runsummary = ''
        paramlist = sorted(paramlist, key= lambda name: name.v_name + name.v_location)
        for idx,expparam in enumerate(paramlist):
            if idx > 0:
                runsummary = runsummary + ',   '

            valstr = expparam.f_val_to_str()
            if len(valstr) >= globally.HDF5_STRCOL_MAX_NAME_LENGTH:
                valstr = valstr[0:globally.HDF5_STRCOL_MAX_NAME_LENGTH-3]
                valstr+='...'
            runsummary = runsummary + expparam.v_name + ': ' +valstr

            if add_table:
                self._all_store_param_or_result_table_entry(expparam, paramtable,
                                                        (HDF5StorageService.ADD_ROW,
                                                         HDF5StorageService.MODIFY_ROW))

        return runsummary



    ######################################### Storing a Trajectory and a Single Run #####################
    def _all_store_param_or_result_table_entry(self,param_or_result,table, flags):
        ''' Stores a single overview table.

        Called from _trj_store_meta_data and store_single_run
        '''
        #assert isinstance(table, pt.Table)

        #check if the instance is already in the table
        location = param_or_result.v_location
        name = param_or_result.v_name
        fullname = param_or_result.v_full_name

        condvars = {'namecol' : table.cols.name, 'locationcol' : table.cols.location,
                    'name' : name, 'location': location}

        condition = """(namecol == name) & (locationcol == location)"""


        colnames = set(table.colnames)

        if HDF5StorageService.REMOVE_ROW in flags:
            insert_dict={}
        else:
            insert_dict = self._all_extract_insert_dict(param_or_result,colnames)

        self._all_add_or_modify_row(fullname,insert_dict,table,condition=condition,
                                    condvars=condvars,flags=flags)


    def _all_get_or_create_table(self,where,tablename,description):

        where_node = self._hdf5file.get_node(where)

        if not tablename in where_node:
            table = self._hdf5file.createTable(where=where_node, name=tablename,
                                               description=description, title=tablename)
        else:
            table = where_node._f_get_child(tablename)

        return table

    def _all_get_node_by_name(self,name):
        path_name = name.replace('.','/')
        where = '/%s/%s' %(self._trajectory_name,path_name)
        return self._hdf5file.get_node(where=where)

    @staticmethod
    def _all_attr_equals(ptitem,name,value):
        return name in ptitem._v_attrs and ptitem._v_attrs[name] == value

    @staticmethod
    def _all_get_from_attrs(ptitem,name):
        if name in ptitem._v_attrs:
            return ptitem._v_attrs[name]
        else:
            return None



    def _all_recall_native_type(self,data,ptitem,prefix):
            ## Numpy Scalars are converted to numpy arrays, but we want to retrieve tha numpy scalar
            # as it was
            typestr = self._all_get_from_attrs(ptitem,prefix+HDF5StorageService.SCALAR_TYPE)
            type_changed = False

            if self._all_attr_equals(ptitem, prefix+HDF5StorageService.COLL_TYPE,
                                     HDF5StorageService.COLL_SCALAR):

                if isinstance(data,np.ndarray):
                    data = np.array([data])[0]
                    type_changed = True


                if not typestr is None:
                    if not typestr == repr(type(data)):
                        data = globally.PARAMETERTYPEDICT[typestr](data)
                        type_changed = True


            elif (self._all_attr_equals(ptitem, prefix+HDF5StorageService.COLL_TYPE,
                                         HDF5StorageService.COLL_TUPLE) or
                    self._all_attr_equals(ptitem, prefix+HDF5StorageService.COLL_TYPE,
                                           HDF5StorageService.COLL_LIST)):

                if not isinstance(data,(list,tuple)):
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



                if self._all_attr_equals(ptitem, prefix+HDF5StorageService.COLL_TYPE,
                                          HDF5StorageService.COLL_TUPLE):
                    data = tuple(data)
                    type_changed = True

            elif self._all_attr_equals(ptitem, prefix+HDF5StorageService.COLL_TYPE,
                                          HDF5StorageService.COLL_MATRIX):
                    data = np.matrix(data)
                    type_changed = True

            return data, type_changed

    def _all_add_or_modify_row(self, item_name, insert_dict, table,index=None, condition=None,
                               condvars=None, flags=(ADD_ROW,MODIFY_ROW,)):


        # A row index can be 0 so we have to add this annoying line
        if not index is None and not condition is None:
            raise ValueError('Please give either a condition or an index or none!')
        elif not condition is None:
            row_iterator = table.where(condition,condvars=condvars)
        elif not index is None:
            row_iterator = table.iterrows(index,index+1)
        else:
            row_iterator = None

        try:
            row = row_iterator.next()
        except AttributeError:
            row = None
        except StopIteration:
            row = None


        if ((HDF5StorageService.MODIFY_ROW in flags or HDF5StorageService.ADD_ROW in flags) and
                HDF5StorageService.REMOVE_ROW in flags):
            raise ValueError('You cannot add or modify and remove a row at the same time.')

        if row == None and HDF5StorageService.ADD_ROW in flags:

            row = table.row

            self._all_insert_into_row(row,insert_dict)

            row.append()

        elif (row != None and HDF5StorageService.MODIFY_ROW in flags):


            self._all_insert_into_row(row,insert_dict)

            row.update()

        elif row != None and HDF5StorageService.REMOVE_ROW in flags:
            rownumber = row.nrow
            multiple_entries = False

            try:
                row_iterator.next()
                multiple_entries = True
            except StopIteration:
                pass

            if  multiple_entries:
                 raise RuntimeError('There is something entirely wrong, >>%s<< '
                                    'appears more than once in table %s.'
                                    %(item_name,table._v_name))

            table.remove_row(rownumber)
        else:
            raise RuntimeError('Something is wrong, you might not have found '
                               'a row, or your flags are not f_set approprialty')

        ## Check if there are 2 entries which should not happen
        multiple_entries = False
        try:
            row_iterator.next()
            multiple_entries = True
        except StopIteration:
            pass
        except AttributeError:
            pass

        if  multiple_entries:
             raise RuntimeError('There is something entirely wrong, >>%s<< '
                                'appears more than once in table %s.'
                                %(item_name,table._v_name))

        ## Check if we added something
        if row == None:
            raise RuntimeError('Could not add or modify entries of >>%s<< in '
                               'table %s' %(item_name,table._v_name))
        table.flush()


    def _all_insert_into_row(self, row, insert_dict):

        for key, val in insert_dict.items():
            row[key] = val


    def _all_extract_insert_dict(self,item,colnames):
        insert_dict={}

        if 'length' in colnames:
            insert_dict['length'] = len(item)

        if 'comment' in colnames:
            insert_dict['comment'] = item.v_comment

        if 'location' in colnames:
            insert_dict['location'] = item.v_location

        if 'name' in colnames:
            insert_dict['name'] = item.v_name

        if 'class_name' in colnames:
            insert_dict['class_name'] = item.f_get_class_name()

        if 'value' in colnames:
            valstr = item.f_val_to_str()
            if len(valstr) >= globally.HDF5_STRCOL_MAX_COMMENT_LENGTH:
                self._logger.info('The value string >>%s<< was too long I truncated it to'
                                     ' %d characters' %
                                     (valstr,globally.HDF5_STRCOL_MAX_COMMENT_LENGTH))
                valstr = valstr[0:globally.HDF5_STRCOL_MAX_COMMENT_LENGTH]
            insert_dict['value'] = valstr

        if 'creator_name' in colnames:
            insert_dict['creator_name'] = item.v_location.split('.')[1]

        if 'idx' in colnames:
            insert_dict['idx'] = item.v_idx

        if 'time' in colnames:
            insert_dict['time'] = item.v_time

        if 'timestamp' in colnames:
            insert_dict['timestamp'] = item.v_timestamp

        if 'array' in colnames:
            arraystr = str(item.f_get_array())
            if len(arraystr) >= globally.HDF5_STRCOL_MAX_COMMENT_LENGTH:
                self._logger.warning('The array string >>%s<< was too long I truncated it to'
                                     '%d characters' %
                                     (arraystr,globally.HDF5_STRCOL_MAX_COMMENT_LENGTH))

                arraystr=arraystr[0:globally.HDF5_STRCOL_MAX_COMMENT_LENGTH]
            insert_dict['array'] = arraystr

        return insert_dict


    def _all_get_groups(self,key):
        newhdf5group = self._trajectory_group
        split_key = key.split('.')
        for name in split_key:
            newhdf5group = newhdf5group._f_get_child(name)
        return newhdf5group

    def _all_create_or_get_groups(self, key):
        newhdf5group = self._trajectory_group
        split_key = key.split('.')
        created = False
        for name in split_key:
            if not name in newhdf5group:
                newhdf5group=self._hdf5file.create_group(where=newhdf5group, name=name, title=name)
                created = True
            else:
                newhdf5group=newhdf5group._f_get_child(name)


        return newhdf5group, created

    ################# Storing and loading Annotations ###########################################

    def _ann_store_annotations(self,item_with_annotations,node):
        if not item_with_annotations.v_annotations.f_is_empty():

            anno_dict = item_with_annotations.v_annotations.__dict__

            # if node is None:
            #     node = self._all_get_node_by_name(item_with_annotations.v_full_name)

            current_attrs = node._v_attrs

            changed = False

            for field_name, val in anno_dict.iteritems():
                field_name_with_prefix = HDF5StorageService.ANNOTATION_PREFIX+field_name
                if not field_name_with_prefix in current_attrs:
                    setattr(current_attrs,field_name_with_prefix,val)
                    changed = True

            if changed:
                setattr(current_attrs,HDF5StorageService.ANNOTATED,True)
                self._hdf5file.flush()


    def _ann_load_annotations(self,item_with_annotations,node):

        # if node is None:
        #     node = self._all_get_node_by_name(item_with_annotations.v_full_name)

        annotated = self._all_get_from_attrs(node,HDF5StorageService.ANNOTATED)

        if annotated:

            annotations =item_with_annotations.v_annotations

            current_attrs = node._v_attrs

            for attr_name in current_attrs._v_attrnames:

                if attr_name.startswith(HDF5StorageService.ANNOTATION_PREFIX):
                    key = attr_name
                    key=key.replace(HDF5StorageService.ANNOTATION_PREFIX,'')

                    data = getattr(current_attrs,attr_name)
                    setattr(annotations,key,data)



    ############################################## Storing Nodes ################################

    def _node_store_node(self,node_in_traj, _hdf5_group = None):


        if _hdf5_group is None:
            _hdf5_group,_ = self._all_create_or_get_groups(node_in_traj.v_full_name)

        self._ann_store_annotations(node_in_traj,_hdf5_group)


    def _node_load_node(self,node_in_traj, _hdf5_group=None):


        if _hdf5_group is None:
            _hdf5_group = self._all_get_node_by_name(node_in_traj.v_full_name)


        self._ann_load_annotations(node_in_traj,_hdf5_group)
        
        

    ################# Storing and Loading Parameters ############################################

    def _prm_extract_missing_flags(self,data_dict, flags_dict):
        for key,data in data_dict.items():
            if not key in flags_dict:
                dtype = type(data)
                if dtype in HDF5StorageService.TYPE_FLAG_MAPPING:
                    flags_dict[key]=HDF5StorageService.TYPE_FLAG_MAPPING[dtype]
                else:
                    raise pex.NoSuchServiceError('I cannot store >>%s<<, I do not understand the'
                                                 'type >>%s<<.' %(key,str(dtype)))



    def _prm_add_meta_info(self,instance,group):
        setattr(group._v_attrs, HDF5StorageService.COMMENT, instance.v_comment)
        setattr(group._v_attrs, HDF5StorageService.CLASS_NAME, instance.f_get_class_name())
        setattr(group._v_attrs,HDF5StorageService.LEAF,1)

        if instance.v_parameter:
            setattr(group._v_attrs, HDF5StorageService.LENGTH,len(instance))

        where = instance.v_location.split('.')[0]
        tablename = HDF5StorageService.TABLE_NAME_MAPPING[where]
        table = getattr(self._trajectory_group,tablename)

        self._all_store_param_or_result_table_entry(instance,table,
                                                    flags=(HDF5StorageService.ADD_ROW,
                                                           HDF5StorageService.MODIFY_ROW))

        if instance.v_parameter and instance.f_is_array():
            tablename = 'explored_parameter_table'
            table = getattr(self._trajectory_group,tablename)
            self._all_store_param_or_result_table_entry(instance,table,
                                                        flags=(HDF5StorageService.ADD_ROW,
                                                           HDF5StorageService.MODIFY_ROW))

    def _prm_store_parameter_or_result(self, msg, instance,*args,**kwargs):

        fullname = instance.v_full_name
        self._logger.debug('Storing %s.' % fullname)


        _hdf5_group = kwargs.pop('_hdf5_group', None)



        if _hdf5_group is None:
            _hdf5_group, newly_created = self._all_create_or_get_groups(fullname)
        else:
            newly_created = False

        if msg == globally.UPDATE_LEAF or newly_created:
            self._prm_add_meta_info(instance,_hdf5_group)

        ## Store annotations
        self._ann_store_annotations(instance,_hdf5_group)


        store_dict = instance._store()

        store_flags = kwargs.pop('store_flags',None)


        if store_flags is None:
            try:
                store_flags = instance._store_flags()
            except AttributeError:
                store_flags = {}


        self._prm_extract_missing_flags(store_dict,store_flags)


        for key, data_to_store in store_dict.items():
            if (not instance.v_parameter or msg == globally.LEAF) and  key in _hdf5_group:
                self._logger.debug('Found %s already in hdf5 node of %s, so I will ignore it.' %
                                   (key, fullname))

                continue
            if store_flags[key] == HDF5StorageService.TABLE:
                self._prm_store_into_pytable(msg,key, data_to_store, _hdf5_group, fullname,
                                             *args,**kwargs)
            elif key in _hdf5_group:
                self._logger.debug('Found %s already in hdf5 node of %s, so I will ignore it.' %
                                   (key, fullname))
                continue
            elif store_flags[key] == HDF5StorageService.DICT:
                self._prm_store_dict_as_table(msg,key, data_to_store, _hdf5_group, fullname,*args,**kwargs)
            elif store_flags[key] == HDF5StorageService.ARRAY:
                self._prm_store_into_array(msg,key, data_to_store, _hdf5_group, fullname,*args,**kwargs)
            elif store_flags[key] == HDF5StorageService.CARRAY:
                self._prm_store_into_carray(msg,key, data_to_store, _hdf5_group, fullname,*args,**kwargs)
            elif store_flags[key] == HDF5StorageService.FRAME:
                self._prm_store_data_frame(msg,key, data_to_store, _hdf5_group, fullname,*args,**kwargs)
            else:
                raise RuntimeError('You shall not pass!')

    def _prm_store_dict_as_table(self, msg, key, data_to_store, group, fullname):

        if key in group:
            raise ValueError('Dictionary >>%s<< already exists in >>%s<<. Appending is not supported (yet).')


        #assert isinstance(data_to_store,dict)

        if key in group:
            raise ValueError('Dict >>%s<< already exists in >>%s<<. Appending is not supported (yet).')

        temp_dict={}
        for innerkey, val in data_to_store.iteritems():
            temp_dict[innerkey] =[val]

        objtable = ObjectTable(data=temp_dict)

        self._prm_store_into_pytable(msg,key,objtable,group,fullname)
        new_table = group._f_get_child(key)
        self._all_set_attributes_to_recall_natives(temp_dict,new_table,
                                                   HDF5StorageService.DATA_PREFIX)

        setattr(new_table._v_attrs,HDF5StorageService.STORAGE_TYPE,
                HDF5StorageService.DICT)

        self._hdf5file.flush()



    def _prm_store_data_frame(self, msg,  key, data_to_store, group, fullname):

        try:

            if key in group:
                # if msg == globally.PARAMETER:
                #     return

                raise ValueError('DataFrame >>%s<< already exists in >>%s<<. Appending is not supported (yet).')



            #assert isinstance(data_to_store,DataFrame)
            #assert isinstance(group, pt.Group)

            name = group._v_pathname+'/' +key
            data_to_store.to_hdf(self._filename, name, append=True,data_columns=True)
            frame_group = group._f_get_child(key)
            setattr(frame_group._v_attrs,HDF5StorageService.STORAGE_TYPE, HDF5StorageService.FRAME)
            self._hdf5file.flush()
        except:
            self._logger.error('Failed storing DataFrame >>%s<< of >>%s<<.' %(key,fullname))
            raise




    def _prm_store_into_carray(self, msg, key, data, group, fullname):


        try:
            if key in group:
                raise ValueError('CArray >>%s<< already exists in >>%s<<. Appending is not supported (yet).')


            # if isinstance(data, np.ndarray):
            #     size = data.size
            if hasattr(data,'__len__'):
                size = len(data)
            else:
                size = 1

            if size == 0:
                self._logger.warning('>>%s<< of >>%s<< is _empty, I will skip storing.' %(key,fullname))
                return


            carray=self._hdf5file.create_carray(where=group, name=key,obj=data)
            self._all_set_attributes_to_recall_natives(data,carray,HDF5StorageService.DATA_PREFIX)
            setattr(carray._v_attrs,HDF5StorageService.STORAGE_TYPE, HDF5StorageService.CARRAY)
            self._hdf5file.flush()
        except:
            self._logger.error('Failed storing array >>%s<< of >>%s<<.' % (key, fullname))
            raise


    def _prm_store_into_array(self, msg, key, data, group, fullname):

        #append_mode = kwargs.f_get('append_mode',None)

        try:
            if key in group:
                # if append_mode == globally.PARAMETER:
                #     return

                raise ValueError('Array >>%s<< already exists in >>%s<<. Appending is not supported (yet).')


            # if isinstance(data, np.ndarray):
            #     size = data.size
            if hasattr(data,'__len__'):
                size = len(data)
            else:
                size = 1

            if size == 0:
                self._logger.warning('>>%s<< of >>%s<< is _empty, I will skip storing.' %(key,fullname))
                return


            array=self._hdf5file.create_array(where=group, name=key,obj=data)
            self._all_set_attributes_to_recall_natives(data,array,HDF5StorageService.DATA_PREFIX)
            setattr(array._v_attrs,HDF5StorageService.STORAGE_TYPE, HDF5StorageService.ARRAY)
            self._hdf5file.flush()
        except:
            self._logger.error('Failed storing array >>%s<< of >>%s<<.' % (key, fullname))
            raise



    def _all_set_attributes_to_recall_natives(self, data, ptitem_or_dict, prefix):

            def _set_attribute_to_item_or_dict(item_or_dict, name,val):
                try:
                    item_or_dict.set_attr(name,val)
                except AttributeError:
                    item_or_dict[name]=val

            if type(data) is tuple:
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLL_TYPE,
                                HDF5StorageService.COLL_TUPLE)

            elif type(data) is list:
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLL_TYPE,
                                HDF5StorageService.COLL_LIST)

            elif type(data) is np.ndarray:
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLL_TYPE,
                                HDF5StorageService.COLL_NDARRAY)

            elif type(data) is np.matrix:
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLL_TYPE,
                                               HDF5StorageService.COLL_MATRIX)

            elif type(data) in globally.PARAMETER_SUPPORTED_DATA:
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLL_TYPE,
                                HDF5StorageService.COLL_SCALAR)

                strtype = repr(type(data))

                if not strtype in globally.PARAMETERTYPEDICT:
                    raise TypeError('I do not know how to handel >>%s<< its type is >>%s<<.' %
                                   (str(data),str(type(data))))

                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.SCALAR_TYPE,strtype)

            elif type(data) is dict:
                _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.COLL_TYPE,
                                HDF5StorageService.COLL_DICT)

            else:
                raise TypeError('I do not know how to handel >>%s<< its type is >>%s<<.' %
                                   (str(data),str(type(data))))

            if type(data) in (list,tuple):
                if len(data) > 0:
                    strtype = repr(type(data[0]))

                    if not strtype in globally.PARAMETERTYPEDICT:
                        raise TypeError('I do not know how to handel >>%s<< its type is '
                                           '>>%s<<.' % (str(data),strtype))

                    _set_attribute_to_item_or_dict(ptitem_or_dict,prefix+HDF5StorageService.SCALAR_TYPE,strtype)



    def _all_remove_parameter_or_result(self, instance, *args,**kwargs):



        trajectory = kwargs.pop('trajectory')
        remove_empty_groups = kwargs.pop('remove_empty_groups',False)

        if instance.v_full_name in trajectory._explored_parameters:
            raise TypeError('You cannot remove an explored parameter of a trajectory stored '
                            'into an hdf5 file.')


        if instance.v_leaf:
            where = instance.v_location.split('.')[0]
            tablename = HDF5StorageService.TABLE_NAME_MAPPING[where]
            table = getattr(self._trajectory_group,tablename)

            self._all_store_param_or_result_table_entry(instance,table,
                                                        flags=(HDF5StorageService.REMOVE_ROW,))

        split_name = instance.v_full_name.split('.')
        node_name = split_name.pop()

        where = '/'+self._trajectory_name+'/' + '/'.join(split_name)


        the_node = self._hdf5file.get_node(where=where,name=node_name)

        if not instance.v_leaf:
            if len(the_node._v_groups) != 0:
                raise TypeError('You cannot remove a group that is not empty!')

        the_node._f_remove(recursive=True)
        #self._hdf5file.remove_node(where=where,name=node_name,recursive=True)





        if remove_empty_groups:
            for irun in reversed(range(len(split_name))):
                where = '/'+self._trajectory_name+'/' + '/'.join(split_name[0:irun])
                node_name = split_name[irun]
                act_group = self._hdf5file.get_node(where=where,name=node_name)
                if len(act_group._v_groups) == 0:
                    self._hdf5file.remove_node(where=where,name=node_name,recursive=True)
                else:
                    break



    def _prm_store_into_pytable(self,msg, tablename,data,hdf5group,fullname):


        try:
            if hasattr(hdf5group,tablename):
                table = getattr(hdf5group,tablename)

                if msg == globally.UPDATE_LEAF:
                    nstart= table.nrows
                    datasize = data.shape[0]
                    if nstart==datasize:
                        self._logger.debug('There is no new data to the parameter >>%s<<. I will'
                                           ' skip storage of table >>%s<<' % (fullname,tablename))
                        return
                    else:
                        self._logger.debug('There is new data to the parameter >>%s<<. I will'
                                           ' add data to table >>%s<<' % (fullname,tablename))

                else:
                    raise ValueError('Table %s already exists, appending is only supported for '
                                     'parameter merging and appending, please use >>msg= %s<<.' %
                                     (tablename,globally.UPDATE_LEAF))

                self._logger.debug('Found table %s in file %s, will append new entries in %s to the table.' %
                                   (tablename,self._filename, fullname))

                ## If the table exists, it already knows what the original data of the input was:
                data_type_dict = {}
            else:
                # if msg == globally.UPDATE_LEAF:
                    # self._logger.debug('Table >>%s<< of >>%s<< does not exist, '
                    #                    'I will create it!' % (tablename,fullname))

                description_dict, data_type_dict = self._prm_make_description(data,fullname)
                table = self._hdf5file.createTable(where=hdf5group,name=tablename,description=description_dict,
                                                   title=tablename)
                nstart = 0

            #assert isinstance(table,pt.Table)
            #assert isinstance(data, ObjectTable)


            row = table.row

            datasize = data.shape[0]


            cols = data.columns.tolist()
            for n in range(nstart, datasize):

                for key in cols:

                    row[key] = data[key][n]

                row.append()

            for field_name, type_description in data_type_dict.iteritems():
                table.set_attr(field_name,type_description)


            setattr(table._v_attrs,HDF5StorageService.STORAGE_TYPE, HDF5StorageService.TABLE)
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

            if not isinstance(series_of_data[0],np.ndarray):
                for idx,item in enumerate(series_of_data):
                    series_of_data[idx] = np.array(item)



        descriptiondict={}
        original_data_type_dict={}

        for key, val in data.iteritems():

            self._all_set_attributes_to_recall_natives(val[0],original_data_type_dict,
                            HDF5StorageService.FORMATTED_COLUMN_PREFIX % key)


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
            self._logger.error('Failure in storing >>%s<< of Parameter/Result >>%s<<.'
                               ' Its type was >>%s<<.' % (key,fullname,str(type(val))))
            raise



    @staticmethod
    def _prm_get_longest_stringsize( string_list):
        ''' Returns the longest stringsize for a string entry across data.
        '''
        maxlength = 1

        for stringar in string_list:
            if not isinstance(stringar,np.ndarray) or stringar.ndim==0:
                stringar = np.array([stringar])

            for string in stringar:
                maxlength = max(len(string),maxlength)

        # Make the string Col longer than needed in order to allow later on slightly large strings
        return maxlength*1.5



    def _prm_load_parameter_or_result(self, param, *args,**kwargs):

        load_only = kwargs.pop('load_only',None)
        _hdf5_group = kwargs.pop('_hdf5_group', None)

        if _hdf5_group is None:
            _hdf5_group = self._all_get_node_by_name(param.v_full_name)

        #self._ann_load_annotations(param,_hdf5_group)


        full_name = param.v_full_name

        self._logger.debug('Loading %s' % full_name)


        load_dict = {}
        for node in _hdf5_group:
            if not load_only is None:

                self._logger.debug('I am in load only mode, I will only lode %s.' %
                                   str(load_only))


                if not node._v_name in load_only:
                    continue
                else:
                    load_only.remove(node._v_name)


            load_type = self._all_get_from_attrs(node,HDF5StorageService.STORAGE_TYPE)

            if load_type == HDF5StorageService.DICT:
                self._prm_read_dictionary(node, load_dict, full_name, *args,**kwargs)
            elif load_type == HDF5StorageService.TABLE:
                self._prm_read_table(node, load_dict, full_name, *args,**kwargs)
            elif load_type in [HDF5StorageService.ARRAY,HDF5StorageService.CARRAY]:
                self._prm_read_array(node, load_dict, full_name, *args,**kwargs)
            elif load_type == HDF5StorageService.FRAME:
                self._prm_read_frame(node, load_dict,full_name, *args,**kwargs)
            else:
                raise pex.NoSuchServiceError('Cannot load %s, do not understand the hdf5 file '
                                             'structure of %s [%s].' %
                                             (full_name, str(node),str(load_type)) )


        if not load_only is None and len(load_only) > 0:
            raise ValueError('You marked %s for load only, but I cannot find these for >>%s<<' %
                             (str(load_only),full_name))
        
        param._load(load_dict)


    def _prm_read_dictionary(self, leaf, load_dict, full_name):
        try:
            temp_dict={}
            self._prm_read_table(leaf,temp_dict,full_name)
            key =leaf._v_name
            temp_table = temp_dict[key]
            temp_dict = temp_table.to_dict('list')

            innder_dict = {}
            load_dict[key] = innder_dict
            for innerkey, vallist in temp_dict.items():
                innder_dict[innerkey] = vallist[0]
        except:
            self._logger.error('Failed loading >>%s<< of >>%s<<.' % (leaf._v_name,full_name))
            raise


    def _prm_read_frame(self,pd_node,load_dict, full_name):
        try:
            name = pd_node._v_name
            pathname = pd_node._v_pathname
            dataframe = read_hdf(self._filename,pathname,mode='r')
            load_dict[name] = dataframe
        except:
            self._logger.error('Failed loading >>%s<< of >>%s<<.' % (pd_node._v_name,full_name))
            raise

    def _prm_read_table(self,table,load_dict, full_name):
        ''' Reads a non-nested Pytables table column by column.

        :type table: pt.Table
        :type load_dict:
        :return:
        '''
        try:
            table_name = table._v_name

            for colname in table.colnames:
                col = table.col(colname)
                data_list=list(col)

                prefix = HDF5StorageService.FORMATTED_COLUMN_PREFIX % colname
                for idx,data in enumerate(data_list):
                    data,type_changed = self._all_recall_native_type(data,table,prefix)
                    if type_changed:
                        data_list[idx] = data
                    else:
                        break

                if table_name in load_dict:
                    load_dict[table_name][colname] = data_list
                else:
                    load_dict[table_name] = ObjectTable(data={colname:data_list})
        except:
            self._logger.error('Failed loading >>%s<< of >>%s<<.' % (table._v_name,full_name))
            raise


    def _prm_read_array(self, array, load_dict, full_name):

        try:
            #assert isinstance(carray,pt.CArray)
            array_name = array._v_name

            result = array.read()
            result, dummy = self._all_recall_native_type(result,array,HDF5StorageService.DATA_PREFIX)

            load_dict[array._v_name]=result
        except:
            self._logger.error('Failed loading >>%s<< of >>%s<<.' % (array._v_name,full_name))
            raise









