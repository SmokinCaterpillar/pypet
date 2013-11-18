"""This module contains implementations of result and parameter containers.

Results and parameters are the leaf nodes of the :class:`~pypet.trajectory.Trajectory` tree.
Instances of results can only be found under the subtree `traj.results`, whereas
parameters are used to handle data kept under `traj.config`, `traj.parameters`, and
`traj.derived_parameters`.

Result objects can handle more than one data item and heterogeneous data.
On the contrary, parameters only handle single data items. However, they can contain
ranges - arrays of homogeneous data items - to allow parameter exploration.

The module contains the following parameters:

    * :class:`~pypet.parameter.BaseParameter`

        Abstract base class to define the parameter interface

    * :class:`~pypet.parameter.Parameter`

        Standard parameter that handles a variety of different data types.

    * :class:`~pypet.parameter.ArrayParameter`

        Parameter class for larger numpy arrays and python tuples

    * :class:`~pypet.parameter.SparseParameter`

        Parameter for Scipy sparse matrices

    * :class:`~pypet.parameter.PickleParameter`

        Parameter that can handle all objects that can be pickled


The module contains the following results:

    * :class:`~pypet.parameter.BaseResult`

        Abstract base class to define the result interface

    * :class:`~pypet.parameter.Result`

        Standard result that handles a variety of different data types

    * :class:`~pypet.parameter.SparseResult`

        Result that can handle Scipy sparse matrices

    * :class:`~pypet.parameter.PickleResult`

        Result that can handle all objects that can be pickled

Moreover, part of this module is also the :class:`~pypet.parameter.ObjectTable`.
This is a specification of pandas_ DataFrames which maintains data types.
It prevents auto-conversion of data to numpy data types, like python integers to
numpy 64 bit integers, for instance.

.. _pandas: http://pandas.pydata.org/

"""

__author__ = 'Robert Meyer'

import logging
try:
    import cPickle as pickle
except ImportError:
    import pickle
import pickletools

import numpy as np
import scipy.sparse as spsp
from pandas import DataFrame

from pypet import pypetconstants
from pypet.naturalnaming import NNLeafNode
import pypet.utils.comparisons as comp
from pypet.utils.decorators import deprecated, copydoc
import pypetexceptions as pex


class ObjectTable(DataFrame):
    """Wrapper class for pandas_ DataFrames.

    It creates data frames with `dtype=object`.

    Data stored into an object table preserves its original type when stored to disk.
    For instance, a python int is not automatically converted to a numpy 64 bit integer (np.int64).

    The object table serves as a data structure to hand data to a storage service.

    Example Usage:

    >>> ObjectTable(data={'characters':['Luke', 'Han', 'Spock'], 'Random_Values' :[42,43,44] })

    Creates the following table:

        ======  ==============  ===========
        Index   Random_Values   characters
        ======  ==============  ===========
        0       42              Luke
        1       43              Han
        2       44              Spock
        ======  ==============  ===========

    .. _pandas: http://pandas.pydata.org/

    """
    def __init__(self, data=None, index = None, columns = None, copy=False):
        super(ObjectTable,self).__init__( data = data, index=index,columns=columns,
                                          dtype=object, copy=copy)


class BaseParameter(NNLeafNode):
    """Abstract class that specifies the methods for a trajectory parameter.

    Parameters are simple container objects for data values. They handle single values as well as
    ranges of potential values. These range arrays contain multiple values which are accessed
    one after the other in individual simulation runs.

    Parameter exploration is usually initiated through the trajectory see
    :func:`~pypet.trajectory.Trajectory.f_explore` and
    :func:`~pypet.trajectory.Trajectory.f_expand`.

    To access the parameter's data value one can call the
    :func:`~pypet.parameter.BaseParameter.f_get` method.

    Parameters support the concept of locking. Once a value of the parameter has been accessed,
    the parameter cannot be changed anymore unless it is explicitly unlocked using
    :func:`~pypet.parameter.BaseParameter.f_unlock`.
    This prevents parameters from being changed during runtime of a simulation.

    If multiprocessing is desired the parameter must be picklable!

    :param full_name:

        The full name of the parameter in the trajectory tree, groupings are
        separated by a colon: `fullname = 'supergroup.subgroup.paramname'`

    :param comment:

        A useful comment describing the parameter:
        `comment = 'Some useful text, dude!'`

    """
    def __init__(self, full_name, comment=''):
        super(BaseParameter,self).__init__(full_name,comment, parameter=True)

        self._locked = False

        # Whether to keep the full range array when pickled or not
        self._full_copy = False

    def f_supports(self, data):
        """Checks whether the data is supported by the parameter."""
        return type(data) in pypetconstants.PARAMETER_SUPPORTED_DATA

    @property
    def v_locked(self):
        """Whether or not the parameter is locked and prevents further modification"""
        return self._locked

    def f_supports_fast_access(self):
        """Checks if parameter supports fast access.

        A parameter supports fast access if it is NOT empty!

        """
        return not self.f_is_empty()


    @property
    def v_full_copy(self):
        """Whether or not the full parameter including the range or only the current
        data is copied during pickling.

        If you run your simulations in multiprocessing mode, the whole trajectory and all
        parameters need to be pickled and are sent to the individual processes.
        Each process than runs an individual point in the parameter space.
        As a consequence, you do not need the full ranges during these calculations.
        Thus, if the full copy mode is set to `False` the parameter is pickled without
        the range array and you can save memory.

        If you want to access the full range during individual runs, you need to set
        `v_full_copy` to `True`.

        It is recommended NOT to do that in order to save memory and also do obey the
        philosophy that individual simulation runs are independent.

        Example usage:

        >>> import pickle
        >>> param = Parameter('examples.fullcopy', data=333, comment='I show you how the copy mode works!')
        >>> param._explore([1,2,3,4])
        >>> dump=pickle.dumps(param)
        >>> newparam = pickle.loads(dump)
        >>> newparam.f_get_range()
        TypeError

        >>> param.v_full_copy=True
        >>> dump = pickle.dumps(param)
        >>> newparam=pickle.loads(dump)
        >>> newparam.f_get_range()
        (1,2,3,4)

        """
        return self._full_copy

    @v_full_copy.setter
    def v_full_copy(self,val):
        """Sets the full copy mode"""
        val=bool(val)
        self._full_copy = val

    @deprecated(msg='Please use `f_has_range()` instead.')
    def f_is_array(self):
        """Returns true if the parameter is explored and contains a range array.

        DEPRECATED: Use `f_has_range()` instead.

        """
        return self.f_has_range()

    def f_has_range(self):
        """Returns true if the parameter is explored and contains a range array.

        ABSTRACT: Needs to be defined in subclass

        """
        raise NotImplementedError( "Should have implemented this." )

    def _restore_default(self):
        """Restores original data if changed due to exploration.

        If a Parameter is explored, the actual data is changed over the course of different
        simulations. This method restores the original data assigned before exploration.

        ABSTRACT: Needs to be defined in subclass

        """
        raise NotImplementedError( "Should have implemented this." )
     
    def __len__(self):
        """Returns the length of the parameter

        Only parameters that have a defined range can have a length larger than 1.
        If the parameter only contains a default value its length is 1.
        If the parameter is empty its length is 0.

        ABSTRACT: Needs to be defined in subclass

        """
        raise NotImplementedError( "Should have implemented this." )

    def f_val_to_str(self):
        """String summary of the value handled by the parameter.

        Note that representing the parameter as a string accesses its value,
        but for simpler debugging, this does not lock the parameter or counts as usage!

        """
        old_locked = self._locked
        try :
            return str(self.f_get())
        except Exception:
            return 'No Evaluation possible (yet)!'
        finally:
            self._locked = old_locked

    def _equal_values(self, val1, val2):
        """Checks if the parameter considers two values as equal.

        This is important for the trajectory in case of merging. In case you want to delete
        duplicate parameter points, the trajectory needs to know when two parameters
        are equal. Since equality is not always implemented by values handled by
        parameters in the same way, the parameters need to judge whether their values are equal.

        The straightforward example here is a numpy array.
        Checking for equality of two numpy arrays yields
        a third numpy array containing truth values of a piecewise comparison.
        Accordingly, the parameter could judge two numpy arrays equal if ALL of the numpy
        array elements are equal.

        In this BaseParameter class values are considered to be equal if they obey
        the function :func:`~pypet.utils.comparisons.nested_equal`.
        You might consider implementing a different equality comparison in your subclass.

        :raises: TypeError: If both values are not supported by the parameter.

        """
        if self.f_supports(val1) != self.f_supports(val2):
            return False

        if not self.f_supports(val1) and not self.f_supports(val2):
                raise TypeError('I do not support the types of both inputs (`%s` and `%s`),'
                                ' therefore I cannot judge whether the two are equal.' %
                                str(type(val1)),str(type(val2)))

        if not self._values_of_same_type(val1,val2):
            return False

        return comp.nested_equal(val1,val2)

    def _values_of_same_type(self, val1, val2):
        """Checks if two values agree in type.

        For example, two 32 bit integers would be of same type, but not a string and an integer,
        nor a 64 bit and a 32 bit integer.

        This is important for exploration. You are only allowed to explore data that
        is of the same type as the default value.

        One could always come up with a trivial solution of `type(val1) is type(val2)`.
        But sometimes your parameter does want even more strict equality or
        less type equality.

        For example, the :class:`~pypet.parameter.Parameter` has a stricter sense of
        type equality regarding numpy arrays. In order to have two numpy arrays of the same type,
        they must also agree in shape. However, the :class:`~pypet.parameter.ArrayParameter`,
        considers all numpy arrays as of being of same type regardless of their shape.

        Moreover, the :class:`~pypet.parameter.SparseParameter` considers all supported
        sparse matrices (csc, csr, bsr, dia) as being of the same type. You can make
        explorations using all these four types at once.

        The difference in how strict types are treated arises from the way parameter data
        is stored to disk and how the parameters hand over their data to the storage service
        (see :func:`pypet.parameter.BaseParameter._store`).

        The :class:`~pypet.parameter.Parameter` puts all it's data in an
        :class:`~pypet.parameter.ObjectTable` which
        has strict constraints on the column sizes. This means that numpy array columns only
        accept numpy arrays with a particular size. In contrast, the array and sparse
        parameter hand over their data as individual items which yield individual entries
        in the hdf5 node. In order to see what I mean simply run an experiment with all 3
        parameters, explore all of them, and take a look at the resulting hdf5 file!

        However, this BaseParameter class implements the straightforward version of
        `type(val1) is type(val2)` to consider data to be of the same type.

        :raises: TypeError: if both values are not supported by the parameter.

        """
        if self.f_supports(val1) != self.f_supports(val2):
            return False

        if not self.f_supports(val1) and not self.f_supports(val2):
                raise TypeError('I do not support the types of both inputs (`%s` and `%s`),'
                                ' therefore I cannot judge whether the two are of same type.' %
                                str(type(val1)),str(type(val2)))

        return type(val1) is type(val2)

    def __str__(self):
        """String representation of the Parameter

        Output format is:`<class_name> full_name (len:X, `comment`): value`.
        If comment is the empty string, the comment is omitted.
        If the parameter is not explored the length is omitted.

        """
        if self.f_has_range():
            lenstr = 'len:%d' % len(self)
        else:
            lenstr = ''

        if self.v_comment:
            commentstr = '`%s`' % self.v_comment
        else:
            commentstr = ''

        if commentstr or lenstr:
            if commentstr and lenstr:
                combined_str = '%s, %s' %(lenstr, commentstr)
            elif commentstr:
                combined_str = commentstr
            elif lenstr:
                combined_str = lenstr
            else:
                raise RuntimeError('You shall not pass!')

            infostr = ' (%s)' %combined_str

        else:
            infostr = ''

        return '<%s> %s%s: %s' % (self.f_get_class_name(), self.v_full_name,
                                   infostr, self.f_val_to_str())


    def f_unlock(self):
        """Unlocks the locked parameter.

        Please use it very carefully, or best do not use this function at all.
        There should better be no reason to unlock a locked parameter!
        The only exception I can think of is to unlock a large derived parameter
        after usage to subsequently call :func:`~pypet.parameter.BaseParameter.f_empty`
        to clear memory.

        """
        self._locked = False

    def f_lock(self):
        """Locks the parameter and forbids further manipulation.

        Changing the data value or exploration range of the parameter are no longer allowed.

        """
        self._locked = True

    def f_set(self,data):
        """Sets a data value for a parameter.

        Example usage:

        >>> param = Parameter('groupA.groupB.myparam', comment='I am a neat example')
        >>> param.f_set(44.0)
        >>> param.f_get()
        44.0

        :raises:

                ParameterLockedException: If parameter is locked

                TypeError: If the type of the data value is not supported by the parameter

        ABSTRACT: Needs to be defined in subclass

        """
        raise NotImplementedError( "Should have implemented this." )

    def __getitem__(self, idx):
        """Equivalent to `f_get_range[idx]`

        :raises: TypeError if parameter has no range

        """
        return self.f_get_range().__getitem__(idx)


    def f_get(self):
        """Returns the current data value of the parameter and locks the parameter.

        :raises: TypeError if the parameter is empty

        Example usage:

        >>> param = Parameter('groupA.groupB.myparam', comment='I am a neat example')
        >>> param.f_set(44.0)
        >>> param.f_get()
        44.0:

        ABSTRACT: Needs to be defined in subclass

        """
        raise NotImplementedError( "Should have implemented this." )

    @deprecated(msg='Please use `f_get_range()` instead!')
    def f_get_array(self):
        """Returns an iterable to iterate over the values of the exploration range.

        Note that the returned values should be either a copy of the exploration range
        or the array must be immutable, for example a python tuple.

        :return: Immutable sequence

        :raises: TypeError if the parameter is not explored

        Example usage:

        >>> param = Parameter('groupA.groupB.myparam',data=22, comment='I am a neat example')
        >>> param._explore([42,43,43])
        >>> param.f_get_array()
        (42,43,44)

        DEPRECATED: Use `f_get_range()` instead!

        """
        return self.f_get_range()

    def f_get_range(self):
        """Returns an iterable to iterate over the values of the exploration range.

        Note that the returned values should be either a copy of the exploration range
        or the array must be immutable, for example a python tuple.

        :return: Immutable sequence

        :raises: TypeError if the parameter is not explored

        Example usage:

        >>> param = Parameter('groupA.groupB.myparam',data=22, comment='I am a neat example')
        >>> param._explore([42,43,43])
        >>> param.f_get_range()
        (42,43,44)

        ABSTRACT: Needs to be defined in subclass

        """
        raise NotImplementedError( "Should have implemented this." )
    
    def _explore(self, iterable):
        """The method to explore a parameter and create a range of entries.

        :param iterable: An iterable specifying the exploration range

             For example:

             >>> param = Parameter('groupA.groupB.myparam',data=22.33,\
              comment='I am a neat example')
             >>> param._explore([3.0,2.0,1.0])

        :raises:

            ParameterLockedException: If the parameter is locked

            TypeError: If the parameter is already explored

        ABSTRACT: Needs to be defined in subclass

        """
        raise NotImplementedError( "Should have implemented this." )

    def _expand(self, iterable):
        """Similar to :func:`~pypet.parameter.BaseParameter._explore` but appends to
        the exploration range.

        :param iterable: An iterable specifying the exploration range.

        :raises:

            ParameterLockedException: If the parameter is locked

            TypeError: If the parameter did not have a range before

        Example usage:

        >>> param = Parameter('groupA.groupB.myparam', data=3.13, comment='I am a neat example')
        >>> param._explore([3.0,2.0,1.0])
        >>> param._expand([42.0,43.0])
        >>> param.f_get_range()
        (3.0,2.0,1.0,42.0,43.0)

        ABSTRACT: Needs to be defined in subclass

        """
        raise NotImplementedError("Should have implemented this.")

    def _set_parameter_access(self, idx=0):
        """Sets the current value according to the `idx` in the exploration range.

        Prepares the parameter for further usage, and tells it which point in the parameter
        space should be accessed by calls to :func:`~pypet.parameter.BaseParameter.f_get`.

        :param idx: The index within the exploration range.

            If the parameter has no range, the single data value is considered
            regardless of the value of `idx`.
            Raises ValueError if the parameter is explored and `idx>=len(param)`.

        :raises: ValueError:

            If the parameter has a range and `idx` is larger or equal to the
            length of the parameter.

        Example usage:

        >>> param = Parameter('groupA.groupB.myparam',data=22.33, comment='I am a neat example')
        >>> param._explore([42.0,43.0,44.0])
        >>> param._set_parameter_access(idx=1)
        >>> param.f_get()
        43.0

        ABSTRACT: Needs to be defined in subclass

        """
        raise NotImplementedError( "Should have implemented this." )
        
    def f_get_class_name(self):
        """ Returns the name of the class i.e. `return self.__class__.__name__`"""
        return self.__class__.__name__


    def f_is_empty(self):
        """True if no data has been assigned to the parameter.

        Example usage:

        >>> param = Parameter('myname.is.example', comment='I am _empty!')
        >>> param.f_is_empty()
        True
        >>> param.f_set(444)
        >>> param.f_is_empty()
        False

        """
        return len(self) == 0

    def _shrink(self):
        """If a parameter is explored, i.e. it has a range, the whole exploration range is deleted.
.
        Note that this function does not erase data from disk. So if the parameter has
        been stored with a service to disk and is shrunk, it can be restored by loading from disk.

        :raises:

            ParameterLockedException: If the parameter is locked

            TypeError: If the parameter has no range


        ABSTRACT: Needs to be defined in subclass

        """
        raise NotImplementedError( "Should have implemented this." )


    def f_empty(self):
        """Erases all data in the parameter.

        Does not erase data from disk. So if the parameter has
        been stored with a service to disk and is emptied,
        it can be restored by loading from disk.

        :raises: ParameterLockedException: If the parameter is locked.

        ABSTRACT: Needs to be defined in subclass

        """
        raise NotImplementedError( "Should have implemented this." )

      
class Parameter(BaseParameter):
    """ The standard container that handles access to simulation parameters.

    Parameters are simple container objects for data values. They handle single values as well as
    the so called exploration range. An array containing multiple values which are accessed
    one after the other in individual simulation runs.

    Parameter exploration is usually initiated through the trajectory see
    `:func:~pypet.trajectory.Trajectory.f_explore` and
    `:func:~pypet.trajectory.Trajectory.f_expand`.

    To access the parameter's data value one can call the :func:`~pypet.parameter.Parameter.f_get`
    method.

    Parameters support the concept of locking. Once a value of the parameter has been accessed,
    the parameter cannot be changed anymore unless it is explicitly unlocked using
    :func:`~pypet.parameter.Parameter.f_unlock`.
    Locking prevents parameters from being changed during runtime of a simulation.

    Supported data values for the parameter are

    * python natives (int, long, str, bool, float, complex),

    * numpy natives, arrays and matrices of type
      np.int8-64, np.uint8-64, np.float32-64, np.complex, np.str

    * python homogeneous non-nested tuples

    Note that for larger numpy arrays it is recommended to use the
    :class:`~pypet.parameter.ArrayParameter`.


    In case you create a new parameter you can pass the following arguments:

    :param full_name: The full name of the parameter. Grouping can be achieved by using colons.

    :param data:

        A data value that is handled by the parameter. It is checked whether the parameter
        :func:`~pypet.parameter.Parameter.f_supports` the data. If not a TypeError is thrown.
        If the parameter becomes explored, the data value is kept as a default. After
        simulation the default value will be restored.

        The data can be accessed as follows:

        >>> param.f_get()
        42

        To change the data after parameter creation one can call
        :func:`~pypet.parameter.Parameter.f_set`:

        >>> param.f_set(43)
        >>> param.f_get()
        43

    :param comment:

        A useful comment describing the parameter.
        The comment can be changed later on using the 'v_comment' variable.

        >>> param.v_comment = 'Example comment'
        >>> print param.v_comment
        'Example comment'

    :raises: TypeError: If `data` is not supported by the parameter.

    Example usage:

    >>> param = Parameter('traffic.mobiles.ncars',data=42, comment='I am a neat example')

    """
    def __init__(self, full_name, data=None, comment=''):
        super(Parameter,self).__init__(full_name,comment)
        self._data= None

        self._default = None # The default value, which is the same as _data in the beginning,
        # but it is necessary to keep a reference to it to restore the original value
        # after exploration

        self._explored_range=tuple() # Tuple that will changed later on if parameter is explored
        self._set_logger()

        if data is not None:
            self.f_set(data)

    def _set_logger(self):
        self._logger = logging.getLogger('pypet.parameter.Parameter=' + self.v_full_name)

    def _restore_default(self):
        """Restores the default data that was set with the
        `:func:`~pypet.parameter.Parameter.f_set` method (or at initialisation).

        If the parameter is explored during the runtime of a simulation,
        the actual value of the parameter is changed and taken from the exploration range.
        Calling :func:`~pypet.parameter.Parameter._restore_default` sets the parameter's value
        back to it's original value.

        Example usage:

        >>> param = Parameter('supergroup1.subgroup2.', data=44, comment='Im a comment!')
        >>> param._explore([1,2,3,4])
        >>> param._set_parameter_access(2)
        >>> param.f_get()
        3
        >>> param._restore_default()
        >>> param.f_get()
        44

        """
        self._data = self._default

    @copydoc(BaseParameter.__len__)
    def __len__(self):
        if self._data is None:
            return 0
        elif len(self._explored_range)>0:
            return len(self._explored_range)
        else:
            return 1

    @copydoc(BaseParameter.f_has_range)
    def f_has_range(self):
        return len(self._explored_range)>0
       
    def __getstate__(self):
        """ Returns the actual state of the parameter for pickling.

        If `v_full_copy` is true the exploration range is also pickled, otherwise it is omitted.

        """
        result = self.__dict__.copy()


        # If we don't need a full copy of the Parameter (because a single process needs
        # only access to a single point in the parameter space) we can delete the rest
        if not self._full_copy :
            result['_explored_range'] = tuple()

        del result['_logger'] #pickling does not work with loggers
        return result

    def __setstate__(self, statedict):
        self.__dict__.update( statedict)
        self._set_logger()
      
    @copydoc(BaseParameter._set_parameter_access)
    def _set_parameter_access(self, idx=0):
        if idx >= len(self) and self.f_has_range():
            raise ValueError('You try to access data item No. %d in the parameter range, '
                             'yet there are only %d potential items.' % (idx, len(self)))
        elif self.f_has_range:
            self._data = self._explored_range[idx]
        else:
            self._logger.warning('You try to change the access to a parameter range of parameter'
                                 ' `%s`. The parameter has no range, your setting has no'
                                 ' effect.')

    def f_supports(self, data):
        """Checks if input data is supported by the parameter."""
        if type(data) is tuple:

            # Parameters cannot handle empty tuples
            if len(data)==0:
                return False

            old_type = None

            # Check if the data in the tuple is homogeneous
            for item in data:
                if not type(item) in pypetconstants.PARAMETER_SUPPORTED_DATA:
                    return False
                if not old_type is None and old_type != type(item):
                    return False
                old_type = type(item)
            return True

        if type(data) in [np.ndarray, np.matrix]:

            if len(data)==0:
                return False

            # Numpy has many string types that depend on the length of the string,
            # We allow all of them
            dtype = data.dtype
            if np.issubdtype(dtype, np.str):
                dtype = np.str
        else:
            dtype=type(data)

        return dtype in pypetconstants.PARAMETER_SUPPORTED_DATA


    def _values_of_same_type(self,val1, val2):
        """Checks if two values agree in type.

        Raises a TypeError if both values are not supported by the parameter.
        Returns false if only one of the two values is supported by the parameter.

        Example usage:

        >>>param._values_of_same_type(42,43)
        True

        >>>param._values_of_same_type(42,'43')
        False

        :raises: TypeError

        """
        if self.f_supports(val1) != self.f_supports(val2):
            return False

        if not self.f_supports(val1) and not self.f_supports(val2):
                raise TypeError('I do not support the types of both inputs (`%s` and `%s`),'
                                ' therefore I cannot judge whether the two are of same type.' %
                                str(type(val1)),str(type(val2)))
        
        if not type(val1) is type(val2):
            return False

        # Numpy arrays must agree in data type and shape
        if type(val1) is np.array:
            if not val1.dtype is val2.dtype:
                return False
            
            if not np.shape(val1)==np.shape(val2):
                return False

        # For tuples we now from earlier checks that the data is homogeneous.
        # Thus, only the type of the first item and the length must agree.
        if type(val1) is tuple:
            return (type(val1[0]) is type(val2[0])) and (len(val1) == len(val2))
        
        return True


    @copydoc(BaseParameter.f_set)
    def f_set(self,data):

        if self.v_locked:
            raise pex.ParameterLockedException('Parameter >>' + self._name + '<< is locked!')

        if self.f_has_range():
            raise AttributeError('Your Parameter is an explored array can no longer change values!')

        val = self._convert_data(data)

        if not self.f_supports(val):
            raise TypeError('Unsupported data `%s`' % str(val))

        self._data= val
        self._default = self._data


    def _convert_data(self, val):
        """Converts data to be handled by the parameter.

        The only operation so far is to set numpy arrays immutable.
        All other data items are simply returned without modification.

        :param val: the data value to convert

        :return: the converted data

        """
        if isinstance(val, np.ndarray):
            val.flags.writeable = False
            return val

        return val


    def f_get_range(self):
        """Returns a python tuple containing the exploration range.

        Example usage:

        >>> param = Parameter('groupA.groupB.myparam',data=22, comment='I am a neat example')
        >>> param._explore([42,43,43])
        >>> param.f_get_range()
        (42,43,44)

        :raises: TypeError: If parameter is not explored.

        """
        if not self.f_has_range():
            raise TypeError('Your parameter `%s` is not array, so cannot return array.' %
                                    self.v_full_name)
        else:
            return self._explored_range


    def _explore(self, explore_iterable):
        """Explores the parameter according to the iterable.

        Raises ParameterLockedException if the parameter is locked.
        Raises TypeError if the parameter does not support the data,
        the types of the data in the iterable are not the same as the type of the default value,
        or the parameter has already an exploration range.

        Note that the parameter will iterate over the whole iterable once and store
        the individual data values into a tuple. Thus, the whole exploration range is
        explicitly stored in memory.

        :param explore_iterable: An iterable specifying the exploration range

        For example:

        >>> param._explore([3.0,2.0,1.0])
        >>> param.f_get_range()
        (3.0, 2.0, 1.0)

        :raises TypeError,ParameterLockedException

        """
        if self.v_locked:
            raise pex.ParameterLockedException('Parameter `%s` is locked!' % self.v_full_name)

        if self.f_has_range():
            raise TypeError('Your Parameter %s is already explored, cannot _explore it further!' %
                            self._name)

        data_tuple = self._data_sanity_checks(explore_iterable)

        self._explored_range = data_tuple
        self.f_lock()

    def _expand(self,explore_iterable):
        """Explores the parameter according to the iterable and appends to the exploration range.

        Raises ParameterLockedException if the parameter is locked.
        Raises TypeError if the parameter does not support the data,
        the types of the data in the iterable are not the same as the type of the default value,
        or the parameter did not have an array before.

        Note that the parameter will iterate over the whole iterable once and store
        the individual data values into a tuple. Thus, the whole exploration range is
        explicitly stored in memory.

        :param explore_iterable: An iterable specifying the exploration range

         For example:

         >>> param = Parameter('Im.an.example', data=33.33, comment='Wooohoo!')
         >>> param._explore([3.0,2.0,1.0])
         >>> param._expand([42.0, 43.42])
         >>> param.f_get_range()
         >>> (3.0, 2.0, 1.0, 42.0, 43.42)

        :raises TypeError, ParameterLockedException

        """
        if self.v_locked:
            raise pex.ParameterLockedException('Parameter `%s` is locked!' % self.v_full_name)

        if not self.f_has_range():
            raise TypeError('Your Parameter `%s` is not an array and can therefore '
                            'not be expanded.' % self._name)

        data_tuple = self._data_sanity_checks(explore_iterable)

        self._explored_range = self._explored_range + data_tuple
        self.f_lock()


    def _data_sanity_checks(self, explore_iterable):
        """Checks if data values are  valid.

        Checks if the data values are supported by the parameter and if the values are of the same
        type as the default value.

        """
        data_tuple = []

        for val in explore_iterable:
            newval = self._convert_data(val)

            if not self.f_supports(newval):
                raise TypeError('%s is of not supported type %s.' % (repr(val),str(type(newval))))

            if not self._values_of_same_type(newval, self._default):
                raise TypeError('Data is not of the same type as the original entry value, '
                                'new type is %s vs old type %s.' %
                                ( str(type(newval)),str(type(self._default))))


            data_tuple.append(newval)


        if len(data_tuple) == 0:
            raise ValueError('Cannot explore an empty list!')

        return tuple(data_tuple)


    def _store(self):
        """Returns a dictionary of formatted data understood by the storage service.

        The data is put into an :class:`~pypet.parameter.ObjectTable` named 'data'.
        If the parameter is explored, the exploration range is also put into another table
        named 'explored_data'.

        :return: Dictionary containing the data and optionally the exploration range.

        """
        store_dict= {'data': ObjectTable(data={'data': [self._data]})}

        if self.f_has_range():
            store_dict['explored_data'] = ObjectTable(data={'data':self._explored_range})


        return store_dict


    def _load(self,load_dict):
        """Loads the data and exploration range from the `load_dict`.

        The `load_dict` needs to be in the same format as the result of the
        :func:`~pypet.parameter.Parameter._store` method.

        """
        self._data = self._convert_data(load_dict['data']['data'][0])
        self._default=self._data
        if 'explored_data' in load_dict:
            self._explored_range = tuple([self._convert_data(x)
                                   for x in load_dict['explored_data']['data'].tolist()])

    @copydoc(BaseParameter.f_get)
    def f_get(self):
        if self.f_is_empty():
            raise TypeError('Parameter `%s` is empty cannot access data' % self.v_full_name)

        self.f_lock() # As soon as someone accesses an entry the parameter gets locked
        return self._data

    @copydoc(BaseParameter._shrink)
    def _shrink(self):

        if self.v_locked:
            raise pex.ParameterLockedException('Parameter %s is locked!' % self.v_full_name)

        if not self.f_has_range():
            raise TypeError('Cannot shrink non-array Parameter.')

        if self.f_is_empty():
            raise TypeError('Cannot shrink empty Parameter.')

        del self._explored_range
        self._explored_range={}

    @copydoc(BaseParameter.f_empty)
    def f_empty(self):

        if self.v_locked:
            raise pex.ParameterLockedException('Parameter %s is locked!' % self.v_full_name)

        if self.f_has_range():
            self._shrink()

        del self._data
        self._data=None


class ArrayParameter(Parameter):
    """Similar to the :class:`:func:`~pypet.parameter.Parameter`, but recommended for
    large numpy arrays and python tuples.

    The array parameter is a bit smarter in memory management than the parameter.
    If a numpy array is used several times within an exploration, only one numpy array is stored by
    the default HDF5 storage service. For each individual run references to the corresponding
    numpy array are stored.

    Since the ArrayParameter inherits from :class:`~pypet.parameter.Parameter` it also
    supports all other native python types.

    """

    IDENTIFIER = '__rr__'
    """Identifier to mark stored data as an array"""

    def _set_logger(self):
        self._logger = logging.getLogger('pypet.parameter.ArrayParameter=' + self.v_full_name)


    def _store(self):
        """Creates a storage dictionary for the storage service.

        If the data is not a numpy array, a numpy matrix, or a tuple, the
        :func:`~pypet.parameter.Parmater._store` method of the parent class is called.

        Otherwise the array is put into the dictionary with the key 'data__rr__'.

        Each array of the exploration range is stored as a separate entry named
        'xa__rr__XXXXXXXX' where 'XXXXXXXX' is the index of the array. Note if an array
        is used more than once in an exploration range (for example, due to cartesian product
        exploration), the array is stored only once.
        Moreover, an :class:`~pypet.parameter.ObjectTable` containing the references
        is stored under the name 'explored_data__rr__' in order to recall
        the order of the arrays later on.

        """
        if not type(self._data) in [np.ndarray, tuple, np.matrix]:
            return super(ArrayParameter,self)._store()
        else:
            store_dict = {'data' + ArrayParameter.IDENTIFIER: self._data}

            if self.f_has_range():
                # Supports smart storage by hashable arrays
                # Keys are the hashable arrays or tuples and values are the indices
                smart_dict = {}

                store_dict['explored_data'+ArrayParameter.IDENTIFIER] = \
                    ObjectTable(columns=['idx'],index=range(len(self)))

                count = 0
                for idx, elem in enumerate(self._explored_range):

                    # First we need to distinguish between tuples and array and extract a
                    # hashable part of the array
                    if isinstance(elem, tuple):
                        hash_elem = elem
                    else:
                        # You cannot hash numpy arrays themselves, but if they are read only
                        # you can hash array.data
                        hash_elem = elem.data

                    # Check if we have used the array before,
                    # i.e. element can be found in the dictionary
                    if hash_elem in smart_dict:
                        name_idx = smart_dict[hash_elem]
                        add = False
                    else:
                        name_idx = count
                        add = True

                    name = self._build_name(name_idx)
                    # Store the reference to the array
                    store_dict['explored_data'+ArrayParameter.IDENTIFIER]['idx'][idx] = \
                        name_idx

                    # Only if the array was not encountered before,
                    # store the array and remember the index
                    if add:
                        store_dict[name] = elem
                        smart_dict[hash_elem] = name_idx
                        count +=1

            return store_dict

    def _build_name(self,name_idx):
        """Formats a name for storage

        :return:

            'xa__rr__XXXXXXXX' where 'XXXXXXXX' is the index of the array

        """
        return 'xa%s%08d' % (ArrayParameter.IDENTIFIER, name_idx)


    def _load(self,load_dict):
        """Reconstructs the data and exploration array.

        Checks if it can find the array identifier in the `load_dict`, i.e. '__rr__'.
        If not calls :class:`~pypet.parameter.Parameter._load` of the parent class.

        If the parameter is explored, the exploration range of arrays is reconstructed
        as it was stored in :func:`~pypet.parameter.ArrayParameter._store`.

        """
        try:
            self._data = load_dict['data'+ArrayParameter.IDENTIFIER]

            if 'explored_data'+ArrayParameter.IDENTIFIER in load_dict:
                explore_table = load_dict['explored_data'+ArrayParameter.IDENTIFIER]

                idx = explore_table['idx']

                explore_list = []

                # Recall the arrays in the order stored in the ObjectTable 'explored_data__rr__'
                for name_idx in idx:
                    arrayname = self._build_name(name_idx)
                    explore_list.append(load_dict[arrayname])

                self._explored_range=tuple([self._convert_data(x) for x in explore_list])

        except KeyError:
            super(ArrayParameter,self)._load(load_dict)

        self._default=self._data


    def _values_of_same_type(self,val1, val2):
        """Checks if two values agree in type.

        The array parameter is less restrictive than the parameter. If both values
        are arrays, matrices or tuples, they are considered to be of same type
        regardless of their size and values they contain.

        """
        if (type(val1) in [np.ndarray, tuple, np.matrix]) and (type(val2) is type(val1)):
            return True
        else:
            return super(ArrayParameter,self)._values_of_same_type(val1,val2)



class SparseParameter(ArrayParameter):
    """Parameter that handles Scipy csr, csc, bsr and dia sparse matrices.

    Sparse Parameter inherits from :class:`pypet.parameter.ArrayParameter` and supports
    arrays and native python data as well.

    Uses similar memory management as its parent class.

    """

    IDENTIFIER = '__spsp__'
    """Identifier to mark stored data as a sparse matrix"""

    DIA_NAME_LIST = ['format', 'data', 'offsets', 'shape']
    """Data names for serialization of dia matrices"""
    OTHER_NAME_LIST = ['format', 'data', 'indices', 'indptr', 'shape']
    """Data names for serialization of csr, csc, and bsr matrices"""

    def _values_of_same_type(self,val1, val2):
        """Checks if two values agree in type.

        The sparse parameter is less restrictive than the parameter. If both values
        are sparse matrices they are considered to be of same type
        regardless of their size and values they contain.

        """
        if self._is_supported_matrix(val1) and self._is_supported_matrix(val2):
            return True
        else:
            return super(SparseParameter,self)._values_of_same_type(val1,val2)

    def _equal_values(self,val1,val2):
        """Matrices are equal if they hash to the same value."""
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
        """Checks if a data is csr, csc, bsr, or dia Scipy sparse matrix"""
        return (spsp.isspmatrix_csc(data) or
                spsp.isspmatrix_csr(data) or
                spsp.isspmatrix_bsr(data) or
                spsp.isspmatrix_dia(data) )


    def f_supports(self, data):
        """Sparse matrices support Scipy csr, csc, bsr and dia matrices and everything their parent
        class the :class:`~pypet.parameter.ArrayParameter` supports.

        """
        if self._is_supported_matrix(data):
            return True
        else:
            return super(SparseParameter,self).f_supports(data)

    @staticmethod
    def _serialize_matrix(matrix):
        """Extracts data from a sparse matrix to make it serializable in a human readable format.

        :return: Tuple with following elements:

            1.

                A list containing data that is necessary to reconstruct the matrix.
                For csr, csc, and bsr matrices the following attributes are extracted:
                `format`, `data`, `indices`, `indptr`, `shape`.
                Where format is simply one of the strings 'csr', 'csc', or 'bsr'.

                For dia matrices the following attributes are extracted:
                `format`, `data`, `offsets`, `shape`.
                Where `format` is simply the string 'dia'.

            2.

                A list containing the names of the extracted attributes.
                For csr, csc, and bsr:

                    [`format`, `data`, `indices`, `indptr`, `shape`]

                For dia:

                    [`format`, `data`, `offsets`, `shape`]

            3.

                A tuple containing the hashable parts of (1) in order to use the tuple as
                a key for a dictionary. Accordingly, the numpy arrays of (1) are
                changed to read-only.

        """
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

        # Extract the `data` property of a read-only numpy array in order to have something
        # hashable.
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
        """Creates a storage dictionary for the storage service.

        If the data is not a supported sparse matrix, the
        :func:`~pypet.parameter.ArrayParmater._store` method of the parent class is called.

        Otherwise the matrix is split into parts with
        :func:`~pypet.parameter.SparseParameter._serialize_matrix` and these are named
        'data__spsp__XXXX' where 'XXXX' is a particular property of the matrix.

        The exploration range is handled similar as in the parent class. Yet, the matrices
        are split into the relevant parts and each part is stored as
        'xspm__spsp__XXXX__spsp__XXXXXXXX` where the first 'XXXX' refer to the property and
        the latter 'XXXXXXX' to the sparse matrix index.

        The :class:`~pypet.parameter.ObjectTable` `explored_data__spsp__` stores the order
        of the matrices and whether the corresponding matrix is dia or not.

        """
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

            if self.f_has_range():
                ## Supports smart storage by hashing
                smart_dict = {}

                store_dict['explored_data'+SparseParameter.IDENTIFIER] = \
                    ObjectTable(columns=['idx','is_dia'],
                                index=range(len(self)))

                count = 0
                for idx,elem in enumerate(self._explored_range):

                    data_list, name_list, hash_tuple = self._serialize_matrix(elem)

                    # Use the hash_tuple as a key for the smart_dict
                    if hash_tuple in smart_dict:
                        name_idx = smart_dict[hash_tuple]
                        add = False
                    else:
                        name_idx = count
                        add = True

                    is_dia=int(len(name_list)==4)
                    rename_list = self._build_names(name_idx,is_dia)

                    store_dict['explored_data'+SparseParameter.IDENTIFIER]['idx'][idx] = name_idx

                    store_dict['explored_data'+SparseParameter.IDENTIFIER]['is_dia'][idx] = is_dia


                    if add:

                        for irun,name in enumerate(rename_list):
                            store_dict[name] = data_list[irun]

                        smart_dict[hash_tuple] = name_idx
                        count +=1

            return store_dict

    def _build_names(self, name_idx, is_dia):
        """Formats a name for storage

        :return: A tuple of names with the following format:

            `xspm__spsp__XXXX__spsp__XXXXXXXX` where the first 'XXXX' refer to the property and
            the latter 'XXXXXXX' to the sparse matrix index.

        """
        name_list = self._get_name_list(is_dia)
        return tuple(['xspm%s%s%s%08d' % (SparseParameter.IDENTIFIER, name,
                                          SparseParameter.IDENTIFIER, name_idx)
                                                for name in name_list])

    def _build_names_old(self, name_idx, is_dia):
        """ONLY for backwards compatibility"""
        name_list = self._get_name_list(is_dia)
        return tuple(['xspm%s%s%08d' % (SparseParameter.IDENTIFIER, name, name_idx)
                                                for name in name_list])

    @staticmethod
    def _reconstruct_matrix(data_list):
        """Reconstructs a matrix from a list containing sparse matrix extracted properties

        `data_list` needs to be formatted as the first result of
        :func:`~pypet.parameter.SparseParameter._serialize_matrix`

        """
        matrix_format = data_list[0]

        if matrix_format == 'csc':
            return spsp.csc_matrix(tuple(data_list[1:4]),shape=data_list[4])
        elif matrix_format == 'csr':
            return spsp.csr_matrix(tuple(data_list[1:4]),shape=data_list[4])
        elif matrix_format == 'bsr':
            return spsp.bsr_matrix(tuple(data_list[1:4]),shape=data_list[4])
        elif matrix_format == 'dia':
            return spsp.dia_matrix(tuple(data_list[1:3]), shape=data_list[3])
        else:
            raise RuntimeError('You shall not pass!')

    def _load(self,load_dict):
        """Reconstructs the data and exploration array

        Checks if it can find the array identifier in the `load_dict`, i.e. '__spsp__'.
        If not, calls :class:`~pypet.parameter.ArrayParameter._load` of the parent class.

        If the parameter is explored, the exploration range of matrices is reconstructed
        as it was stored in :func:`~pypet.parameter.SparseParameter._store`.

        """
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

                    # To make everything work with the old format we have the try catch block
                    try:
                        name_list = self._build_names(name_id,is_dia)
                        data_list = [load_dict[name] for name in name_list]
                    except KeyError:
                        name_list = self._build_names_old(name_id,is_dia)
                        data_list = [load_dict[name] for name in name_list]

                    matrix = self._reconstruct_matrix(data_list)
                    explore_list.append(matrix)

                self._explored_range=tuple(explore_list)


        except KeyError:
            super(SparseParameter,self)._load(load_dict)

        self._default=self._data


class PickleParameter(Parameter):
    """A parameter class that supports all picklable objects, and pickles everything!

    If you use the default HDF5 storage service, the pickle dumps are stored to disk.
    Works similar to the array parameter regarding memory management (Equality of objects
    is based on object id).

    There is no straightforward check to guarantee that data is picklable, so you have to
    take care that all data handled by the PickleParameter supports pickling.

    You can pass the pickle protocol via `protocol=2` to the constructor or change it with
    the `v_protocol` property. Default protocol is 0.
    Note that after storage to disk changing the protocol has no effect.
    If the parameter is loaded, `v_protocol` is set to the protocol used to store the data.

    """
    def __init__(self, full_name, data=None, comment='',protocol=2):
        super(PickleParameter,self).__init__(full_name,data,comment)
        self._protocol=None
        self.v_protocol=protocol

    @property
    def v_protocol(self):
        """ The protocol used to pickle data, default is 0.

        See pickle_ documentation for the protocols.

        .. _pickle: http://docs.python.org/2/library/pickle.html

        """
        return self._protocol

    @v_protocol.setter
    def v_protocol(self, value):
        """Sets the protocol"""
        self._protocol = value


    def _set_logger(self):
        self._logger = logging.getLogger('pypet.parameter.PickleParameter=' + self.v_full_name)

    def f_supports(self, data):
        """There is no straightforward check if an object can be pickled and this function will
        always return `True`.

        So you have to take care in advance that the item can be pickled.

        """
        return True

    def _convert_data(self, val):
        """No conversion necessary, therefore we simply return the value."""
        return val

    def _build_name(self,name_id):
        """Formats names for storage

        Explored data is stored as 'xp_XXXXXXXX' where 'XXXXXXXX' is the index of the object.

        """
        return 'xp_%08d' % name_id

    def _store(self):
        """Returns a dictionary for storage.

        Every element in the dictionary except for 'explored_data' is a pickle dump.

        Reusage of objects is identified over the object id, i.e. python's built-in id function.

        'explored_data' contains the references to the objects to be able to recall the
        order of objects later on.

        """
        store_dict={}
        dump = pickle.dumps(self._data, protocol=self.v_protocol)
        store_dict['data'] = dump

        if self.f_has_range():

            store_dict['explored_data'] = \
                ObjectTable(columns=['idx'],index=range(len(self)))

            smart_dict = {}
            count = 0


            for idx, val in enumerate(self._explored_range):

                obj_id = id(val)

                if obj_id in smart_dict:
                    name_id = smart_dict[obj_id]
                    add = False
                else:
                    name_id = count
                    add = True

                name = self._build_name(name_id)
                store_dict['explored_data']['idx'][idx] = name_id

                if add:
                    store_dict[name] = pickle.dumps(val,protocol=self.v_protocol)
                    smart_dict[obj_id] = name_id
                    count +=1

        return store_dict

    @staticmethod
    def _get_protocol(dump):
        protolist = [tup[0].proto for tup in pickletools.genops(dump)]
        #op, fs, snd = next(pickletools.genops(dump))
        return int(max(protolist))

    def _load(self,load_dict):
        """Reconstructs objects from the pickle dumps in `load_dict`.

        The 'explored_data' entry in `load_dict` is used to reconstruct
        the exploration range in the correct order.

        Sets the `v_protocol` property to the protocol used to store 'data'.

        """
        dump = load_dict['data']

        self._data = pickle.loads(dump)

        self.v_protocol = self._get_protocol(dump)


        if 'explored_data'in load_dict:
                explore_table = load_dict['explored_data']

                name_col = explore_table['idx']

                explore_list = []
                for name_id in name_col:
                    arrayname = self._build_name(name_id)
                    loaded = pickle.loads(load_dict[arrayname])
                    explore_list.append(loaded)

                self._explored_range=tuple(explore_list)


        self._default=self._data


class BaseResult(NNLeafNode):
    """Abstract base API for results.

    Compared to parameters (see :class:`~pypet.parameter.BaseParameter`) results are also
    initialised with a full name and a comment.
    Yet, results can contain more than a single value and heterogeneous data.

    """
    def __init__(self, full_name, comment=''):
        super(BaseResult,self).__init__(full_name,comment, parameter=False)



class Result(BaseResult):
    """Light Container that stores basic python and numpy data.

    Note that no sanity checks on individual data is made (only on outer data structure)
    and you have to take care, that your data is understood by the storage service.
    It is assumed that results tend to be large and therefore sanity checks would be too expensive.

    Data that can safely be stored into a Result are:

        *   python natives (int, long, str, bool, float, complex),

        *
            numpy natives, arrays and matrices of type
            np.int8-64, np.uint8-64, np.float32-64, np.complex, np.str

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

        *   pandas DataFrames_

        *   :class:`~pypet.parameter.ObjectTable`

    .. _DataFrames: http://pandas.pydata.org/pandas-docs/dev/dsintro.html#dataframe

    Note that containers should NOT be empty (like empty dicts or lists) at the time
    they are saved to disk. The standard HDF5 storage service cannot store empty containers!
    The Result emits a warning if you hand over an empty container.

    Data is set on initialisation or with :func:`~pypet.parameter.Result.f_set`

    Example usage:

    >>> res = Result('supergroup.subgroup.myresult', comment='I am a neat example!' \
        [1000,2000], {'a':'b','c':333}, hitchhiker='Arthur Dent')


    In case you create a new result you can pass the following arguments:

    :param fullanme: The fullname of the result, grouping can be achieved by colons,

    :param comment:

        A useful comment describing the result.
        The comment can later on be changed using the `v_comment` variable

        >>> param.v_comment
        'I am a neat example!'

    :param args:

        Data that is handled by the result.
        The first positional argument is stored with the name of the result.
        Following arguments are stored with `name_X` where `X` is the position
        of the argument.

    :param kwargs:

        Data that is handled by the result, it is kept by the result under the names
        specified by the keys of kwargs.

        >>> res.f_get(0)
        [1000,2000]
        >>> res.f_get(1)
        {'a':'b','c':'d'}
        >>> res.f_get('myresult')
        [1000,2000]
        >>> res.f_get('hitchhiker')
        'ArthurDent'
        >>> res.f_get('myresult','hitchhiker')
        ([1000,2000], 'ArthurDent')

        Can be changed or more can be added via :func:`~pypet.parameter.Result.f_set`

        >>> result.f_set('Uno',x='y')
        >>> result.f_get(0)
        'Uno'
        >>> result.f_get('x')
        'y'


        Alternative method to put and retrieve data from the result container is via `__getattr__` and
        `__setattr__`

        >>> res.ford = 'prefect'
        >>> res.ford
        'prefect'

    :raises: TypeError:

        If the data format in args or kwargs is not known to the result. Checks type of
        outer data structure, i.e. checks if you have a list or dictionary.
        But it does not check on individual values within dicts or lists.

    """
    def __init__(self, full_name, *args, **kwargs):
        comment = kwargs.pop('comment','')
        super(Result,self).__init__(full_name,comment)
        self._data = {}
        self._set_logger()
        self.f_set(*args,**kwargs)
        self._no_data_string = False


    @property
    def v_no_data_string(self):
        """Whether or not to give a short summarizing string when calling
         :func:`~pypet.parameter.Result.f_val_to_str`.

        Can be set to `False` if the evaluation of stored data into string is too costly.

        """
        return self._no_data_string

    @v_no_data_string.setter
    def v_no_data_string(self,boolean):
        """Sets the no_data_string property"""
        self._no_data_string=boolean


    def __contains__(self, item):
        return item in self._data


    def f_val_to_str(self):
        """Summarizes data handled by the result as a string.

        Calls `__str__` on all handled data if `v_no_data_string=False`, else only
        the name/key of the handled data is printed.

        Truncates the string if it is longer than
        :const:`pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH`

        :return: string

        """
        if not self._no_data_string:
            resstr=''
            for key in sorted(self._data.keys()):
                val = self._data[key]
                resstr+= '%s=%s, ' % (key, str(val))

                if len(resstr) >= pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH:
                    resstr = resstr[0:pypetconstants.HDF5_STRCOL_MAX_VALUE_LENGTH-3]+'...'
                    return resstr

            return resstr[0:-2]
        else:
            resstr = ', '.join(sorted(self._data.keys()))

            if len(resstr) >= pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH:
                    resstr = resstr[0:pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH-3]+'...'
                    return resstr

            return resstr

    def __str__(self):
        """String representation of the result.

        Output format is '<class_name> name (`comment`): value_string'

        The `value_string` is obtained from :func:`~pypet.parameter.Result.f_val_to_str`.

        If the comment is the empty string, the comment is omitted.

        """
        datastr = self.f_val_to_str()

        if self.v_comment:
            return '<%s> %s (`%s`): %s' % (self.f_get_class_name(),
                                                  self.v_full_name,self.v_comment,datastr)
        else:
            return '<%s> %s: %s' % (self.f_get_class_name(),self.v_full_name,datastr)



    def _set_logger(self):
        self._logger = logging.getLogger('pypet.parameter.Result=' + self.v_full_name)


    def __getstate__(self):
        result = self.__dict__.copy()
        del result['_logger'] #pickling does not work with loggers
        return result


    def __setstate__(self, statedict):
        self.__dict__.update( statedict)
        self._set_logger()

    def f_to_dict(self, copy = True):
        """Returns all handled data as a dictionary

        :param copy:

            Whether the original dictionary or a shallow copy is returned.

        :return: Data dictionary

        """
        if copy:
            return self._data.copy()
        else:
            return self._data


    def f_is_empty(self):
        """True if no data has been put into the result.

        Also True if all data has been erased via :func:`~pypet.parameter.Result.f_empty`.

        """
        return len(self._data)== 0

    @copydoc(BaseResult.f_empty)
    def f_empty(self):
        del self._data
        self._data={}

    def f_set(self,*args, **kwargs):
        """ Method to put data into the result.

        :param args:

            The first positional argument is stored with the name of the result.
            Following arguments are stored with `name_X` where `X` is the position
            of the argument.

        :param kwargs: Arguments are stored with the key as name.

        :raises: TypeError if outer data structure is not understood.

        Example usage:

        >>> res = Result('supergroup.subgroup.myresult', comment='I am a neat example!')
        >>> res.f_set(333,42.0, mystring='String!')
        >>> res.f_get('myresult')
        333
        >>> res.f_get('myresult_1')
        42.0
        >>> res.f_get(1)
        42.0
        >>> res.f_get('mystring')
        'String!'

        """
        for idx,arg in enumerate(args):
            if idx == 0:
                valstr = self.v_name
            else:
                valstr = self.v_name+'_'+str(idx)
            self.f_set_single(valstr,arg)

        for key, arg in kwargs.items():
            self.f_set_single(key,arg)


    def __getitem__(self, name):
        """ Equivalent to calling `f_get(name)` (see :func:`~pypet.parameter.BaseResult.f_get`)."""
        return self.f_get(name)

    def __iter__(self):
        """Equivalent to iterating over the keys of the data dictionary."""
        return self._data.__iter__()

    def f_get(self,*args):
        """Returns items handled by the result.

         If only a single name is given, a single data item is returned. If several names are
         given, a list is returned. For integer inputs the result returns `resultname_X`.

         If the result contains only a single entry you can call `f_get()` without arguments.
         If you call `f_get()` and the result contains more than one element a ValueError is
         thrown.

         If the requested item(s) cannot be found an AttributeError is thrown.

        :param args: strings-names or integers

        :return: Single data item or tuple of data

        Example:

        >>> res = Result('supergroup.subgroup.myresult', comment='I am a neat example!' \
        [1000,2000], {'a':'b','c':333}, hitchhiker='Arthur Dent')
        >>> res.f_get('hitchhiker')
        'Arthur Dent'
        >>> res.f_get(0)
        [1000,2000]
        >>> res.f_get('hitchhiker', 'myresult')
        ('Arthur Dent', [1000,2000])

        """

        if len(args) == 0:
            if len(self._data) == 1:
                return self._data[self._data.keys()[0]]
            elif len(self._data) >1:
                raise ValueError('Your result `%s` contains more than one entry: '
                                 '`%s` Please use >>f_get<< with one of these.' %
                                 (self.v_full_name, str(self._data.keys())))
            else:
                raise AttributeError('Your result `%s` is empty, cannot access data.' %
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
                raise  AttributeError('`%s` is not part of your result `%s`.' %
                                      (name,self.v_full_name))

            result_list.append(self._data[name])

        if len(args)==1:
            return result_list[0]
        else:
            return result_list

    def f_set_single(self, name, item):
        """Sets a single data item of the result.

        Raises TypeError if the type of the outer data structure is not understood.
        Note that the type check is shallow. For example, if the data item is a list,
        the individual list elements are NOT checked whether their types are appropriate.

        :param name: The name of the data item

        :param item: The data item

        :raises: TypeError

        Example usage:

        >>> res.f_set_single('answer', 42)
        >>> res.f_get('answer')
        42

        """
        if self._supports(item):

            self._check_if_empty(item, name)

            if name in self._data:
                self._logger.debug('Replacing `%s` in result `%s`.' % (name, self.v_full_name))

            self._data[name] = item
        else:
            raise TypeError('Your result `%s` of type `%s` is not supported.' %
                                 (name,str(type(item))))

    def _check_if_empty(self, item, name):
        """Checks if the result is requested to handle an empty item, like an empty list or
        dictionary.

        Empty items are problematic because they cannot be stored by the storage service.
        Emits a waring in case of an empty item.

        """
        try:
            if len(item) ==0:
                self._logger.warning('The Item `%s` is empty.' % name)
        except TypeError:
            # If the item does not support `len` operation we can ignore that
            pass

    def _supports(self, item):
        """Checks if outer data structure is supported."""
        return type(item) in ((np.ndarray,ObjectTable,DataFrame,dict,tuple,list,np.matrix)+
                             pypetconstants.PARAMETER_SUPPORTED_DATA)


    def f_supports_fast_access(self):
        """Whether or not the result supports fast access.

        A result supports fast access if it contains exactly one item with the name of the result.

        """
        return len(self._data)==1 and self.v_name in self._data

    def _store(self):
        """Returns a storage dictionary understood by the storage service.

        Simply returns a shallow copy of its own data dictionary.

        """
        store_dict ={}
        store_dict.update(self._data)
        return store_dict

    def _load(self, load_dict):
        """Loads data from load_dict"""
        self._data = load_dict

    def __delattr__(self, item):
        """ Deletes an item from the result.

        If the item has been stored to disk before with a storage service, this storage is not
        deleted!

        :param item: Name of item to delete

        :raises: AttributeError if the item does not exist

        Example usage:

        >>> res = Result('Iam.an.example', comment = 'And a neat one, indeed!', fortytwo=42)
        >>> 'fortytwo' in res
        True
        >>> del res.fortytwo
        >>> 'fortytwo' in res
        False

        """
        if item[0]=='_':
            del self.__dict__[item]
        elif item in self._data:
            del self._data[item]
        else:
            raise AttributeError('Your result `%s` does not contain %s.' % (self.name_,item))

    def __setattr__(self, key, value):
        if key[0]=='_':
            # Change a private attribute
            self.__dict__[key] = value
        elif hasattr(self.__class__,key):
            # Work around for python properties
            python_property = getattr(self.__class__,key)
            if python_property.fset is None:
                raise AttributeError('%s is read only!' % key)
            else:
                python_property.fset(self,value)
        else:
            self.f_set_single(key, value)

    def __getattr__(self, name):
        if not '_data' in self.__dict__:
            raise AttributeError('This is to avoid pickling issues!')

        if not name in self._data:
            raise  AttributeError('`%s` is not part of your result `%s`.' %
                                  (name,self.v_full_name))

        return self._data[name]

class SparseResult(Result):
    """Handles Scipy sparse matrices.

    Supported Formats are csr, csc, bsr, and dia.

    Subclasses the standard result and can also handle all data supported by
    :class:`~pypet.parameter.Result`.

    """

    IDENTIFIER = SparseParameter.IDENTIFIER
    """Identifier string to label sparse matrix data"""

    @copydoc(Result.f_set_single)
    def f_set_single(self, name, item):
        if SparseResult.IDENTIFIER in name:
            raise AttributeError('Your result name contains the identifier for sparse matrices,'
                                 ' please do not use %s in your result names.' %
                                 SparseResult.IDENTIFIER)
        else:
            super(SparseResult,self).f_set_single(name,item)


    def _supports(self, item):
        """Supports everything of parent class and csr, csc, bsr, and dia sparse matrices."""
        if SparseParameter._is_supported_matrix(item):
            return True
        else:
            return super(SparseResult,self)._supports(item)

    @copydoc(Result._check_if_empty)
    def _check_if_empty(self, item, name):
        if SparseParameter._is_supported_matrix(item):
            if item.getnnz()==0:
                self._logger.warning('The Item `%s` is empty.' % name)
        else:
            super(SparseResult,self)._check_if_empty(item, name)

    def _store(self):
        """Returns a storage dictionary understood by the storage service.

        Sparse matrices are extracted similar to the :class:`~pypet.parameter.SparseParameter` and
        marked with the identifier `__spsp__`.

        """
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
        """Loads data from `load_dict`

        Reconstruction of sparse matrices similar to the :class:`~pypet.parameter.SparseParameter`.

        """
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
    """ Result that digest everything and simply pickles it!

    Note that it is not checked whether data can be pickled, so take care that it works!

    You can pass the pickle protocol via `protocol=2` to the constructor or change it with
    the `v_protocol` property. Default protocol is 0.

    Note that after storage to disk changing the protocol has no effect.
    If the parameter is loaded, `v_protocol` is set to a protocol used to
    store an item. Note that items are reconstructed from a dictionary and the protocol
    is taken from the first one found in the dictionary. This is a rather arbitrary choice.
    Yet, the underlying assumption is that all items were pickled with the same protocol,
    which is the general case.

    """
    def __init__(self, full_name, *args, **kwargs):
        self._protocol=None
        protocol = kwargs.pop('protocol', 0)
        self.v_protocol= protocol

        super(PickleResult,self).__init__(full_name, *args, **kwargs)


    @property
    def v_protocol(self):
        """ The protocol used to pickle data, default is 0.

        See pickle_ documentation for the protocols.

        .. _pickle: http://docs.python.org/2/library/pickle.html

        """
        return self._protocol

    @v_protocol.setter
    def v_protocol(self, value):
        """Sets the protocol"""
        self._protocol = value

    def f_set_single(self, name, item):
        """Adds a single data item to the pickle result.

         Note that it is NOT checked if the item can be pickled!

        """
        self._data[name] = item

    def _set_logger(self):
        self._logger = logging.getLogger('pypet.parameter.PickleResult=' + self.v_full_name)

    def _store(self):
        """Returns a dictionary containing pickle dumps"""
        store_dict ={}
        for key, val in self._data.items():
            store_dict[key] = pickle.dumps(val, protocol=self.v_protocol)
        return store_dict

    def _load(self, load_dict):
        """Reconstructs all items from the pickle dumps in `load_dict`.

        Sets the `v_protocol` property to the protocol of the first reconstructed item.

        """
        for idx, key in enumerate(load_dict):
            val = load_dict[key]
            self._data[key] = pickle.loads(val)
            if idx == 0:
                self.v_protocol = PickleParameter._get_protocol(val)