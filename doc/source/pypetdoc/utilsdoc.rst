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


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Multiprocessing Directory Creation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Function that calls ``os.makedirs`` but takes care about race conditions if multiple
processes or threads try to create the directories at the same time.

.. autofunction:: pypet.racedirs

^^^^^^^^^^^^^^^^^^^^^^^^^
Merging many Trajectories
^^^^^^^^^^^^^^^^^^^^^^^^^

You can easily merge several trajectories located in one directory into one with

.. autofunction:: pypet.merge_all_in_folder


^^^^^^^^^^^
Manual Runs
^^^^^^^^^^^

If you don't want to use an Environment but manually schedule runs, take a look at the
following decorator:

.. autofunction:: pypet.manual_run


-------------------------------------------------------------------
General Equality Function and Comparisons of Parameters and Results
-------------------------------------------------------------------

.. automodule:: pypet.utils.comparisons
    :members:

