=========
pypet
=========

The new python parameter exploration toolkit. pypet manages exploration of the parameter space and
data storage into HDF5 files for you.

===========================
IMPORTANT!
===========================

The current program is a **BETA** version,
please treat it as such and use very carefully.

Moreover, you WILL NOT be able to use trajectories that were created with the *ALPHA*
version any more. I am sorry if you have already explored a lot of parameter spaces.
If this bugs you a lot, let me know and I'll take a look whether I could write
a converter.

Note that until the 0.1.0 version there still might be some changes to the API. Yet, with  0.1.0
I will guarantee a stable API.

I decided to integrate pypet first in my own research project before publishing the
official 0.1.0 release. Thus, I have a more profound testing environment than only using
unittests. The official 0.1.0 release is postponed to beginning of next year or end of
this year.
However, feel free to use this beta version and feel free to give feedback,
suggestions, and report bugs. Either write my an email (robert.meyer (at) ni.tu-berlin.de)
or use github (https://github.com/SmokinCaterpillar/pypet) issues :-)

Thanks!

---------------------
Requirements
---------------------

Python 2.6 or 2.7

* tables >= 2.3.1

* pandas >= 0.12.0

* numpy >= 1.6.1

* scipy >= 0.9.0

For git integration you additionally need

* GitPython

=========================
What is pypet all about?
=========================

Whenever you do numerical simulations in science, you come across two major challenges.
First, you need some way to save your data. Secondly, you extensively explore the parameter space.
In order to accomplish both you write some hacky IO functionality to get it done the quick and
dirty way. This means storing stuff into text files, as MATLAB m-files, or whatever comes in handy.

After a while and many simulations later, you want to look back at some of your very
first results. But because of
unforeseen circumstances, you changed a lot of your code. As a consequence, you can no longer
use your old data, but you need to write a hacky converter to format your previous results
to your new needs.
The more complexity you add to your simulations, the worse it gets, and you spend way
too much time handling your data and results than doing science.

Indeed, this was a situation I was confronted with pretty soon during my PhD.
So this project was born. I wanted to tackle the IO problems more generally and produce code
that was not specific to my current simulations, but I could also use for future scientific
projects right out of the box.

The python parameter exploration toolkit (*pypet*) provides a framework to define *parameters* that
you need to run your simulations.
You can actively explore these by following a *trajectory* through the space spanned
by the parameters.
And finally, you can get your *results* together and store everything appropriately to disk.
Currently the storage method of choice is HDF5 (http://www.hdfgroup.org/HDF5/).

---------------------------
Package Organization
---------------------------

This project encompasses these core modules:

*  The `pypet.parameters` module including  containers for parameters and results.

*  The `pypet.trajectory` module for managing the parameters and results,
   and providing a way to *explore* your parameter space. Somewhat related is also the
   `pypet.naturalnaming` module, that provides functionality to access and put data into
   the *trajectory*.

*  The `pypet.environment` module for handling the running of simulations.

*  The `pypet.storageservice` for saving your data to disk.

---------------------------
Install
---------------------------

Simply install via `pip install --pre pypet`

Or

Package release can also be found on https://pypi.python.org/pypi/pypet. Download, unpack
and `python setup.py install` it.

pypet has been tested for python 2.6 and python 2.7 for Linux using
*Travis-CI* (https://www.travis-ci.org/). However, so far there was only limited testing under
Windows.

In principle, pypet should work for **Windows** out of the box if you have installed
all prerequisites (pytables, pandas, scipy, numpy). Yet, installing with
pip is not possible. You have to download the tar file from https://pypi.python.org/pypi/pypet and
unzip it (using WinRaR, 7zip, etc. You might need to unpack it twice, first
the `tar.gz` file and then the remaining `tar` file in the subfolder). Next, open a windows
terminal and navigate to your unpacked pypet files to the folder containing the `setup.py` file.
As above run from the terminal `python setup.py install`.

By the way, the source code is available at https://github.com/SmokinCaterpillar/pypet.

---------------------------
Documentation
---------------------------

Documentation can be found on http://pypet.readthedocs.org/.

If you have questions feel free to contact me at **robert.meyer (at) ni.tu-berlin.de**

---------------------------
Acknowledgements
---------------------------


*   Thanks to Robert Pröpper and Philipp Meier for answering all my Python questions.

    You might wanna check out their SpykeViewer (https://github.com/rproepp/spykeviewer)
    tool for visualization of MEA recordings and NEO (http://pythonhosted.org/neo) data


*   Thanks to Owen Mackwood for his SNEP toolbox which provided the initial ideas
    for this project.


*   Thanks to the BCCN Berlin (http://www.bccn-berlin.de),
    the Research Training Group GRK 1589/1, and the
    Neural Information Processing Group ( http://www.ni.tu-berlin.de) for support.

--------------
Main Features
--------------

* **Novel tree container** `Trajectory`, for handling and managing of
  parameters and results of numerical simulations

* **Grouping** of parameters and results

* Accessing handled items via **natural naming**, e.g. `traj.parameters.traffic.ncars`

* Support for many different **data formats**

    * python native data types: bool, int, long, float, str, complex

    * list, tuple, dict

    * Numpy arrays and matrices

    * Scipy sparse matrices

    * pandas DataFrames (http://pandas.pydata.org/)

    * BRIAN Quantities (http://briansimulator.org/)

    * BRIAN Monitors

* Easily **extendible** to other data formats!

* **Exploration** of the parameter space of your simulations

* **Merging** of *trajectories* residing in the same space

* Support for **multiprocessing**, distribute your individual simulation runs to several
  processes.

* **Storage** of simulation data, i.e. the *trajectory*, *parameters*, and *results* into
  **HDF5** files

* **Dynamic Loading**, load only the data you need at the moment and free it afterwards

* **Resuming** a crashed simulation (maybe due to power shut down) after the latest completed run

* **Annotations** of parameters, results and groups, these annotations are stored as HDF5 node attributes

* **Git Integration**, make automatic commits of your source code every time you run an experiment

======================
Quick Working Example
======================

The best way to show how stuff works is by giving examples. I will start right away with a
very simple code snippet.

Well, what we have in mind is some sort of numerical simulation. For now we will keep it simple,
let's say we need to simulate the multiplication of 2 values, i.e. `z=x*y`.
We have two objectives, a) we want to store results of this simulation `z` and
b) we want to explore the parameter space and try different values of `x` and `y`.

Let's take a look at the snippet at once:

::

    from pypet.environment import Environment
    from pypet.utils.explore import cartesian_product

    def multiply(traj):
        z=traj.x*traj.y
        traj.f_add_result('z',z=z, comment='I am the product of two reals!')

    # Create an environment that handles running
    env = Environment(trajectory='Example1_No1',filename='./HDF/example_01.hdf5',
                      file_title='ExampleNo1', log_folder='./LOGS/')

    # Get the trajectory from the environment
    traj = env.v_trajectory

    # Add both parameters
    traj.f_add_parameter('x', 1.0, comment='Im the first dimension!')
    traj.f_add_parameter('y', 1.0, comment='Im the second dimension!')

    # Explore the parameters with a cartesian product:
    traj.f_explore(cartesian_product({'x':[1.0,2.0,3.0,4.0], 'y':[6.0,7.0,8.0]}))

    # Run the simulation
    env.f_run(multiply)

And now let's go through it one by one. At first we have a job to do, that is multiplying two real
values:

::

    def multiply(traj):
        z=traj.x * traj.y
        traj.f_add_result('z',z)


This is our function multiply. The function uses a so called `Trajectory`
container which manages our parameters. We can access the parameters simply by natural naming,
as seen above via `traj.x` and `traj.y`. The result `z` is simply added as a result with name `'z'`
to the `traj` object.

After the definition of the job that we want to simulate, we create an environment which
will run the simulation.

::

    # Create an environment that handles running
    env = Environment(trajectory='Example1_01',filename='./HDF/example_01.hdf5',
                      file_title='Example_01', log_folder='./LOGS/',
                      comment = 'I am the first example!')


The environment uses some parameters here, that is the name of the new trajectory, a filename to
store the trajectory into, the title of the file, a folder for the log files, and a
comment that is added to the trajectory. There are more options available like
the number of processors for multiprocessing or how verbose the final hdf5 file is supposed to be.
Check out the documentation (http://pypet.readthedocs.org/) if you want to know more.
The environment will automatically generate a trajectory for us which we can access via:

::

    # Get the trajectory from the environment
    traj = env.v_trajectory

Now we need to populate our trajectory with our parameters. They are added with the default values
of `x=y=1.0`:

::

    # Add both parameters
    traj.f_add_parameter('x', 1.0, comment='Im the first dimension!')
    traj.f_add_parameter('y', 1.0, comment='Im the second dimension!')

Well, calculating `1.0*1.0` is quite boring, we want to figure out more products, that is
the results of the cartesian product set `{1.0,2.0,3.0,4.0} x {6.0,7.0,8.0}`.
Therefore, we use `f_explore` in combination with the builder function
`cartesian_product`:

::

    # Explore the parameters with a cartesian product:
    traj.f_explore(cartesian_product({'x':[1.0,2.0,3.0,4.0], 'y':[6.0,7.0,8.0]}))

Finally, we need to tell the environment to run our job `multiply`:

::

    # Run the simulation
    env.f_run(multiply)

And that's it. The environment and the storage service will have taken care about the storage
of our trajectory and the results we have computed.

So have fun using this tool!

Cheers,
    Robert

================================
Miscellaneous
================================

--------------------------------
Tests
--------------------------------

Tests can be found in `pypet/tests`.
Note that they involve heavy file IO and it might not be the case
that you have privileges on your system to write files to a temporary folder.
The tests suite will make use of the `tempfile.gettempdir()` function to
access a temporary folder.

You can run all tests with `$ python all_tests.py` which can also be found under
`pypet/tests`.
You can pass additional arguments as `$ python all_tests.py -k --folder=myfolder/` with
`-k` to keep the hdf5 files created by the tests (if you want to inspect them, otherwise
they will be deleted after the completed tests)
and `--folder=` to specify a folder where to store the hdf5 files instead of the temporary one.
If the folder cannot be created the program defaults to `tempfile.gettempdir()`.

------------------------------------
License
------------------------------------

BSD, please read LICENSE file.

------------------------------------
Legal Notice
------------------------------------

pypet was created by Robert Meyer at the Neural Information Processing Group (TU Berlin),
supported by the Research Training Group GRK 1589/1.

------------------------------------
Contact
------------------------------------

**robert.meyer (at) ni.tu-berlin.de**

Marchstr. 23

MAR 5.046

D-10587 Berlin