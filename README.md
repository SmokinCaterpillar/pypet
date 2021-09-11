# pypet

[![Travis Build Status](https://travis-ci.com/SmokinCaterpillar/pypet.svg?branch=master)](https://travis-ci.com/SmokinCaterpillar/pypet)
[![Appveyor Build status](https://ci.appveyor.com/api/projects/status/9amhj3iyf105xa2y/branch/master?svg=true)](https://ci.appveyor.com/project/SmokinCaterpillar/pypet/branch/master)
[![Coverage Status](https://coveralls.io/repos/github/SmokinCaterpillar/pypet/badge.svg?branch=master)](https://coveralls.io/github/SmokinCaterpillar/pypet?branch=master)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/bdc483ee47304b97a334bb2922d83e8f)](https://www.codacy.com/gh/SmokinCaterpillar/pypet/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=SmokinCaterpillar/pypet&amp;utm_campaign=Badge_Grade)
[![PyPI version](https://badge.fury.io/py/pypet.svg)](https://badge.fury.io/py/pypet)
[![Documentation Status](https://readthedocs.org/projects/pypet/badge/?version=latest)](http://pypet.readthedocs.io/en/latest/?badge=latest)

The new python parameter exploration toolkit:
*pypet* manages exploration of the parameter space
of any numerical simulation in python,
thereby storing your data into HDF5 files for you.
Moreover, *pypet* offers a new data container which
lets you access all your parameters and results
from a single source. Data I/O of your simulations and
analyses becomes a piece of cake!


## Requirements

Python 3.7 or higher and

* tables >=  3.5.0

* pandas >= 1.0.0

* numpy >= 1.16.0

* scipy >= 1.3.0

* HDF5 >= 1.10.0


There are also some optional packages that you can but do not have to install.

If you want to combine *pypet* with SCOOP you need

* scoop >= 0.7.1

For git integration you additionally need

* GitPython >= 3.1.3

To utilize the cap feature for multiprocessing you need

* psutil >= 5.7.0

To utilize the continuing of crashed trajectories you need

* dill >= 0.3.1

Automatic Sumatra records are supported for

* Sumatra >= 0.7.1


## Python 2.7

This release no longer supports Python 2.7.
If you are still using Python 2.7, you need to
use the pypet legacy version 0.3.0 (https://pypi.python.org/pypi/pypet/0.3.0).


# What is pypet all about?

Whenever you do numerical simulations in science, you come across two major challenges.
First, you need some way to save your data. Secondly, you extensively explore the parameter space.
In order to accomplish both you write some hacky I/O functionality to get it done the quick and
dirty way. This means storing stuff into text files, as *MATLAB* *m*-files, 
or whatever comes in handy.

After a while and many simulations later, you want to look back at some of your very
first results. But because of unforeseen circumstances, you changed a lot of your code.
As a consequence, you can no longer use your old data, but you need to write a hacky
converter to format your previous results to your new needs.
The more complexity you add to your simulations, the worse it gets, and you spend way
too much time formatting your data than doing science.

Indeed, this was a situation I was confronted with pretty soon at the beginning of my PhD.
So this project was born. I wanted to tackle the I/O problems more generally and produce code
that was not specific to my current simulations, but I could also use for future scientific
projects right out of the box.

The python parameter exploration toolkit (*pypet*) provides a framework to define *parameters*
that you need to run your simulations. You can actively explore these by following a
*trajectory* through the space spanned by the parameters.
And finally, you can get your *results* together and store everything appropriately to disk.
The storage format of choice is HDF5 (http://www.hdfgroup.org/HDF5/) via PyTables
(http://www.pytables.org/).


## Package Organization

This project encompasses these core modules:

*  The `pypet.environment` module for handling the running of simulations

*  The `pypet.trajectory` module for managing the parameters and results,
   and providing a way to *explore* your parameter space. Somewhat related is also the
   `pypet.naturalnaming` module, that provides functionality to access and put data into
   the *trajectory*.

*  The `pypet.parameters` module including containers for parameters and results

*  The `pypet.storageservice` for saving your data to disk


## Install

If you don't have all prerequisites (*numpy*, *scipy*, *tables*, *pandas*) install them first.
These are standard python packages, so chances are high that they are already installed.
By the way, in case you use the python package manager ``pip``
you can list all installed packages with ``pip freeze``.

Next, simply install *pypet* via ``pip install pypet``

**Or**

The package release can also be found on https://pypi.python.org/pypi/pypet. Download, unpack
and ``python setup.py install`` it.

**Or**

In case you use **Windows**, you have to download the tar file from https://pypi.python.org/pypi/pypet 
and unzip it. Next, open a windows terminal
and navigate to your unpacked *pypet* files to the folder containing the `setup.py` file.
As above run from the terminal ``python setup.py install``.


## Documentation and Support

Documentation can be found on http://pypet.readthedocs.org/.

If you have any further questions feel free to contact me at **robert.meyer (at) alcemy.tech**.


## Main Features

* **Novel tree container** `Trajectory`, for handling and managing of
  parameters and results of numerical simulations

* **Group** your parameters and results into meaningful categories

* Access data via **natural naming**, e.g. `traj.parameters.traffic.ncars`

* Automatic **storage** of simulation data into HDF5 files via PyTables

* Support for many different **data formats**

    * python native data types: bool, int, long, float, str, complex

    * list, tuple, dict

    * Numpy arrays and matrices

    * Scipy sparse matrices

    * pandas DataFrames (http://pandas.pydata.org/)

    * BRIAN2 quantities and monitors (http://briansimulator.org/)

* Easily **extendable** to other data formats!

* **Exploration** of the parameter space of your simulations

* **Merging** of *trajectories* residing in the same space

* Support for **multiprocessing**, *pypet* can run your simulations in parallel

* **Analyse** your data on-the-fly during multiprocessing

* **Adaptively** explore tha parameter space combining *pypet* with optimization
  tools like the evolutionary algorithms framework DEAP (http://deap.readthedocs.org/en/)

* **Dynamic Loading**, load only the parts of your data you currently need

* **Resume** a crashed or halted simulation

* **Annotate** your parameters, results and groups

* **Git Integration**, let *pypet* make automatic commits of your codebase

* **Sumatra Integration**, let *pypet* add your simulations to the *electronic lab notebook* tool
  Sumatra (http://neuralensemble.org/sumatra/)
  
* *pypet* can be used on **computing clusters** or multiple servers at once if it is combined with
  SCOOP (http://scoop.readthedocs.org/)


# Quick Working Example

The best way to show how stuff works is by giving examples. I will start right away with a
very simple code snippet.

Well, what we have in mind is some sort of numerical simulation. For now we will keep it simple,
let's say we need to simulate the multiplication of 2 values, i.e. `z=x*y`.
We have two objectives, a) we want to store results of this simulation `z` and
b) we want to explore the parameter space and try different values of `x` and `y`.

Let's take a look at the snippet at once:

```python
from pypet import Environment, cartesian_product

def multiply(traj):
    """Example of a sophisticated simulation that involves multiplying two values.

    :param traj:

        Trajectory containing the parameters in a particular combination,
        it also serves as a container for results.

    """
    z=traj.x * traj.y
    traj.f_add_result('z',z, comment='I am the product of two values!')

# Create an environment that handles running our simulation
env = Environment(trajectory='Multiplication',filename='./HDF/example_01.hdf5',
                    file_title='Example_01',
                    comment = 'I am the first example!')

# Get the trajectory from the environment
traj = env.trajectory

# Add both parameters
traj.f_add_parameter('x', 1.0, comment='Im the first dimension!')
traj.f_add_parameter('y', 1.0, comment='Im the second dimension!')

# Explore the parameters with a cartesian product
traj.f_explore(cartesian_product({'x':[1.0,2.0,3.0,4.0], 'y':[6.0,7.0,8.0]}))

# Run the simulation with all parameter combinations
env.run(multiply)
```

And now let's go through it one by one. At first we have a job to do, that is multiplying two
values:

```python
def multiply(traj):
    """Example of a sophisticated simulation that involves multiplying two values.

    :param traj:

        Trajectory containing the parameters in a particular combination,
        it also serves as a container for results.

    """
    z=traj.x * traj.y
    traj.f_add_result('z',z, comment='I am the product of two values!')
```

This is our simulation function `multiply`. The function uses a so called *trajectory*
container which manages our parameters. We can access the parameters simply by natural naming,
as seen above via `traj.x` and `traj.y`. The value of `z` is simply added as a result
to the `traj` object.

After the definition of the job that we want to simulate, we create an environment which
will run the simulation.

```python
# Create an environment that handles running our simulation
env = Environment(trajectory='Multiplication',filename='./HDF/example_01.hdf5',
                    file_title='Example_01',
                    comment = 'I am the first example!')
```

The environment uses some parameters here, that is the name of the new trajectory, a filename to
store the trajectory into, the title of the file, and a comment that is added to the trajectory. 
There are more options available like the number of processors for multiprocessing or 
how verbose the final HDF5 file is supposed to be.
Check out the documentation (http://pypet.readthedocs.org/) if you want to know more.
The environment will automatically generate a trajectory for us which we can access via:

```python
# Get the trajectory from the environment
traj = env.trajectory
```

Now we need to populate our trajectory with our parameters. They are added with the default values
of `x=y=1.0`.

```python
# Add both parameters
traj.f_add_parameter('x', 1.0, comment='Im the first dimension!')
traj.f_add_parameter('y', 1.0, comment='Im the second dimension!')
```

Well, calculating `1.0 * 1.0` is quite boring, we want to figure out more products, that is
the results of the cartesian product set `{1.0,2.0,3.0,4.0} x {6.0,7.0,8.0}`.
Therefore, we use `f_explore` in combination with the builder function
`cartesian_product`.

```python
# Explore the parameters with a cartesian product
traj.f_explore(cartesian_product({'x':[1.0,2.0,3.0,4.0], 'y':[6.0,7.0,8.0]}))
```

Finally, we need to tell the environment to run our job `multiply` with all parameter
combinations.

```python
# Run the simulation with all parameter combinations
env.run(multiply)
```

And that's it. The environment will evoke the function `multiply` now 12 times with
all parameter combinations. Every time it will pass a `traj` container with another one of these
12 combinations of different `x` and `y` values to calculate the value of `z`.
Moreover, the environment and the storage service will have taken care about the storage
of our trajectory  - including the results we have computed - into an HDF5 file.

So have fun using this tool!

Cheers,
    Robert


# Miscellaneous

## Acknowledgements

*   Thanks to Robert Pröpper and Philipp Meier for answering all my Python questions

    You might want to check out their SpykeViewer (https://github.com/rproepp/spykeviewer)
    tool for visualization of MEA recordings and NEO (http://pythonhosted.org/neo) data

*   Thanks to Owen Mackwood for his SNEP toolbox which provided the initial ideas
    for this project
    
*   Thanks to Mehmet Nevvaf Timur for his work on the SCOOP integration and the ``'NETQUEUE'`` feature

*   Thanks to Henri Bunting for his work on the BRIAN2 subpackage

*   Thanks to the BCCN Berlin (http://www.bccn-berlin.de),
    the Research Training Group GRK 1589/1, and the
    Neural Information Processing Group ( http://www.ni.tu-berlin.de) for support


## Tests

Tests can be found in `pypet/tests`.
Note that they involve heavy file I/O and you need privileges
to write files to a temporary folder.
The tests suite will make use of the `tempfile.gettempdir()` function to
create such a temporary folder.

Each test module can be run individually, for instance `$ python trajectory_test.py`.

You can run **all** tests with `$ python all_tests.py` which can also be found under
`pypet/tests`.
You can pass additional arguments as `$ python all_tests.py -k --folder=myfolder/`
with `-k` to keep the HDF5 and log files created by the tests 
(if you want to inspect them, otherwise they will be deleted after the completed tests),
and `--folder=` to specify a folder where to store the HDF5 files instead of the temporary one.
If the folder cannot be created, the program defaults to `tempfile.gettempdir()`.

Running all tests can take up to 20 minutes. The test suite encompasses more than **1000** tests
and has a code coverage of about **90%**!

Moreover, *pypet* is constantly tested with Python 3.7 and 3.8 for **Linux** using
Travis-CI. Testing for **Windows** platforms is performed via Appveyor.
The source code is available at https://github.com/SmokinCaterpillar/pypet/.


## License

BSD, please read LICENSE file.


## Legal Notice

*pypet* was created by Robert Meyer at the Neural Information Processing Group (TU Berlin),
supported by the Research Training Group GRK 1589/1.


## Contact

**robert.meyer (at) alcemy.tech**

alcemy GmbH

Choriner Str. 83

10119 Berlin, Germany
