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
from mypet.utils.helpful_functions import nest_dictionary




class BaseParameter(object):
    ''' Specifies the methods that need to be implemented for a Trajectory Parameter
    
    It is initialized with a location that specifies its position within the Trajectory, e.g.:
    Parameters.group.paramname
    The shorter name of the parameter is name=paramname, accordingly.
        
    For storing a parameter into hdf5 format the parameter implements a full node, how the storage 
    in the node is handled is left to the user.
        
    The parameter class can instantiate a single parameter as well as an array with several 
    parameters (of the same type) for exploration.
    
    Parameters can be locked to forbid further modification.
    If multiprocessing is desired the parameter must be pickable!
    ''' 
    def __init__(self, fullname):
        self._fullname = fullname
        split_name = fullname.split('.')
        self._name=split_name.pop()
        self._location='.'.join(split_name)
        self._comment = ''
        self._isarray = False
        self._locked = False

    def _rename(self, fullname):
        self._fullname = fullname
        split_name = fullname.split('.')
        self._name=split_name.pop()
        self._location('.'.join(split_name))

    def get_comment(self):
        return self._comment

    def is_array(self):
        return self._isarray

    def is_locked(self):
        return self._locked

    def get_location(self):
        return self._location
     
    def __len__(self):
        ''' Returns the length of the parameter.
        
        Only parameters that will be explored have a length larger than 1.
        If no values have been added to the parameter it's length is 0.
        '''
        raise NotImplementedError( "Should have implemented this." )
    
    # def __getitem__(self,key):
    #     if not self.has_value(key):
    #         raise KeyError('%s has entry named %s.' %(self._fullname,key))
    #     if not isinstance(key, str):
    #         raise TypeError('None string keys are not supported!')
    #
    #     return getattr(self, key)
    
    def __store__(self):
        raise NotImplementedError( "Should have implemented this." )

    def __load__(self, load_dict):
        raise NotImplementedError( "Should have implemented this." )

    def lock(self):
        ''' Locks the parameter and allows no further modification.'''
        raise NotImplementedError( "Should have implemented this." )

    def return_default(self):
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

    def __contains__(self, item):
        return self.has_value(self, item)

    def set(self, *ars,**kwargs):
        ''' Sets specific values for a parameter.
        Has to raise ParameterLockedException if parameter is locked.

        For example:
        >>> param1.set(val1=5, val2=6.0)
        
        >>> print parm1.val1 
        >>> 5
        '''
        raise NotImplementedError( "Should have implemented this." )

    def get(self,name):
        raise NotImplementedError( "Should have implemented this." )
    
    def explore(self, expdict,**kwexpdict):
        ''' The default method to create and explored parameter containing an array of entries.

        **kwexpdict is a dictionary containing all entries as lists
        For example:
        >>> param.explore(**{'entry1':[1,2,3],'entry2'=[3.0,2.0,1.0]})

        You can also call it via
        >>> param.explore({'entry1':[1,2,3],'entry2'=[3.0,2.0,1.0]})

        '''
        raise NotImplementedError( "Should have implemented this." )
    
    def set_parameter_access(self, n=0):
        ''' Prepares the parameter for further usage, and tells it which point in the parameter space should be
        accessed for future calls.
        :param n: The index of the parameter space point
        :return:
        '''
        raise NotImplementedError( "Should have implemented this." )
        
    def get_class_name(self):  
        return self.__class__.__name__

    def get_name(self):
        ''' Returns the name of the parameter.'''
        return self._name

    def get_entry_names(self):
        ''' Returns a list of all entry names with which the parameter can be accessed
        '''
        raise NotImplementedError( "Should have implemented this." )

      
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

    def __init__(self, fullname,*args,**kwargs):
        super(Parameter,self).__init__(fullname)
        self._comment= Parameter.standard_comment
        self._data={} #The Data
        self._default_expression = None

        
        self._logger = logging.getLogger('mypet.parameter.Parameter=' + self._fullname)
        
        self.set(*args,**kwargs)

        self._n = 0
        self._fullcopy = False

        
       
    def __getstate__(self):
        ''' Returns the actual state of the parameter for pickling. 
        '''
        result = self.__dict__.copy()
        result['_data'] = self._data.copy()

        # If we don't need a full copy of the Parameter (because a single process needs only access to a single point
        #  in the parameter space we can delete the rest
        if not self._fullcopy:
            for key in result['_data']:
                old_list = result['_data'][key]
                new_one_item_list = [old_list[self._n]]
                result['_data'][key] = new_one_item_list

            # Now we have shrunk the Parameter
            result['_n'] = 0

        del result['_logger'] #pickling does not work with loggers
        return result
    
    def __setstate__(self, statedict):
        ''' Sets the state for unpickling.
        '''
        self.__dict__.update( statedict)
        self._logger = logging.getLogger('mypet.parameter.Parameter=' + self._fullname)
      
        
    def set_parameter_access(self, n=0):
        if self.is_array():
            self._n = n
        else:
            self._n = 0


    def has_value(self,valuename):
        return valuename in self._data

    def __len__(self):

        if len(self._data)==0:
            return 0
        else:
            return len(self._data.itervalues().next())
    
    def become_array(self):
        self._isarray = True
    
    
    
    def _is_supported_data(self, data):
        ''' Checks if input data is supported by the parameter'''
        result = isinstance(data, ( np.int, np.str, np.float, np.bool, np.complex))

        if isinstance(data, np.ndarray):
            dtype = data.dtype
            result = (np.issubdtype(dtype, np.int) or
                np.issubdtype(dtype, np.str) or
                np.issubdtype(dtype, np.float) or
                np.issubdtype(dtype, np.bool) or
                np.issubdtype(dtype, np.complex) )

        return result


    

      
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
            self.set_single(name,value)
        
    def set(self,*args,**kwargs):

        for idx, arg in enumerate(args):
            # if idx == 0:
            #     self.val = arg
            # else:
            valname = 'val' + str(idx)
            setattr(self, valname, arg)

        for key, arg in kwargs.items():
            setattr(self, key, arg)

    def _test_default(self):
        old_locked = self._locked
        try:
            eval(self._default_expression)
        except Exception,e:
            self._logger.warning('Your default expression >>%s<< failed to evaluate with error: %s' % (val,str(e)))

        self._locked = old_locked
    
    def set_single(self,name,val,pos=0):
        ''' Adds a single entry to the parameter.
        
        This method is called for statements like:
        >>> param.entry = 4
        
        If the parameter was originally an array, the array is deleted because a setting is change 
        of the default entries of the parameter.
        '''

        not_admissable_names= set(dir(self))

        if name in not_admissable_names:
            raise AttributeError('Your parameter %s cannot have %s as an entry, the name is similar to one of it\'s methods'
            % (self._fullname,name))

        if self.is_locked():
            raise pex.ParameterLockedException('Parameter ' + self._name + ' is locked!')


        # The comment is not in the _data list:
        if name == 'Comment' or name=='comment':
            self._comment = val
            return

        if name =='Default' or name == 'default':
            assert isinstance(val,str)
            self._default_expression=val
            self._test_default()
            return

        if name == 'FullCopy' or name =='fullcopy':
            self.set_copy_mode(val)
            return

        if name == 'val' or name == 'Val':
            raise AttributeError('Sorry, cannot add entry >>val<< or >>Val<<. These names are reserved for for fast access to the default value.')

        val = self._convert_data(val)

        if not self._is_supported_data(val):
            raise AttributeError('Unsupported data type: ' +str(type(val)))

        if pos >= len(self) and pos > 0:
            raise AttributeError('Cannot manipulate the parameter at position %d, it contains only %d entries.'%(pos,len(self)))


        if self.is_array():
            if not name in self._data:
                self._logger.warning('Your Parameter is an array and does not contain %s, I will create a new entry called %s and use the supplied value as the default.' %(name,name))
                length=len(self)

                self._data[name] =[val for irun in range(length)]
            else:
                if not self._values_of_same_type(val,self._data[name][0]):
                    raise AttributeError('You want to put %s in the entry %s, but the types do not match, default type is %s and your type is %s!' %(str(val),name,str(type(self._data[name][0])),type(val)))
                self._data[name][pos]=val
        else:

            if name in self._data:
                old_val = self._data[name][0]
                self._logger.debug('Replacing entry %s in parameter %s, previous value was %s, new value is %s' % (name,self._fullname,str(old_val),str(val)))
                if not type(old_val) == type(val):
                    self._logger.warning('Type of entry %s in parameter %s has changed, previous type was %s, type now is %s.' % (name,self._fullname,str(type(old_val)),str(type(val))))

            self._data[name] = [val]
            if not self._default_expression:
                self._default_expression = 'self.'+name



    def _convert_data(self, val):
        ''' Converts int,bool,str,float to the corresponing numpy types. Sets numpy arrays immutable.

        :param val: the val to convert
        :return: the numpy type val
        '''
        if isinstance(val,int):
            val = np.int64(val)
            return val

        if isinstance(val,float):
            val = np.float(val)
            return val

        if isinstance(val,str):
            val = np.str(val)
            return val

        if isinstance(val,bool):
            val = np.bool(val)
            return val

        if isinstance(val,complex):
            val = np.complex(val)
            return val

        if isinstance(val, np.ndarray):

            dtype = val.dtype
            if np.issubdtype(dtype,np.int):
                val = val.astype(np.int64,copy=False)
            elif np.issubdtype(dtype,np.float):
                val = val.astype(np.float,copy=False)
            elif np.issubdtype(dtype,np.bool):
                val = val.astype(np.bool,copy=False)
            elif np.issubdtape(dtype,np.complex):
                val = val.astype(np.complex,copy=False)
            elif np.issubdtype(dtype,np.str):
                val = val.astype(dtype,np.str)
            else:
                raise AttributeError('You should never ever come here!')

            val.flags.writeable = False

        return val

    def lock(self):
        self._locked = True
        
    def get_entry_names(self):
        return self._data.keys()
        
    def change_values_in_array(self,name,values,positions):
        ''' Changes the values of entries for given positions if the parameter is an array.
        
        For example:
        
        >>> param.change_values_in_array('entry',[18.0,3.0,4.0],[1,5,9])
        
        '''  

        if self.is_locked():
            raise pex.ParameterLockedException('Parameter ' + self._name + ' is locked!')

        if not self.is_array():
            raise pex.ParameterNotArrayException('Parameter ' + self._name + ' is not an array!')
        

        if not isinstance(positions, list) and not isinstance(positions, tuple):
            positions = [positions];
            values = [values];
        else:
            if not len(positions) == len(values):
                raise AttributeError('Parameter ' + self._name + ': List are not of equal length, positions has ' +len(positions)  +' entries and values ' + len(values) +'.')
        
        for idx, pos in enumerate(positions) :      
        
            val = values[idx]
            
            self.set_single(self,name,val,pos)
            
    def to_dict_of_lists(self):
        ''' Returns a list of dictionaries of the data items.
        
        Each data item is a separate dictionary
        '''
        return_dict = {}
        for key, val_list in self._data.items():
            return_dict[key] = val_list[:]


    def to_list_of_dicts(self):
        ''' Returns a dictionary with all value names as keys and a list of values.
        '''
        
        result_list = [{}]

        for key,val_list in self._data.items():
            for idx,val in enumerate(val_list):
                if len(result_list) <= idx:
                    result_list.append({})
                result_list[idx][key] = val

    def explore(self, explore_dict = None, **kwexplore_dict):
        ''' Changes a parameter to an array to allow exploration.
        
        The input is a dictionary of lists.
        can be called via explore(input_dict) or explore(**input_dict)
        '''
        if self.is_locked():
            raise pex.ParameterLockedException('Parameter %s is locked!' % self._fullname)

        # Check whether a dictionary is provided...
        if explore_dict == None:
            explore_dict = kwexplore_dict
        else:
            if kwexplore_dict:
                self._logger.warning('The function has been called via explore(dict1,**dict2). I will only use dict1.')



        for key,values in explore_dict.items():
            if not isinstance(values, list):
                raise AttributeError('Dictionary does not contain lists, thus no need for parameter exploration.')

            val=values.pop(0)

            if self.is_array():
                self._logger.warning('You are exploring the parameter %s that is already an array, I will delete the current array.' % self._fullname)
                self.shrink()

            if not key in self._data:
                self._logger.warning('Key ' + key + ' not found for parameter ' + self._name + ',\n I don not appreciate this but will add it to the parameter.')

            self.set_single(key, val)


        self.become_array()
        self.add_items(explore_dict)


    
    
    def add_items(self,itemdict=None,**kwitemdict):
        ''' Adds entries for a given input dictionary containing lists.
        
        For example:
        >>> param.add_items_as_dict({'entry1':[1,2,3],'entry2':[3.0,2.0,1.0]})
        
        or more simply:
        >>> param.add_items_as_dict(entry1=[1,2,3],entry2=[3.0,2.0,1.0])
        '''
        
        if self.is_locked():
            raise pex.ParameterLockedException('Parameter ' + self._fullname + ' is locked!')


        if not self.is_array():
            raise pex.ParameterNotArrayException('Your Parameter %s is not an array please use explore to turn it into an array.' % self.get_fullname())

        if itemdict == None:
            itemdict = kwitemdict
        else:
            if kwitemdict:
                self._logger.warning('The function has been called via explore(dict1,**dict2). I will only use dict1.')


        #check if all the lists are equally long:
        prev_length = -1
        for key, val_list in itemdict.items():
            if not isinstance(val_list, list):
                val_list = [val_list]

            if not prev_length == -1:
                if not prev_length == len(val_list):
                    raise AttributeError('The entry lists you want to add to the parameter are of unequal length!')

            prev_length = len(val_list)


        length_before_adding = len(self)
        self._increase(prev_length)

        for key, val_list in itemdict.items():
            for idx,val in enumerate(val_list):
                self.set_single(name=key,val=val,pos=idx+length_before_adding)

          

    def _increase(self, size):
        ''' Increases a Parameter array by a given size and fills it with the value given at the first positions.
        :param size: The size with which the Parameter array will be increased
        '''
        if not self.is_array():
            raise pex.ParameterNotArrayException('Your Parameter %s is not an array cannot increase the size.' % self._fullname)
        for key, val_list in self._data.items():
            val_list.extend([val_list[0] for irun in range(size)])

    def _store_data(self, store_dict):

        store_dict[self._name] = {}
        for key, val in self._data.items():
            store_dict[self._name][key] = self._data[key][:]



    def _store_meta_data(self,store_dict):

        store_dict['Info'] = {'Name':[self._name],
                   'Location':[self._location],
                   'Comment':[self._comment],
                   'Type':[str(type(self))],
                   'Class_Name': [self.__class__.__name__]}



    def _store_default_expression(self,store_dict):

        if self._default_expression:
            store_dict['Default'] = {'Default_Expression':[self._default_expression]}




    def __store__(self):
        store_dict={}
        self._store_meta_data(store_dict)
        self._store_data(store_dict)
        self._store_default_expression(store_dict)

        return store_dict


    def _load_meta_data(self, load_dict):
        info_dict = load_dict['Info'][0]

        self._name = info_dict['Name']
        self._location = info_dict['Location']
        self._comment = info_dict['Comment']
        assert str(type(self)) == info_dict['Type']
        assert self.__class__.__name__ == info_dict['Class_Name']

        return load_dict


    def _load_data(self, load_dict):
        self._data = load_dict[self._name]
        return load_dict


    def _load_default_expression(self,load_dict):
        self._default_expression=None

        if 'Default' in load_dict:
            if 'Default_Expression' in load_dict['Default']:
                self._default_expression=load_dict['Default']['Default_Expression'][0]
                self._test_default()

        return load_dict

    def _check_if_array(self):
        if len(self)>1:
            self._isarray=True
        else:
            self._isarray=False


    def __load__(self,load_dict):
        self._load_meta_data(load_dict)
        self._load_data(load_dict)
        self._load_default_expression(load_dict)
        self._check_if_array()




    def to_dict(self):
        ''' Returns the entries of the parameter as a dictionary.
        
        Only the first parameter is returned in case of a parameter array.
        '''
        result_dict={}
        for key, val_list in self._data():
            result_dict[key]=val_list[0]

    def set_copy_mode(self, val):
        assert isinstance(val, bool)
        self._fullcopy = val


    def get(self, name,n=None):

        if n == None:
            n=self._n

        if name == 'FullCopy' or name =='fullcopy':
            return self._fullcopy

        if name == 'Default' or name=='default':
            return self._default_expression

        if name == 'val' or name == 'Val':
            return self.return_default()

        if name == 'comment' or name=='Comment':
            return self._comment
            
        if not name in self._data:
            raise AttributeError('Parameter %s does not have attribute or entry %s.' %(self._fullname,name))
        
        if n >= len(self):
            raise ValueError('Cannot access %dth element, parameter has only %d elements.' % (n,len(self)))


        self.lock()
        return self._data[name][n]

    def return_default(self):
        if self._default_expression:
            return eval(self._default_expression)
        else:
            self._logger.debug('Parameter has no default value yet.')
            return None

    
    def __getattr__(self,name):
        if (not '_data' in self.__dict__ or
            not '_n' in self.__dict__ or
            not '_fullname' in self.__dict__):

            raise AttributeError('This is to avoid pickling issues!')
        
        return self.get(name)
 
    def shrink(self):
        ''' Shrinks the parameter array to a single parameter.
        '''
        self._isarray = False
        for key, val_list in self._data.items():
            del val_list[1:]
 
    
     


class SparseParameter(Parameter):
    ''' A parameter class that supports sparse scipy matrices.
    
    Supported formats are csc,csr and lil. Note that all sparce matrices are converted to
    csr before storage.
    In case of a parameter array the matrices need to be of the very same size, i.e. the amount
    of nonzero entries must be the same.
    '''
    separator = '_spsp_'

    def _is_supported_data(self, data):
        ''' Simply checks if data is supported '''
        if super(SparseParameter,self)._is_supported_data(data):
            return True
        if spsp.issparse(data):
            return True
        return False

    def _values_of_same_type(self,val1, val2):
        if not super(SparseParameter,self)._values_of_same_type(val1, val2):
            return False
        
        if spsp.issparse(val1):
            if not val1.dtype == val2.dtype:
                return False
            if not len(val1.nonzero()[0]) == len(val2.nonzero()[0]):
                return False

        return True

    def set_single(self,name,val,pos=0):
        if SparseParameter.separator in name:
            raise AttributeError('Sorry your entry cannot contain >>%s<< this is reserved for storing sparse matrices.' % SparseParameter.separator)

        super(SparseParameter,self).set_single(name,val,pos)

    def _load_data(self, load_dict):
        sparse_matrices = {}
        for key,val in self.load_dict[self._name].items():
            if SparseParameter.separator in key:
                sparse_matrices[key]=val
                del load_dict[self._name][key]


        sparse_matrices = nest_dictionary(sparse_matrices)

        for name, mat_dict in sparse_matrices.items():
            arformat = mat_dict['format']
            ardata = mat_dict['data']
            arindptr= mat_dict['indptr']
            arindices = mat_dict['indices']
            arshape = mat_dict['shape']
            arstoredformat=mat_dict['storedformat']

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

            load_dict[self._name][name] = sparsematlist


        super(SparseParameter,self)._load_data(load_dict)




    def _store_data(self,store_dict):
        super(SparseParameter,self)._store_data(store_dict)
        data_dict = store_dict[self._name]

        for key, val_list in data_dict.items():
            if spsp.isspmatrix(val_list[0]):
                del data_dict[key]
                data_dict[key+'__format']=[]
                data_dict[key+SparseParameter.separator+'data']=[]
                data_dict[key+SparseParameter.separator+'indptr'] = []
                data_dict[key+SparseParameter.separator+'indices'] = []
                data_dict[key+SparseParameter.separator+'shape']=[]
                data_dict[key+SparseParameter.separator+'storedformat'] = []
                for idx, val in enumerate(val_list):
                    data_dict[key+SparseParameter.separator+'format'].append(val.format)
                    val = val.tocsr()
                    data_dict[key+SparseParameter.separator+'data'].append(val.data)
                    data_dict[key+SparseParameter.separator+'indptr'].append(val.indptr)
                    data_dict[key+SparseParameter.separator+'indices'].append(val.indices)
                    data_dict[key+SparseParameter.separator+'shape'].append(np.array(np.shape(val)))
                    data_dict[key+SparseParameter.separator+'storedformat'].append(val.format)





      

            
                            

class BaseResult(object):
    ''' The basic result class.
    
    It is a subnode of the tree, but how storage is handled is completely determined by the user.
    
    The result does know the name of the parent trajectory and the file because it might
    autonomously write results to the hdf5 file.
    '''
            
    def __init__(self, fullname):
        self._fullname = fullname
        split_name = fullname.split('.')
        self._name=split_name.pop()
        self._location('.'.join(split_name))

    def _rename(self, fullname):
        self._fullname = fullname
        split_name = fullname.split('.')
        self._name=split_name.pop()
        self._location('.'.join(split_name))

    def get_name(self):
        return self._name
    
    def get_fullname(self):
        return self._fullname

    def get_location(self):
        return self._location
    
    def gfn(self):
        return self.get_fullname()
    
    def get_class_name(self):  
        return self.__class__.__name__

class SimpleResult(BaseResult,SparseParameter):  
    ''' Simple Container for results. 
    
    In fact this is a lazy implementation, its simply a sparse parameter^^
    For simplicity it cannot be locked and it is always an array.
    '''        
    pass

    def is_locked(self):
        return False

    def is_array(self):
        return True


     

