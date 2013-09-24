__author__ = 'Robert Meyer'




''' Module for data containers, these are containers for parameters and results.
==========================================
General idea behind parameters and results
==========================================

The classes in this module are general containers for data that you acquire or need
to run any sort of scientific simulation in Python.

-----------------------------------------
Parameters
-----------------------------------------

A specific container is the so called parameter container (Base API is found in BaseParameter
class) it is used to keep data that is explicitly required as parameters for your simulations.
For example, this could be the numbers or cars for traffic jam simulations, or for
brain simulations the number of neurons, conductances of ion channels etc.

Parameter containers fulfill four further important
jobs:

 *  A key concept in numerical simulations is exploration of the parameter space. Therefore,
    the parameter containers not only keep a single value but can hold an exploration array
    of values.
    To avoid confusion with numpy arrays, I will explicitly always say exploration array.
    The individual values in the exploration array can be accessed one after the other
    for distinct simulations.

 *  It can be locked, meaning as soon as the parameter is assigned to hold a specific
    value and the value has already been used somewhere (for instance, creating X neurons),
    it cannot be changed any longer (except after being explicitly unlocked).
    This prevents the nasty error of having a particular parameter value
    at the beginning of a simulation but changing it during runtime for whatever reason. This
    can make your simulations impossible to understand by other people running them.
    Or even you running it again with different parameter settings but observing the
    very same results, since your parameter is changed later on in your simulations!
    In fact I ran into this problem during my PhD using someone else's simulations.
    Thus, debugging took ages. As a consequence this project was born.

    By definition parameters are fixed values, that once used never change.
    An exception to this rule is solely the exploration of the parameter space, but this
    requires to run a number of distinct simulations anyway.

 *  It provides a method to compare values in a strict boolean sense. For instance, this is
    important given you want to merge trajectories and delete simulations that have been done
    twice. The problem with most objects using them as parameters is that they have custom
    equality functions. Comparing two numpy arrays with '==' will returned a third array
    of truth values, for instance. But in order to identify equal parameter values,
    we need a single boolean value. Here the paramter container for numpy arrays could define
    the equality of two numpy arrays (with numpy as np) as
    >>> np.all(numpyarray1 == numpyarray2)
    which returns a single boolean value.

 *  It has a rough idea of how to serialize and store parameter values.
    If you intend to use basic parameter values like python int,str,bool or numpy arrays and
    data, you can ignore this part, otherwise go on:

    Conceptually it is always a good idea to have the storage of stuff and its use distinct. This
    allows you to change the storage method or service later on, to migrate from hdf5 to SQL,
    for example. This is also the case in this project. Yet, parameters know how to preprocess their
    values in order to serialize them. More precisley, they know how to turn their values
    into very basic data structures.
    They can convert values and their exploration arrays of values into stuff like
    numpy data types and numpy arrays, python native data types (int,str, etc) or pandas tables.
    These structures are then used by the independent storage service to actually put the data
    to disk (whatever that is).
    If a parameter is loaded from disk, these sort of basic data formats are given back
    to the parameter container which reconstructs the original value.

    Why is this important anyway?
    This becomes important as soon as you want to implement your own special parameter, that can
    use more complex objects as parameters. For instance, you have not only the number of cars
    as a parameter but a specific car object, that is principally complex in itself.
    This example is kind of far fetched, because the best idea would be to have the indivdual
    cars attributes as basic parameters (like number of doors, number of wheels etc.) and
    having the car construction as part of your simulation. But in pricniple this is possible.
    More realistic examples are BRIAN parameters, for the BRIAN neuron simulation package.
    A BRIAN value f_contains a number as well as a unit, so in order to store it to disk,
    both need to be separated.

Types of parameters supported so far:

 *  Parameter:
    Container for native python data: int,float,str,bool,complex
    Numpy data and arrays: np.int8-64, np.uint8-64, np.float32-64, np.complex, np.str
        Numpy arrays are allowed as well, however for larger numpy arrays, the ArrayParameter
        is recommended because it will keep a large array only once, even if it is used several
        times during exploration in the exploration array.

 *  ArrayParameter:
    Container for native python data as well as tuples and numpy arrays.
    The array parameter is the method of choice for large numpy arrays or python tuples.
    These are kept only once (and by the hdf5 storage service stored only once to disk)
    and in the exploration array you can find references to these arrays. This is particularly
    usefule if you reuse an array many times in distinct simulation, for example by exploring
    the parameter space in form of a cartesian product.


 *  PickleParameter:
    Container for all the data that can be pickled. Like the array parameter, distinct objects
    are kept only once and are refferred to in the exploration array


There is also the BrianParameter in the pypet.brian.parameter module.



------------------------------------
Results
------------------------------------

So far not many types of results (Base API found in BaseResult) exist
(only the Result and the BrianMonitorResult).
They provide less functionality than parameters. They can simply hold some simulation results.
For example, time course of traffic jam, voltage traces of neurons, etc.
If results are handed to these containers and they are in the right format, they
will in the end automatically be stored to disk.

Types of results supported so far:
 *  Result
    Container for basic data like native python types, numpy arrays and pandas tables (!).

 *  PickleResult
    Container for everything that can be pickled


There is also the BrianMonitorResult in the myper.brian.parameter module.

-----------------------------------
Object Table
-----------------------------------

Finally the ObjectTable class is a wrapper for pandas_ data frames.

.. _pandas: http://pandas.pydata.org/
'''
import logging
import petexceptions as pex
import numpy as np
from pypet.utils.helpful_functions import nested_equal, copydoc
from pypet import globally
from pandas import DataFrame
from pypet.naturalnaming import NNLeafNode

try:
    import cPickle as pickle
except:
    import pickle





class ObjectTable(DataFrame):
    ''' Wrapper class for pandas data frames.
    It creates data frames with dtype=object.

    Data stored into an object table preserves its original type. For instance, a python int
    is not automatically converted to a numpy 64 bit integer (np.int64).

    The object table serves as a standard data structure to hand data to a storage service.
    Given the default HDF5 storage service the types of the stored data are also preserved
    and reconstructed after loading from disk.

    '''
    def __init__(self, data=None, index = None, columns = None, copy=False):
        super(ObjectTable,self).__init__( data = data, index=index,columns=columns,
                                          dtype=object, copy=copy)





class BaseParameter(NNLeafNode):
    '''Abstract class that specifies the methods that need to be implemented for a trajectory
    parameter

    Parameters are simple container objects for data values. They handle single values as well as
    the so called exploration array. An array containing multiple values which are accessed
    one after the other in individual simulation runs.

    Parameter exploration is usually initiated through the trajectory see
    `:func:~pypet.trajectory.Trajectory.explore` and `:func:~pypet.trajectory.Trajectory.expand`.

    To access the parameter's data value one can call the :func:`f_get` method. Granted the parameter
    is explored via the trajectory, in order to
    access values of the exploration array, one first has to call the :func:`f_set_parameter_access`
    method with the index of the run and then use :func:`f_get`.

    Parameters support the concept of locking. Once a value of the parameter has been accessed,
    the parameter cannot be changed anymore unless it is explicitly unlocked using :func:`f_unlock`.
    This prevents parameters from being changed during runtime of a simulation.

    If multiprocessing is desired the parameter must be pickable!

    :param fullname: The fullname of the parameter in the trajectory tree, groupings are
        separated by a colon:
        `fullname = 'supergroup.subgroup.paramname'`

    :param comment: A useful comment describing the parameter:
        `comment = 'The number of cars for traffic jam simulations'`
    ''' 
    def __init__(self, full_name, comment=''):
        super(BaseParameter,self).__init__(full_name,comment, parameter=True)


        self._locked = False
        self._full_copy = False




    @property
    def v_locked(self):
        '''Whether or not the parameter is locked and prevents further modification'''
        return self._locked





    # @property
    # def v_value(self):
    #     '''The current value of the parameter'''
    #     return self.f_get()

    @property
    def v_full_copy(self):
        '''Whether or not the full parameter including the exploration array or only the current
        data is copied during pickling.

        If you run your simulations in multiprocessing mode, the whole trajectory and all
        parameters need to be pickled and are sent to the individual processes.
        Each process than runs an individual point in the parameter space trajectory.
        As a consequence, you do not need the exploration array during these calculations.
        Thus, if the full copy mode is f_set to False the parameter is pickled without
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
        ()
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

    def f_restore_default(self):
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
        `:const:`globally.HDF5_STRCOL_MAX_COMMENT_LENGTH`

        '''
        old_locked = self._locked
        try :
            restr= str(self.f_get())

            if len(restr) >= globally.HDF5_STRCOL_MAX_VALUE_LENGTH:
                restr=restr[0:globally.HDF5_STRCOL_MAX_VALUE_LENGTH-3]+'...'

            return restr
        except Exception, e:
            return 'No Evaluation possible (yet)!'
        finally:
            self._locked = old_locked


    def f_supports(self, data):
        ''' Checks whether the data is supported by the parameter.

        '''
        return type(data) in globally.PARAMETER_SUPPORTED_DATA

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

        # if self.f_is_array():
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

    # def __getitem__(self, idx):
    #     '''  Equivalent to `f_get_idx(idx)`
    #     '''
    #     return self.f_get_idx()
    #
    # def f_get_idx(self,idx):
    #     ''' If the parameter is explored you can directly access the value and index idx.
    #
    #     Raises TypeError if the parameter is not an array.
    #
    #     '''
    #     raise NotImplementedError( "Should have implemented this." )

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

    def f_set_parameter_access(self, idx=0):
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
        >>> param.f_set_parameter_access(idx=1)
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
    :func:`~pypet.parameter.Parameter.f_set_parameter_access`
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
        :func:`~pypet.parameter.Parameter.f_restore_default`.
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

    def f_restore_default(self):
        ''' Restores the default data, that was set with the `:func:`~pypet.parameter.Parameter.f_set`
        method (or at initialisation).

        If the parameter is explored during the runtime of a simulation,
        the actual value of the parameter is changed and taken from the exploration array.
        Calling :func:`~pypet.parameter.Parameter.f_restore_default` sets the parameter's value
        back to it's original value.

        Example usage:

        >>> param = Parameter('supergroup1.subgroup2.', data=44, comment='Im a comment!')
        >>> param._explore([1,2,3,4])
        >>> param.f_set_parameter_access(2)
        >>> print param.f_get()
        >>> 3
        >>> param.f_restore_default()
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
      
    @copydoc(BaseParameter.f_set_parameter_access)
    def f_set_parameter_access(self, idx=0):
        if idx >= len(self) and self.f_is_array():
            raise ValueError('You try to access the %dth parameter in the array of parameters, '
                             'yet there are only %d potential parameters.' % (idx, len(self)))
        else:
            self._data = self._explored_data[idx]

    def f_supports(self, data):
        ''' Checks if input data is supported by the parameter.'''

        if type(data) is tuple:
            for item in data:
                old_type = None
                if not type(item) in globally.PARAMETER_SUPPORTED_DATA:
                    return False
                if not old_type is None and old_type != type(item):
                    return False
                old_type = type(item)
            return True

        if type(data) in [np.ndarray, np.matrix]:
            dtype = data.dtype
            if np.issubdtype(dtype,np.str):
                dtype = np.str
        else:
            dtype=type(data)

        return dtype in globally.PARAMETER_SUPPORTED_DATA


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
            raise TypeError('Unsupported data type: ' +str(type(val)))

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
            raise TypeError('Your parameter is not array, so cannot return array')
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

    '''

    IDENTIFIER = '__rr__'

    def _set_logger(self):
        self._logger = logging.getLogger('pypet.parameter.ArrayParameter=' + self.v_full_name)

    def _store(self):

        if not type(self._data) in [np.ndarray, tuple, np.matrix]:
            return super(ArrayParameter,self)._store()
        else:
            store_dict = {}

            store_dict['data'] = ObjectTable(columns=['data'+ArrayParameter.IDENTIFIER],index=[0])

            store_dict['data']['data'+ArrayParameter.IDENTIFIER] = 'data_array'


            store_dict['data_array'] = self._data

            if self.f_is_array():
                ## Supports smart storage by hashing numpy arrays are hashed by their data attribute
                smart_dict = {}

                store_dict['explored_data']=ObjectTable(columns=['data'+ArrayParameter.IDENTIFIER],index=range(len(self)))

                count = 0
                for idx,elem in enumerate(self._explored_data):

                    try:
                        hash(elem)
                        hash_elem = elem
                    except TypeError:
                        hash_elem = elem.data

                    if hash_elem in smart_dict:
                        name_id = smart_dict[hash_elem]
                        add = False
                    else:
                        name_id = count
                        add = True

                    name = self._build_name(name_id)
                    store_dict['explored_data']['data'+ArrayParameter.IDENTIFIER][idx] = name_id

                    if add:
                        store_dict[name] = elem
                        smart_dict[hash_elem] = name_id
                        count +=1

            return store_dict

    def _build_name(self,name_id):
        return 'ea_%s_%08d' % (ArrayParameter.IDENTIFIER,name_id)




    def _load(self,load_dict):
        data_table = load_dict['data']
        data_name = data_table.columns.tolist()[0]
        if ArrayParameter.IDENTIFIER in data_name:
            arrayname =  data_table['data'+ArrayParameter.IDENTIFIER][0]
            self._data = self._convert_data(load_dict[arrayname])


            if 'explored_data' in load_dict:
                explore_table = load_dict['explored_data']

                name_col = explore_table['data'+ArrayParameter.IDENTIFIER]

                explore_list = []
                for name_id in name_col:
                    arrayname = self._build_name(name_id)
                    explore_list.append(load_dict[arrayname])

                self._explored_data=tuple([self._convert_data(x) for x in explore_list])


        else:
            super(ArrayParameter,self)._load(load_dict)

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
        return 'ed_%s_%08d' % (PickleParameter.IDENTIFIER,name_id)

    def _store(self):
        store_dict={}
        dump = pickle.dumps(self._data)
        store_dict['data']=ObjectTable(data={'data'+PickleParameter.IDENTIFIER : ['data_dump']})

        store_dict['data_dump'] = dump
        if self.f_is_array():

            store_dict['explored_data']=ObjectTable(columns=['data'+PickleParameter.IDENTIFIER],index=range(len(self)))

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
                store_dict['explored_data']['data'+PickleParameter.IDENTIFIER][idx] = name_id

                if add:
                    store_dict[name] = pickle.dumps(val)
                    smart_dict[obj_id] = name_id
                    count +=1

        return store_dict

    def _load(self,load_dict):

        dump_name = load_dict['data']['data'+PickleParameter.IDENTIFIER][0]
        dump = load_dict[dump_name]
        self._data = pickle.loads(dump)

        if 'explored_data' in load_dict:
                explore_table = load_dict['explored_data']

                name_col = explore_table['data'+PickleParameter.IDENTIFIER]

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

    >>> res = Result('supergroup.subgroup.resultname', comment='I am a neat example!' \
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
        >>> print res.f_get('res_0')
        [1000,2000]
        >>> print res.f_get('hitchhiker')
        'ArthurDent'
        >>> print res.f_get('res_0','hitchhiker')
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

                if len(resstr) >= globally.HDF5_STRCOL_MAX_VALUE_LENGTH:
                    resstr = resstr[0:globally.HDF5_STRCOL_MAX_VALUE_LENGTH-3]+'...'
                    return resstr

            resstr=resstr[0:-2]
            return resstr
        else:
            resstr = ', '.join(self._data.keys())

            if len(resstr) >= globally.HDF5_STRCOL_MAX_COMMENT_LENGTH:
                    resstr = resstr[0:globally.HDF5_STRCOL_MAX_COMMENT_LENGTH-3]+'...'

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

        :param args: Arguments listed here ar stored with name 'res%d' where %d is the position in
                     the args tuple.

        :param kwargs: Arguments are stored with the key as name.

        >>> res = Result('supergroup.subgroup.resultname', comment='I am a neat example!')
        >>> res.f_set(333,mystring='String!')
        >>> res.f_get('res0')
        333
        >>> res.f_get('mystring')
        'String!'

        '''
        for idx,arg in enumerate(args):
            valstr = 'res_'+str(idx)
            self.f_set_single(valstr,arg)

        for key, arg in kwargs.items():
            self.f_set_single(key,arg)




    def f_get(self,*args):
        ''' Returns items handled by the result.

         If only a single name is given a single data item returned, if several names are
         given, a list is returned. For integer inputs the results returns 'res%d'.

        :param args: strings-names or integers

        :return: Single data item or tuple of data

        Example:

        >>> res = Result('supergroup.subgroup.resultname', comment='I am a neat example!' \
        [1000,2000], {'a':'b','c':'d'}, hitchhiker='Arthur Dent')
        >>> res.f_get('hitchhiker')
        'Arthur Dent'
        >>> res.f_get(0)
        [1000,2000]
        >>> res.f_get('hitchhiker', 'res0')
        ('Arthur Dent', [1000,2000])

        '''

        result_list = []
        for name in args:
            try:
                name = 'res_%d' % name
            except TypeError:
                pass

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

        if type(item) in ((np.ndarray,ObjectTable,DataFrame,dict,tuple,list,np.matrix)+
                             globally.PARAMETER_SUPPORTED_DATA):
            if (not type(item) in globally.PARAMETER_SUPPORTED_DATA) and len(item) == 0:
                self._logger.warning('The Item >>%s<< is _empty.' % name)

            self._data[name] = item
        else:
            raise AttributeError('Your result >>%s<< of type >>%s<< is not supported.' %
                                 (name,str(type(item))))



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



class PickleResult(Result):
    ''' Result that digest everything and simply pickles it!

    Note that it is not checked whether data can be pickled, so take care that it works!
    '''


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
            store_dict[key] = pickle.dumps(val)
        return store_dict


    def _load(self, load_dict):
        for key, val in load_dict.items():
            self._data[key] = pickle.loads(val)