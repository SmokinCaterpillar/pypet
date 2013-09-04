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
For example, this could bethe numbers or cars for traffic jam simulations, or for
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
    A BRIAN value contains a number as well as a unit, so in order to store it to disk,
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


There is also the BrianParameter in the mypet.brian.parameter module.



------------------------------------
Results
------------------------------------

So far not many types of results (Base API found in BaseResult) exist
(only the SimpleResult and the BrianMonitorResult).
They provide less functionality than parameters. They can simply hold some simulation results.
For example, time course of traffic jam, voltage traces of neurons, etc.
If results are handed to these containers and they are in the right format, they
will in the end automatically be stored to disk.

Types of results supported so far:
 *  SimpleResult
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
from mypet.utils.helpful_functions import nested_equal
from mypet import globally
from pandas import DataFrame



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




class BaseParameter(object):
    '''Abstract class that specifies the methods that need to be implemented for a trajectory
    parameter

    The parameter class can hold a single value as well as an exploration array with several
    values (of the same type) for exploration. If the parameter is an array due to exploration,
    the original value is still kept as a default value.
    
    Parameters can be locked to forbid further modification.
    If multiprocessing is desired the parameter must be pickable!

    :param fullname: The fullname of the parameter in the trajectory tree, groupings are
        separated by a colon:
        fullname = supergroup.subgroup.paramname

    :param comment: A useful comment describing the parameter:
        comment = 'The number of cars for traffic jam simulations'
    ''' 
    def __init__(self, fullname, comment=''):
        self._fullname = fullname
        split_name = fullname.split('.')
        self._name=split_name.pop()
        self._location='.'.join(split_name)
        self.set_comment(comment)

        self._locked = False

    def _rename(self, fullname):
        ''' Renames the parameter.
        '''
        self._fullname = fullname
        split_name = fullname.split('.')
        self._name=split_name.pop()
        self._location='.'.join(split_name)

    def set_comment(self, comment):
        ''' Sets the comment of the parameter.

        Checks if length of the comment is in accordance with the maximum length defined
        in the globally module. If not, the comment is truncated.
        '''
        assert isinstance(comment,str)
        if len(comment)>=globally.HDF5_STRCOL_MAX_COMMENT_LENGTH:
            self._logger.warning('Your comment is to long, maximum number of character is %d, you have %d. I will truncate it.'
                             % (globally.HDF5_STRCOL_MAX_COMMENT_LENGTH, len(comment)))
            self._comment = comment[0:globally.HDF5_STRCOL_MAX_COMMENT_LENGTH]

        self._comment=comment

    def get_comment(self):
        ''' Returns the comment.

        Example usage:
        >>> param = Parameter('supergroup.subgroup.paramname',data=42, comment='I am a neat example')
        >>> print param.get_comment()
        >>> 'I am a neat example'
        '''
        return self._comment

    def is_array(self):
        ''' Returns true if the parameter is explored and contains an exploration array.
        '''
        raise NotImplementedError( "Should have implemented this." )

    def restore_default(self):
        ''' If a Parameter is explored, the actual data is changed over the course of different
        simulations, This method restores the original data assigned before exploration.
        '''
        raise NotImplementedError( "Should have implemented this." )


    def is_locked(self):
        ''' Returns whether the parameter is locked or not.
        '''
        return self._locked

    def get_location(self):
        ''' Returns the location of the parameter within the trajectory tree.

        Example usage:
        >>> param = Parameter('supergroup.subgroup.paramname',data=42, comment='I am a neat example')
        >>> print param.get_location()
        >>> 'supergroup.subgroup'

        '''
        return self._location
     
    def __len__(self):
        ''' Returns the length of the parameter.
        
        Only parameters that are explored can have a length larger than 1.
        If no values have been added to the parameter it's length is 0.
        '''
        raise NotImplementedError( "Should have implemented this." )

    
    def _store(self):
        ''' Method called by the storage service for serialization.

        The method converts the parameter's value and exploration array into a simple
        data structures that can be stored to disk.
        Returns a dictionary containing these simple structures.
        Understood structures are
        * python natives (int,str,bool,float,complex),
        * python lists and tuples
        * numpy natives and arrays of type np.int8-64, np.uint8-64, np.float32-64,
                                            np.complex, np.str
        * python dictionaries of the previous types (flat not nested!)
        * pandas data frames
        * object tables

        :return: A dictionary containing basic data structures.
        '''
        raise NotImplementedError( "Should have implemented this." )

    def _load(self, load_dict):
        ''' Method called by the storage service to reconstruct the original parameter.

        Data contained in the load_dict is equal to the data provided by the parameter
        when previously called with _store()

        :param load_dict: The dictionary containing basic data structures
        '''
        raise NotImplementedError( "Should have implemented this." )


    def val2str(self):
        ''' String representation of the value handled by the parameter. Note that representing
        the parameter as a string accesses its value, but for simpler debugging, this does not
        lock the parameter or counts as usage!
        '''
        old_locked = self._locked
        try :
            return str(self.get())
        except Exception, e:
            return 'No Evaluation possible (yet)!'
        finally:
            self._locked = old_locked


    def supports(self, data):
        ''' Checks whether the data is supported by the parameter.
        '''
        return type(data) in globally.PARAMETER_SUPPORTED_DATA

    def _equal_values(self,val1,val2):
        ''' Checks if the parameter considers two values as equal.

        If both values are not supported by the parameter, a TypeError is thrown.
        :raises: TypeError
        :return: True or False
        '''
        if self.supports(val1) != self.supports(val2):
            return False

        if not self.supports(val1) and not self.supports(val2):
                raise TypeError('I do not support the types of both inputs (>>%s<< and >>%s<<),'
                                ' therefore I cannot judge whether the two are equal.' %
                                str(type(val1)),str(type(val2)))

        if not self._values_of_same_type(val1,val2):
            return False

        return nested_equal(val1,val2)

    def _values_of_same_type(self,val1,val2):
        ''' Checks if two values agree in type.

        For example two 32 bit integers would be of same type, but not a string and an integer.

        Throws a type error if both values are not supported by the parameter.

        :raises: TypeError

        :return: True or False
        '''

        if self.supports(val1) != self.supports(val2):
            return False

        if not self.supports(val1) and not self.supports(val2):
                raise TypeError('I do not support the types of both inputs (>>%s<< and >>%s<<),'
                                ' therefore I cannot judge whether the two are of same type.' %
                                str(type(val1)),str(type(val2)))

        return type(val1) == type(val2)



    def __str__(self):
        if self.get_comment():

            returnstr = '%s (Length:%d, Comment:%s): %s   ' % (self._fullname, len(self), self.get_comment(), self.val2str())
        else:
            returnstr = '%s (Length:%d): %s   ' % (self._fullname, len(self), self.val2str())

        # if self.is_array():
        #     returnstr += ', Array: %s' %str(self.get_array())

        return returnstr


    def unlock(self):
        ''' Unlocks the locked parameter.'''
        self._locked = False

    def lock(self):
        ''' Locks the parameter and forbids further manipulation.

        Changing the data value or exploration of the parameter are no longer allowed.

        '''
        self._locked = True


    def gfn(self):
        ''' Short for get_fullname '''
        return self.get_fullname()
    
    def get_fullname(self):
        ''' param.get_fullname() -> Returns the fullname of the parameter

        Example usage:
        >>> param = Parameter('supergroup.subgroup.paramname',data=42, comment='I am a neat example')
        >>> print param.get_fullname()
        >>> 'supergroup.subgroup.paramname'

        '''
        return self._fullname



    def set(self,data):
        ''' Sets specific values for a parameter.
        Has to raise ParameterLockedException if parameter is locked.
        And has to raise an Attribute Error if the parameter is an array or if the type of the
        data value is not supported by the parameter.

        Example usage:
        >>> param = Parameter('groupA.groupB.myparam', comment='I am a neat example')
        >>> param.set(44.0)
        >>> print parm.get()
        >>> 44.0

        :raises: ParameterLockedException, AttributeError.
        '''
        raise NotImplementedError( "Should have implemented this." )


    def get(self,name):
        ''' Returns the current data value of the parameter and locks the parameter.

        Example usage:
        >>> param = Parameter('groupA.groupB.myparam', comment='I am a neat example')
        >>> param.set(44.0)
        >>> print parm.get()
        >>> 44.0:

        '''
        raise NotImplementedError( "Should have implemented this." )

    def get_array(self):
        ''' Returns an iterable to iterate over the values of the exploration array.

        Note that the returned values should be either a copy of the exploration array
        or the array must be immutable, for example a python tuple.
        :return: immutable iterable

        Example usage:
        >>> param = Parameter('groupA.groupB.myparam',data=22, comment='I am a neat example')
        >>> param.explore([42,43,43])
        >>> print param.get_array()
        >>> (42,43,44)
        '''
        raise NotImplementedError( "Should have implemented this." )
    
    def explore(self, iterable):
        ''' The default method to create and explored parameter containing an array of entries.

        Raises ParameterLockedExcpetion if the parameter is locked.
        Raises TypeError if the parameter is already an array.


        :param iterable: An iterable specifying the exploration array
        For example:
        >>> param = Parameter('groupA.groupB.myparam',data=22.33, comment='I am a neat example')
        >>> param.explore([3.0,2.0,1.0])

        :raises: ParameterLockedExcpetion, TypeError
        '''
        raise NotImplementedError( "Should have implemented this." )

    def expand(self, iterable):
        ''' Similar to :func:`explore` but appends to the exploration array.

        Raises ParameterLockedExcpetion if the parameter is locked.
        Raises TypeError if the parameter is not an array.

        :param iterable: An iterable specifying the exploration array.
        Example usage:
        >>> param = Parameter('groupA.groupB.myparam',data=3.13, comment='I am a neat example')
        >>> param.explore([3.0,2.0,1.0])
        >>> param.expand([42.0,43.0])
        >>> print param.get_array()
        >>> (3.0,2.0,1.0,42.0,43.0)

        :raises: ParameterLockedExcpetion, TypeError
        '''
        raise NotImplementedError("Should have implemented this.")

    def set_parameter_access(self, idx=0):
        ''' Sets the current value according to the `idx` item in the exploration array

        Prepares the parameter for further usage, and tells it which point in the parameter
        space should be accessed by calls to :func:`get`.

        :param idx: The index within the exploration parameter

        If the parameter is not an array, the single data value is considered regardles of the
        value of idx.
        Raises ValueError if the parameter is explored and idx>=len(param)

        :raises: ValueError

        Example usage:
        >>> param = Parameter('groupA.groupB.myparam',data=22.33, comment='I am a neat example')
        >>> param.explore([42.0,43.0,44.0])
        >>> param.set_parameter_access(idx=1)
        >>> print param.get()
        >>> 43.0

        '''
        raise NotImplementedError( "Should have implemented this." )
        
    def get_classname(self):
        ''' Returns the name of the class i.e.
        `return self.__class__.__name__`
        '''
        return self.__class__.__name__

    def get_name(self):
        ''' Returns the name of the parameter.

        Example usage:
        >>> param = Parameter('supergroup.subgroup.paramname',data=42, comment='I am a neat example')
        >>> print param.get_name()
        >>> 'paramname'
        '''
        return self._name

    def is_empty(self):
        ''' True if no data has been assinged to the parameter.

        >>> param = Parameter('myname.is.example', comment='I am empty!')
        >>> param.is_empty()
        >>> True
        >>> param.set(444)
        >>> param.is_empty()
        >>> False
        '''
        return len(self) == 0

    def shrink(self):
        ''' If a parameter is explored, i.e. it is an array, the whole exploration is deleted,
        and the parameter is no longer an array.
        Raises ParameterLockedException if the parameter is locked.
        Raises TypeError is the parameter is not an array.

        Note that this function does not erase data from disk. So if the parameter has
        been stored with a service to disk and is shrunk, it can be restored by loading from
        disk.

        :raises: ParameterLockedException, TypeError
        '''
        raise NotImplementedError( "Should have implemented this." )


    def empty(self):
        '''Erases all data in the parameter. If the parameter was an explored array it is
        also shrunk (see :func:`shrink`).
        Raises ParameterLockedException if the parameter is locked.

        Does not erase data from disk. So if the parameter has
        been stored with a service to disk and is emptied, it can be restored by loading from
        disk.

        :raises: ParameterLockedException
        '''
        raise NotImplementedError( "Should have implemented this." )
      
class Parameter(BaseParameter):
    ''' The standard parameter that handles access to simulation parameters.
    
    Supported Data types are
    * python natives (int,str,bool,float,complex),
    * numpy natives and non nested arrays of type np.int8-64, np.uint8-64, np.float32-64,
                            np.complex, np.str
    * python homogeneous not nested lists and tuples, lists are automatically converted to tuples
    
    Note that for larger numpy arrays it is recommended to use the ArrayParameter.

    For parameter exploration, see :func:`explore` and :func`expand`

     Example usage:
     >>> param = Parameter('traffic.mobiles.ncars',data=42, comment='I am a neat example')

    :param fullname: The fullname of the parameter. Grouping can be achieved by using colons.

    :param data: A data value that is handled by the parameter. It is checked whether the parameter
        supports the data. If not an AttributeError is thrown. If the parameter becomes
        explored (see :py:func:`.explore`), the data value is kept as a default. After
        simulation the default value can be retained by calling :func:`restore_default`.
        The data can be accessed as follows:
        >>> param.get()
        >>> 42

        To change the data after parameter creation one can call :func:`set`:
        >>> param.set(43)
        >>> param.get()
        >>> 43

    :param comment: A useful comment describing the parameter.
        The comment can be changed later on using :func:`set_comment' and retrieved using
        :func:`get_comment'
        >>> param.get_comment()
        >>> 'I am a neat example'

    :raises: AttributeError
    '''
    def __init__(self, fullname, data=None, comment=''):
        super(Parameter,self).__init__(fullname,comment)
        self._data= None
        self._default = None #The default value, which is the same as Data,
        # but it is necessary to keep a reference to it to restore the original value
        # after exploration
        self._explored_data=tuple()#The Explored Data
        self._set_logger()

        if not data == None:
            self.set(data)
        self._fullcopy = False

    def _set_logger(self):
        self._logger = logging.getLogger('mypet.parameter.Parameter=' + self._fullname)

    def restore_default(self):
        ''' Restores the default data, that was set with the `set` method (or at initialisation).

        If the parameter is explored during the runtime of a simulation,
        the actual value of the parameter is changed and taken from the exploration array.
        (See also :func:`explore`). Calling :func:`restore_default' sets the parameter's value
        back to it's original value.

        Example usage:
        >>> param = Parameter('supergroup1.subgroup2.')
        '''
        self._data = self._default

    def __len__(self):
        if self._data is None:
            return 0
        elif len(self._explored_data)>0:
            return len(self._explored_data)
        else:
            return 1

    def is_array(self):
        return len(self._explored_data)>0
       
    def __getstate__(self):
        ''' Returns the actual state of the parameter for pickling. 
        '''
        result = self.__dict__.copy()


        # If we don't need a full copy of the Parameter (because a single process needs
        # only access to a single point in the parameter space we can delete the rest
        if not self._fullcopy :
            result['_explored_data'] = tuple()

        del result['_logger'] #pickling does not work with loggers
        return result




    def __setstate__(self, statedict):
        ''' Sets the state for unpickling.
        '''
        self.__dict__.update( statedict)
        self._set_logger()
      
        
    def set_parameter_access(self, idx=0):
        if idx >= len(self) and self.is_array():
            raise ValueError('You try to access the %dth parameter in the array of parameters, yet there are only %d potential parameters.' %(idx,len(self)))
        else:
            self._data = self._explored_data[idx]

    def supports(self, data):
        ''' Checks if input data is supported by the parameter.'''

        if isinstance(data, tuple):
            for item in data:
                old_type = None
                if not type(item) in globally.PARAMETER_SUPPORTED_DATA:
                    return False
                if not old_type is None and old_type != type(item):
                    return False
                old_type = type(item)
            return True

        if isinstance(data, np.ndarray):
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
        >>>True

        >>>param._values_of_same_type(42,'43')
        >>>False

        :raises: TypeError

        :return: True or False
        '''
        if self.supports(val1) != self.supports(val2):
            return False

        if not self.supports(val1) and not self.supports(val2):
                raise TypeError('I do not support the types of both inputs (>>%s<< and >>%s<<),'
                                ' therefore I cannot judge whether the two are of same type.' %
                                str(type(val1)),str(type(val2)))
        
        if not type(val1) == type(val2):
            return False
        
        if type(val1) == np.array:
            if not val1.dtype == val2.dtype:
                return False
            
            if not np.shape(val1)==np.shape(val2):
                return False
        
        return True




    
    def set(self,data):
        ''' Adds data value to the Parameter.

        The data becomes the parameters default value, which is restored by calling
        :func:'restore_default'

        Raises ParameterLockedException if the parameter is locked and AttributeError
        if the parameter is an array (and not locked) or the type of the data is not supported.

        :param data: the data value handled by the parameter.

        :raises: ParameterLockedException, AttributeError

        Example usage:
        >>> param.set('Hello World!')
        >>> param.get()
        >>> 'Hello World!'
        '''

        if self.is_locked():
            raise pex.ParameterLockedException('Parameter >>' + self._name + '<< is locked!')


        if self.is_array():
            raise AttributeError('Your Parameter is an explored array can no longer change values!')


        val = self._convert_data(data)

        if not self.supports(val):
            raise AttributeError('Unsupported data type: ' +str(type(val)))

        self._data= val
        self._default = self._data




    def _convert_data(self, val):
        ''' Converts data to be handled by the parameter

        * sets numpy arrays immutable.
        * converts lists to tuples

        :param val: the data value to convert
        :return: the converted data
        '''
        if isinstance(val,(list)):
            val = tuple(val)

        if isinstance(val, np.ndarray):
            val.flags.writeable = False
            return val

        return val


        
    def get_array(self):
        if not self.is_array():
            raise TypeError('Your parameter is not array, so cannot return array')
        else:
            return self._explored_data


    def explore(self, explore_iterable):
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
        >>> param.explore([3.0,2.0,1.0])
        >>> param.get_array()
        >>> (3.0,2.0,1.0)

        :raises TypeError,ParameterLockedExcpetion
        '''
        if self.is_locked():
            raise pex.ParameterLockedException('Parameter >>%s<< is locked!' % self._fullname)

        if self.is_array():
            raise TypeError('Your Parameter %s is already explored, cannot explore it further!' % self._name)


        data_tuple = self._data_sanity_checks(explore_iterable)



        self._explored_data = data_tuple
        self.lock()

    def expand(self,explore_iterable):
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
        >>> param.explore([3.0,2.0,1.0])
        >>> param.get_array()
        >>> (3.0,2.0,1.0)

        :raises TypeError,ParameterLockedExcpetion
        '''
        if self.is_locked():
            raise pex.ParameterLockedException('Parameter >>%s<< is locked!' % self._fullname)

        if not self.is_array():
            raise TypeError('Your Parameter is not an array and can therefore not be expanded.' % self._name)


        data_tuple = self._data_sanity_checks(explore_iterable)



        self._explored_data = self._explored_data + data_tuple
        self.lock()


    def _data_sanity_checks(self, explore_iterable):
        ''' Checks if data values are legal.

        Checks if the data values are supported by the parameter and if the values are of the same
        type as the default value.
        '''
        data_tuple = []

        default_val = self._data

        for val in explore_iterable:
            newval = self._convert_data(val)


            if not self.supports(newval):
                raise TypeError('%s is of not supported type %s.' % (repr(val),str(type(newval))))

            if not self._values_of_same_type(newval,default_val):
                raise TypeError('Data is not of the same type as the original entry value, new type is %s vs old type %s.' % ( str(type(newval)),str(type(default_val))))


            data_tuple.append(newval)


        if len(data_tuple) == 0:
            raise ValueError('Cannot explore an empty list!')

        return tuple(data_tuple)


    def _store(self):
        store_dict={}
        store_dict['data'] = ObjectTable(data={'data':[self._data]})
        if self.is_array():
            store_dict['explored_data'] = ObjectTable(data={'data':self._explored_data})


        return store_dict


    def _load(self,load_dict):
        self._data = load_dict['data']['data'][0]
        self._default=self._data
        if 'explored_data' in load_dict:
            self._explored_data = tuple(load_dict['explored_data']['data'].tolist())


    def set_full_copy(self, val):
        ''' Sets the full copy mode.

        If you run your simulations in multiprocessing mode, the whole trajectory and all
        parameters need to be pickled and are sent to the individual processes.
        Each process than runs an individual point in the parameter space trajectory.
        As a consequence, you do not need the exploration array during these calculations.
        Thus, if the full copy mode is set to False the parameter is pickled without
         the exploration array and you can save memory.

        If you want to access the full exploration array during individual runs, you need to set
        fullcopy to True (:func:`set_full_copy(True)).

        It is recommended NOT to do that in order to save memory and also do obey the
        philosophy that individual simulations are independent.

        :param val: True or False

        Example usage:
        >>> import pickle
        >>> param = Parameter('examples.fullcopy', data=333, comment='I show you how the copy mode works!')
        >>> param.explore([1,2,3,4])
        >>> dump=pickle.dumps(param)
        >>> newparam = pickle.loads(dump)
        >>> print newparam.get_array()
        >>> ()

        >>> param.set_full_copy(True)
        >>> dump = pickle.dumps(param)
        >>> newparam=pickle.loads(dump)
        >>> print newparam.get_array()
        >>> (1,2,3,4)
        '''
        assert isinstance(val, bool)
        self._fullcopy = val


    def get(self):
        self.lock() # As soon as someone accesses an entry the parameter gets locked
        return self._data


    def shrink(self):
        if self.is_empty():
            raise TypeError('Cannot shrink empty Parameter.')

        if self.is_locked():
            raise pex.ParameterLockedException('Parameter %s is locked!' % self._fullname)

        self._explored_data={}


    def empty(self):
        if self.is_locked():
            raise pex.ParameterLockedException('Parameter %s is locked!' % self._fullname)

        self.shrink()
        self._data=None

     

class ArrayParameter(Parameter):

    ''' Similar to the :class:`Parameter`, but recommended for large numpy arrays and python tuples.

    The array parameter is a bit smarter in memory management than the parameter.
    If a numpy array is used several times within an exploration, only one numpy array is stored by
    the default HDF5 storage service. For each individual run references to the corresponding
    numpy array are stored.
    '''

    IDENTIFIER = '__rr__'

    def _set_logger(self):
        self._logger = logging.getLogger('mypet.parameter.ArrayParameter=' + self._fullname)

    def _store(self):

        if not isinstance(self._data,(np.ndarray,tuple)):
            return super(ArrayParameter,self)._store()
        else:
            store_dict = {}

            store_dict['data'] = ObjectTable(columns=['data'+ArrayParameter.IDENTIFIER],index=[0])

            store_dict['data']['data'+ArrayParameter.IDENTIFIER] = 'data_array'


            store_dict['data_array'] = self._data

            if self.is_array():
                ## Supports smart storage by hashing numpy arrays are hashed by their data attribute
                smart_dict = {}

                store_dict['explored_data']=ObjectTable(columns=['data'+ArrayParameter.IDENTIFIER],index=range(len(self)))

                count = 0
                for idx,elem in enumerate(self._explored_data):

                    if isinstance(elem, np.ndarray):
                        hash_elem = elem.data
                    else:
                        hash_elem = elem

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



    def _convert_data(self, val):
         ''' Converts data to be used with the array parameter.

         Python lists are converted to python tuples.
         '''
         if isinstance(val, list):
             return tuple(val)
         elif isinstance(val, tuple):
             return val
         else:
             return super(ArrayParameter,self)._convert_data(val)

    def _load(self,load_dict):
        data_table = load_dict['data']
        data_name = data_table.columns.tolist()[0]
        if ArrayParameter.IDENTIFIER in data_name:
            arrayname =  data_table['data'+ArrayParameter.IDENTIFIER][0]
            self._data = load_dict[arrayname]


            if 'explored_data' in load_dict:
                explore_table = load_dict['explored_data']

                name_col = explore_table['data'+ArrayParameter.IDENTIFIER]

                explore_list = []
                for name_id in name_col:
                    arrayname = self._build_name(name_id)
                    explore_list.append(load_dict[arrayname])

                self._explored_data=tuple(explore_list)


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
        self._logger = logging.getLogger('mypet.parameter.PickleParameter=' + self._fullname)

    def supports(self, data):
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
        if self.is_array():

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





      

            
                            

class BaseResult(object):
    ''' The basic api to store results.

    Compared to parameters (see :class: BaseParameter) results are also initialised with a fullname
    and a comment.
    As before grouping is achieved by colons in the name.

    Example usage:
    >>> result = SimpleResult(fullname='very.important.result',comment='I am important but empty :('
    '''
    def __init__(self, fullname, comment=''):
        self._fullname = fullname
        split_name = fullname.split('.')
        self._name=split_name.pop()
        self.set_comment(comment)
        self._location='.'.join(split_name)



    def set_comment(self, comment):
        ''' Sets the comment of the result.

        Checks if length of the comment is in accordance with the maximum length defined
        in the globally module. If not, the comment is truncated.
        '''
        assert isinstance(comment,str)
        if len(comment)>=globally.HDF5_STRCOL_MAX_COMMENT_LENGTH:
            self._logger.warning('Your comment is to long, maximum number of character is %d, you have %d. I will truncate it.'
                             % (globally.HDF5_STRCOL_MAX_COMMENT_LENGTH, len(comment)))
            self._comment = comment[0:globally.HDF5_STRCOL_MAX_COMMENT_LENGTH]
        self._comment=comment

    def get_comment(self):
        ''' Returns the comment of the result.
        '''
        return self._comment


    def _rename(self, fullname):
        ''' Renames the result.
        '''
        self._fullname = fullname
        split_name = fullname.split('.')
        self._name=split_name.pop()
        self._location='.'.join(split_name)

    def get_name(self):
        ''' Returns the name of the result.

        Example usage:
        >>> res = SimpleResult('examples.about.results.result1', comment = 'I am a neat example!')
        >>> print res.get_name()
        >>> 'result1'
        '''
        return self._name
    
    def get_fullname(self):
        ''' Returns the fullname of the result.

        Example usage:
        >>> res = SimpleResult('examples.about.results.result1', comment = 'I am a neat example!')
        >>> print res.get_fullname()
        >>> 'examples.about.results.result1'
        '''
        return self._fullname

    def get_location(self):
        ''' Returns the location of the result.

        Example usage:
        >>> res = SimpleResult('examples.about.results.result1', comment = 'I am a neat example!')
        >>> print res.get_fullname()
        >>> 'examples.about.results'
        '''
        return self._location
    
    def gfn(self):
        ''' Short for :func:`get_fullname'
        '''
        return self.get_fullname()
    
    def get_classname(self):
        ''' Returns the classname of the result,
        equivalent to `return self.__class__.__name__`
        '''
        return self.__class__.__name__

    def _store(self):
        ''' Method called by the storage service for serialization.

        The method converts the result's value into  simple
        data structures that can be stored to disk.
        Returns a dictionary containing these simple structures.
        Understood basic strucutres are
        * python natives (int,str,bool,float,complex),
        * python lists and tuples
        * numpy natives and arrays of type np.int8-64, np.uint8-64, np.float32-64,
                                            np.complex, np.str
        * python dictionaries of the previous types (flat not nested!)
        * pandas data frames
        * object tables

        :return: A dictionary containing basic data structures.
        '''
        raise NotImplementedError('Implement this!')

    def _load(self, load_dict):
        ''' Method called by the storage service to reconstruct the original result.

        Data contained in the load_dict is equal to the data provided by the result
        when previously called with _store()

        :param load_dict: The dictionary containing basic data structures
        '''
        raise  NotImplementedError('Implement this!')


    def is_empty(self):
        ''' Returns true if no data is stored into the result.
        :return:
        '''
        raise NotImplementedError('You should implement this!')

    def empty(self):
        ''' Erases all data in the result and afterwards >>is_empty()<< should evaluate True
        '''
        raise NotImplementedError('You should implement this!')




class SimpleResult(BaseResult):
    ''' Light Container that stores tables and arrays.
    Note that no sanity checks on individual data is made
    and you have to take care, that your data is understood by the storage service.
    It is assumed that results tend to be large and therefore sanity checks would be too expensive.

    Data that can safely be stored into a SimpleResult are:
        * python natives (int,str,bool,float,complex),
        * numpy natives and arrays of type np.int8-64, np.uint8-64, np.float32-64,
                                            np.complex, np.str
        * python dictionaries of the previous types (python natives + numpy natives and arrays
                                                        flat not nested!)
        * python lists and tuples of the previous types (python natives + numpy natives and arrays)
        * pandas data frames
        * object tables

    Such values are either set on initialisation of with :func:'set'

    Example usage:
    >>> res = SimpleResult('supergroup.subgroup.resultname', comment='I am a neat example!' \
        [1000,2000], {'a':'b','c':'d'}, hitchhiker='Arthur Dent')

    :param fullanme: The fullname of the result, grouping can be achieved are separated by colons,


    :param comment: A useful comment describing the parameter.
        The comment can later on be changed using :func:`set_comment' and retrieved using
        :func:`get_comment'
        >>> param.get_comment()
        >>> 'I am a neat example!'

    :param args: data that is handled by the result, it is kept by the result under the names
        `run%d` with `%d` being the position in the argument list.
        Can be changed or more can be added via :func:'set'

    :param kwargs: data that is handled by the result, it is kept by the result under the names
        specified by the keys of kwargs.
        Can be changed or more can be added via :func:'set'
        >>> print res.get(0)
        >>> [1000,2000]

        >>> print res.get(1)
        >>> {'a':'b','c':'d'}

        >>> print res.get('res0')
        >>> [1000,2000]

        >>> print res.get('hitchhiker')
        >>> 'ArthurDent'

        >>> print res.get('res0','hitchhiker')
        >>> ([1000,2000], 'ArthurDent')

    Raises an AttributeError if the data in args or kwargs is not supported (but only checks type of
    outer data structure, like dicts, list, but not individual values in dicts or lists.

    :raises: AttributeError

    Alternatively one can also use :func:'set'
    >>> result.set('Uno',x='y')
    >>> print result.get(0)
    >>> 'Uno'
    >>> print result.get('x')


    Alternative method to put and retrieve data from the result container is via `__getattr__` and
    `__setattr__'

    >>> res.ford = 'prefect'
    >>> res.ford
    >>> 'prefect'

    '''
    def __init__(self, fullname, *args, **kwargs):
        comment = kwargs.pop('comment','')
        super(SimpleResult,self).__init__(fullname,comment)
        self._data = {}
        self._set_logger()
        self.set(*args,**kwargs)


    def __contains__(self, item):
        return item in self._data



    def __str__(self):
        if self.get_comment():
            return '%s (Comment:%s): %s' % (self.get_fullname(),self.get_comment(),str(self._data.keys()))
        else:
            return '%s: %s' % (self.get_fullname(),str(self._data.keys()))



    def _set_logger(self):
        self._logger = logging.getLogger('mypet.parameter.SimpleResult=' + self._fullname)


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

    def to_dict(self):
        ''' Returns all handled data as a dictionary (shallow copy)
        :return: Shallow copy of the data dictionary
        '''
        return self._data.copy()


    def is_empty(self):
        ''' Ture if no data has been put into the result.
        Also True if all data has been erased via :func:'empty'
        '''
        return len(self._data)== 0

    def empty(self):
        ''' Removes all data from the result.
        '''
        self._data={}

    def get_comment(self):
        return self._comment

    def set(self,*args, **kwargs):
        ''' Method to put data into the result.

        :param args:
        :param kwargs:
        :return:
        '''
        for idx,arg in enumerate(args):
            valstr = 'res'+str(idx)
            self.set_single(valstr,arg)

        for key, arg in kwargs.items():
            self.set_single(key,arg)


    def get(self,*args):

        result_list = []
        for name in args:
            if isinstance(name,int):
                name = 'res%d' % name

            result_list.append(self._data[name])

        if len(args)>1:
            return result_list[0]
        else:
            return tuple(result_list)

    def set_single(self, name, item):
        ''' Sets a single data item to the result.

        Raises AttributeError if the type of the data is not understood.
        Note that the type check is shallow. For example, if the data item is a list,
        the individual list elements are NOT checked whether their types are appropriate.

        :param name: The name of the data item
        :param item: The data item

        :raises: AttributeError

        Example usage:
        >>> res.set_single('answer', 42)
        >>> res.get('answer')
        >>> 42
        '''
        if name in ['comment', 'Comment']:
            assert isinstance(item,str)
            self._comment = item

        if isinstance(item, (np.ndarray,ObjectTable,DataFrame,dict,tuple,list,
                             globally.PARAMETER_SUPPORTED_DATA)):
            if not isinstance(item,globally.PARAMETER_SUPPORTED_DATA) and len(item) == 0:
                self._logger.warning('The Item >>%s<< is empty.' % name)

            self._data[name] = item
        else:
            raise AttributeError('Your result >>%s<< of type >>%s<< is not supported.' % (name,str(type(item))))




    def _store(self):
        store_dict ={}
        store_dict.update(self._data)
        return store_dict




    def _load(self, load_dict):
        self._data = load_dict



    def __delattr__(self, item):
        ''' Deletes an item from the result.
        :param item: The item to delete

        Example usage:
        >>> res = SimpleResult('Iam.an.example', comment = 'And a neat one, indeed!', fortytwo=42)
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
            raise AttributeError('Your result >>%s<< does not contain %s.' % (self.get_name(),item))

    def __setattr__(self, key, value):
        if key[0]=='_':
            self.__dict__[key] = value
        else:
            self.set_single(key, value)

    def __getattr__(self, name):

        if (not '_data' in self.__dict__ or
            not '_fullname' in self.__dict__):

            raise AttributeError('This is to avoid pickling issues!')

        if name in ['Comment', 'comment']:
            return self._comment

        if not name in self._data:
            raise  AttributeError('>>%s<< is not part of your result >>%s<<.' % (name,self._fullname))

        return self._data[name]



class PickleResult(SimpleResult):
    ''' Result that eats everything and simply pickles it!
    '''

    def set_single(self, name, item):
        self._data[name] = item


    def _set_logger(self):
        self._logger = logging.getLogger('mypet.parameter.PickleResult=' + self._fullname)



    def _store(self):
        store_dict ={}
        for key, val in self._data.items():
            store_dict[key] = pickle.dumps(val)
        return store_dict


    def _load(self, load_dict):
        for key, val in load_dict.items():
            self._data[key] = pickle.loads(val)