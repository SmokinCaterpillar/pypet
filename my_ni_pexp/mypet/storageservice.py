__author__ = 'robert'


import logging
import tables as pt
import os
import numpy as np
from mypet.trajectory import Trajectory,SingleRun
from mypet.parameter import BaseParameter, BaseResult, SimpleResult
from mypet import globally








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

    def store(self,*args,**kwargs):
        raise NotImplementedError('Implement this!')

    def load(self,*args,**kwargs):
        raise NotImplementedError('Implement this!')

class LazyStorageService(StorageService):

    def load(self,*args,**kwargs):
        pass

    def store(self,*args,**kwargs):
        pass

class HDF5StorageService(StorageService):
    ''' General Service to handle the storage of a Trajectory and Parameters
    '''

    def __init__(self, filename, filetitle, trajectoryname):
        self._filename = filename
        self._filetitle = filetitle
        self._trajectoryname = trajectoryname
        self._hdf5file = None
        self._trajectorygroup = None
        self._logger = logging.getLogger('mypet.storageservice_HDF5StorageService=' + self._filename)
        self._lock = None



    def load(self,*args,**kwargs):
        try:

            args = list(args)
            stuff_to_load = args.pop(0)

            if isinstance(stuff_to_load,Trajectory):
                return self._load_trajectory(stuff_to_load,*args,**kwargs)


            if isinstance(stuff_to_load, (BaseParameter,BaseResult)):
                return self._load_parameter_or_result(stuff_to_load,*args,**kwargs)


        except Exception,e:
            if isinstance(self._hdf5file,pt.File):
                if self._hdf5file.isopen:
                    self._hdf5file.close()
                    self._hdf5file = None
                    self._trajectorygroup = None
            raise



    def store(self,*args,**kwargs):
        try:

            args = list(args)

            stuff_to_store = args.pop(0)

            if isinstance(stuff_to_store,Trajectory):

                self._store_trajectory(stuff_to_store,*args,**kwargs)

            elif isinstance(stuff_to_store,SingleRun):

                self._store_single_run(stuff_to_store,*args,**kwargs)

            elif isinstance(stuff_to_store,(BaseParameter,BaseResult)):
                self._store_parameter_or_result(stuff_to_store,*args,**kwargs)

            else:
                raise AttributeError('Your storage of >>%s<< (args[0]) did not work, type of >>%s<< not supported' % (str(stuff_to_store),str(type(stuff_to_store))))

        except Exception,e:

            if isinstance(self._hdf5file,pt.File):
                if self._hdf5file.isopen:
                    self._hdf5file.flush()
                    self._hdf5file.close()
                    self._hdf5file = None
                    self._trajectorygroup = None
            raise


    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        result['_lock'] = None
        return result

    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._logger = logging.getLogger('mypet.storageservice_HDF5StorageService=' + self._filename)


    ######################## LOADING A TRAJECTORY #################################################

    def _load_trajectory(self,traj,trajectoryname, filename, replace,
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
        if filename:
            openfilename = filename
        else:
            openfilename = self._filename



        if not os.path.isfile(openfilename):
            raise ValueError('Filename ' + openfilename + ' does not exist.')
        self._hdf5file = pt.openFile(filename=openfilename, mode='r')

        if isinstance(trajectoryname,int):
            nodelist = self._hdf5file.listNodes(where='/')

            if trajectoryname >= len(nodelist) or trajectoryname < -len(nodelist):
                raise ValueError('Trajectory No. %d does not exists, there are only %d trajectories in %s.'
                % (self._trajectoryname,len(nodelist),filename))

            self._trajectorygroup = nodelist[trajectoryname]
            trajectoryname = self._trajectorygroup._v_name

        if replace:
            assert traj.is_empty()
            traj._name = trajectoryname
            self._trajectoryname = trajectoryname
            self._filename = filename

        try:
            self._trajectorygroup = self._hdf5file.getNode(where='/', name=trajectoryname)
        except Exception:
            raise ValueError('Trajectory ' + trajectoryname + ' does not exist.')

        self._load_meta_data(traj, replace)

        self._load_config(traj, load_params)
        self._load_params(traj, load_params)
        self._load_derived_params(traj, load_derived_params)
        self._load_results(traj, load_results)

        self._hdf5file.flush()
        self._hdf5file.close()

        self._hdf5file = None
        self._trajectorygroup = None


    def _load_meta_data(self,traj,  replace):
        metatable = self._trajectorygroup.Info
        metarow = metatable[0]

        traj._length = metarow['Length']

        if replace:
            traj._comment = metarow['Comment']
            traj._time = metarow['Timestamp']
            traj._formatted_time = metarow['Time']
            traj._loadedfrom=(metarow['Loaded_From_Trajectory'],metarow['Loaded_From_Filename'])


    def _load_config(self,traj,load_params):
        paramtable = self._trajectorygroup.ConfigTable
        self._load_any_param_or_result_table(traj,traj._config,paramtable, load_params)

    def _load_params(self,traj, load_params):
        paramtable = self._trajectorygroup.ParameterTable
        self._load_any_param_or_result_table(traj,traj._parameters,paramtable, load_params)

    def _load_derived_params(self,traj, load_derived_params):
        paramtable = self._trajectorygroup.DerivedParameterTable
        self._load_any_param_or_result_table(traj,traj._derivedparameters,paramtable, load_derived_params)

    def _load_results(self,traj,trajectoryname,filename, load_results):
        resulttable = self._trajectorygroup.ResultTable
        self._load_any_param_or_result_table(traj,traj._results,resulttable,True,trajectoryname,filename, load_results)


    def _load_any_param_or_result_table(self,traj, wheredict, paramtable, load_mode):
        ''' Loads a single parameter from a pytable.

        :param paramtable: The overiew pytable containing all parameters
        '''
        assert isinstance(paramtable,pt.Table)

        if len(wheredict) != 0:
            raise ValueError('You cannot load instances from %s into your trajectory since your trajectory is not empty.'
            % paramtable._v_name)

        if load_mode == globally.LOAD_SKELETON or load_mode == globally.LOAD_DATA:
            colnames = paramtable.colnames

            for row in paramtable.iterrows():
                location = row['Location']
                name = row['Name']
                fullname = location+'.'+name
                class_name = row['Class_Name']
                if fullname in wheredict:
                    self._logger.warn('Paremeter or Result >>%s<< is already in your trajectory, I am overwriting it.'
                                                                                     % fullname)



                new_class = traj._create_class(class_name)
                paraminstance = new_class(fullname)
                assert isinstance(paraminstance, (BaseParameter,BaseResult))


                if 'Size' in colnames:
                    size = row['Size']
                    if size > 1 and size != len(traj):
                        raise RuntimeError('Your are loading a parameter >>%s<< with length %d, yet your trajectory has lenght %d, something is wrong!'
                                           % (fullname,size,len(traj)))
                    elif size > 1:
                        traj._exploredparameters[fullname]=paraminstance
                    elif size == 1:
                        pass
                    else:
                        RuntimeError('You shall not pass!')

                if paramtable._v_name in ['DerivedParameterTable', 'ResultTable']:
                    #creator_name = row['Creator_Name']
                    creator_id = row['Creator_ID']
                    if paramtable._v_name == 'DerivedParameterTable':
                        if not creator_id in traj._id_to_dpar:
                            traj._id_to_dpar[creator_id] = []
                        traj._id_to_dpar[creator_id].append(paraminstance)
                        traj._dpar_to_id[fullname] = creator_id
                    elif paramtable._v_name == 'ResultTable':
                        if not creator_id in traj._id_to_res:
                            traj._id_to_res[creator_id] = []
                        traj._id_to_res[creator_id].append(paraminstance)
                        traj._res_to_id[fullname] = creator_id
                    else:
                        raise RuntimeError('You shall not pass!')



                if load_mode == globally.LOAD_DATA:
                    self.load(paraminstance)


                wheredict[fullname]=paraminstance

                traj._nninterface._add_to_nninterface(fullname, paraminstance)


    ######################## Storing a Signle Run ##########################################

    def _store_single_run(self,single_run):
        ''' Stores the derived parameters and results of a single run.
        '''

        assert isinstance(single_run,SingleRun)

        traj = single_run._single_run
        n = single_run.get_n()

        self._logger.info('Start storing run %d with name %s.' % (n,single_run.get_name()))
        self._hdf5file = pt.openFile(filename=self._filename, mode='a', title=self._filetitle)

        #print 'Storing %d' %n
        self._trajectorygroup = self._hdf5file.getNode(where='/', name=self._trajectoryname)



        paramtable = getattr(self._trajectorygroup, 'DerivedParameterTable')
        self._store_single_table(traj._derivedparameters, paramtable, traj.get_name(),n)
        self._store_dict(traj._derivedparameters)


        paramtable = getattr(self._trajectorygroup, 'ResultTable')
        self._store_single_table(traj._results, paramtable, traj.get_name(),n)
        self._store_dict(traj._results)

        # For better readability add the explored parameters to the Results
        self._add_explored_params(single_run)

        self._hdf5file.flush()
        self._hdf5file.close()
        self._hdf5file = None
        self._trajectorygroup = None

        self._logger.info('Finished storing run %d with name %s' % (n,single_run.get_name()))



    def _add_explored_params(self, single_run):
        ''' Stores the explored parameters as a Node in the HDF5File under the results nodes for easier comprehension of the hdf5file.
        '''
        paramdescriptiondict={'Location': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                'Name': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                'Class_Name': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                'Value' :pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH)}

        where = '/'+self._trajectoryname+'/Results/'+single_run.get_name()
        paramtable = self._hdf5file.createTable(where=where, name='ExploredParameterTable',
                                                description=paramdescriptiondict, title='ExploredParameterTable')

        paramdict = single_run._parent_trajectory._exploredparameters
        self._store_single_table(paramdict, paramtable, None,-1)



    ######################################### Storing a Trajectory and a Single Run #####################
    def _store_single_table(self,paramdict,paramtable, creator_name, creator_id):
        ''' Stores a single overview table.

        Called from _store_meta_data and store_single_run
        '''

        assert isinstance(paramtable, pt.Table)


        #print paramtable._v_name

        newrow = paramtable.row
        colnames = set(paramtable.colnames)
        for key, val in paramdict.items():
            if 'Size' in colnames:
                newrow['Size'] = len(val)


            if 'Location' in colnames:
                newrow['Location'] = val.get_location()

            if 'Name' in colnames:
                newrow['Name'] = val.get_name()

            if 'Class_Name' in colnames:
                newrow['Class_Name'] = val.get_class_name()

            if 'Value' in colnames:
                valstr = val.to_str()
                if len(valstr) >= globally.HDF5_STRCOL_MAX_NAME_LENGTH:
                    valstr = valstr[0:globally.HDF5_STRCOL_MAX_NAME_LENGTH-1]
                newrow['Value'] = valstr

            if 'Creator_Name' in colnames:
                newrow['Creator_Name'] = creator_name

            if 'Creator_ID' in colnames:
                newrow['Creator_ID'] = creator_id

            if 'Parent_Trajectory' in colnames:
                newrow['Parent_Trajectory'] = self._trajectoryname

            newrow.append()

        paramtable.flush()

    def _store_dict(self, data_dict):
        for key,val in data_dict.items():
            self.store(val)


    def _store_meta_data(self,traj):
        ''' Stores general information about the trajectory in the hdf5file.

        The 'Info' table will contain ththane name of the trajectory, it's timestamp, a comment,
        the length (aka the number of single runs), and if applicable a previous trajectory the
        current one was originally loaded from.
        The name of all derived and normal parameters as well as the results are stored in
        appropriate overview tables.
        Thes include the fullname, the name, the name of the class (e.g. SparseParameter),
        the size (1 for single parameter, >1 for explored parameter arrays).
        In case of a derived parameter or a result, the name of the creator trajectory or run
        and the id (-1 for trajectories) are stored.
        '''


        descriptiondict={'Name': pt.StringCol(len(traj._name)),
                         'Time': pt.StringCol(len(traj._formatted_time)),
                         'Timestamp' : pt.FloatCol(),
                         'Comment': pt.StringCol(len(traj._comment)),
                         'Length':pt.IntCol(),
                         'Loaded_From_Trajectory' : pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                         'Loaded_From_Filename' : pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH)}

        infotable = self._hdf5file.createTable(where=self._trajectorygroup, name='Info', description=descriptiondict, title='Info')
        newrow = infotable.row
        newrow['Name']=traj._name
        newrow['Timestamp']=traj._time
        newrow['Time']=traj._formatted_time
        newrow['Comment']=traj._comment
        newrow['Length'] = traj._length
        newrow['Loaded_From_Trajectory']=traj._loadedfrom[0]
        newrow['Loaded_From_Filename']=traj._loadedfrom[1]

        newrow.append()
        infotable.flush()


        tostore_dict =  {'ConfigTable':traj._config,
                         'ParameterTable':traj._parameters,
                         'DerivedParameterTable':traj._derivedparameters,
                         'ExploredParameterTable' :traj._exploredparameters,
                         'ResultTable' : traj._results}

        for key, dictionary in tostore_dict.items():

            paramdescriptiondict={'Location': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                  'Name': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                  'Class_Name': pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH)}


            if not key == 'ResultTable':
                paramdescriptiondict.update({'Size' : pt.Int64Col()})
                paramdescriptiondict.update({'Value' :pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH)})


            if key in ['DerivedParameterTable', 'ResultTable']:
                paramdescriptiondict.update({'Creator_Name':pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                             'Parent_Trajectory':pt.StringCol(globally.HDF5_STRCOL_MAX_NAME_LENGTH),
                                             'Creator_ID':pt.Int64Col()})

            paramtable = self._hdf5file.createTable(where=self._trajectorygroup, name=key, description=paramdescriptiondict, title=key)

            self._store_single_table(dictionary, paramtable, traj._name,-1)


    def _store_trajectory(self, traj):
        ''' Stores a trajectory to the in __init__ specified hdf5file.
        '''



        self._logger.info('Start storing Trajectory %s.' % self._trajectoryname)
        (path, filename)=os.path.split(self._filename)
        if not os.path.exists(path):
            os.makedirs(path)




        self._hdf5file = pt.openFile(filename=self._filename, mode='a', title=self._filetitle)

        self._trajectorygroup = self._hdf5file.createGroup(where='/', name=traj._name, title=traj._name)


        self._store_meta_data(traj)

        self._store_dict(traj._config)
        self._store_dict(traj._parameters)
        self._store_dict(traj._results)
        self._store_dict(traj._derivedparameters)


        self._hdf5file.flush()

        self._hdf5file.close()
        self._hdf5file = None
        self._trajectorygroup = None
        self._logger.info('Finished storing Trajectory.')


    ################# Storing and Loading Parameters ############################################


    def _store_parameter_or_result(self, param):

        fullname = param.get_fullname()
        self._logger.debug('Storing %s.' % fullname)
        store_dict = param.__store__()


        newly_opened = False
        if self._hdf5file == None:
            self._hdf5file = pt.openFile(filename=self._filename, mode='a', title=self._filetitle)
            self._trajectorygroup = self._hdf5file.createGroup(where='/', name=self._trajectoryname, title=self._trajectoryname)
            newly_opened = True

        self._check_and_convert_dictionary_structure(store_dict)
        self._check_info_dict(param, store_dict)

        group= self._create_groups(fullname)



        for key, data_to_store in store_dict.items():
            if isinstance(data_to_store, dict):
                self._store_into_pytable(key, data_to_store, group, fullname)
            elif isinstance(data_to_store, np.ndarray):
                self._store_into_array(key, data_to_store, group, fullname)
            else:
                raise AttributeError('I don not know how to store %s of %s. Cannot handle type %s.'%(key,fullname,str(type(data_to_store))))


        if newly_opened:
            self._hdf5file.flush()

            self._hdf5file.close()
            self._hdf5file = None
            self._trajectorygroup = None


    def _check_and_convert_dictionary_structure(self,store_dict):
        ''' Checks for all dictionaries in store_dict, whether they contain lists or only single items. If the latter
         is true the single items are converted to lists
        :param store_dict: The dictionary containing the data
        :return:
        '''
        for datadict in store_dict.values():
            if isinstance(datadict,dict):
                for key, val in datadict.items():
                    if not isinstance(val, list):
                        val = [val]
                        datadict[key] = val

    def _store_into_array(self, key, data, group, fullname):
        atom = pt.Atom.from_dtype(data.dtype)
        carray=self._hdf5file.createCArray(where=group, name=key,atom=atom,shape=data.shape)
        carray[:]=data
        self._hdf5file.flush()

    def _check_info_dict(self,param, store_dict):
        ''' Checks if the storage dictionary contains an appropriate description of the parameter.
        This entry is called Info, and should contain only a single
        :param param: The parameter to store
        :param store_dict: the dictionary that describes how to store the parameter
        '''
        if not 'Info' in store_dict:
            store_dict['Info']={}

        info_dict = store_dict['Info']

        test_item = info_dict.itervalues().next()
        if len(test_item)>1:
            raise AttributeError('Your description of the parameter %s, generated by __store__ and stored into >>Info<< has more than a single dictionary in the list.' % param.get_fullname())


        if not 'Name' in info_dict:
            info_dict['Name'] = [param.get_name()]
        else:
            assert info_dict['Name'][0] == param.get_name()

        if not 'Location' in info_dict:
            info_dict['Location'] = [param.get_location()]
        else:
            assert info_dict['Location'][0] == param.get_location()

        # if not 'Comment' in info_dict:
        #     info_dict['Comment'] = [param.get_comment()]
        # else:
        #     assert info_dict['Comment'][0] == param.get_comment()

        if not 'Type' in info_dict:
            info_dict['Type'] = [str(type(param))]
        else:
            assert info_dict['Type'][0] == str(type(param))


        if not 'Class_Name' in info_dict:
            info_dict['Class_Name'] = [param.__class__.__name__]
        else:
            assert info_dict['Class_Name'][0] == param.__class__.__name__



    def _create_groups(self, key):
        newhdf5group = self._trajectorygroup
        split_key = key.split('.')
        for name in split_key:
            if not newhdf5group.__contains__(name):
                newhdf5group=self._hdf5file.createGroup(where=newhdf5group, name=name, title=name)
            else:
                newhdf5group = getattr(newhdf5group, name)

        return newhdf5group

    def _store_into_pytable(self,tablename,data,hdf5group,fullname):

        if hasattr(hdf5group,tablename):
            table = getattr(hdf5group,tablename)
            self._logger.debug('Found table %s in file %s, will append new entries in %s to the table.' % (tablename,
                                                                                                           self._filename,
                                                                                                           fullname))

            ## Check if the colnames and dtypes work together
            # colnames = table.colnames
            # for key, val_list in data.items():
            #     if not key in colnames:
            #         raise AttributeError('Failed storing %s. Cannot append new data to table, since entry %s is not a column of table %s.' % (fullname,key,tablename))
        else:
            description_dict = self._make_description(data,fullname)
            table = self._hdf5file.createTable(where=hdf5group,name=tablename,description=description_dict,
                                               title=tablename)

        assert isinstance(table,pt.Table)

        nrows = table.nrows
        row = table.row

        datasize = len(data.itervalues().next())


        for n in range(nrows, datasize):

            for key,val_list in data.items():
                row[key] = val_list[n]

            row.append()

        table.flush()
        self._hdf5file.flush()



    def _make_description(self, data, fullname):
        ''' Returns a dictionary that describes a pytbales row.
        '''

        descriptiondict={}

        for key, val in data.items():


            col = self._get_table_col(val)

            # if col is None:
            #     raise TypeError('Entry %s of %s cannot be translated into pytables column' % (key,fullname))

            descriptiondict[key]=col

        return descriptiondict


    def _get_table_col(self, val_list):
        ''' Creates a pytables column instance.

        The type of column depends on the type of parameter entry.
        '''


        val = val_list[0]


        if type(val) == int:
            return pt.IntCol()

        if type(val) == str:
            itemsize = int(self._get_longest_stringsize(val_list))
            return pt.StringCol(itemsize)

        if isinstance(val, np.ndarray):
            if np.issubdtype(val.dtype,np.str):
                itemsize = int(self._get_longest_stringsize(val_list))
                return pt.StringCol(itemsize,shape=val.shape)
            else:
                return pt.Col.from_dtype(np.dtype((val.dtype,val.shape)))
        else:
            return pt.Col.from_dtype(np.dtype(type(val)))




    def _get_longest_stringsize(self, string_list):
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



    def _load_parameter_or_result(self, param):

        fullname = param.get_fullname()
        self._logger.debug('Start Loading %s' % fullname)

        newly_opened = False
        if self._hdf5file == None:
            self._hdf5file = pt.openFile(filename=self._filename, mode='r', title=self._filetitle)
            self._trajectorygroup = getattr(self._hdf5file,self._trajectoryname)

        try:
            hdf5group = eval('self._trajectorygroup.'+fullname)
        except Exception, e:
            raise AttributeError('Parameter %s cannot be found in the hdf5file %s and trajectory %s' % (fullname,self._filename,self._trajectoryname))

        load_dict = {}
        for leaf in hdf5group:
            if isinstance(leaf, pt.Table):
                self._read_table(leaf, load_dict)
            elif isinstance(leaf, pt.CArray):
                self._read_carray(leaf, load_dict)

        if newly_opened:
            self._hdf5file.close()
            self._hdf5file = None
            self._trajectorygroup = None


        param.__load__(load_dict)


    def _read_table(self,table,load_dict):
        ''' Reads a non-nested Pytables table column by column.

        :type table: pt.Table
        :type load_dict:
        :return:
        '''

        table_name = table._v_name
        load_dict[table_name]={}
        for colname in table.colnames:
            col = table.col(colname)
            load_dict[table_name][colname]=list(col)

    def _read_carray(self, carray, load_dict):

        assert isinstance(carray,pt.CArray)
        array_name = carray._v_name

        load_dict[array_name] = carray[:]

