================================
What is P37 all about?
================================

Whenever you do numerical simulations in science, you come across two major problems.
First, you need some way to save your data. Secondly, you extensively explore the parameter space.
In order to accomplish both you write some hacky IO functionality to get it done the quick and
dirty way. Storing stuff into text files, as MATLAB m-files, or whatever comes in handy.

After a while and many simulations later, you want to look back at some of your very
first results. But because of
unforeseen circumstances you changed lots of your code. As a consequence, you can no longer
use your old data, but you need to write a hacky converter to format your previous results
to your new needs.
The more complexity you add to your simulations, the worse it gets, and you spend way
too much time handling your data and results than doing science.

Indeed, this was a situation I was confronted with pretty quickly during my PhD.
So this project was born. I wanted to tackle the IO problems more generally and produce code
that was not specific to my current simulations, but I could also use for future scientific
projects right out of the box.

This toolset provides a framework to define *parameters* that you need to run your simulations.
You can actively explore these by following a *trajectory* through the space spanned
by the parameters.
And finally, you can get your results together and store everything appropriately to disk.
Currently the storage method of choice is _HDF5.

.. HDF5: http://www.hdfgroup.org/HDF5/


==============================
Getting Started
==============================

This project encompasses four core modules:

 *  The :mod:`mypet.parameters` module including  containers for parameters and results,

 *  The :mod:`mypet.trajectory` module for managing the parameters and results,
    and providing a way to *_explore* your parameter space. Somewhat related is also the
    `mypet.naturalnaming` module, that provides functionality to access and put data into
    the *trajectory*.

 *  The :mod:`mypet.environment` module for handling the running of simulations.

 *  The :mod:`mypet.storageservice` for saving your data to disk. If you are satisfied with
    the given service to store everything into HDF5 files, you do not need to worry about this
    at all.

--------------------------------
Quick (and not so Dirty) Example
--------------------------------

The best way to show how stuff works is by giving examples. I will start right away with a
very simple code snippet.

Well, what we have in mind is some sort of simulation. For now we will keep it simple,
let's say we need to simulate the multiplication of 2 values, i.e. :math:`z=x*y`
We have two objectives, a) we want to store results of this simulation :math:`z` and
b) we want to _explore the parameter space and try different values of :math:`x` and :math:`y`.

Let's take a look at the snippet at once:

.. code-block:: python

    from mypet.environment import Environment
    from mypet.utils.explore import cartesian_product


    def multiply(traj):
        z=traj.x*traj.y
        traj.f_add_result('z',z=z, comment='Im the product of two reals!')


    # Create and environment that handles running
    env = Environment(trajectory='Example1_No1',filename='./HDF/example1_quick_and_dirty.hdf5',
                      file_title='ExampleNo1', log_folder='./LOGS/')

    # Get the trajectory from the environment
    traj = env.get_trajectory()

    # Add both parameters
    traj.f_add_parameter('x', 1.0, comment='Im the first dimension!')
    traj.f_add_parameter('y', 1.0, comment='Im the second dimension!')

    # Explore the parameters with a cartesian product:
    traj.f_explore(cartesian_product({'x':[1.0,2.0,3.0,4.0], 'y':[6.0,7.0,8.0]}))

    # Run the simulation
    env.run(multiply)



And now let's go through it one by one. At first we have a job to do, that is multiplying two real
values:

.. code-block:: python

    def multiply(traj):
        z=traj.x * traj.y
        traj.f_add_result('z',z=z)

This is our function multiply. The function gets a so called :class:`~mypet.trajectory.Trajectory`
container which manages our parameters. We can access the parameters simply by natural naming,
as seen above via `traj.x` and `traj.y`. The result `z` is simply added as a result to the `traj` object.

After the definition of the job that we want to simulate, we create an environment which
will run the simulation.

.. code-block:: python

    # Create and environment that handles running
    env = Environment(trajectory='Example1_01',filename='./HDF/example_01.hdf5',
                      file_title='Example_01', log_folder='./LOGS/',
                      comment = 'I am the first example!')


The environment uses some parameters, that is the name of the new trajectory, a filename to
store the trajectory into, the title of the file, a folder for the log files, and a
comment that is added to the trajectory.
The environment will automatically generate a trajectory for us which we can access via:


..code-block::python

    # Get the trajectory from the environment
    traj = env.get_trajectory()

Now we need to populate our trajectory with our parameters. They are added with the default values
of :math:`x=y=1.0`

.. code-block:: python

    # Add both parameters
    traj.f_add_parameter('x', 1.0, comment='Im the first dimension!')
    traj.f_add_parameter('y', 1.0, comment='Im the second dimension!')

Well, calculating :math:`1.0*1.0` is quite boring, we want to figure out more products, that is
the results of the cartesian product set :math:`\{1.0,2.0,3.0,4.0\} \times \{6.0,7.0,8.0\}`.
Therefore we use :func:`~mypet.trajectory.Trajectory.explore` in combination with the builder function
:func:`~mypet.utils.explore.cartesian_product`.

Finally, we need to tell the environment to run our job `multiply`

.. code-block:: python

    # Run the simulation
    env.run(multiply)

And that's it. If we now inspect the new hdf5 file in `examples/HDF/example_01.hdf5`,
we will see that our results have been stored right in there, and, of course, the trajectory with
our parameters is included, too.

.. image:: /figures/example_01.png
