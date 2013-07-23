from scipy.optimize.anneal import _state
from numpy.lib._iotools import _is_bytes_like

__author__ = 'robert'


import logging
import tables as pt
import os
import numpy as np
from mypet.trajectory import Trajectory,SingleRun
from mypet.parameter import BaseParameter, BaseResult


import collections

def flatten(d, parent_key=''):
    items = []
    for k, v in d.items():
        new_key = parent_key + '/' + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten(v, new_key).items())
        else:
            items.append((new_key, v))
    return dict(items)

class HDF5StorageService(object):
    ''' General Service to handle the storage of a Trajectory and Parameters
    '''

    MAX_NAME_LENGTH = 1024

    def __init__(self, filename, filetitle):
        self._filename = filename
        self._filetitle = filetitle
        self._hdf5file = None
        self._trajectorygroup = None
        self._logger = logging.getLogger('mypet.storageservice_HDF5StorageService=' + self.filename)


    def load(self,*args,**kwargs):
        stuff_to_load = args.pop(0)

        if isinstance(stuff_to_load,Trajectory
            self._load_trajectory(stuff_to_load,*args,**kwargs)

    def store(self,*args,**kwargs):

        stuff_to_store = args.pop(0)


        if isinstance(stuff_to_store,Trajectory):

            type = kwargs.pop('type')

            if type == 'Trajectory':
                self._store_trajectory(stuff_to_store)

            else:
                n = kwargs.pop('n')
                self._store_single_run(stuff_to_store,n)

        elif isinstance(stuff_to_store,BaseParameter):
            traj=kwargs.pop('traj')
            self._store_parameter(stuff_to_store,traj)

        else:
            raise AttributeError('Your storage did not work, type of args[0] >>%s<< not supported' % str(type(stuff_to_store)))

    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger']
        return result

    def __setstate__(self, statedict):
        self.__dict__.update(statedict)
        self._logger = logging.getLogger('mypet.storageservice_HDF5StorageService=' + self.filename)


    ######################## LOADING A TRAJECTORY #################################################

    def _load_trajectory(self,traj, trajectoryname, filename = None, load_derived_params = False, load_results = False, replace = False):
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
        if load_derived_params:
            self._load_derived_params(traj)
        if load_results:
            self._load_results(traj,trajectoryname,filename)

        self._hdf5file.close()



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
        self._load_any_param_or_result(traj,traj._parameters,paramtable)

    def _load_derived_params(self,traj):
        paramtable = self._trajectorygroup.DerivedParameterTable
        self._load_any_param_or_result(traj,traj._derivedparameters,paramtable)

    def _load_results(self,traj,trajectoryname,filename):
        resulttable = self._trajectorygroup.ResultsTable
        self._load_any_param_or_result(traj,traj._results,resulttable,True,trajectoryname,filename)


    def _load_any_param_or_result(self,traj,wheredict,paramtable,creating_result_tree=False, trajectory_name = None, filename = None):
        ''' Loads a single parameter from a pytable.

        :param paramtable: The overiew pytable containing all parameters
        '''
        assert isinstance(paramtable,pt.Table)

        for row in paramtable.iterrows():
            location = row['Location']
            name = row['Name']
            fullname = location+'.'+name
            class_name = row['Class_Name']
            if location in wheredict:
                self._logger.warn('Paremeter ' + fullname + ' is already in your trajectory, I am overwriting it.')
                del wheredict[fullname]
                continue

            if paramtable._v_name in ['DerivedParameterTable', 'ResultsTable']:
                #creator_name = row['Creator_Name']
                creator_id = row['Creator_ID']

            new_class = traj._create_class(class_name)

            if not creating_result_tree:
                paraminstance = new_class(name,location)
            else:
                paraminstance= new_class(name, location, trajectory_name, filename)
                if not creator_id in traj._result_ids:
                    traj._result_ids[creator_id]=[]
                traj._result_ids[creator_id].append(paraminstance)

            where = 'self._trajectorygroup.' + fullname
            paramgroup = eval(where)

            assert isinstance(paraminstance, (BaseParameter,BaseResult))

            if not creating_result_tree:
                paraminstance.load_from_hdf5(paramgroup)

                if len(paraminstance)>1:
                    traj._exploredparameters[fullname] = paraminstance

            wheredict[fullname]=paraminstance

            traj._nninterface._add_to_nninterface(fullname, paraminstance)


    ######################## Storing a Signle Run ##########################################

    def _store_single_run(self,traj,trajectory_name,n):
        ''' Stores the derived parameters and results of a single run.
        '''
        self._hdf5file = pt.openFile(filename=self._filename, mode='a', title=self._filetitle)

        #print 'Storing %d' %n
        self._trajectorygroup = self._hdf5file.getNode(where='/', name=trajectory_name)



        paramtable = getattr(self._trajectorygroup, 'DerivedParameterTable')
        self._store_single_table(traj._derivedparameters, paramtable, traj.get_name(),n,trajectory_name)


        self._store_dict(traj._derivedparameters)


        paramtable = getattr(self._trajectorygroup, 'ResultsTable')
        self._store_single_table(traj._results, paramtable, traj.get_name(),n,trajectory_name)


        self._store_dict(traj._results)

        self._hdf5file.flush()
        self._hdf5file.close()
        self._hdf5file = None
        self._trajectorygroup = None


    ######################################### Storing a Trajectory and a Single Run #####################
    def _store_single_table(self,paramdict,paramtable, creator_name, creator_id, parent_trajectory):
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


            newrow['Full_Name'] = key
            newrow['Name'] = val.get_name()
            newrow['Class_Name'] = val.get_class_name()


            if paramtable._v_name in ['DerivedParameterTable', 'ResultsTable']:
                newrow['Creator_Name'] = creator_name
                newrow['Creator_ID'] = creator_id
                newrow['Parent_Trajectory'] = parent_trajectory

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


        loaddict = {'Trajectory' : pt.StringCol(self.MAX_NAME_LENGTH),
                    'Filename' : pt.StringCol(self.MAX_NAME_LENGTH)}

        descriptiondict={'Name': pt.StringCol(len(traj._name)),
                         'Time': pt.StringCol(len(traj._formatted_time)),
                         'Timestamp' : pt.FloatCol(),
                         'Comment': pt.StringCol(len(traj._comment)),
                         'Length':pt.IntCol(),
                         'Loaded_From': loaddict.copy()}

        infotable = self._hdf5file.createTable(where=self._trajectorygroup, name='Info', description=descriptiondict, title='Info')
        newrow = infotable.row
        newrow['Name']=traj._name
        newrow['Timestamp']=traj._time
        newrow['Time']=traj._formatted_time
        newrow['Comment']=traj._comment
        newrow['Length'] = traj._length
        newrow['Loaded_From/Trajectory']=traj._loadedfrom[0]
        newrow['Loaded_From/Filename']=traj._loadedfrom[1]

        newrow.append()
        infotable.flush()


        tostore_dict =  {'ParameterTable':traj._parameters, 'DerivedParameterTable':traj._derivedparameters, 'ExploredParameterTable' :traj._exploredparameters,'ResultsTable' : traj._results}

        for key, dictionary in tostore_dict.items():

            paramdescriptiondict={'Full_Name': pt.StringCol(Trajectory.MAX_NAME_LENGTH),
                                  'Name': pt.StringCol(Trajectory.MAX_NAME_LENGTH),
                                  'Class_Name': pt.StringCol(Trajectory.MAX_NAME_LENGTH)}

            if not key == 'ResultsTable':
                paramdescriptiondict.update({'Size' : pt.IntCol()})

            if key in ['DerivedParameterTable', 'ResultsTable']:
                paramdescriptiondict.update({'Creator_Name':pt.StringCol(Trajectory.MAX_NAME_LENGTH),
                                             'Parent_Trajectory':pt.StringCol(Trajectory.MAX_NAME_LENGTH),
                                             'Creator_ID':pt.IntCol()})

            paramtable = self._hdf5file.createTable(where=trajectorygroup, name=key, description=paramdescriptiondict, title=key)

            self._store_single_table(dictionary, paramtable, traj._name,-1,traj._name)


    def _store_trajectory(self, traj):
        ''' Stores a trajectory to the in __init__ specified hdf5file.
        '''
        self._logger.info('Start storing Parameters.')
        (path, filename)=os.path.split(self._filename)
        if not os.path.exists(path):
            os.makedirs(path)




        self._hdf5file = pt.openFile(filename=self._filename, mode='a', title=self._filetitle)

        self._trajectorygroup = self._hdf5file.createGroup(where='/', name=traj._name, title=traj._name)


        self._store_meta_data(traj)




        self._store_dict(traj._parameters)
        self._store_dict(traj._results)
        self._store_dict(traj._derivedparameters)


        self._hdf5file.flush()

        self._hdf5file.close()
        self._hdf5file = None
        self._trajectorygroup = None
        self._logger.info('Finished storing Parameters.')


    ################# Storing and Loading Parameters ############################################


    def _store_parameter(self, param, traj):
        fullname = param.get_fullname()
        self._logger.debug('Start Storing %s' % fullname)

        newly_opened = False
        if self._hdf5file == None:
            self._hdf5file = pt.openFile(filename=self._filename, mode='a', title=self._filetitle)
            self._trajectorygroup = self._hdf5file.createGroup(where='/', name=traj._name, title=traj._name)
            newly_opened = True

        store_dict = param.__store__()
        self._check_info_dict(param, store_dict)

        group= self._create_groups(self._trajectorygroup, fullname)



        for key, list_of_dicts in store_dict:
            self._store_into_a_pytable(key, list_of_dicts, group, fullname)


        if newly_opened:
            self._hdf5file.flush()

            self._hdf5file.close()
            self._hdf5file = None
            self._trajectorygroup = None


    def _check_info_dict(self,param, store_dict):
        ''' Checks if the storage dictionary contains an appropriate description of the parameter.
        This entry is called Info, and should contain only a single
        :param param: The parameter to store
        :param store_dict: the dictionary that describes how to store the parameter
        '''
        if not 'Info' in store_dict:
            store_dict['Info']=[{}]

        if not len(store_dict['Info'])==1:
            raise AttributeError('Your description of the parameter %s, generated by __store__ and stored into >>Info<< has more than a single dictionary in the list.' % param.get_fullname())

        info_dict = store_dict['Info'][0]

        if not 'Name' in info_dict:
            info_dict['Name'] = param.get_name()
        else:
            assert info_dict['Name'] == param.get_name()

        if not 'Location' in info_dict:
            info_dict['Location'] = param.get_location()
        else:
            assert info_dict['Location'] == param.get_location()

        if not 'Comment' in info_dict:
            info_dict['Comment'] = param.get_comment()
        else:
            assert info_dict['Comment'] == param.get_comment()

        if not 'Type' in info_dict:
            info_dict['Type'] = str(type(param))
        else:
            assert info_dict['Type'] == str(type(param))


        if not 'Class_Name' in info_dict:
            info_dict['Class_Name'] = param.__class__.__name__
        else:
            assert info_dict['Class_Name'] == str(type(param))



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

        description_dict = self._make_description(data,fullname)

        table = self._hdf5file.create_table(hdf5group,tablename,description_dict)

        row = table.row()

        for data_dict in data:
            flat_dict = flatten(data_dict)

            for key,val in flat_dict.items():
                row[key] = val

            row.append()

        table.flush()



    def _make_description(self, data_list, fullname):
        ''' Returns a dictionary that describes a pytbales row.
        '''

        descriptiondict={}

        for key, val in data_list[0].items():


            col = self._get_table_col( val, key, data_list)

            if col is None:
                raise TypeError('Entry %s of %s cannot be translated into pytables column' % (key,fullname))

            descriptiondict[key]=col

        return descriptiondict


    def _get_table_col(self, val, key,  data_list):
        ''' Creates a pytables column instance.

        The type of column depends on the type of parameter entry.
        '''
        if isinstance(val, np.int):
                return pt.IntCol()
        if isinstance(val, np.float):
                return pt.Float64Col()
        if isinstance(val, np.bool):
                return pt.BoolCol()
        if isinstance(val, np.str):
                itemsize = int(self._get_longest_stringsize(key,data_list))
                return pt.StringCol(itemsize=itemsize)
        if isinstance(val, np.ndarray):
            valdtype = val.dtype
            valshape = np.shape(val)

            if np.issubdtype(valdtype, int):
                    return pt.IntCol(shape=valshape)
            if np.issubdtype(valdtype, float):
                    return pt.Float64Col(shape=valshape)
            if np.issubdtype(valdtype, bool):
                    return pt.BoolCol(shape=valshape)

        return None

    def _get_longest_stringsize(self,key, data_list):
        ''' Returns the longest stringsize for a string entry across data.
        '''
        maxlength = 1
        strings = []

        for data_dict in data_list:
            string = data_dict[key]
            maxlength = max(len(string),maxlength)

        return maxlength



    def _load_parameter(self, param, traj):

        fullname = param.get_fullname()
        self._logger.debug('Start Loading %s' % fullname)

        newly_opened = False
        if self._hdf5file == None:
            self._hdf5file = pt.openFile(filename=self._filename, mode='r', title=self._filetitle)
            self._trajectorygroup = getattr(self._hdf5file,traj.get_name()))

        try:
            hdf5group = eval('self._trajectorygroup.'+fullname)
        except Exception, e:
            raise AttributeError('Parameter %s cannot be found in the hdf5file %s and trajectory %s' % (fullname,self._filename,traj.get_name()))

        load_dict = {}
        for table in hdf5group:
            self._read_param_table(table, load_dict)

        if newly_opened:
            self._hdf5file.close()
            self._hdf5file = None
            self._trajectorygroup = None


    def _read_param_table(table,load_dict)
        '''

        :param table:
        :type table: pt.Table
        :param load_dict:
        '''

        table_name = table._v_name
        load_dict[table_name]=[]
        for row in table:
            for key,val in row.


