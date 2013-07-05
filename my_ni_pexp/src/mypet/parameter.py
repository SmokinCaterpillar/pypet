'''
Created on 17.05.2013

@author: Robert Meyer
'''

import logging
import petexceptions as pex
import tables as pt
import numpy as np
import scipy.sparse as spsp
import copy
from numpy.numarray.numerictypes import IsType



class BaseParameter(object):
    ''' Specifies the methods that need to be implemented for a Trajectory Parameter
    
    It is initialized with a fullname that specifies its position within the Trajectory, e.g.:
    Parameters.group.paramname
    The shorter name of the parameter is name=paramname, accordingly.
        
    For storing a parameter into hdf5 format the parameter implements a full node, how the storage 
    in the node is handled is left to the user.
        
    The parameter class can instantiate a single parameter as well as an array with several 
    parameters (of the same type) for exploration.
    It is recommended to also implement the __getatr__ and __setatr__ methods, because para.val 
    should return the value of the entry only for the first parameter in an array.
    param.val = 1 should also only modify the very first parameter only.
    The other entries can only be accessed during a particular run. Therefore, explored parameters 
    create for each run a copy of themselves with the corresponding array element as the only 
    parameter entries.
    
    Parameters can be locked to forbid further modification.
    If multiprocessing is desired the parameter must be pickable!
    ''' 
    def __init__(self, name, fullname):
        self._name=name
        self._fullname = fullname
        
    def __len__(self):
        ''' Returns the length of the parameter.
        
        Only parameters that will be explored have a length larger than 1.
        If no values have been added to the parameter it's length is 0.
        '''
        raise NotImplementedError( "Should have implemented this." )
    
    def __call__(self,*args):
        ''' param(name) -> Value stored at param.name
        
        A call to the parameter with the given argument returns the value of the argument. If the parameter is an array only the first entry of the given name should be returned.
        '''
        raise NotImplementedError( "Should have implemented this." )
    
    def lock(self):
        ''' Locks the parameter and allows no further modification except exploration.'''
        raise NotImplementedError( "Should have implemented this." )
        
    def store_to_hdf5(self,hdf5file,hdf5group):
        ''' Method to store a parameter to an hdf5file.
        
        :param hdf5group: is the group where the parameter is stored in the hdf5file. The name of the group is the name of the parameter.
        '''
        raise NotImplementedError( "Should have implemented this." )
    
    def load_from_hdf5(self,hdf5group):
        ''' param.load_from_hdf5(hdf5group)-> Recovers parameter from the given group in a hdf5file.
        
            The name of the group is equal to the parameter name.
        '''
        raise NotImplementedError( "Should have implemented this." )
    

    def gfn(self,valuename=None):
        ''' Short for get_fullname '''
        return self.get_fullname(valuename)
    
    def get_fullname(self,valuename=None):
        ''' param.get_fullname(valuname) -> Returns the fullname of the parameter 
        
        For example:
            param.gfn('myentry') could return Parameter.myparam.myentry
        
        Calling get_fullname() returns the full name of the parameter ignoring the entries.
        '''
        if not valuename:
            return self._fullname
        if not self.has_value(valuename):
            raise AttributeError('Parameter has not entry ' + valuename +'.')
        return self._fullname +'.'+ valuename
    
    def has_value(self,valuename):
        ''' Checks whether a parameter as a specific value entry.'''
        raise NotImplementedError( "Should have implemented this." )
        
    def set(self, **args):
        ''' Sets specific values for a parameter.
        Has to raise ParameterLockedException if parameter is locked.

        For example:
        >>> param1.set(val1=5, val2=6.0)
        
        >>> print parm1.val1 
        >>> 5
        '''
        raise NotImplementedError( "Should have implemented this." )
    
    def explore(self, *listargs,**dictargs):
        ''' The default method to create and explored parameter containing an array of entries.
        
        *listargs is a dictionary containing lists of all entries as dicts.
        For example:
        >>> param.explore([{'entry1':1,'entry2':3.0},{'entry2':1,'entry2':2.0},{'entry1':3,'entry2':1.0}])
        
        **dictargs is a dictionary containing all entries as lists
        For example:
        >>> param.explore({'entry1':[1,2,3],'entry2'=[3.0,2.0,1.0]})
        
        Note that it is recommended only to support one of the two approaches at the same time.
        '''
        raise NotImplementedError( "Should have implemented this." )
    
    def access_parameter(self, n=0):
        ''' Returns a shallow copy of the parameter for the nth run.
        
        If the parameter is an array only the nth element of the array is used to build a novel parameter.
        If the parameter's length is only 1, the parameter itself is returned.
        '''
        raise NotImplementedError( "Should have implemented this." )
        
    def get_class_name(self):  
        return self.__class__.__name__

    def get_name(self):
        ''' Returns the name of the parameter.'''
        return self._name
    

  
  
class Data(object):
        '''The most fundamental entity that contains the actual data, it is separated to simplify the naming.
        It is more a placeholder for a dictionary.
        
        This allows storing of data in the form:
        data.entry = 1
        
        which maps to
        data.__dict__['entry']=1
        '''
        pass
      
class Parameter(BaseParameter):
    ''' The standard parameter that handles creation and access to simulation parameters.
    
    Supported Data types are int, string, bool, float and numpy arrays.
    The actual data entries are stored in the _data list, each element is a Data item.
    
    If the parameter is not an array the list has only a single data element.
    Each parameter can have several entries (which are stored in a Data item) as entryname value pairs 
    of supported data.
    
    Entries can be accessed and created via natural naming:
    >>> param.entry1 = 3.8
    
    >>> print param.entry1
    >>> 3.8
    
    Note that the user cannot modify entries of parameter arrays except for the very first parameter.
    In fact, changing an entry of a parameter array deletes the array and reduces _data list to contain
    only a single parameter.
    To change the whole parameter array, the corresponding methods in the trajectory should be called,
    like explore, for instance.
    '''
   
    # The comment that is added if no comment is specified
    standard_comment = 'Dude, please explain a bit what your fancy parameter is good for!'

    def __init__(self, name, fullname,*args,**kwargs):
        super(Parameter,self).__init__(name,fullname)
        self._locked=False
        self._comment= Parameter.standard_comment
        self._data=[Data()] #The list
        self._isarray = False
        self._default = None
        #self._accesspointer = 0
        #self._constructor='Parameter'
        
        #self._accessname = accessname
        
        #self._accessedfrom = None
        
        self._logger = logging.getLogger('mypet.parameter.Parameter=' + self._fullname)
        #self._logger.debug('Created the Parameter ' + self._name)
        
                
        for idx, arg in enumerate(args):
            if idx == 0:
                self.val = arg
            else:
                valname = 'val' + str(idx)
                setattr(self, valname, arg)
        
        for key, arg in kwargs.items():
            setattr(self, key, arg)
        
       
    def __getstate__(self):
        ''' Returns the actual state of the parameter for pickling. 
        '''
        result = self.__dict__.copy()
        del result['_logger'] #pickling does not work with loggers
        return result
    
    def __setstate__(self, statedict):
        ''' Sets the state for unpickling.
        '''
        self.__dict__.update( statedict)
        self._logger = logging.getLogger('mypet.parameter.Parameter=' + self._fullname)
      
        
    def access_parameter(self, n=0):
        ''' Returns a shallow copy of the parameter for a single trajectory run.
        
        If the parameter is an array the copy contains only the nth data element as the first data 
        element.
        '''
        if not self.is_array():
            return self
        else:
            if n >= len(self):
                raise ValueError('n %i is larger than entries in parameter %s, only has %i entries.' % (n,self.gfn(),len(self)))
            

            newParam = Parameter(self._name,self._fullname)
            newParam._default = self._default
            newParam._data[0].__dict__ = self._data[n].__dict__.copy()

            return newParam
            
    def __call__(self,valuename=None,n=0):
        ''' Returns the value which was called for.
        
        For example:
        >>> print param1('entry1')
        >>> 1.0
        
        If the the parameter is called via param(), the default value is returned, which is the 
        first stored item.
        '''
        
        if not valuename:
            if not self._default:
                self._logger.info('Parameter has no entries yet.')
                return None
            else:
                return self.get(self._default,n)
        if not self.has_value(valuename):
            return None
        
        return self.get(valuename,n)


    def has_value(self,valuename):
        return valuename in self._data[0].__dict__

    def __len__(self):
        if len(self._data)==1:
            if len(self._data[0].__dict__) == 0:
                return 0
        return len(self._data)

    
    def _become_array(self):
        self._isarray = True
    
    
    
    def _is_supported_data(self, data):
        ''' Checks if input data is supported by the parameter'''
        return isinstance(data, (np.ndarray, int, str, float, bool))
    

      
    def _values_of_same_type(self,val1, val2):
        ''' Checks if two values are of the same type.
        
        This is important for exploration and adding of elements to the parameter array.
        New added elements must agree with the type of previous elements.
        '''
        
        if not type(val1) == type(val2):
            return False
        
        if type(val1) == np.array:
            if not val1.dtype == val2.dtype:
                return False
            
            if not np.shape(val1)==np.shape(val2):
                return False
        
        return True
        

    def add_comment(self,comment):
        ''' Adds a comment to the current comment
        
        :param comment: The comment as string which is added to the existing comment
        '''
        #Replace the standard comment:
        if self._comment == Parameter.standard_comment:
            self._comment = comment
        else:
            self._comment = self._comment + '; ' + comment
            
            
       
    def __setattr__(self,name,value):
        
        if name[0]=='_':
            self.__dict__[name] = value
        else:
            self._set_single(name,value)
        
    def set(self,**args):

        for key, val in args.items():
            self._set_single(key, val)

    
    def _set_single(self,name,val):
        ''' Adds a single entry to the parameter.
        
        This method is called for statements like:
        >>> param.entry = 4
        
        If the parameter was originally an array, the array is deleted because a setting is change 
        of the default entries of the parameter.
        '''
        if self._locked:
            raise pex.ParamterLockedException('Parameter ' + self._name + ' is locked!')
        
        # The comment is not in the _data list:
        if name == 'Comment' or name=='comment':
            self._comment = val
            return
        
     
        if not self._is_supported_data(val):
            raise AttributeError('Unsupported data type: ' +str(type(val)))
        elif not self._isarray:
            if name in self._data[0].__dict__:
                self._logger.warning('Redefinition of Parameter, the old value of ' + name + ' will be overwritten.')
            self._data[0].__dict__[name] = val
            if not self._default:
                self._default=name
        else:
            self._logger.warning('Redefinition of Parameter, the array will be deleted.')
            if name in self._data[0].__dict__:
                self._logger.warning('Redefinition of Parameter, the old value of ' + name + ' will be overwritten.')
            self._data[0].__dict__[name] = val;
            if not self._default:
                self._default=name
            del self._data[1:]
            self._isarray = False
    
    def lock(self):
        self._locked = True;
        
    
        
    def change_values_in_array(self,name,values,positions):
        ''' Changes the values of entries for given positions if the parameter is an array.
        
        For example:
        
        >>> param.change_values_in_array('entry',[18.0,3.0,4.0],[1,5,9])
        
        '''  
        
        if not self._isarray:
            raise pex.ParameterNotArrayException('Parameter ' + self._name + ' is not an array!')
        
        if self._locked:
            raise pex.ParameterLockedException('Parameter ' + self._name + ' is locked!') 
    
    
        if not isinstance(positions, list):
            positions = [positions];
            values = [values];
        else:
            if not len(positions) == len(values):
                raise AttributeError('Parameter ' + self._name + ': List are not of equal length, positions has ' +len(positions)  +' entries and values ' + len(values) +'.')
        
        for idx, pos in enumerate(positions) :      
        
            val = values[idx]
            
            if not len(self._data) >= pos:
                raise AttributeError('Parameter ' + self._name + ' does not have ' +str(pos) +' data items.')
            
           
            if not hasattr(self._data[0], name):
                raise AttributeError('Parameter ' + self._name + ' does not have ' + name +' data.')
            
            if not self._is_supported_data(val):
                    raise AttributeError()
            
            default_val = self._data[0].__dict__[name]
            
            if not self._values_of_same_type(val,default_val):
                raise AttributeError('Parameter ' + self._name + ' has different default type for ' + name)
            
            self._data[pos].__dict__[name]=val
            
    def to_list_of_dicts(self):
        ''' Returns a list of dictionaries of the data items.
        
        Each data item is a separate dictionary
        '''
#         if not self._isarray:
#             resultdict = self._data[0].__dict__.copy()
#         
#         else:
        resultdict = []
        for item in self._data:
            resultdict.append(item.__dict__.copy())
        
        return resultdict
    
    
    def is_array(self):  
        return self._isarray
    
    def is_locked(self):
        return self._locked
        

    def to_dict_of_lists(self):
        ''' Returns a dictionary with all value names as keys and a list of values.
        '''
        
        resultdict = self._data[0].__dict__.copy()
         
        for key in resultdict.iterkeys():
            resultdict[key] = [resultdict[key]]
            if self.is_array():
                for dataitem in self._data[1:]:
                    curr_list = resultdict[key]
                    curr_list.append(dataitem.__dict__[key])
                    resultdict[key] = curr_list
        return resultdict

    def explore(self, *explore_list, **explore_dict):
        ''' Changes a parameter to an array to allow exploration.
        
        The input is either a dictionary of lists or a list of dictionaries.
        It is first checked if a dictionary is provided and then if a list is supplied,
        both methods cannot be used at the same time.
        '''
        if self._locked:
            self._logger.warning('Parameter ' + self._name + 'is locked, but I will allow exploration.')
        
        # Check whether a dictionary is provided...
        if explore_dict:
            for key,values in explore_dict.items():
                if not isinstance(values, list):
                    raise AttributeError('Dictionary does not contain lists, thus no need for parameter exploration.')
                
                val=values[0]
             
                
                
                if not key in self._data[0].__dict__:
                    self._logger.warning('Key ' + key + ' not found for parameter ' + self._name + ',\n I don not appreciate this but will add it to the parameter.')
                elif not self._values_of_same_type(val, self._data[0].__dict__[key]):
                    self._logger.warning('Key ' + key + ' found for parameter ' + self._name + ', but the types are not matching.\n Previous type was ' + str(type( self._data[0].__dict__[key])) + ', type now is ' + str(type(val))+ '. I don not appreciate this but will overwrite the parameter.')
                if  key in self._data[0].__dict__:
                    del self._data[0].__dict__[key]
                self._set_single(key, val)
            
            del self._data[1:]
            self._become_array()
            self.add_items_as_dict(**explore_dict)
            self._data = self._data[1:]
        #...or if a list is given:
        elif explore_list:
            for key,val in explore_list[0].items():
                
              
                                
                if not key in self._data[0].__dict__:
                    self._logger.warning('Key ' + key + ' not found for parameter ' + self._name + ',\n I don not appreciate this but will add it to the parameter.')
                elif not self._values_of_same_type(val, self._data[0].__dict__[key]):
                    self._logger.warning('Key ' + key + ' found for parameter ' + self._name + ', but the types are not matching.\n Previous type was ' + str(type( self._data[0].__dict__[key])) + ', type now is ' + str(type(val))+ '. I don not appreciate this but will overwrite the parameter.')
                if  key in self._data[0].__dict__:
                    del self._data[0].__dict__[key]
                self._set_single(key, val)
            
            del self._data[1:]
            self._become_array()
            self.add_items_as_list(*explore_list)
            self._data = self._data[1:]
            
        
    
    
    def add_items_as_dict(self,**itemdict):
        ''' Adds entries for a given input dictionary containing lists.
        
        For example:
        >>> param.add_items_as_dict(**{'entry1':[1,2,3],'entry2':[3.0,2.0,1.0]})
        
        or more simply:
        >>> param.add_items_as_dict(entry1=[1,2,3],entry2=[3.0,2.0,1.0])
        '''
        
        if self._locked:
            raise pex.ParameterLockedException('Parameter ' + self._name + ' is locked!') 
        
        if not self._isarray:
            raise pex.ParameterNotArrayException('Parameter ' + self._name + ' is not an array!')
    
#         if not isinstance(itemdict[itemdict.keys()[0]], list):
#             act_length = 1
#         else:
        act_length = len(itemdict[itemdict.keys()[0]])
            
        # Check if all new entries follow the default configuration of the parameter:
        for key in itemdict.keys():
            # Check if the parameter contains the value names:
            if not key in self._data[0].__dict__:
                self._logger.warning('Key ' + key + ' not found in Parameter, I am ignoring it.')
            # If not a list is supplied it is assumed that only a single parameter entry is added:
            if not isinstance(itemdict[key],list):
                itemdict[key] = [list]
            # Check if all lists have the same length:
            if not act_length == len(itemdict[key]):
                raise AttributeError('The entries of the dictionary do not have the same length.')
        
        # Add the data entries to the parameter:
        for idx in range(act_length):
            newdata = Data();
            
            for key, val in self._data[0].__dict__.items():
                # If an entry of the parameter is not specified for exploration use the default value:
                if not key in itemdict:
                    itemdict[key] = [val for id in range(act_length)]
                else:
                    newval = itemdict[key][idx];
                  
                    if not self._values_of_same_type(val,newval):
                        raise AttributeError('Parameter ' + self._name + ' has different default type for ' + key)
                    
                newdata.__dict__[key] = itemdict[key][idx]
            
            self._data.append(newdata) 
          
    
    def add_items_as_list(self,*itemdicts):
        ''' Adds entries given a list containing dictionaries.
        
        For example:
        >>> param.add_items_as_list(*[{'entry1':1,'entry2':3.0},{'entry2':1,'entry2':2.0},{'entry1':3,'entry2':1.0}])
        
        or more simply:
        >>> param.add_items_as_dict({'entry1':1,'entry2':3.0},{'entry2':1,'entry2':2.0},{'entry1':3,'entry2':1.0})
        '''
        
        if self._locked:
            raise pex.ParameterLockedException('Parameter ' + self._name + ' is locked!') 
         
        if not self._isarray:
            raise pex.ParameterNotArrayException('Parameter ' + self._name + ' is not an array!')
        
#         if not isinstance(itemdicts,list):
#             itemdicts = [itemdicts]
    
        # Check if all new entries follow the default configuration of the parameter:
        for itemdict in itemdicts:
            for key in itemdict.keys():
                if not key in self._data[0].__dict__:
                    self._logger.warning('Key ' + key + ' not found in Parameter, I am ignoring it.')
            newdata = Data();
            
            for key, val in self._data[0].__dict__.items():
                # If an entry of the parameter is not specified for exploration use the default value:
                if not key in itemdict:
                    itemdict[key] = val
                else:
                    newval = itemdict[key];
                   
                    if not self._values_of_same_type(val,newval):
                        raise AttributeError('Parameter ' + self._name + ' has different default type for ' + key)
                    
                newdata.__dict__[key] = itemdict[key]
            
            self._data.append(newdata)
     
    def _get_longest_stringsize(self,key):   
        ''' Returns the longest stringsize for a string entry across the parameter array.
        '''
        maxlength = 0
        for dataitem in self._data:
            maxlength = max(len(dataitem.__dict__[key]),maxlength)
        
        return maxlength
        
    def _get_table_col(self, key, val):
        ''' Creates a pytables column instance.
        
        The type of column depends on the type of parameter entry.
        '''
        if isinstance(val, int):
                return pt.IntCol()
        if isinstance(val, float):
                return pt.Float64Col()
        if isinstance(val, bool):
                return pt.BoolCol()
        if isinstance(val, str):
                itemsize = int(self._get_longest_stringsize(key) * 1.5)
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
            
                
    def _make_description(self):
        ''' Returns a dictionary that describes a pytbales row.
        '''
        
        descriptiondict={}
        
        for key, val in self._data[0].__dict__.items():
                       
            col = self._get_table_col(key, val)
            
            if col is None:
                raise TypeError('Entry ' + key + ' cannot be translated into pytables column')
            
            descriptiondict[key]=col
             
        return descriptiondict
                    
    def _store_single_item(self,row,key,val):
        ''' Adds a signle entry value to a pytables row.
        
        This one liner is only added to simplify inheritance for other parameter classes like the 
        SparseParameter.
        '''
        row[key] = val
    
    def store_to_hdf5(self,hdf5file,hdf5group):
        ''' Writes a parameter as a pytable to an hdf5 file.
        
        First adds a table called 'Info' with basic information of the parameter.
        The second table has the name of the parameter and contains all entries stored in _data.
        '''
        self._logger.debug('Start storing.')
        tabledict = self._make_description()

        table = hdf5file.createTable(where=hdf5group, name=self._name, description=tabledict, title=self._name);
        
        for item in self._data:
            newrow = table.row
            for key, val in item.__dict__.items():
                self._store_single_item(newrow,key,val)
            
            newrow.append()
        
        table.flush()
        
        commentlength = int(len(self._comment)*1.5)
        infodict= {'Name':pt.StringCol(self._string_length_large(self._name)), 
                   'Full_Name': pt.StringCol(self._string_length_large(self._fullname)), 
                   'Comment':pt.StringCol(self._string_length_large(self._comment)),
                   'Type':pt.StringCol(self._string_length_large(str(type(self)))),
                   'Class_Name': pt.StringCol(self._string_length_large(self.__class__.__name__))}
        infotable=hdf5file.createTable(where=hdf5group, name='Info', description=infodict, title='Info')
        newrow = infotable.row
        newrow['Name'] = self._name
        newrow['Full_Name'] = self._fullname
        newrow['Comment'] = self._comment
        newrow['Type'] = str(type(self))
        newrow['Class_Name'] = self.__class__.__name__
        newrow.append()
        
        infotable.flush()
        
        self._logger.debug('Finished storing.')
  
        
    def load_from_hdf5(self, hdf5group):
        ''' Loads a parameter from an hdf5 file.
        
        The file is not needed, the user has to supply only the corresponding hdf5 group and the 
        file must have been opened somewhere else.
        '''
        
        assert isinstance(hdf5group,pt.Group)
        
        infotable = hdf5group.Info
        
        assert isinstance(infotable,pt.Table)
        
        inforow = infotable[0]

        self._comment = inforow['Comment']
        
        table = getattr(hdf5group,self._name)
        assert isinstance(table,pt.Table)
        
        nrows = table.nrows
      
        datanames = table.colnames
        #self.set(dataitem)
        
        dict_of_lists = {}
        
        for colname in datanames:
            dict_of_lists[colname] = self._load_single_col(table,colname)
            val = dict_of_lists[colname].pop(0)
            self._set_single(colname, val)
          
        if nrows > 1:
            self._become_array()  
        
        if self.is_array():
            self.add_items_as_dict(**dict_of_lists)
            
    def _load_single_col(self,table,colname):
        ''' Loads a single entry of a parameter (array) from a pytables column.
        '''
        assert isinstance(table, pt.Table)
        
        col_data = table.col(colname)
        if len(col_data.shape)==1:
            list_data = col_data.tolist()
        else:
            list_data  =[a for a in col_data]
        return list_data

        
    
    def _string_length_large(self,string):  
        return  int(len(self._comment)*1.5)
                
    
    def to_dict(self):
        ''' Returns the entries of the parameter as a dictionary.
        
        Only the first parameter is returned in case of a parameter array.
    '''
        return self._data[0].__dict__.copy()
        
    def get(self, name,n=0):
        
        if name == 'val':
            name = self._default
            
        if  not hasattr(self._data[0],name):
            raise AttributeError('Parameter ' + self._name + ' does not have attribute ' + name +'.')
        
        if n >= len(self):
            raise ValueError('Cannot access %dth element, parameter has only %d elements.' % (n,len(self)))
        return self._data[n].__dict__[name]
        
    
    def __getattr__(self,name):
        if not hasattr(self, '_data'):
            raise AttributeError('This is to avoid pickling issues!')
        
        return self.get(name)
 
    def shrink(self):
        ''' Shrinks the parameter array to a single parameter.
        '''
        self._isarray = False
        del self._data[1:]
 
    
     




class SparseParameter(Parameter):
    ''' A parameter class that supports sparse scipy matrices.
    
    Supported formats are csc,csr and lil. Note that all sparce matrices are converted to
    csr before storage.
    In case of a parameter array the matrices need to be of the very same size, i.e. the amount
    of nonzero entries must be the same.
    '''
    
    def _is_supported_data(self, data):
        ''' Simply checks if data is supported '''
        if super(SparseParameter,self)._is_supported_data(data):
            return True
        if spsp.issparse(data):
            return True
        return False
    
    def _get_table_col(self,key,val):
        ''' Creates a table column that supports a sparse matrix.
        
        A sparse matrix is stored in a nested pytable with four columns.
        One column for the data, two columns for the indices, and one column for the shape.
        '''
        if spsp.issparse(val):
            
            sparsedict={}
            #val = spsp.lil_matrix(100,100)
            valformat = val.format
            sparsedict['format']=pt.StringCol(3)
            sparsedict['storedformat']=pt.StringCol(3)
            val = val.tocsr()
            
            shape = np.shape(val)
            shape = np.array(shape)
            data_list= [ val.data,val.indptr,val.indices,shape]
            
            idx_list = ['data', 'indptr','indices','shape']
            for idx, dat in enumerate(data_list):
                sidx = idx_list[idx]
                valdtype = dat.dtype
                valshape = dat.shape
                if np.issubdtype(valdtype,int):
                    sparsedict[sidx] = pt.IntCol(shape=valshape)
                elif np.issubdtype(valdtype, float):
                    sparsedict[sidx] = pt.Float64Col(shape=valshape)
                elif np.issubdtype(valdtype, bool):
                    sparsedict[sidx] = pt.BoolCol(shape=valshape)
                else:
                    self._logger.error('You should NOT be here, something is wrong!')
                    
            return sparsedict
                
        return super(SparseParameter,self)._get_table_col(key,val)
                         
    def _store_single_item(self,row,key,val):
        ''' Stores a single sparse matrix into a nested pytables row.
        '''
        # Check if this is a sparse matrix
        if not hasattr(val, 'format'):
            super(SparseParameter,self)._store_single_item(row,key,val)
        else:
            row[key+'/format'] = val.format
            val = val.tocsr()
            row[key+'/storedformat'] = val.format
            row[key+'/data'] = val.data
            row[key+'/indptr'] = val.indptr
            row[key+'/indices'] = val.indices
            shape = np.shape(val)
            shape = np.array(shape)
            row[key+'/shape'] = shape
    


    def _values_of_same_type(self,val1, val2):
        if not super(SparseParameter,self)._values_of_same_type(val1, val2):
            return False
        
        if spsp.issparse(val1):
            #if not val1.format == val2.format:
            #    return False
            if not val1.dtype == val2.dtype:
                return False
            #if not val1.shape == val2.shape:
                #return False
            if not len(val1.nonzero()[0]) == len(val2.nonzero()[0]):
                return False

        return True
    

      
    def _load_single_col(self,table,colname):
        ''' Loads sparse matrices from a single column.
        
        If the loaded column does not strore a sparse matrix, the method of the superclass is used.
        The matrices are loaded in csr format and subsequently converted to their original type
        (might take very long for large lil matrices).
        '''
        assert isinstance(table, pt.Table)
        
        col = table.col(colname)
        
        coldtype = col.dtype
        
        if len(coldtype)>1:
            arformat = col['format']
            ardata = col['data']
            arindptr= col['indptr']
            arindices = col['indices']
            arshape = col['shape']
            arstoredformat=col['storedformat']
            
            sparsematlist = []
            for idx in range(len(arformat)):
                matformat = arformat[idx]
                storedformat=arstoredformat[idx]
                data = ardata[idx]
                indptr = arindptr[idx]
                indices = arindices[idx]
                shape = arshape[idx]
                
                if storedformat == 'csr':
                    sparsemat = spsp.csr_matrix((data, indices, indptr),shape)
                    if matformat == 'lil':
                        sparsemat = sparsemat.tolil() #Ui Ui might be expensive
                    if matformat == 'csc':
                        sparsemat = sparsemat.tocsc()
                else:
                    self._logger.error('If the matrix was not stored in csr format, I am afraid I have to tell you that other formats are not supported yet.')

                
                sparsematlist.append(sparsemat)
            
            return sparsematlist
        else:
            return super(SparseParameter,self)._load_single_col(table,colname)
            
                            

class BaseResult(object):
    ''' The basic result class.
    
    It is a subnode of the tree, but how storage is handled is completely determined by the user.
    
    The result does know the name of the parent trajectory and the file because it might
    autonomously write results to the hdf5 file.
    '''
            
    def __init__(self, name, fullname, parent_trajectory_name, filename):
        self._name=name
        self._fullname = fullname
        self._paren_trajectory = parent_trajectory_name
        self._filename = filename
        
    def store_to_hdf5(self,hdf5file,hdf5group):
        ''' Method to store a result to an hdf5file.
        
        It is called by the trajectory if a single run should be stored.
        
        Does not throw an exception if not implemented, because you might want to
        store your results at a different point in time, so if the function is called
        by the trajectory via storing a single run, nothing happens.
        '''
        pass
        #raise NotImplementedError( "Should have implemented this." )
    
    def get_name(self):
        return self._name
    
    def get_fullname(self):
        return self._fullname
    
    def gfn(self):
        return self.get_fullname()

class SimpleResult(BaseResult,SparseParameter):  
    ''' Simple Container for results. 
    
    In fact this is a lazy implementation, its simply a sparse parameter^^
    '''        
    def __init__(self, name, fullname, parent_trajectory_name, filename, *args,**kwargs):
        super(SimpleResult,self).__init__(name, fullname, parent_trajectory_name, filename)
        super(SparseParameter,self).__init__(name,fullname,*args,**kwargs)

    def store_to_hdf5(self,hdf5file,hdf5group):
        super(SparseParameter,self).store_to_hdf5(hdf5file,hdf5group)


    def load_from_hdf5(self):
        hdf5file = pt.openFile(filename=self._filename, mode='r')
        trajectorygroup = hdf5file.getNode('/', self._paren_trajectory)
        
        where = 'trajectorygroup.' + self._fullname
        hdf5group = eval(where)
        
        super(SparseParameter,self).load_from_hdf5(hdf5group)
        
        hdf5file.close()
        
        return self
    
    def erase(self):
        del self._data
        


     

