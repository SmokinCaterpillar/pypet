__author__ = 'robert'


import logging
import tables as pt
import os
import numpy as np
from mypet.trajectory import Trajectory,SingleRun
from mypet.parameter import BaseParameter, BaseResult


import collections



class HDF5StorageService(object):
    ''' General Service to handle the storage of a Trajectory and Parameters
    '''

    MAX_NAME_LENGTH = 1024

    def __init__(self, filename, filetitle, trajectoryname):
        self._filename = filename
        self._filetitle = filetitle
        self._trajectoryname = trajectoryname
        self._hdf5file = None
        self._trajectorygroup = None
        self._logger = logging.getLogger('mypet.storageservice_HDF5StorageService=' + self._filename)


    def load(self,*args,**kwargs):

        lock = None

        try:
            stuff_to_load = args.pop(0)


            if 'lock' in kwargs:
                lock = kwargs.pop('lock')
                lock.acquire()

            if isinstance(stuff_to_load,Trajectory):
                return self._load_trajectory(stuff_to_load,*args,**kwargs)


            if isinstance(stuff_to_load, (BaseParameter,BaseResult)):
                return self._load_parameter_or_result(stuff_to_load,*args,**kwargs)


            if lock:
                lock.release()
                lock = None

        except Exception,e:
            if isinstance(self._hdf5file,pt.File):
                if self._hdf5file.isopen:
                    self._hdf5file.close()
                    self._hdf5file = None
                    self._trajectorygroup = None

            if lock:
                lock.release()
            raise


    def store(self,*args,**kwargs):

        lock = None
        args = list(args)

        try:
            if 'lock' in kwargs:
                lock = kwargs.pop('lock')
                lock.acquire()


            stuff_to_store = args.pop(0)

            if isinstance(stuff_to_store,Trajectory):

                self._store_trajectory(stuff_to_store,*args,**kwargs)

            elif isinstance(stuff_to_store,SingleRun):

                self._store_single_run(stuff_to_store,*args,**kwargs)

            elif isinstance(stuff_to_store,(BaseParameter,BaseResult)):
                self._store_parameter_or_result(stuff_to_store,*args,**kwargs)

            else:
                raise AttributeError('Your storage of >>%s<< (args[0]) did not work, type of >>%s<< not supported' % (str(stuff_to_store),str(type(stuff_to_store))))

            if lock:
                lock.release()
                lock = None

        except Exception,e:

            if isinstance(self._hdf5file,pt.File):
                if self._hdf5file.isopen:
                    self._hdf5file.flush()
                    self._hdf5file.close()
                    self._hdf5file = None
                    self._trajectorygroup = None

            if lock:
                lock.release()
            raise



    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        return result

    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._logger = logging.getLogger('mypet.storageservice_HDF5StorageService=' + self.filename)


    ######################## LOADING A TRAJECTORY #################################################

    def _load_trajectory(self,traj, trajectoryname, filename = None, load_skeleton = True, load_derived_params = False, load_results = False, replace = False):
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
            openfilename = traj._filename

        if replace:
            traj._name = trajectoryname
            traj._filename = filename


        traj._loadedfrom = (trajectoryname,os.path.abspath(openfilename))

        if not os.path.isfile(openfilename):
            raise AttributeError('Filename ' + openfilename + ' does not exist.')

        self._hdf5file = pt.openFile(filename=openfilename, mode='r')


        try:
            self._trajectorygroup = self._hdf5file.getNode(where='/', name=trajectoryname)
        except Exception:
            raise AttributeError('Trajectory ' + trajectoryname + ' does not exist.')

        self._load_meta_data(traj, replace)
        self._load_params(traj)
        if load_skeleton or load_derived_params:
            self._load_derived_params(traj, load_derived_params)

        if load_skeleton or load_results:
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
            traj._loadedfrom=metarow['Loaded_From']
        else:
            traj.add_comment(metarow['Comment'])


    def _load_params(self,traj):
        paramtable = self._trajectorygroup.ParameterTable
        self._load_any_param_or_result(traj,traj._parameters,paramtable, True)

    def _load_derived_params(self,traj, load_derived_params):
        paramtable = self._trajectorygroup.DerivedParameterTable
        self._load_any_param_or_result(traj,traj._derivedparameters,paramtable, load_derived_params)

    def _load_results(self,traj,trajectoryname,filename, load_results):
        resulttable = self._trajectorygroup.ResultsTable
        self._load_any_param_or_result(traj,traj._results,resulttable,True,trajectoryname,filename, load_results)


    def _load_any_param_or_result(self,traj, wheredict, paramtable, load_data=True):
        ''' Loads a single parameter from a pytable.

        :param paramtable: The overiew pytable containing all parameters
        '''
        assert isinstance(paramtable,pt.Table)

        for row in paramtable.iterrows():
            location = row['Location']
            name = row['Name']
            fullname = location+'.'+name
            class_name = row['Class_Name']
            if fullname in wheredict:
                self._logger.warn('Paremeter ' + fullname + ' is already in your trajectory, I am overwriting it.')

            if paramtable._v_name in ['DerivedParameterTable', 'ResultsTable']:
                #creator_name = row['Creator_Name']
                creator_id = row['Creator_ID']

            new_class = traj._create_class(class_name)
            paraminstance = new_class(fullname)

            assert isinstance(paraminstance, (BaseParameter,BaseResult))

            if isinstance(paraminstance,BaseResult):
                if not creator_id in traj._result_ids:
                    traj._result_ids[creator_id]=[]
                traj._result_ids[creator_id].append(paraminstance)


            if load_data:
                self.load(paraminstance,traj=traj.get_name())

            if isinstance(paraminstance,BaseParameter):
                if paraminstance.is_array():
                    traj._exploredparameters[fullname] = paraminstance

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
        self._trajectorygroup = self._hdf5file.getNode(where='/', name=self._trajectory_name)



        paramtable = getattr(self._trajectorygroup, 'DerivedParameterTable')
        self._store_single_table(traj._derivedparameters, paramtable, traj.get_name(),n)
        self._store_dict(traj._derivedparameters)


        paramtable = getattr(self._trajectorygroup, 'ResultsTable')
        self._store_single_table(traj._results, paramtable, traj.get_name(),n)
        self._store_dict(traj._results)

        self._hdf5file.flush()
        self._hdf5file.close()
        self._hdf5file = None
        self._trajectorygroup = None

        self._logger.info('Finished storing run % n with name %s' % (n,single_run.get_name()))


    ######################################### Storing a Trajectory and a Single Run #####################
    def _store_single_table(self,paramdict,paramtable, creator_name, creator_id):
        ''' Stores a single overview table.

        Called from _store_meta_data and store_single_run
        '''

        assert isinstance(paramtable, pt.Table)


        #print paramtable._v_name

        newrow = paramtable.row
        for key, val in paramdict.items():
            if not paramtable._v_name == 'ResultsTable' :
                newrow['Size'] = len(val)
            else:
                #check if this is simply an added explored parameter to easily comprehend the
                # hdf5 tree with a viewer
                if 'ExploredParameters' in key:
                    continue;


            newrow['Location'] = val.get_location()
            newrow['Name'] = val.get_name()
            newrow['Class_Name'] = val.get_class_name()


            if paramtable._v_name in ['DerivedParameterTable', 'ResultsTable']:
                newrow['Creator_Name'] = creator_name
                newrow['Creator_ID'] = creator_id
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
                         'Loaded_From_Trajectory' : pt.StringCol(self.MAX_NAME_LENGTH),
                         'Loaded_From_Filename' : pt.StringCol(self.MAX_NAME_LENGTH)}

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
                         'ResultsTable' : traj._results}

        for key, dictionary in tostore_dict.items():

            paramdescriptiondict={'Location': pt.StringCol(HDF5StorageService.MAX_NAME_LENGTH),
                                  'Name': pt.StringCol(HDF5StorageService.MAX_NAME_LENGTH),
                                  'Class_Name': pt.StringCol(HDF5StorageService.MAX_NAME_LENGTH)}

            if not key == 'ResultsTable':
                paramdescriptiondict.update({'Size' : pt.Int64Col()})

            if key in ['DerivedParameterTable', 'ResultsTable']:
                paramdescriptiondict.update({'Creator_Name':pt.StringCol(HDF5StorageService.MAX_NAME_LENGTH),
                                             'Parent_Trajectory':pt.StringCol(HDF5StorageService.MAX_NAME_LENGTH),
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


        self._check_info_dict(param, store_dict)

        group= self._create_groups(fullname)



        for key, data_to_store in store_dict.items():
            if isinstance(data_to_store, dict):
                self._store_into_pytable(key, data_to_store, group, fullname)
            elif isinstance(data_to_store, np.array):
                self._store_into_array(key, data_to_store, group, fullname)
            else:
                raise AttributeError('I don not know how to store %s of %s. Cannot handle type %s.'%(key,fullname,str(type(data_to_store))))


        if newly_opened:
            self._hdf5file.flush()

            self._hdf5file.close()
            self._hdf5file = None
            self._trajectorygroup = None


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
            store_dict['Info']=[{}]

        info_dict = store_dict['Info']

        if not len(info_dict.itervalues().next())==1:
            raise AttributeError('Your description of the parameter %s, generated by __store__ and stored into >>Info<< has more than a single dictionary in the list.' % param.get_fullname())


        if not 'Name' in info_dict:
            info_dict['Name'] = [param.get_name()]
        else:
            assert info_dict['Name'][0] == param.get_name()

        if not 'Location' in info_dict:
            info_dict['Location'] = [param.get_location()]
        else:
            assert info_dict['Location'][0] == param.get_location()

        if not 'Comment' in info_dict:
            info_dict['Comment'] = [param.get_comment()]
        else:
            assert info_dict['Comment'][0] == param.get_comment()

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


            col = self._get_table_col(key, val)

            if col is None:
                raise TypeError('Entry %s of %s cannot be translated into pytables column' % (key,fullname))

            descriptiondict[key]=col

        return descriptiondict


    def _get_table_col(self, key, val_list):
        ''' Creates a pytables column instance.

        The type of column depends on the type of parameter entry.
        '''
        val = val_list[0]
        if isinstance(val, np.int64):
            return pt.Int64Col()
        if isinstance(val, np.float):
            return pt.Float64Col()
        if isinstance(val, np.bool):
            return pt.BoolCol()
        if isinstance(val, np.str):
            itemsize = int(self._get_longest_stringsize(key,val_list))
            return pt.StringCol(itemsize=itemsize)
        if isinstance(val,np.complex):
            return pt.ComplexCol()
        if isinstance(val, np.ndarray):
            valdtype = val.dtype
            valshape = np.shape(val)

            if np.issubdtype(valdtype, np.int64):
                return pt.Int64Col(shape=valshape)
            if np.issubdtype(valdtype, np.float):
                return pt.Float64Col(shape=valshape)
            if np.issubdtype(valdtype, np.bool):
                return pt.BoolCol(shape=valshape)
            if np.issubdtype(valdtype,np.complex):
                return pt.ComplexCol(shape=valshape)
            if np.issubdtype(valdtype,np.str):
                return pt.StringCol(shape=valshape)


        return None

    def _get_longest_stringsize(self,key, string_list):
        ''' Returns the longest stringsize for a string entry across data.
        '''
        maxlength = 1

        for string in string_list:
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

