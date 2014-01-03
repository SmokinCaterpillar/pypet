=========================
Parameters and Results
=========================

.. automodule:: pypet.parameter

-------------------------
Parameter Quicklinks
-------------------------

.. currentmodule:: pypet.parameter


.. autosummary::
    :nosignatures:

    ~Parameter.f_set
    ~Parameter.f_get
    ~Parameter.f_empty
    ~Parameter.f_get_range
    ~Parameter.f_has_range
    ~Parameter.f_supports


-------------------------
Result Quicklinks
-------------------------

.. autosummary::
    :nosignatures:

    ~Result.f_set
    ~Result.f_get
    ~Result.f_empty
    ~Result.f_to_dict

--------------------
Parameter
--------------------
.. autoclass:: pypet.parameter.Parameter
    :members:
    :inherited-members:

----------------------
ArrayParameter
----------------------

.. autoclass:: pypet.parameter.ArrayParameter
    :members:

----------------------
SparseParameter
----------------------

.. autoclass:: pypet.parameter.SparseParameter
    :members:

----------------------
PickleParameter
----------------------

.. autoclass:: pypet.parameter.PickleParameter
    :members:


-----------------------
Result
-----------------------

.. autoclass:: pypet.parameter.Result
    :members:
    :inherited-members:

----------------------------
SparseResult
----------------------------

.. autoclass:: pypet.parameter.SparseResult
    :members:
    :inherited-members:

----------------------------
PickleResult
----------------------------

.. autoclass:: pypet.parameter.PickleResult
    :members:

-----------------------------
Object Table
-----------------------------

.. autoclass:: pypet.parameter.ObjectTable
    :members:

-----------------------------------------------------------------------
The Abstract Base Classes of Parameters and Results
-----------------------------------------------------------------------

These classes serve as a reference if you want to implement your own parameter or result.
Therefore, also private functions are listed.

.. autoclass:: pypet.parameter.BaseParameter
    :members:
    :inherited-members:
    :private-members:
    :special-members:
    :undoc-members:

.. autoclass:: pypet.parameter.BaseResult
    :members:
    :inherited-members:
    :private-members:
    :special-members:
    :undoc-members:



