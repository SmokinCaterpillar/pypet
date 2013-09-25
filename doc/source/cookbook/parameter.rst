
.. _more-on-parameters:

================================
More on Parameters and Results
================================

-----------------------------
Parameters
-----------------------------

The parameter container (Base API is found in :class:`~pypet.parameter.BaseParameter`)
is used to keep data that is explicitly required as parameters for your simulations.
They are the containers of choice for everything in the trajectory stored under *parameters*,
*config*, and *derived_parameters*.

Parameter containers fulfill further important jobs:

 *  A key concept in numerical simulations is **exploration** of the parameter space. Therefore,
    the parameter containers not only keep a single value but can hold an *exploration array*
    of values.
    To avoid confusion with numpy arrays, I will explicitly always state exploration array.
    Exploration is initiated via the trajectory, see :ref:`parameter-exploration`.
    The individual values in the exploration array can be accessed one after the other
    for distinct simulations (see :func:`~pypet.parameter.Parameter.f_set_parameter_access`).
    How the exploration array is implemented depends on the parameter.

 *  The parameter can be **locked**, meaning as soon as the parameter is assigned to hold a specific
    value and the value has already been used somewhere,
    it cannot be changed any longer (except after being explicitly unlocked).
    This prevents the nasty error of having a particular parameter value
    at the beginning of a simulation but changing it during runtime for whatever reason. This
    can make your simulations impossible to understand by other people running them.
    Or you might run simulations with different parameter settings but observing the
    very same results, since your parameter is changed later on in your simulations!
    In fact, I ran into this problem during my PhD using someone else's simulations.
    Thus, debugging took ages. As a consequence, this project was born.

    By definition parameters are fixed values, that once used never change.
    An exception to this rule is solely the *exploration*
    of the parameter space (see :ref:`parameter-exploration`), but this
    requires to run a number of distinct simulations anyway.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Values supported by Parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Parameters are very restrictive in terms of the
data the except. The :class:`~pypet.parameter.Parameter` excepts only:

    * python natives (int,str,bool,float,complex),

    * numpy natives, arrays and matrices of type np.int8-64, np.uint8-64, np.float32-64,
      np.complex, np.str

    * python homogeneous not nested  tuples

And by *only*, I mean they except exactly these types and nothing else, not even objects
that are derived from these data types.

Why, so very restrictive again? Well, the reason is that we store these values to disk into
hdf5 later on. We want to recall them occasionally, and maybe even rerun our experiments.
However, as soon as you store data into an hdf5 files, most often information about the exact type
is lost. So if you store, for instance, a numpy matrix via pytables and recall it, you will get
a numpy array instead. So the storage service that comes with this package will take care
that the exact type of an instance is NOT lost. However, this guarantee of type conservations
comes with the cost that types are restricted.

However, that does not mean that data not supported cannot be used as a parameter at all.
You have two possibilities if your data is not supported. First, write your own parameter
that converts your data to the basic types supported by the storage service (and this is easy
the API :class:`~pypet.parameter.BaseParameter` is really small. Or second of all,
simply put your data into the :class:`~pypet.parameter.PickleParameter` and it can be stored later
on to hdf5 as the pickle string.

Note that as soon as you add data or explore data it will immediately be checked if the data
is supported and if not a TypeError is thrown.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Types of Parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
So far, the following parameters exist:

 *  :class:`~pypet.parameter.Parameter`:

    Container for native python data: int,float,str,bool,complex and
    Numpy data: np.int8-64, np.uint8-64, np.float32-64, np.complex, np.str.
    Numpy arrays and matrices are allowed as well.

    However for larger numpy arrays,
    the ArrayParameter
    is recommended. The array parameter will keep a large array only once,
    even if it is used several
    times during exploration in the exploration array.

 *  :class:`~pypet.parameter.ArrayParameter`

    Container for native python data as well as tuples and numpy arrays.
    The array parameter is the method of choice for large numpy arrays or python tuples.
    These are kept only once (and by the hdf5 storage service stored only once to disk)
    and in the exploration array you can find references to these arrays. This is particularly
    useful if you reuse an array many times in distinct simulation, for example, by exploring
    the parameter space in form of a cartesian product.
    For instance, assume you explore a numpy array with default value
    `numpy.array([1,2,3])`.
    A potential exploration could be: `[numpy.array([1,2,3]),numpy.array([3,4,3]),
    numpy.array([1,2,3]),numpy.array([3,4,3])]`
    So you reuse `numpy.array([1,2,3])` and `numpy.array([3,4,3])` twice. If you would
    put this data into the standard Parameter, the full list `[numpy.array([1,2,3]),numpy.array([3,4,3]),
    numpy.array([1,2,3]),numpy.array([3,4,3])` would be stored to disk.
    The ArrayParameter is smarter. It will store `numpy.array([1,2,3])` and `numpy.array([3,4,3])`
    once and in addition a list of references
    `[ref_to_array_1,ref_to_array_2,ref_to_array_1,ref_to_array_2]`


 *  :class:`~pypet.parameter.PickleParameter`:

    Container for all the data that can be pickled. Like the array parameter, distinct objects
    are kept only once and are referred to in the exploration array.

Parameters can be changed and values can be requested with the getter and setter methods:
:func:`~pypet.parameter.Parameter.f_get` and :func:`~pypet.parameter.Parameter.f_set`.

For people using BRIAN_ quantities, there also exists a
:class:`~pypet.brian.parameter.BrianParameter`.


------------------------------------
Results
------------------------------------

Results are less restrictive in their acceptance of values. And they can handle more than a
single data item.

They support a constructor and a getter and setter that have positional and keyword arguments.
And, of course, results support natural naming as well.

For example:

    >>> res = Result('supergroup.subgroup.myresult', comment='I am a neat example!')
    >>> res.f_set(333,mystring='String!')
    >>> res.f_get('myresult')
    333
    >>> res.f_get('mystring')
    'String!'
    >>> res.mystring
    'String!'
    >>> res.myresult
    333

If you use `f_set(*args)` the first positional argument is added to the result having the name
of the result, here 'myresult'. Subsequent positional arguments are added with 'name_X' where *X*
is the position of the argument. Positions are counted starting from zero so `f_set('a','b','c')`
will add the entries `'myresult,myresult_1,myresult_2'` to your result.

Using :func:`~pypet.parameter.Result.f_get` you can request several items at once.
If you ask for `f_get(itemname)` you will get in return the item with that name. If you
request `f_get(itemname1,itemname2,....)` you will get a list in return containing the items.
To refer to items stored with 'name_X' providing the index value is sufficient:

    >>> res.f_get(0)
    333

If your result contains only a single item you can simply call `f_get()` without any arguments.
But if you call `f_get()` without any arguments and the result contains more than one item
a ValueError is thrown.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Types of Results
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following results exist:

* :class:`~pypet.parameter.Result`:

    Light Container that stores tables and arrays.

    Note that no sanity checks on individual data is made
    and you have to take care, that your data is understood by the storage service.
    It is assumed that results tend to be large and therefore sanity checks would be too expensive.

    Data that can safely be stored into a Result are:

        * python natives (int,str,bool,float,complex),

        * numpy natives, arrays and matrices of type np.int8-64, np.uint8-64, np.float32-64,
          np.complex, np.str


        * python lists and tuples of the previous types (python natives + numpy natives and arrays)

        * python dictionaries of the previous types (not nested!)

        * pandas_ data frames

        * :class:`~pypet.parameter.ObjectTable`

                Object tables are special pandas_ data frames with `dtype=object`, i.e. everything
                you keep in object tables will keep its type and won't be auto-converted py pandas.


* :class:`~pypet.parameter.PickleResult`

    Result that digest everything and simply pickles it!

    Note that it is not checked whether data can be pickled, so take care that it works!


For those of you using BRIAN_, there exists also the
:class:`pypet.brian.parameter.BrianMonitorResult`


.. _BRIAN: http://briansimulator.org/

.. _pandas: http://pandas.pydata.org/pandas-docs/dev/index.html