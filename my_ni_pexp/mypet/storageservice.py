from numpy.oldnumeric.ma import _ptp

__author__ = 'robert'


import logging
import tables as pt
import os
import numpy as np
from functools import wraps
from mypet.trajectory import Trajectory,SingleRun
from mypet.parameter import BaseParameter, BaseResult, SimpleResult
from mypet import globally


from mypet.parameter import ObjectTable
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
    UPDATEROW = 'UPDATE'


    TABLENAME_MAPPING = {
        'parameters' : 'parameter_table',
        'config' : 'config_table',
        'derived_parameters' : 'derived_parameter_table',
        'results' : 'result_table'
    }

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
                self._trj_load_trajectory(stuff_to_load,*args,**kwargs)


            elif msg == globally.RESULT or msg == globally.PARAMETER:
                self._prm_load_parameter_or_result(stuff_to_load,*args,**kwargs)

            elif msg ==globally.LIST:
                self._srvc_load_several_items(stuff_to_load,*args,**kwargs)

            else:
                raise ValueError('I do not know how to handle >>%s<<' % msg)

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

            elif msg == globally.UPDATETRAJECTORY:
                self._trj_update_trajectory(stuff_to_store,*args,**kwargs)

            elif msg == globally.TRAJECTORY:

                self._trj_store_trajectory(stuff_to_store,*args,**kwargs)

            elif msg == globally.SINGLERUN:

                self._srn_store_single_run(stuff_to_store,*args,**kwargs)

            elif msg == globally.RESULT or msg == globally.PARAMETER or msg == globally.UPDATEPARAMETER:
                self._prm_store_parameter_or_result(msg,stuff_to_store,*args,**kwargs)

            elif msg == globally.LIST:
                self._srvc_store_several_items(stuff_to_store,*args,**kwargs)

            else:
                raise ValueError('I do not know how to handle >>%s<<' % msg)

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


                    self._hdf5file = pt.openFile(filename=self._filename, mode=mode, title=self._filetitle)
                    if not ('/'+self._trajectoryname) in self._hdf5file:
                        if not msg == globally.TRAJECTORY:
                            raise ValueError('Your trajectory cannot be found in the hdf5file, please use >>traj.store()<< before storing anyhting else.')
                        self._hdf5file.createGroup(where='/', name= self._trajectoryname, title=self._trajectoryname)

                    # if not ('/'+self._trajectoryname) in self._hdf5file:
                    #     raise ValueError('File %s does not contain trajectory %s.' % (self._filename,
                    #                                                                   self._trajectoryname))
                    self._trajectorygroup = self._hdf5file.get_node('/'+self._trajectoryname)

                elif mode == 'r':
                    ### Fuck Pandas, we have to wait until the next relaese until this is supported:
                    mode = 'a'
                    if not os.path.isfile(self._filename):
                        raise ValueError('Filename ' + self._filename + ' does not exist.')

                    self._hdf5file = pt.openFile(filename=self._filename, mode=mode, title=self._filetitle)

                    if isinstance(self._trajectoryname,int):
                        nodelist = self._hdf5file.listNodes(where='/')

                        if self._trajectoryname >= len(nodelist) or self._trajectoryname < -len(nodelist):
                            raise ValueError('Trajectory No. %d does not exists, there are only %d trajectories in %s.'
                            % (self._trajectoryname,len(nodelist),self._filename))

                        self._trajectorygroup = nodelist[self._trajectoryname]
                        self._trajectoryname = self._trajectorygroup._v_name
                    else:
                        if not ('/'+self._trajectoryname) in self._hdf5file:
                            raise ValueError('File %s does not contain trajectory %s.' % (self._filename,
                                                                                          self._trajectoryname))
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
        self._logger = logging.getLogger('mypet.storageservice_HDF5StorageService=' + self._filename)


    ########################### MERGING ###########################################################

    def _trj_merge_trajectories(self,other_trajectory_name,rename_dict,*args,**kwargs):


        copy_nodes = kwargs.pop('copy_nodes', False)
        delete_trajectory = kwargs.pop('delete_trajectory', False)

        if copy_nodes and delete_trajectory:
            raise ValueError('You want to copy nodes, but delete the old trajectory, this is too much overhead, please use copy_nodes = False, delete_trajectory = True')


        # other_trajectory_name = other_trajectory.get_fullname()
        if not ('/'+other_trajectory_name) in self._hdf5file:
            raise TypeError('Cannot merge >>%s<< and >>%s<<, because the second trajectory cannot be found in my file.')

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

        infotable = getattr(self._trajectorygroup,'info')
        insert_dict = self._all_extract_insert_dict(traj,infotable.colnames)
        self._all_add_or_modify_row(traj.get_name(),insert_dict,infotable,0,[],HDF5StorageService.MODIFYROW)


        for result_name in new_results:
            result = traj.get(result_name)
            self._all_store_param_or_result_table_entry(result,'result_table',flag=HDF5StorageService.ADDROW)

        for param_name in changed_parameters:
            param = traj.get(param_name)
            self.store(globally.UPDATEPARAMETER,param,*args,**kwargs)


        run_table = getattr(self._trajectorygroup,'run_table')
        actual_rows = run_table.nrows
        self._trj_fill_run_table_with_dummys(len(traj)-actual_rows)


        for runname in traj.get_run_names():
            run_info = traj.get_run_information(runname)
            run_info['name'] = runname
            id = run_info['id']


            traj.prepare_paramspacepoint(id)
            run_summary=self._srn_add_explored_params(runname,traj._exploredparameters.values())


            run_info['parameter_summary'] = run_summary

            self._all_add_or_modify_row(runname,run_info,run_table,id,[],flag=HDF5StorageService.MODIFYROW)

        traj.restore_default()



    ######################## LOADING A TRAJECTORY #################################################

    def _trj_load_trajectory(self,traj, replace,
                         load_params, load_derived_params, load_results):

        ''' Loads a single trajectory from a given file.

        Per default derived parameters and results are not loaded. If the filename is not specified
        the file where the current trajectory is supposed to be stored is taken.

        If the user wants to load results, the actual data is not loaded, only dummy objects
        are created, which must load their data independently. It is assumed that
        results of many simulations are large and should not be loaded all together into memory.

        If replace is true than the current trajectory name is replaced by the name of the loaded
        trajectory, so is the filename.
        '''

        if replace:
            assert traj.is_empty()
        else:
            traj._loadedfrom= self._filename+': '+self._trajectoryname

        self._trj_load_meta_data(traj, replace)

        self._trj_load_config(traj, load_params)
        self._trj_load_params(traj, load_params)
        self._trj_load_derived_params(traj, load_derived_params)
        self._trj_load_results(traj, load_results)



    def _trj_load_meta_data(self,traj,  replace):
        metatable = self._trajectorygroup.info
        metarow = metatable[0]

        traj._length = metarow['length']

        if replace:
            traj._comment = metarow['comment']
            traj._time = metarow['timestamp']
            traj._formatted_time = metarow['time']
            # traj._loadedfrom=(metarow['loaded_from'])

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
        self._trj_load_any_param_or_result_table(globally.PARAMETER,traj,traj._config,paramtable, load_params)

    def _trj_load_params(self,traj, load_params):
        paramtable = self._trajectorygroup.parameter_table
        self._trj_load_any_param_or_result_table(globally.PARAMETER,traj,traj._parameters,paramtable, load_params)

    def _trj_load_derived_params(self,traj, load_derived_params):
        paramtable = self._trajectorygroup.derived_parameter_table
        self._trj_load_any_param_or_result_table(globally.PARAMETER,traj,traj._derivedparameters,paramtable, load_derived_params)

    def _trj_load_results(self,traj, load_results):
        resulttable = self._trajectorygroup.result_table
        self._trj_load_any_param_or_result_table(globally.RESULT,traj,traj._results, resulttable, load_results)


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
                        self._logger.warn('Paremeter or Result >>%s<< is already in your trajectory, I am overwriting it.'
                                                                                 % fullname)

                new_class = traj._create_class(class_name)
                paraminstance = new_class(fullname,comment=comment)
                assert isinstance(paraminstance, (BaseParameter,BaseResult))


                if 'length' in colnames:
                    size = row['length']
                    if size > 1 and size != len(traj):
                        raise RuntimeError('Your are loading a parameter >>%s<< with length %d, yet your trajectory has lenght %d, something is wrong!'
                                           % (fullname,size,len(traj)))
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

        The 'info' table will contain ththane name of the trajectory, it's timestamp, a comment,
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

        infotable = self._hdf5file.createTable(where=self._trajectorygroup, name='info', description=descriptiondict, title='info')

        insert_dict = self._all_extract_insert_dict(traj,infotable.colnames)
        self._all_add_or_modify_row(traj.get_name(),insert_dict,infotable,[],[],flag=HDF5StorageService.ADDROW)


        rundescription_dict = {'name': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                         'time': pt.StringCol(len(traj.get_time())),
                         'timestamp' : pt.FloatCol(),
                         'id' : pt.Int64Col(),
                         'completed' : pt.Int64Col(),
                         'parameter_summary' : pt.StringCol(globally.HDF5_STRCOL_MAX_COMMENT_LENGTH)}

        runtable = self._hdf5file.createTable(where=self._trajectorygroup, name='run_table', description=rundescription_dict, title='run_table')

        self._trj_fill_run_table_with_dummys(len(traj))



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
                paramdescriptiondict.update({'length' : pt.Int64Col()})
                paramdescriptiondict.update({'value' :pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH)})




            paramtable = self._hdf5file.createTable(where=self._trajectorygroup, name=key, description=paramdescriptiondict, title=key)

            paramtable.flush()



    def _trj_fill_run_table_with_dummys(self, ndummys):

        runtable = getattr(self._trajectorygroup,'run_table')

        insert_dict = dict(name='Call me Maybe', time='Time for Beer',
                           timestamp=42.0, id=1337,
                           parameter_summary='Dont waste your time with a PhD!',
                           completed = 0)

        for idx in range(ndummys):
            self._all_add_or_modify_row('Dummy Row', insert_dict, runtable,[],[],flag=HDF5StorageService.ADDROW)

        runtable.flush()


    def _trj_store_trajectory(self, traj):
        ''' Stores a trajectory to the in __init__ specified hdf5file.
        '''

        self._logger.info('Start storing Trajectory %s.' % self._trajectoryname)

        self._trj_store_meta_data(traj)

        self._all_store_dict(globally.PARAMETER,traj._config)
        self._all_store_dict(globally.PARAMETER,traj._parameters)
        self._all_store_dict(globally.RESULT,traj._results)
        self._all_store_dict(globally.PARAMETER,traj._derivedparameters)


        self._logger.info('Finished storing Trajectory.')


    ######################## Storing a Signle Run ##########################################

    def _srn_store_single_run(self,single_run):
        ''' Stores the derived parameters and results of a single run.
        '''

        assert isinstance(single_run,SingleRun)

        traj = single_run._single_run
        n = single_run.get_n()

        self._logger.info('Start storing run %d with name %s.' % (n,single_run.get_name()))




        paramtable = getattr(self._trajectorygroup, 'derived_parameter_table')

        self._all_store_dict(globally.PARAMETER,traj._derivedparameters)


        paramtable = getattr(self._trajectorygroup, 'result_table')

        self._all_store_dict(globally.RESULT,traj._results)

        # For better readability add the explored parameters to the results
        run_summary = self._srn_add_explored_params(single_run.get_name(),single_run._parent_trajectory._exploredparameters.values())
        table = getattr(self._trajectorygroup,'run_table')

        insert_dict = self._all_extract_insert_dict(single_run,table.colnames)
        insert_dict['parameter_summary'] = run_summary
        insert_dict['completed'] = 1
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

            valstr = expparam.to_str()
            if len(valstr) >= globally.HDF5_STRCOL_MAX_NAME_LENGTH:
                valstr = valstr[0:globally.HDF5_STRCOL_MAX_NAME_LENGTH-1]
            runsummary = runsummary + expparam.get_name() + ': ' +valstr

            self._all_store_param_or_result_table_entry(expparam, paramtable, HDF5StorageService.UPDATEROW)

        return runsummary



    ######################################### Storing a Trajectory and a Single Run #####################
    def _all_store_param_or_result_table_entry(self,param_or_result,tablename_or_table, flag):
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


        # if modified:
        #     flag = HDF5StorageService.MODIFYROW
        # else:
        #     flag = HDF5StorageService.ADDROW

        colnames = set(table.colnames)
        insert_dict = self._all_extract_insert_dict(param_or_result,colnames)

        self._all_add_or_modify_row(fullname,insert_dict,table,condition,condvars,flag)


    def _all_add_or_modify_row(self, itemname, insert_dict, table, condition_or_row_index=None, condvars=None, flag=ADDROW):


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


        if row == None and (flag == HDF5StorageService.ADDROW or flag == HDF5StorageService.UPDATEROW):

            row = table.row

            self._all_insert_into_row(row,insert_dict)

            row.append()

        elif row != None and flag == HDF5StorageService.MODIFYROW or flag == HDF5StorageService.UPDATEROW:


            self._all_insert_into_row(row,insert_dict)

            row.update()

        elif row != None and flag == HDF5StorageService.ADD:
            pass # If the row was found, do not change it
        elif row != None and flag == HDF5StorageService.REMOVEROW:
            row = rowiterator.next()
            table.remove_row(row.nrow)
        else:
            raise RuntimeError('Something is wrong, you might not have found a row, or your flags are not set approprialty')

        ## Check if there are 2 entries which should not happen
        multiple_entries = False
        try:
            rowiterator.next()
            multiple_entries = True
        except:
            pass

        if  multiple_entries:
             raise RuntimeError('There is something entirely wrong, >>%s<< appears more than once in table %s.' %(itemname,table._v_name))

        ## Check if we added something
        if row == None:
            raise RuntimeError('Could not add or modify entries of >>%s<< in table %s' %(itemname,table._v_name))
        table.flush()

    def _all_store_dict(self, msg, data_dict):
        for val in data_dict.itervalues():
            self.store(msg,val)


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
            valstr = item.to_str()
            if len(valstr) >= globally.HDF5_STRCOL_MAX_NAME_LENGTH:
                valstr = valstr[0:globally.HDF5_STRCOL_MAX_NAME_LENGTH-1]
            insert_dict['value'] = valstr

        if 'creator_name' in colnames:
            insert_dict['creator_name'] = item.get_location().split('.')[1]

        if 'id' in colnames:
            insert_dict['id'] = item.get_n()

        if 'time' in colnames:
            insert_dict['time'] = item.get_time()

        if 'timestamp' in colnames:
            insert_dict['timestamp'] = item.get_timestamp()

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


        if msg == globally.RESULT or msg == globally.PARAMETER:
            self._all_store_param_or_result_table_entry(param,tablename,flag=HDF5StorageService.ADDROW)
        elif msg == globally.UPDATEPARAMETER:
            self._all_store_param_or_result_table_entry(param,tablename,flag=HDF5StorageService.MODIFYROW)
        else:
            raise RuntimeError('You shall not pass!')
        fullname = param.get_fullname()
        self._logger.debug('Storing %s.' % fullname)
        store_dict = param._store()


        #self._check_dictionary_structure(store_dict)
        #self._prm_check_info_dict(param, store_dict)

        group= self._all_create_groups(fullname)

        for key, data_to_store in store_dict.items():
            if isinstance(data_to_store, ObjectTable):
                self._prm_store_into_pytable(msg,key, data_to_store, group, fullname,*args,**kwargs)
            elif msg == globally.UPDATEPARAMETER and key in group:
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



        objtable = ObjectTable(data=data_to_store,index=[0])

        self._prm_store_into_pytable(msg,key,objtable,group,fullname)
        group._f_get_child(key).set_attr('DICT',1)



    def _prm_store_data_frame(self, msg,  key, data_to_store, group, fullname,*args,**kwargs):

        try:

            if key in group:
                # if msg == globally.UPDATEPARAMETER:
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
                # if append_mode == globally.UPDATEPARAMETER:
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
                # if append_mode == globally.UPDATEPARAMETER:
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
            if isinstance(data,tuple):
                array.set_attr('TUPLE',1)
            if isinstance(data, globally.PARAMETER_SUPPORTED_DATA):
                array.set_attr('SCALAR',1)
        #carray[:]=data
            self._hdf5file.flush()
        except:
            self._logger.error('Failed storing array >>%s<< of >>%s<<.' % (key, fullname))
            raise


    def _prm_check_info_dict(self,param, store_dict):
        ''' Checks if the storage dictionary contains an appropriate description of the parameter.
        This entry is called info, and should contain only a single
        :param param: The parameter to store
        :param store_dict: the dictionary that describes how to store the parameter
        '''
        if not 'info' in store_dict:
            store_dict['info']={}

        info_dict = store_dict['info']

        test_item = info_dict.itervalues().next()
        if len(test_item)>1:
            raise AttributeError('Your description of the parameter %s, generated by _store and stored into >>info<< has more than a single dictionary in the list.' % param.get_fullname())


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

                if msg == globally.UPDATEPARAMETER:
                    nstart= table.nrows
                else:
                    raise ValueError('Table %s already exists, appending is only supported for parameter merging and appending, please use >>msg= %s<<.'
                                     %(tablename,globally.UPDATEPARAMETER))

                self._logger.debug('Found table %s in file %s, will append new entries in %s to the table.'
                                   % (tablename,self._filename, fullname))

            else:
                if msg == globally.UPDATEPARAMETER:
                    raise TypeError('You want to append to a parameter table >>%s<< that does not exist!' % fullname)

                description_dict = self._prm_make_description(data,fullname)
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

            table.flush()
            self._hdf5file.flush()
        except:
            self._logger.error('Failed storing table >>%s<< of >>%s<<.' %(tablename,fullname))
            raise



    def _prm_make_description(self, data, fullname):
        ''' Returns a dictionary that describes a pytbales row.
        '''


        descriptiondict={}

        for key, val in data.iteritems():


            col = self._prm_get_table_col(key, val, fullname)

            # if col is None:
            #     raise TypeError('Entry %s of %s cannot be translated into pytables column' % (key,fullname))

            descriptiondict[key]=col

        return descriptiondict


    def _prm_get_table_col(self, key, column, fullname):
        ''' Creates a pytables column instance.

        The type of column depends on the type of parameter entry.
        '''

        try:
            val = column[0]


            if type(val) == int:
                return pt.IntCol()

            if type(val) == str:
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



    def _prm_load_parameter_or_result(self, param):

        fullname = param.get_fullname()
        self._logger.debug('Loading %s' % fullname)

        try:
            hdf5group = eval('self._trajectorygroup.'+fullname)
        except Exception, e:
            raise AttributeError('Parameter or Result %s cannot be found in the hdf5file %s and trajectory %s' % (fullname,self._filename,self._trajectoryname))

        load_dict = {}
        for leaf in hdf5group:
            if isinstance(leaf,pt.Table) and 'DICT' in leaf.attrs and leaf.attrs['DICT']:
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
        key =leaf.name
        temp_table = temp_dict[key]
        temp_dict = temp_table.to_dict('list')

        load_dict[key]={}
        for innerkey, vallist in temp_dict.items():
            load_dict[innerkey] = vallist[0]


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
        load_dict[table_name]=ObjectTable(columns = table.colnames, index=range(table.nrows))
        for colname in table.colnames:
            col = table.col(colname)
            load_dict[table_name][colname]=list(col)

    def _prm_read_array(self, array, load_dict):

        #assert isinstance(carray,pt.CArray)
        array_name = array._v_name


        if 'TUPLE' in array.attrs and array.attrs['TUPLE']:
            load_dict[array_name] = tuple(array.read())
        else:
            result = array.read()

            ## Numpy Scalars are converted to numpy arrays, but we want to retrieve tha numpy scalar
            # as it was
            if isinstance(result,np.ndarray) and 'SCALAR' in array.attrs and array.attrs['SCALAR']:
                # this is the best way I know to actually restore the original data and not some strange
                # rank 0 scalars
                load_dict[array_name] = np.array([result])[0]
            else:
                load_dict[array_name] = result



