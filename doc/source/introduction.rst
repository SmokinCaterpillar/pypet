================================
What is pypet all about?
================================

Whenever you do numerical simulations in science you come across two major problems.
First, you need some way to save your data. Secondly, you extensively explore the parameter space.
In order to accomplish both you write some hacky I/O functionality to get it done the quick and
dirty way. Storing stuff into text files, as MATLAB m-files, or whatever comes in handy.

After a while and many simulations later, you want to look back at some of your very
first results. But because of
unforeseen circumstances, you changed lots of your code. As a consequence, you can no longer
use your old data, but you need to write a hacky converter to format your previous results
to your new needs.
The more complexity you add to your simulations, the worse it gets, and you spend way
too much time formatting your data than doing science.

Indeed, this was a situation I was confronted with pretty quickly during my PhD.
So this project was born. I wanted to tackle the I/O problems more generally and produce code
that was not specific to my current simulations, but I could also use for future scientific
projects right out of the box.

The **python parameter exploration toolkit** (*pypet*) provides a framework to define *parameters*
that you need to run your simulations.
You can actively explore these by following a *trajectory* through the space spanned
by the parameters.
And finally, you can get your *results* together and store everything appropriately to disk.
Currently the storage method of choice is HDF5_ via PyTables_.


---------------------------
Install
---------------------------

Simply install via `pip install --pre pypet`

Or

Package release can also be found on `pypi.python.org`_. Download, unpack
and `python setup.py install` it.

*pypet* has been tested for python 2.6 and python 2.7 for Linux using
Travis-CI_. However, so far there was only limited testing under
Windows.

In principle, *pypet* should work for **Windows** out of the box if you have installed
all prerequisites (pytables, pandas, scipy, numpy). Yet, installing with
pip is not possible. You have to download the tar file from `pypi.python.org`_ and
unzip it (using WinRaR, 7zip, etc. You might need to unpack it twice, first
the `tar.gz` file and then the remaining `tar` file in the subfolder). Next, open a windows
terminal [#win]_
and navigate to your unpacked *pypet* files to the folder containing the `setup.py` file.

As above run from the terminal `python setup.py install`.

By the way, the source code is available at `github.com/SmokinCaterpillar/pypet`_.

.. _Travis-CI: https://www.travis-ci.org/

.. _`pypi.python.org`: https://pypi.python.org/pypi/pypet

.. _`github.com/SmokinCaterpillar/pypet`: https://github.com/SmokinCaterpillar/pypet

.. [#Win]

    By the way, you open a terminal by pressing *Windows Button* + *R*.
    Then type *cmd* into the dialog box and press *OK*.

---------------------------------
What to do with pypet?
---------------------------------

The whole project evolves around a novel container object called *trajectory*.
A *trajectory* is a container for *parameters* and *results* of numerical simulations
in python. In fact a *trajectory* instantiates a tree and the
tree structure will be mapped one to one in the HDF5 file if you store data to disk.
But more on that later.

As said before a *trajectory* contains *parameters*, the basic building blocks that
completely define the initial conditions of your numerical simulations. Usually these are
very basic data types, like integers, floats or maybe a bit more complex numpy arrays.

For example, you have written a set functions that simulate traffic
jam in Rome. Your simulation takes a lot of *parameters*, the amount of
cars (integer), their potential destinations (numpy array of strings),
number of pedestrians (integer),
random number generator seeds (numpy integer array), open parking spots in Rome
(Your *parameter* value is probably 0 here), and all other sorts of things.
These values are added to your *trajectory* container and can be retrieved from there
during the runtime of your simulation.

Doing numerical simulations usually means that you cannot find analytical solutions to your
problems. Accordingly, you want to evaluate your simulations on very different *parameter* settings
and investigate the effect of changing the *parameters*. To phrase that differently, you want to
*explore* the parameter space. Coming back to the traffic jam simulations, you could tell your
*trajectory* that you want to investigate how different amounts of cars and pedestrians
influence traffic problems in Rome. So you define sets of combinations of cars and pedestrians
and make individual simulation *runs* for these sets. To phrase that differently,
you follow a predefined *trajectory* of points through your *parameter* space.
And that's why the container is called *trajectory*.

For each *run* of your simulation, with a particular combination of cars and pedestrians, you
record time series data of traffic densities at major sites in Rome. This time series data
(let's say they are pandas_ DataFrames) can also be added to your *trajectory* container.
In the end everything will be stored to disk. The storage is handled by an
extra service to store the *trajectory* into an
HDF5_ file on your hard drive. Probably other formats like SQL will come soon (or maybe you
want to contribute some code, and write an SQL storage service?).

An example code snippet (way less sophisticated than traffic simulations)
of a numerical simulation handled by *pypet* is given below.



--------------------------------
Quick (and not so Dirty) Example
--------------------------------

The best way to show how stuff works is by giving examples. I will start right away with a
very simple code snippet (it can also be found here: :ref:`example-01`).

Well, what we have in mind is some sort of numerical simulation. For now we will keep it simple,
let's say we need to simulate the multiplication of 2 values, i.e. :math:`z=x*y`.
We have two objectives, a) we want to store results of this simulation :math:`z` and
b) we want to *explore* the parameter space and try different values of :math:`x` and :math:`y`.

Let's take a look at the snippet at once:

.. code-block:: python

    from pypet.environment import Environment
    from pypet.utils.explore import cartesian_product


    def multiply(traj):
        z=traj.x*traj.y
        traj.f_add_result('z',z, comment='I am the product of two values!')


    # Create and environment that handles running
    env = Environment(trajectory='Example1_No1',filename='./HDF/example_01.hdf5'',
                      file_title='ExampleNo1', log_folder='./LOGS/',
                      comment='I am a simple example!')

    # Get the trajectory from the environment
    traj = env.get_trajectory()

    # Add both parameters
    traj.f_add_parameter('x', 1.0, comment='Im the first dimension!')
    traj.f_add_parameter('y', 1.0, comment='Im the second dimension!')

    # Explore the parameters with a cartesian product
    traj.f_explore(cartesian_product({'x':[1.0,2.0,3.0,4.0], 'y':[6.0,7.0,8.0]}))

    # Run the simulation
    env.f_run(multiply)



And now let's go through it one by one. At first we have a job to do, that is multiplying
two values:

.. code-block:: python

    def multiply(traj):
        z=traj.x * traj.y
        traj.f_add_result('z',z, comment='I am the product of two values!')

This is our function `multiply`. The function gets a so called :class:`~pypet.trajectory.Trajectory`
container which manages our parameters. We can access the parameters simply by natural naming,
as seen above via `traj.x` and `traj.y`. The value of `z` is simply added as a result to the
`traj` container.

After the definition of the job that we want to simulate, we create an environment which
will run the simulation.

.. code-block:: python

    # Create and environment that handles running
    env = Environment(trajectory='Example1_01',filename='./HDF/example_01.hdf5',
                      file_title='Example_01', log_folder='./LOGS/',
                      comment = 'I am a simple example!')


The environment uses some parameters, that is the name of the new trajectory, a filename to
store the trajectory into, the title of the file, a folder for the log files, and a
comment that is added to the trajectory. You can pass many more optional arguments if you like,
check out :ref:`more-on-environment` and :class:`~pypet.environment.Environment`
for a complete list.
The environment will automatically generate a trajectory for us which we can access via:

.. code-block::python

    # Get the trajectory from the environment
    traj = env.get_trajectory()

Now we need to populate our trajectory with our parameters. They are added with the default values
of :math:`x=y=1.0`.

.. code-block:: python

    # Add both parameters
    traj.f_add_parameter('x', 1.0, comment='Im the first dimension!')
    traj.f_add_parameter('y', 1.0, comment='Im the second dimension!')

Well, calculating :math:`1.0*1.0` is quite boring, we want to figure out more products, that is
the results of the cartesian product set :math:`\{1.0,2.0,3.0,4.0\} \times \{6.0,7.0,8.0\}`.
Therefore we use :func:`~pypet.trajectory.Trajectory.f_explore` in combination with the builder function
:func:`~pypet.utils.explore.cartesian_product` that yields the cartesian product of both
parameter ranges.

.. code-block:: python

    # Explore the parameters with a cartesian product:
    traj.f_explore(cartesian_product({'x':[1.0,2.0,3.0,4.0], 'y':[6.0,7.0,8.0]}))

Finally, we need to tell the environment to run our job `multiply` with all parameter
combinations.

.. code-block:: python

    # Run the simulation
    env.f_run(multiply)

And that's it. If we now inspect the new HDF5 file in `examples/HDF/example_01.hdf5`,
we will see that our results have been stored right in there, in fact the whole trajectory with
our parameters was saved to disk.

.. image:: /figures/example_01.png


^^^^^^^^^^^^^^^^^^^^^^^^
Loading the data
^^^^^^^^^^^^^^^^^^^^^^^^

We end this example by showing how we could reload the data that we have computed before.
Here we want to load all data at once and just print the result of `run_00000001` where
`x` was 2.0 and `y` was 6.0.

.. code-block:: python

    from pypet.trajectory import Trajectory

    # So, first let's create a new trajectory and pass it the path and name of the HDF5 file.
    traj = Trajectory(filename='experiments/example_01/HDF5/example_01.hdf5')

    # Now we want to load all stored data.
    traj.f_load(index=-1, load_parameters=2, load_results=2)

    # Finally we want to print a result of a particular run.
    # Let's take the second run named `run_00000001` (Note that counting starts at 0!).
    print 'The result of run_00000001 is: '
    print traj.run_00000001.z

This yields the statement *The result of run_00000001 is: 12* printed to the console.

Some final remarks to the command:

.. code-block:: python

    # Now we want to load all stored data.
    traj.f_load(index=-1, load_parameters=2, load_results=2)

Above `index` specifies that we want to load the trajectory with that particular index
within the HDF5 file. We could instead also specify a `name`.
Counting works also backwards, so `-1` yields the last or newest trajectory in the file.

Next we need to specify how the data is loaded.
Therefore, we have to set the keyword arguments `load_parameters` and `load_results`,
here we chose both to be `2`.
`0` would mean we do not want to load anything at all.
`1` would mean we only want to load the empty hulls or skeletons of our parameters
or results. Accordingly, we would add parameters or results to our trajectory
but they would not contain any data.
Instead `2` means we want to load the parameters and results including the data they contain.
If you want to know more about how to load trajectories take a look at :ref:`more-on-loading` and
the :class:`~pypet.trajectory.Trajectory` documentation.


------------------
Basic Work Flow
------------------

Basic workflow is summarized in the image you can find below.
Usually you use an :class:`~pypet.environment.Environment` for handling the execution and running
of your simulation.
As in the example code snippet from before the environment will provide a
:class:`~pypet.trajectory.Trajectory` container for you to fill in (groups of) parameters.
During the execution of your simulation with individual parameter combinations
a so called :class:`~pypet.trajectory.SingleRun` container (a reduced version of the
*trajectory* containing only one particular parameter combination)  can be used to store results.
All data that you hand over to a *trajectory* or *single run* is automatically
stored into an HDF5 file by a :class:`~pypet.storageservice.HDF5StorageService`.

.. image:: figures/layout.png
    :width: 940


.. _HDF5: http://www.hdfgroup.org/HDF5/

.. _pandas: http://pandas.pydata.org/

------------------------------
Main Features
------------------------------

* **Novel tree container** `Trajectory`, for handling and managing of
  parameters and results of numerical simulations

* **Group** your parameters and results into meaningful categories

* Access data via **natural naming**, e.g. `traj.parameters.traffic.ncars`

* Automatic **storage** of simulation data into HDF5_ files via PyTables_

* Support for many different **data formats**

    * python native data types: bool, int, long, float, str, complex

    * list, tuple, dict

    * Numpy arrays and matrices

    * Scipy sparse matrices

    * pandas_ DataFrames

    * BRIAN_ quantities and monitors

* Easily **extendable** to other data formats!

* **Exploration** of the parameter space of your simulations

* **Merging** of *trajectories* residing in the same space

* Support for **multiprocessing**, *pypet* can run your simulations in parallel

* **Dynamic Loading**, load only the parts of your data you currently need

* **Resume** a crashed or halted simulation (maybe due to power shut down)

* **Annotate** your parameters, results and groups

* **Git Integration**, let *pypet* make automatic commits of your codebase


.. _pandas: http://pandas.pydata.org/

.. _BRIAN: http://briansimulator.org/

.. _GitPython: http://pythonhosted.org/GitPython/0.3.1/index.html

.. _HDF5: http://www.hdfgroup.org/HDF5/

.. _PyTables: http://www.pytables.org/moin/PyTables



