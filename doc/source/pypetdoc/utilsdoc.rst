=====
Utils
=====

---------------------
Exploration Functions
---------------------

.. automodule:: pypet.utils.explore
    :members: cartesian_product, find_unique_points


-----------------
Utility Functions
-----------------

^^^^^^^^^^^^^^^^^^^^^
HDF5 File Compression
^^^^^^^^^^^^^^^^^^^^^

You can use the following function to compress an existing HDF5 file
that already contains a trajectory. This only works under **Linux**.

.. autofunction:: pypet.compact_hdf5_file

^^^^^^^^^^^
Progressbar
^^^^^^^^^^^

Simple progressbar that can be used during a for-loop (no initialisation necessary).
It displays progress and estimates remaining time.

.. autofunction:: pypet.progressbar

-------------------------------------------------------------------
General Equality Function and Comparisons of Parameters and Results
-------------------------------------------------------------------

.. automodule:: pypet.utils.comparisons
    :members:

