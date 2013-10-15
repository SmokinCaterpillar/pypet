__author__ = 'Robert Meyer'


import logging
import pypetexceptions as pex
import numpy as np
from pypet.utils.helpful_functions import nested_equal, copydoc
from pypet import pypetconstants
from pandas import DataFrame
from pypet.naturalnaming import NNLeafNode
import scipy.sparse as spsp

try:
    import cPickle as pickle
except:
    import pickle





class ObjectTable(DataFrame):
    ''' Wrapper class for pandas data frames.
    It creates data frames with dtype=object.

    Data stored into an object table preserves its original type when stored to disk.
    For instance, a python int
    is not automatically converted to a numpy 64 bit integer (np.int64).

    The object table serves as a standard data structure to hand data to a storage service.

    '''
    def __init__(self, data=None, index = None, columns = None, copy=False):
        super(ObjectTable,self).__init__( data = data, index=index,columns=columns,
                                          dtype=object, copy=copy)





class BaseParameter(NNLeafNode):
    '''Abstract class that specifies the methods that need to be implemented for a trajectory
    parameter.

    Parameters are simple container objects for data values. They handle single values as well as
    the so called exploration array. An array containing multiple values which are accessed
    one after the other in individual simulation runs.

    Parameter exploration is usually initiated through the trajectory see
    `:func:~pypet.trajectory.Trajectory.explore` and :func:`~pypet.trajectory.Trajectory.expand`.

    To access the parameter's data value one can call the :func:`f_get` method.

    Parameters support the concept of locking. Once a value of the parameter has been accessed,
    the parameter cannot be changed anymore unless it is explicitly unlocked using :func:`f_unlock`.
    This prevents parameters from being changed during runtime of a simulation.

    If multiprocessing is desired the parameter must be picklable!

    :param fullname:

        The fullname of the parameter in the trajectory tree, groupings are
        separated by a colon:
        `fullname = 'supergroup.subgroup.paramname'`

    :param comment:

        A useful comment describing the parameter:
        `comment = 'Some useful text, dude!'`

    ''' 
    def __init__(self, full_name, comment=''):
        super(BaseParameter,self).__init__(full_name,comment, parameter=True)


        self._locked = False
        self._full_copy = False

    def f_supports(self, data):
        ''' Checks whether the data is supported by the parameter.

        '''
        return type(data) in pypetconstants.PARAMETER_SUPPORTED_DATA


    @property
    def v_locked(self):
        '''Whether or not the parameter is locked and prevents further modification'''
        return self._locked


    @property
    def v_fast_accessible(self):
        '''A parameter is fast accessible if it is NOT empty!'''
        return not self.f_is_empty()


    @property
    def v_full_copy(self):
        '''Whether or not the full parameter including the exploration array or only the current
        data is copied during pickling.

        If you run your simulations in multiprocessing mode, the whole trajectory and all
        parameters need to be pickled and are sent to the individual processes.
        Each process than runs an individual point in the parameter space trajectory.
        As a consequence, you do not need the exploration array during these calculations.
        Thus, if the full copy mode is set to False the parameter is pickled without
        the exploration array and you can save memory.

        If you want to access the full exploration array during individual runs, you need to set
        `v_full_copy` to True.

        It is recommended NOT to do that in order to save memory and also do obey the
        philosophy that individual simulations are independent.

        Example usage:

        >>> import pickle
        >>> param = Parameter('examples.fullcopy', data=333, comment='I show you how the copy mode works!')
        >>> param._explore([1,2,3,4])
        >>> dump=pickle.dumps(param)
        >>> newparam = pickle.loads(dump)
        >>> print newparam.f_get_array()
        TypeError

        >>> param.v_full_copy=True
        >>> dump = pickle.dumps(param)
        >>> newparam=pickle.loads(dump)
        >>> print newparam.f_get_array()
        (1,2,3,4)


        '''
        self._full_copy

    @v_full_copy.setter
    def v_full_copy(self,val):
        ''' Sets the full copy mode.'''
        val=bool(val)
        self._full_copy = val





    def f_is_array(self):
        ''' Returns true if the parameter is explored and contains an exploration array.
        '''
        raise NotImplementedError( "Should have implemented this." )

    def _restore_default(self):
        ''' Restores original data if changed due to exploration.

        If a Parameter is explored, the actual data is changed over the course of different
        simulations. This method restores the original data assigned before exploration.

        '''
        raise NotImplementedError( "Should have implemented this." )



     
    def __len__(self):
        ''' Returns the length of the parameter.
        
        Only parameters that are explored can have a length larger than 1.
        If no values have been added to the parameter its length is 0.

        '''
        raise NotImplementedError( "Should have implemented this." )




    def f_val_to_str(self):
        ''' String summary of the value handled by the parameter.

        Note that representing
        the parameter as a string accesses its value, but for simpler debugging, this does not
        lock the parameter or counts as usage!

        String is truncated if it is longer or equal to the value specified in
        `:const:`~pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH`

        '''
        old_locked = self._locked
        try :
            restr= str(self.f_get())

            if len(restr) >= pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH:
                restr=restr[0:pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH-3]+'...'

            return restr
        except Exception, e:
            return 'No Evaluation possible (yet)!'
        finally:
            self._locked = old_locked



    def _equal_values(self,val1,val2):
        ''' Checks if the parameter considers two values as equal.


        :return: True or False
        :raises: TypeError: If both values are not supported by the parameter.

        '''
        if self.f_supports(val1) != self.f_supports(val2):
            return False

        if not self.f_supports(val1) and not self.f_supports(val2):
                raise TypeError('I do not support the types of both inputs (>>%s<< and >>%s<<),'
                                ' therefore I cannot judge whether the two are equal.' %
                                str(type(val1)),str(type(val2)))

        if not self._values_of_same_type(val1,val2):
            return False

        return nested_equal(val1,val2)

    def _values_of_same_type(self,val1,val2):
        ''' Checks if two values agree in type.

        For example, two 32 bit integers would be of same type, but not a string and an integer,
        or not a 64 bit and a 32 bit integer.

        :return: True or False

        :raises: TypeError: if both values are not supported by the parameter.

        '''

        if self.f_supports(val1) != self.f_supports(val2):
            return False

        if not self.f_supports(val1) and not self.f_supports(val2):
                raise TypeError('I do not support the types of both inputs (>>%s<< and >>%s<<),'
                                ' therefore I cannot judge whether the two are of same type.' %
                                str(type(val1)),str(type(val2)))

        return type(val1) == type(val2)



    def __str__(self):
        if self.v_comment:

            returnstr = '<%s>: %s (Length:%d, Comment:%s): %s' % \
                        (self.f_get_class_name(), self.v_full_name, len(self),
                         self.v_comment, self.f_val_to_str())
        else:
            returnstr = '<%s>: %s (Length:%d): %s' % (self.f_get_class_name(),
                                                         self.v_full_name,
                                                         len(self), self.f_val_to_str())

        # if self.():
        #     returnstr += ', Array: %s' %str(self.f_get_array())

        return returnstr


    def f_unlock(self):
        ''' Unlocks the locked parameter.

        Please use it very carefully, or best do not use this function at all. There should
        better be no reason to unlock a locked parameter!

        '''
        self._locked = False

    def f_lock(self):
        ''' Locks the parameter and forbids further manipulation.

        Changing the data value or exploration array of the parameter are no longer allowed.

        '''
        self._locked = True




    def f_set(self,data):
        ''' Sets specific values for a parameter.

        Example usage:

        >>> param = Parameter('groupA.groupB.myparam', comment='I am a neat example')
        >>> param.f_set(44.0)
        >>> print parm.f_get()
        >>> 44.0

        :raises: ParameterLockedException:  if parameter is locked.

                 TypeError: If the parameter is an array or if the type of the
                                 data value is not supported by the parameter.

        '''
        raise NotImplementedError( "Should have implemented this." )

    def __getitem__(self, idx):
        '''  Equivalent to `f_get_array[idx]`

        :raises: TypeError if parameter is not an array
        '''
        return self.f_get_array().__getitem__(idx)


    def f_get(self):
        ''' Returns the current data value of the parameter and locks the parameter.

        Example usage:

        >>> param = Parameter('groupA.groupB.myparam', comment='I am a neat example')
        >>> param.f_set(44.0)
        >>> print parm.f_get()
        >>> 44.0:

        '''

        raise NotImplementedError( "Should have implemented this." )

    def f_get_array(self):
        ''' Returns an iterable to iterate over the values of the exploration array.

        Note that the returned values should be either a copy of the exploration array
        or the array must be immutable, for example a python tuple.

        :return: immutable sequence

        Example usage:

        >>> param = Parameter('groupA.groupB.myparam',data=22, comment='I am a neat example')
        >>> param._explore([42,43,43])
        >>> print param.f_get_array()
        >>> (42,43,44)

        '''

        raise NotImplementedError( "Should have implemented this." )
    
    def _explore(self, iterable):
        ''' The default method to create and explored parameter containing an array of entries.

        :param iterable: An iterable specifying the exploration array

                         For example:

                         >>> param = Parameter('groupA.groupB.myparam',data=22.33,\
                          comment='I am a neat example')
                         >>> param._explore([3.0,2.0,1.0])

        :raises: ParameterLockedExcpetion: if the parameter is locked.

                 TypeError: if the parameter is already an array.

        '''

        raise NotImplementedError( "Should have implemented this." )

    def _expand(self, iterable):
        ''' Similar to :func:`_explore` but appends to the exploration array.


        :param iterable: An iterable specifying the exploration array.


        :raises: ParameterLockedExcpetion: If the parameter is locked.

                 TypeError: if the parameter is not an array.

        Example usage:

        >>> param = Parameter('groupA.groupB.myparam',data=3.13, comment='I am a neat example')
        >>> param._explore([3.0,2.0,1.0])
        >>> param._expand([42.0,43.0])
        >>> print param.f_get_array()
        >>> (3.0,2.0,1.0,42.0,43.0)

        '''
        raise NotImplementedError("Should have implemented this.")

    def _set_parameter_access(self, idx=0):
        ''' Sets the current value according to the `idx` in the exploration array.

        Prepares the parameter for further usage, and tells it which point in the parameter
        space should be accessed by calls to :func:`~pypet.parameter.Parameter.f_get`.

        :param idx: The index within the exploration parameter

                    If the parameter is not an array, the single data value is considered
                    regardless of the value of `idx`.
                    Raises ValueError if the parameter is explored and `idx>=len(param)`

        :raises: ValueError: if the parameter is an array and `idx` is larger or equal to the
                             length of the parameter

        Example usage:

        >>> param = Parameter('groupA.groupB.myparam',data=22.33, comment='I am a neat example')
        >>> param._explore([42.0,43.0,44.0])
        >>> param._set_parameter_access(idx=1)
        >>> print param.f_get()
        >>> 43.0

        '''
        raise NotImplementedError( "Should have implemented this." )
        
    def f_get_class_name(self):
        ''' Returns the name of the class i.e.
        `return self.__class__.__name__`

        '''
        return self.__class__.__name__


    def f_is_empty(self):
        ''' True if no data has been assigned to the parameter.

        >>> param = Parameter('myname.is.example', comment='I am _empty!')
        >>> param.f_is_empty()
        >>> True
        >>> param.f_set(444)
        >>> param.f_is_empty()
        >>> False

        '''
        return len(self) == 0

    def _shrink(self):
        ''' If a parameter is explored, i.e. it is an array, the whole exploration is deleted.

        Afterwards the parameter is no longer an array.

        Note that this function does not erase data from disk. So if the parameter has
        been stored with a service to disk and is shrunk, it can be restored by loading from
        disk.

        :raises: ParameterLockedException: if the parameter is locked.

                 TypeError: if  is the parameter is not an array.
        '''
        raise NotImplementedError( "Should have implemented this." )


    def f_empty(self):
        '''Erases all data in the parameter.

        Does not erase data from disk. So if the parameter has
        been stored with a service to disk and is emptied, it can be restored by loading from
        disk.

        :raises: ParameterLockedException: If the parameter is locked.

        '''
        raise NotImplementedError( "Should have implemented this." )






      
class Parameter(BaseParameter):
    ''' The standard parameter that handles access to simulation parameters.

    Parameters are simple container objects for data values. They handle single values as well as
    the so called exploration array. An array containing multiple values which is accessed
    one after the other in individual simulation runs.


    Parameter exploration is usually initiated through the trajectory see
    `:func:~pypet.trajectory.Trajectory.explore` and `:func:~pypet.trajectory.Trajectory.expand`.

    To access the parameter's data value one can call the :func:`~pypet.parameter.Parameter.f_get`
    method. Granted the parameter
    is explored via the trajectory, in order to
    access values of the exploration array, one first has to call the
    :func:`~pypet.parameter.Parameter._set_parameter_access`
    method with the index of the run and then use :func:`~pypet.parameter.Parameter.f_get`.

    Parameters support the concept of locking. Once a value of the parameter has been accessed,
    the parameter cannot be changed anymore unless it is explicitly unlocked using
    :func:`~pypet.parameter.Parameter.f_unlock`.
    Locking prevents parameters from being changed during runtime of a simulation.
    
    Supported data values for the parameter are

    * python natives (int,str,bool,float,complex),

    * numpy natives, arrays and matrices of type np.int8-64, np.uint8-64, np.float32-64,
      np.complex, np.str

    * python homogeneous not nested  tuples
    
    Note that for larger numpy arrays it is recommended to use the ArrayParameter.


     Example usage:

     >>> param = Parameter('traffic.mobiles.ncars',data=42, comment='I am a neat example')

    :param full_name: The full name of the parameter. Grouping can be achieved by using colons.

    :param data: A data value that is handled by the parameter. It is checked whether the parameter
        :func:`~pypet.parameter.Parameter.f_supports` the data. If not an TypeError is thrown.
        If the parameter becomes explored, the data value is kept as a default. After
        simulation the default value can be retained by calling
        :func:`~pypet.parameter.Parameter._restore_default`.
        The data can be accessed as follows:

        >>> param.f_get()
        42

        To change the data after parameter creation one can call :func:`~pypet.parameter.Parameter.f_set`:

        >>> param.f_set(43)
        >>> print param.f_get()
        43

    :param comment: A useful comment describing the parameter.
        The comment can be changed later on using the 'v_comment' variable.

        >>> print param.v_comment
        >>> 'I am a neat example'

    :raises: AttributeError: If `data` is not supported by the parameter.

    '''
    def __init__(self, full_name, data=None, comment=''):
        super(Parameter,self).__init__(full_name,comment)
        self._data= None
        self._default = None #The default value, which is the same as Data,
        # but it is necessary to keep a reference to it to restore the original value
        # after exploration
        self._explored_data=tuple()#The Explored Data
        self._set_logger()

        if not data == None:
            self.f_set(data)




    def _set_logger(self):
        self._logger = logging.getLogger('pypet.parameter.Parameter=' + self.v_full_name)

    def _restore_default(self):
        ''' Restores the default data, that was set with the `:func:`~pypet.parameter.Parameter.f_set`
        method (or at initialisation).

        If the parameter is explored during the runtime of a simulation,
        the actual value of the parameter is changed and taken from the exploration array.
        Calling :func:`~pypet.parameter.Parameter._restore_default` sets the parameter's value
        back to it's original value.

        Example usage:

        >>> param = Parameter('supergroup1.subgroup2.', data=44, comment='Im a comment!')
        >>> param._explore([1,2,3,4])
        >>> param._set_parameter_access(2)
        >>> print param.f_get()
        >>> 3
        >>> param._restore_default()
        >>> print param.f_get()
        >>> 44

        '''
        self._data = self._default

    def __len__(self):
        if self._data is None:
            return 0
        elif len(self._explored_data)>0:
            return len(self._explored_data)
        else:
            return 1

    @copydoc(BaseParameter.f_is_array)
    def f_is_array(self):
        return len(self._explored_data)>0
       
    def __getstate__(self):
        ''' Returns the actual state of the parameter for pickling.

        '''
        result = self.__dict__.copy()


        # If we don't need a full copy of the Parameter (because a single process needs
        # only access to a single point in the parameter space we can delete the rest
        if not self._full_copy :
            result['_explored_data'] = tuple()

        del result['_logger'] #pickling does not work with loggers
        return result




    def __setstate__(self, statedict):
        ''' Sets the state for unpickling.

        '''
        self.__dict__.update( statedict)
        self._set_logger()
      
    @copydoc(BaseParameter._set_parameter_access)
    def _set_parameter_access(self, idx=0):
        if idx >= len(self) and self.f_is_array():
            raise ValueError('You try to access the %dth parameter in the array of parameters, '
                             'yet there are only %d potential parameters.' % (idx, len(self)))
        else:
            self._data = self._explored_data[idx]

    def f_supports(self, data):
        ''' Checks if input data is supported by the parameter.'''

        if type(data) is tuple:

            if len(data)==0:
                return False

            for item in data:
                old_type = None
                if not type(item) in pypetconstants.PARAMETER_SUPPORTED_DATA:
                    return False
                if not old_type is None and old_type != type(item):
                    return False
                old_type = type(item)
            return True

        if type(data) in [np.ndarray, np.matrix]:

            if len(data)==0:
                return False

            dtype = data.dtype
            if np.issubdtype(dtype,np.str):
                dtype = np.str
        else:
            dtype=type(data)

        return dtype in pypetconstants.PARAMETER_SUPPORTED_DATA


    def _values_of_same_type(self,val1, val2):
        ''' Checks if two values agree in type.

        Raises a TypeError if both values are not supported by the parameter.
        Returns False if only one of the two values is supported by the parameter.

        Example usage:

        >>>param._values_of_same_type(42,43)
        True

        >>>param._values_of_same_type(42,'43')
        False

        :raises: TypeError

        :return: True or False

        '''
        if self.f_supports(val1) != self.f_supports(val2):
            return False

        if not self.f_supports(val1) and not self.f_supports(val2):
                raise TypeError('I do not support the types of both inputs (>>%s<< and >>%s<<),'
                                ' therefore I cannot judge whether the two are of same type.' %
                                str(type(val1)),str(type(val2)))
        
        if not type(val1) is type(val2):
            return False
        
        if type(val1) is np.array:
            if not val1.dtype is val2.dtype:
                return False
            
            if not np.shape(val1)==np.shape(val2):
                return False

        if type(val1) is tuple:
            return type(val1[0]) is type(val2[0])
        
        return True




    @copydoc(BaseParameter.f_set)
    def f_set(self,data):

        if self.v_locked:
            raise pex.ParameterLockedException('Parameter >>' + self._name + '<< is locked!')


        if self.f_is_array():
            raise AttributeError('Your Parameter is an explored array can no longer change values!')


        val = self._convert_data(data)

        if not self.f_supports(val):
            raise TypeError('Unsupported data >>%s<<' % str(val))

        self._data= val
        self._default = self._data




    def _convert_data(self, val):
        ''' Converts data to be handled by the parameter

        * sets numpy arrays immutable.

        :param val: the data value to convert

        :return: the converted data

        '''


        if type(val) is np.ndarray:
            val.flags.writeable = False
            return val

        return val


    @copydoc(BaseParameter.f_get_array)
    def f_get_array(self):
        ''' Returns an python tuple of the exploration array.


        :return: data tuple

        Example usage:

        >>> param = Parameter('groupA.groupB.myparam',data=22, comment='I am a neat example')
        >>> param._explore([42,43,43])
        >>> print param.f_get_array()
        >>> (42,43,44)

        '''
        if not self.f_is_array():
            raise TypeError('Your parameter >>%s<< is not array, so cannot return array.' %
                                    self.v_full_name)
        else:
            return self._explored_data


    def _explore(self, explore_iterable):
        ''' Explores the parameter according to the iterable.

        Raises ParameterLockedException if the parameter is locked.
        Raises TypeError if the parameter does not support the data,
        the types of the data in the iterable are not the same as the type of the default value,
        or the parameter has already an exploration array.

        Note that the parameter will iterate over the whole iterable once and store
        the individual data values into a tuple. Thus, the whole exploration array is
        explicitly stored in memory.

        :param iterable: An iterable specifying the exploration array

        For example:

        >>> param._explore([3.0,2.0,1.0])
        >>> param.f_get_array()
        (3.0,2.0,1.0)


        :raises TypeError,ParameterLockedException

        '''
        if self.v_locked:
            raise pex.ParameterLockedException('Parameter >>%s<< is locked!' % self.v_full_name)

        if self.f_is_array():
            raise TypeError('Your Parameter %s is already explored, cannot _explore it further!' % self._name)


        data_tuple = self._data_sanity_checks(explore_iterable)

        self._explored_data = data_tuple
        self.f_lock()

    def _expand(self,explore_iterable):
        ''' Explores the parameter according to the iterable and appends to the exploration array.

        Raises ParameterLockedException if the parameter is locked.
        Raises TypeError if the parameter does not support the data,
        the types of the data in the iterable are not the same as the type of the default value,
        or the parameter was not an array before.

        Note that the parameter will iterate over the whole iterable once and store
        the individual data values into a tuple. Thus, the whole exploration array is
        explicitly stored in memory.

        :param iterable: An iterable specifying the exploration array

                         For example:

                         >>> param = Parameter('Im.an.example', data=33.33, comment='Wooohoo!')
                         >>> param._explore([3.0,2.0,1.0])
                         >>> param.f_get_array()
                         >>> (3.0,2.0,1.0)

        :raises TypeError,ParameterLockedException

        '''
        if self.v_locked:
            raise pex.ParameterLockedException('Parameter >>%s<< is locked!' % self.v_full_name)

        if not self.f_is_array():
            raise TypeError('Your Parameter is not an array and can therefore not be expanded.' % self._name)


        data_tuple = self._data_sanity_checks(explore_iterable)



        self._explored_data = self._explored_data + data_tuple
        self.f_lock()


    def _data_sanity_checks(self, explore_iterable):
        ''' Checks if data values are legal.

        Checks if the data values are supported by the parameter and if the values are of the same
        type as the default value.
        '''
        data_tuple = []

        default_val = self._data

        for val in explore_iterable:
            newval = self._convert_data(val)


            if not self.f_supports(newval):
                raise TypeError('%s is of not supported type %s.' % (repr(val),str(type(newval))))

            if not self._values_of_same_type(newval,default_val):
                raise TypeError('Data is not of the same type as the original entry value, new type is %s vs old type %s.' % ( str(type(newval)),str(type(default_val))))


            data_tuple.append(newval)


        if len(data_tuple) == 0:
            raise ValueError('Cannot _explore an _empty list!')

        return tuple(data_tuple)

    @copydoc(BaseParameter._store)
    def _store(self):
        store_dict={}
        store_dict['data'] = ObjectTable(data={'data':[self._data]})
        if self.f_is_array():
            store_dict['explored_data'] = ObjectTable(data={'data':self._explored_data})


        return store_dict

    @copydoc(BaseParameter._load)
    def _load(self,load_dict):
        self._data = self._convert_data(load_dict['data']['data'][0])
        self._default=self._data
        if 'explored_data' in load_dict:
            self._explored_data = tuple([self._convert_data(x)
                                   for x in load_dict['explored_data']['data'].tolist()])



    @copydoc(BaseParameter.f_get)
    def f_get(self):
        self.f_lock() # As soon as someone accesses an entry the parameter gets locked
        return self._data

    @copydoc(BaseParameter._shrink)
    def _shrink(self):
        if self.f_is_empty():
            raise TypeError('Cannot _shrink _empty Parameter.')

        if self.v_locked:
            raise pex.ParameterLockedException('Parameter %s is locked!' % self.v_full_name)

        del self._explored_data
        self._explored_data={}

    @copydoc(BaseParameter.f_empty)
    def f_empty(self):
        if self.v_locked:
            raise pex.ParameterLockedException('Parameter %s is locked!' % self.v_full_name)

        self._shrink()
        del self._data
        self._data=None

     

class ArrayParameter(Parameter):

    ''' Similar to the :class:`:func:`~pypet.parameter.Parameter`, but recommended for
    large numpy arrays and python tuples.

    The array parameter is a bit smarter in memory management than the parameter.
    If a numpy array is used several times within an exploration, only one numpy array is stored by
    the default HDF5 storage service. For each individual run references to the corresponding
    numpy array are stored.

    Since the ArrayParameter inherits from :class:`~pypet.parameter.Parameter` it also
    supports all other native python types.

    '''

    IDENTIFIER = '__rr__'

    def _set_logger(self):
        self._logger = logging.getLogger('pypet.parameter.ArrayParameter=' + self.v_full_name)

    def _store(self):

        if not type(self._data) in [np.ndarray, tuple, np.matrix]:
            return super(ArrayParameter,self)._store()
        else:
            store_dict = {}

            store_dict['data'+ArrayParameter.IDENTIFIER] = self._data

            if self.f_is_array():
                ## Supports smart storage by hashing numpy arrays are hashed by their data attribute
                smart_dict = {}

                store_dict['explored_data'+ArrayParameter.IDENTIFIER] = \
                    ObjectTable(columns=['idx'],index=range(len(self)))

                count = 0
                for idx,elem in enumerate(self._explored_data):

                    try:
                        hash(elem)
                        hash_elem = elem
                    except TypeError:
                        hash_elem = elem.data

                    if hash_elem in smart_dict:
                        name_idx = smart_dict[hash_elem]
                        add = False
                    else:
                        name_idx = count
                        add = True

                    name = self._build_name(name_idx)
                    store_dict['explored_data'+ArrayParameter.IDENTIFIER]['idx'][idx] = \
                        name_idx

                    if add:
                        store_dict[name] = elem
                        smart_dict[hash_elem] = name_idx
                        count +=1

            return store_dict

    def _build_name(self,name_id):
        return 'xa%s%08d' % (ArrayParameter.IDENTIFIER, name_id)




    def _load(self,load_dict):
        try:
            self._data = load_dict['data'+ArrayParameter.IDENTIFIER]

            if 'explored_data'+ArrayParameter.IDENTIFIER in load_dict:
                explore_table = load_dict['explored_data'+ArrayParameter.IDENTIFIER]

                name_col = explore_table['idx']

                explore_list = []
                for name_id in name_col:
                    arrayname = self._build_name(name_id)
                    explore_list.append(load_dict[arrayname])

                self._explored_data=tuple([self._convert_data(x) for x in explore_list])

        except KeyError:
            super(ArrayParameter,self)._load(load_dict)

        self._default=self._data


    def _values_of_same_type(self,val1, val2):
        ''' The array parameter is less restrictive than the parameter. If both values
        are arrays, matrices or tuples, they are considered to be of same type
        regardless of their size and values they contain.
        '''
        if (type(val1) in [np.ndarray, tuple, np.matrix]) and (type(val2) is type(val1)):
            return True
        else:
            return super(ArrayParameter,self)._values_of_same_type(val1,val2)



class SparseParameter(ArrayParameter):
    ''' Parameter that handles scipy csr, csc, bsr and dia matrices.

    Sparse Parameter inherits from :class:`pypet.parameter.ArrayParameter` and supports
    arrays and native python data as well.
    '''

    IDENTIFIER = '__spsp__'

    DIA_NAME_LIST = ['format', 'data', 'offsets', 'shape']
    OTHER_NAME_LIST = ['format', 'data', 'indices', 'indptr', 'shape']

    def _values_of_same_type(self,val1, val2):
        ''' The sparse parameter is less restrictive than the parameter. If both values
        are sparse matrices they are considered to be of same type
        regardless of their size and values they contain.
        '''
        if self._is_supported_matrix(val1) and self._is_supported_matrix(val2):
            return True
        else:
            return super(SparseParameter,self)._values_of_same_type(val1,val2)

    def _equal_values(self,val1,val2):
        '''Matrices are equal if they hash to the same value'''
        if self._is_supported_matrix(val1):
            if self._is_supported_matrix(val2):

                _,_,hash_tuple_1 = self._serialize_matrix(val1)
                _,_,hash_tuple_2 = self._serialize_matrix(val2)

                return hash(hash_tuple_1)==hash(hash_tuple_2)
            else:
                return False
        else:
            return super(SparseParameter,self)._equal_values(val1,val2)

    @staticmethod
    def _is_supported_matrix(data):
        return (spsp.isspmatrix_csc(data) or
                spsp.isspmatrix_csr(data) or
                spsp.isspmatrix_bsr(data) or
                spsp.isspmatrix_dia(data) )


    def f_supports(self, data):
        '''Sparse matrices support scipy csr, csc, bsr and dia matrices and everything their parent
        class the :calls:`~pypet.parameter.ArrayParameter` supports.

        :return: True of False if data is supported.

        '''
        if self._is_supported_matrix(data):
            return True
        else:
            return super(SparseParameter,self).f_supports(data)

    @staticmethod
    def _serialize_matrix(matrix):
        if (spsp.isspmatrix_csc(matrix) or
            spsp.isspmatrix_csr(matrix) or
            spsp.isspmatrix_bsr(matrix)):
            return_list= [matrix.data, matrix.indices, matrix.indptr, matrix.shape]

            return_names=SparseParameter.OTHER_NAME_LIST

            if spsp.isspmatrix_csc(matrix):
                return_list= ['csc'] + return_list
            elif spsp.isspmatrix_csr(matrix):
                return_list= ['csr'] + return_list
            elif spsp.isspmatrix_bsr(matrix):
                return_list= ['bsr'] + return_list
            else:
                raise RuntimeError('You shall not pass!')

        elif spsp.isspmatrix_dia(matrix):
            return_list=['dia', matrix.data, matrix.offsets, matrix.shape]

            return_names=SparseParameter.DIA_NAME_LIST
        else:
            raise RuntimeError('You shall not pass!')

        hash_list = []
        for item in return_list:
            if type(item) is np.ndarray:
                item.flags.writeable = False
                hash_list.append(item.data)
            else:
                hash_list.append(item)

        return return_list, return_names, tuple(hash_list)


    def _set_logger(self):
        self._logger = logging.getLogger('pypet.parameter.SparseParameter=' + self.v_full_name)

    @staticmethod
    def _get_name_list(is_dia):
        if is_dia:
            return SparseParameter.DIA_NAME_LIST
        else:
            return SparseParameter.OTHER_NAME_LIST

    def _store(self):

        if not self._is_supported_matrix(self._data):
            return super(SparseParameter,self)._store()
        else:
            store_dict = {}
            data_list, name_list, hash_tuple= self._serialize_matrix(self._data)
            rename_list = ['data%s%s' % (SparseParameter.IDENTIFIER,name)
                                 for name in name_list]

            is_dia = int(len(rename_list)==4)
            store_dict['data%sis_dia' % SparseParameter.IDENTIFIER]= is_dia

            for idx,name in enumerate(rename_list):
                store_dict[name] = data_list[idx]

            if self.f_is_array():
                ## Supports smart storage by hashing
                smart_dict = {}

                store_dict['explored_data'+SparseParameter.IDENTIFIER] = \
                    ObjectTable(columns=['idx','is_dia'],
                                index=range(len(self)))

                count = 0
                for idx,elem in enumerate(self._explored_data):

                    data_list, name_list, hash_tuple = self._serialize_matrix(elem)

                    if hash_tuple in smart_dict:
                        name_id = smart_dict[hash_tuple]
                        add = False
                    else:
                        name_id = count
                        add = True

                    is_dia=int(len(name_list)==4)
                    rename_list = self._build_names(name_id,is_dia)

                    store_dict['explored_data'+SparseParameter.IDENTIFIER]['idx'][idx] = name_id

                    store_dict['explored_data'+SparseParameter.IDENTIFIER]['is_dia'][idx] = is_dia


                    if add:

                        for irun,name in enumerate(rename_list):
                            store_dict[name] = data_list[irun]

                        smart_dict[hash_tuple] = name_id
                        count +=1

            return store_dict

    def _build_names(self, name_id, is_dia):
        name_list = self._get_name_list(is_dia)
        return tuple(['xspm%s%s%08d' % (SparseParameter.IDENTIFIER, name, name_id)
                                    for name in name_list])


    @staticmethod
    def _reconstruct_matrix(data_list):

        format = data_list[0]

        if format == 'csc':
            return spsp.csc_matrix(tuple(data_list[1:4]),shape=data_list[4])
        elif format == 'csr':
            return spsp.csr_matrix(tuple(data_list[1:4]),shape=data_list[4])
        elif format == 'bsr':
            return spsp.bsr_matrix(tuple(data_list[1:4]),shape=data_list[4])
        elif format == 'dia':
            return spsp.dia_matrix(tuple(data_list[1:3]), shape=data_list[3])
        else:
            raise RuntimeError('You shall not pass!')



    def _load(self,load_dict):
        try:
            is_dia =  load_dict['data%sis_dia' % SparseParameter.IDENTIFIER]

            name_list = self._get_name_list(is_dia)
            rename_list = ['data%s%s' % (SparseParameter.IDENTIFIER,name)
                                 for name in name_list]

            data_list = [load_dict[name] for name in rename_list]
            self._data = self._reconstruct_matrix(data_list)


            if 'explored_data'+SparseParameter.IDENTIFIER in load_dict:
                explore_table = load_dict['explored_data'+SparseParameter.IDENTIFIER]

                idx_col = explore_table['idx']
                dia_col = explore_table['is_dia']

                explore_list = []
                for irun, name_id in enumerate(idx_col):
                    is_dia = dia_col[irun]
                    name_list = self._build_names(name_id,is_dia)
                    data_list = [load_dict[name] for name in name_list]
                    matrix = self._reconstruct_matrix(data_list)
                    explore_list.append(matrix)

                self._explored_data=tuple(explore_list)


        except KeyError:
            super(SparseParameter,self)._load(load_dict)

        self._default=self._data


class PickleParameter(Parameter):
    ''' A parameter class that supports all pickable objects, and pickles everything!

    If you use the default HDF5 storage service, the pickle dumps are stored on disk.
    Works similar to the array parameter regarding memory management.

    '''
    IDENTIFIER='__pckl__'

    def _set_logger(self):
        self._logger = logging.getLogger('pypet.parameter.PickleParameter=' + self.v_full_name)

    def f_supports(self, data):
        ''' There is no straightforward check if an object can be pickled, so you have to take care that it can be pickled '''
        return True

    def _convert_data(self, val):
        return val

    def _build_name(self,name_id):
        return 'xp%s%08d' % (PickleParameter.IDENTIFIER,name_id)

    def _store(self):
        store_dict={}
        dump = pickle.dumps(self._data)
        store_dict['data'+PickleParameter.IDENTIFIER] = dump

        if self.f_is_array():

            store_dict['explored_data'+PickleParameter.IDENTIFIER] = \
                ObjectTable(columns=['idx'],index=range(len(self)))

            smart_dict = {}
            count = 0


            for idx, val in enumerate(self._explored_data):

                obj_id = id(val)

                if obj_id in smart_dict:
                    name_id = smart_dict[obj_id]
                    add = False
                else:
                    name_id = count
                    add = True

                name = self._build_name(name_id)
                store_dict['explored_data'+PickleParameter.IDENTIFIER]['idx'][idx] = name_id

                if add:
                    store_dict[name] = pickle.dumps(val)
                    smart_dict[obj_id] = name_id
                    count +=1

        return store_dict

    def _load(self,load_dict):

        dump = load_dict['data'+PickleParameter.IDENTIFIER]
        self._data = pickle.loads(dump)

        if 'explored_data'+PickleParameter.IDENTIFIER in load_dict:
                explore_table = load_dict['explored_data'+PickleParameter.IDENTIFIER]

                name_col = explore_table['idx']

                explore_list = []
                for name_id in name_col:
                    arrayname = self._build_name(name_id)
                    loaded = pickle.loads(load_dict[arrayname])
                    explore_list.append(loaded)

                self._explored_data=tuple(explore_list)


        self._default=self._data





      

            
                            

class BaseResult(NNLeafNode):
    ''' The basic api to store results.

    Compared to parameters (see :class: BaseParameter) results are also initialised with a fullname
    and a comment.
    As before grouping is achieved by colons in the name.

    Example usage:

    >>> result = Result(fullname='very.important.result',comment='I am important but f_emptyty :('

    '''
    def __init__(self, full_name, comment=''):
        super(BaseResult,self).__init__(full_name,comment, parameter=False)



class Result(BaseResult):
    ''' Light Container that stores tables and arrays.

    Note that no sanity checks on individual data is made
    and you have to take care, that your data is understood by the storage service.
    It is assumed that results tend to be large and therefore sanity checks would be too expensive.

    Data that can safely be stored into a Result are:

        * python natives (int,str,bool,float,complex),

        * numpy natives, arrays and matrices of type np.int8-64, np.uint8-64, np.float32-64,
          np.complex, np.str


        *

            python lists and tuples of the previous types
            (python natives + numpy natives and arrays)
            Lists and tuples are not allowed to be nested and must be
            homogeneous, i.e. only contain data of one particular type.
            Only integers, or only floats, etc.

        *
            python dictionaries of the previous types (not nested!), data can be
            heterogeneous, keys must be strings. For example, one key-value pair
            of string and int and one key-value pair of string and float, and so
            on.

        * pandas DataFrames_

        * :class:`pypet.parameter.ObjectTable`

    .. _DataFrames: http://pandas.pydata.org/pandas-docs/dev/dsintro.html#dataframe

    Such values are either set on initialisation of with :func:`~pypet.parameter.Result.f_set`

    Example usage:

    >>> res = Result('supergroup.subgroup.myresult', comment='I am a neat example!' \
        [1000,2000], {'a':'b','c':'d'}, hitchhiker='Arthur Dent')

    :param fullanme: The fullname of the result, grouping can be achieved are separated by colons,


    :param comment: A useful comment describing the parameter.
        The comment can later on be changed using the `v_comment` variable

        >>> param.v_comment
        'I am a neat example!'

    :param args: data that is handled by the result, it is kept by the result under the names
        `run%d` with `%d` being the position in the argument list.
        Can be changed or more can be added via :func:`~pypet.parameter.Result.f_set`

    :param kwargs: data that is handled by the result, it is kept by the result under the names
        specified by the keys of kwargs.
        Can be changed or more can be added via :func:`~pypet.parameter.Result.f_set`

        >>> print res.f_get(0)
        [1000,2000]
        >>> print res.f_get(1)
        {'a':'b','c':'d'}
        >>> print res.f_get('myresult')
        [1000,2000]
        >>> print res.f_get('hitchhiker')
        'ArthurDent'
        >>> print res.f_get('myresult','hitchhiker')
        ([1000,2000], 'ArthurDent')


    :raises: AttributeError: If the data in args or kwargs is not supported. Checks type of
                             outer data structure, i.e. checks if you have a list or dictionary.
                             But it does not check on individual values within dicts or lists.

    Alternatively one can also use :func:`~pypet.parameter.Result.f_set`

    >>> result.f_set('Uno',x='y')
    >>> print result.f_get(0)
    'Uno'
    >>> print result.f_get('x')
    'y'


    Alternative method to put and retrieve data from the result container is via `__getattr__` and
    `__setattr__`

    >>> res.ford = 'prefect'
    >>> res.ford
    'prefect'

    '''
    def __init__(self, full_name, *args, **kwargs):
        comment = kwargs.pop('comment','')
        super(Result,self).__init__(full_name,comment)
        self._data = {}
        self._set_logger()
        self.f_set(*args,**kwargs)
        self._no_data_string = False


    @property
    def v_no_data_string(self):
        '''Whether or not to give a short summarizing string when calling
         :func:`~pypet.parameter.Result.f_val_to_str`.

        Can be set to False if the evaluation of stored data into string is too costly.

        '''
        return self._no_data_string

    @v_no_data_string.setter
    def v_no_data_string(self,boolean):
        self._no_data_string(boolean)


    def __contains__(self, item):
        return item in self._data


    def f_val_to_str(self):
        ''' Summarizes data handled by the result as a string.
        Calls `__str__` on all handled data if `v_no_data_string=True`, else only
        the name/key of the handled data is printed.

        :return: string

        '''
        if not self._no_data_string:
            resstr=''
            for key,val in iter(sorted(self._data.items())):
                resstr+= '%s=%s, ' % (key, str(val))

                if len(resstr) >= pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH:
                    resstr = resstr[0:pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH-3]+'...'
                    return resstr

            resstr=resstr[0:-2]
            return resstr
        else:
            resstr = ', '.join(self._data.keys())

            if len(resstr) >= pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH:
                    resstr = resstr[0:pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH-3]+'...'

            return resstr



    def __str__(self):

        datastr = str([(key,str(type(val))) for key,val in self._data.iteritems()])
        if self.v_comment:
            return '<%s>: %s (Comment:%s): %s' % (self.f_get_class_name(),
                                                  self.v_full_name,self.v_comment,datastr)
        else:
            return '<%s>: %s: %s' % (self.f_get_class_name(),self.v_full_name,datastr)



    def _set_logger(self):
        self._logger = logging.getLogger('pypet.parameter.Result=' + self.v_full_name)


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
        self._set_logger()

    def f_to_dict(self, copy = True):
        ''' Returns all handled data as a dictionary

        :param copy: Whether the original dictionary or a shallow copy is returned. If you get
                     the real thing, please do not modify it!

        :return: Data dictionary

        '''
        if copy:
            return self._data.copy()
        else:
            return self._data


    def f_is_empty(self):
        ''' True if no data has been put into the result.

        Also True if all data has been erased via :func:`~pypet.parameter.Result.f_empty`

        '''
        return len(self._data)== 0

    @copydoc(BaseResult.f_empty)
    def f_empty(self):
        del self._data
        self._data={}

    def f_set(self,*args, **kwargs):
        ''' Method to put data into the result.

        :param args: The first positional argument is stored with the name of the result.
                    Following arguments are stored with `name_X` where `X` is the position
                    of the argument.

        :param kwargs: Arguments are stored with the key as name.

        >>> res = Result('supergroup.subgroup.myresult', comment='I am a neat example!')
        >>> res.f_set(333,42.0mystring='String!')
        >>> res.f_get('myresult')
        333
        >>> res.f_get('myresult_1')
        42.0
        >>> res.f_get(1)
        42.0
        >>> res.f_get('mystring')
        'String!'

        '''
        for idx,arg in enumerate(args):
            if idx == 0:
                valstr = self.v_name
            else:
                valstr = self.v_name+'_'+str(idx)
            self.f_set_single(valstr,arg)

        for key, arg in kwargs.items():
            self.f_set_single(key,arg)


    def __getitem__(self, name):
        ''' Equivalent to calling `f_get(name)` (see :func:`~pypet.parameter.BaseResult.f_get`).
        '''
        return self.f_get(name)

    def f_get(self,*args):
        ''' Returns items handled by the result.

         If only a single name is given a single data item is returned, if several names are
         given, a list is returned. For integer inputs the results returns `resultname_X`.

         If the result contains only a single entry you can call `f_get()` without arguments.
         If you call `f_get()` and the result contains more than one element a ValueError is
         thrown.

        :param args: strings-names or integers

        :return: Single data item or tuple of data

        Example:

        >>> res = Result('supergroup.subgroup.myresult', comment='I am a neat example!' \
        [1000,2000], {'a':'b','c':'d'}, hitchhiker='Arthur Dent')
        >>> res.f_get('hitchhiker')
        'Arthur Dent'
        >>> res.f_get(0)
        [1000,2000]
        >>> res.f_get('hitchhiker', 'myresult')
        ('Arthur Dent', [1000,2000])

        '''

        if len(args) == 0:
            if len(self._data) == 1:
                return self._data[self._data.keys()[0]]
            elif len(self._data) >1:
                raise ValueError('Your result >>%s<< contains more than one entry: '
                                 '>>%s<< Please use >>f_get<< with one of these.' %
                                 (self.v_full_name, str(self._data.keys())))
            else:
                raise AttributeError('Your result >>%s<< is empty, cannot access data.' %
                                     self.v_full_name)

        result_list = []
        for name in args:
            if name == 0:
                name = self.v_name
            else:
                try:
                    name = self.v_name+'_%d' % name
                except TypeError:
                    pass

            if not name in self._data:
                raise  AttributeError('>>%s<< is not part of your result >>%s<<.' %
                                      (name,self.v_full_name))

            result_list.append(self._data[name])

        if len(args)==1:
            return result_list[0]
        else:
            return result_list

    def f_set_single(self, name, item):
        ''' Sets a single data item to the result.

        Raises AttributeError if the type of the data is not understood.
        Note that the type check is shallow. For example, if the data item is a list,
        the individual list elements are NOT checked whether their types are appropriate.

        :param name: The name of the data item
        :param item: The data item

        :raises: AttributeError

        Example usage:

        >>> res.f_set_single('answer', 42)
        >>> res.f_get('answer')
        >>> 42
        '''
        if name in ['comment', 'Comment']:
            self.v_comment= item

        if self._supports(item):

            self._check_if_empty(item, name)

            self._data[name] = item
        else:
            raise AttributeError('Your result >>%s<< of type >>%s<< is not supported.' %
                                 (name,str(type(item))))

    def _check_if_empty(self, item, name):
        try:
            if len(item) ==0:
                self._logger.warning('The Item >>%s<< is empty.' % name)
        except TypeError:
            # If the item does not support len operation we can ignore that
            pass

    def _supports(self, item):
        return type(item) in ((np.ndarray,ObjectTable,DataFrame,dict,tuple,list,np.matrix)+
                             pypetconstants.PARAMETER_SUPPORTED_DATA)


    @property
    def v_fast_accessible(self):
        '''A result is fast accessible if it contains exactly one item!'''
        return len(self._data)==1 and self.v_name in self._data

    @copydoc(NNLeafNode._store)
    def _store(self):
        store_dict ={}
        store_dict.update(self._data)
        return store_dict




    def _load(self, load_dict):
        self._data = load_dict



    def __delattr__(self, item):
        ''' Deletes an item from the result.

        If the item has been stored to disk before with a storage service, this storage is not
        deleted!

        :param item: The item to delete

        Example usage:

        >>> res = Result('Iam.an.example', comment = 'And a neat one, indeed!', fortytwo=42)
        >>> print 'fortytwo' in res
        >>> True
        >>> del res.fortytwo
        >>> print 'fortytwo' in res
        >>> False

        '''
        if item[0]=='_':
            del self.__dict__[item]
        elif item in self._data:
            del self._data[item]
        else:
            raise AttributeError('Your result >>%s<< does not contain %s.' % (self.name_,item))

    def __setattr__(self, key, value):
        if key[0]=='_':
            self.__dict__[key] = value
        elif hasattr(self.__class__,key):
            property = getattr(self.__class__,key)
            if property.fset is None:
                raise AttributeError('%s is read only!' % key)
            else:
                property.fset(self,value)
        else:
            self.f_set_single(key, value)

    def __getattr__(self, name):

        if (not '_data' in self.__dict__):

            raise AttributeError('This is to avoid pickling issues!')

        if name in ['Comment', 'comment']:
            return self._comment

        if not name in self._data:
            raise  AttributeError('>>%s<< is not part of your result >>%s<<.' % (name,self.v_full_name))

        return self._data[name]

class SparseResult(Result):
    ''' Adds the support of scipy sparse matrices to the result.

    Supported Formats are csr, csc, bsr, and dia.
    Supports also all data, handled by the standard result.
    '''

    IDENTIFIER = SparseParameter.IDENTIFIER

    def f_set_single(self, name, item):
        if SparseResult.IDENTIFIER in name:
            raise AttributeError('Your result name contains the identifier for sparse matrices,'
                                 ' please do not use %s in your result names.' %
                                 SparseResult.IDENTIFIER)
        else:
            super(SparseResult,self).f_set_single(name,item)


    def _supports(self, item):
        if SparseParameter._is_supported_matrix(item):
            return True
        else:
            return super(SparseResult,self)._supports(item)

    def _check_if_empty(self, item, name):
        if SparseParameter._is_supported_matrix(item):
            if item.getnnz()==0:
                self._logger.warning('The Item >>%s<< is empty.' % name)
        else:
            super(SparseResult,self)._check_if_empty(item, name)

    def _store(self):
        store_dict = {}
        for key, val in self._data.iteritems():
            if SparseParameter._is_supported_matrix(val):

                data_list, name_list, hash_tuple= SparseParameter._serialize_matrix(val)
                rename_list = ['%s%s%s' % (key, SparseParameter.IDENTIFIER,name)
                                     for name in name_list]

                is_dia = int(len(rename_list)==4)
                store_dict[key+SparseResult.IDENTIFIER+'is_dia'] =  is_dia

                for idx,name in enumerate(rename_list):
                    store_dict[name] = data_list[idx]

            else:
                store_dict[key]=val

        return  store_dict

    def _load(self, load_dict):

        for key in load_dict.keys():
            # We delete keys over time:
            if key in load_dict:
                if SparseResult.IDENTIFIER in key:
                    new_key = key.split(SparseResult.IDENTIFIER)[0]

                    is_dia = load_dict.pop(new_key+SparseResult.IDENTIFIER+'is_dia')

                    name_list = SparseParameter._get_name_list(is_dia)
                    rename_list = ['%s%s%s' % (new_key,SparseResult.IDENTIFIER,name)
                                         for name in name_list]

                    data_list = [load_dict.pop(name) for name in rename_list]
                    matrix = SparseParameter._reconstruct_matrix(data_list)
                    self._data[new_key]=matrix
                else:
                    self._data[key]=load_dict[key]







class PickleResult(Result):
    ''' Result that digest everything and simply pickles it!

    Note that it is not checked whether data can be pickled, so take care that it works!
    '''

    IDENTIFIER=PickleParameter.IDENTIFIER

    def f_set_single(self, name, item):
        '''Adds a single data item to the pickle result.

         Note that it is NOT checked if the item can be pickled!

        '''
        self._data[name] = item


    def _set_logger(self):
        self._logger = logging.getLogger('pypet.parameter.PickleResult=' + self.v_full_name)



    def _store(self):
        store_dict ={}
        for key, val in self._data.items():
            store_dict[key+PickleResult.IDENTIFIER] = pickle.dumps(val)
        return store_dict


    def _load(self, load_dict):
        for key, val in load_dict.items():
            new_key = key[:-len(PickleResult.IDENTIFIER)]
            self._data[new_key] = pickle.loads(val)