=========
pyPET
=========

The new python parameter exploration toolbox. pyPET manages exploration of the parameter space and
data storage for you. Currently supported storage is HDF5!

--------------------------------
What is pyPET all about?
--------------------------------


Whenever you do numerical simulations in science, you come across two major problems.
First, you need some way to save your data. Secondly, you extensively explore the parameter space.
In order to accomplish both you write some hacky IO functionality to get it done the quick and
dirty way. Storing stuff into text files, as MATLAB m-files, or whatever comes in handy.

After a while and many simulations later, you want to look back at some of your very
first results. But because of
unforeseen circumstances, you changed lots of your code. As a consequence, you can no longer
use your old data, but you need to write a hacky converter to format your previous results
to your new needs.
The more complexity you add to your simulations, the worse it gets, and you spend way
too much time handling your data and results than doing science.

Indeed, this was a situation I was confronted with pretty quickly during my PhD.
So this project was born. I wanted to tackle the IO problems more generally and produce code
that was not specific to my current simulations, but I could also use for future scientific
projects right out of the box.

The python parameter exploration toolkit (*pyPET*) provides a framework to define *parameters* that
you need to run your simulations.
You can actively explore these by following a *trajectory* through the space spanned
by the parameters.
And finally, you can get your results together and store everything appropriately to disk.
Currently the storage method of choice is HDF5.


---------------------------
Organization
---------------------------

This project encompasses these core modules:

 *  The :mod:`pypet.parameters` module including  containers for parameters and results,

 *  The :mod:`pypet.trajectory` module for managing the parameters and results,
    and providing a way to *explore* your parameter space. Somewhat related is also the
    `pypet.naturalnaming` module, that provides functionality to access and put data into
    the *trajectory*.

 *  The :mod:`pypet.environment` module for handling the running of simulations.

 *  The :mod:`pypet.storageservice` for saving your data to disk.


---------------------------
Documentation
---------------------------

Link to the Docs will come soon!

---------------------------
Quick Working Example
---------------------------

The best way to show how stuff works is by giving examples. I will start right away with a
very simple code snippet.

Well, what we have in mind is some sort of numerical simulation. For now we will keep it simple,
let's say we need to simulate the multiplication of 2 values, i.e. :math:`z=x*y`
We have two objectives, a) we want to store results of this simulation :math:`z` and
b) we want to _explore the parameter space and try different values of :math:`x` and :math:`y`.

Let's take a look at the snippet at once:



    from pypet.environment import Environment
    from pypet.utils.explore import cartesian_product


    def multiply(traj):
        z=traj.x*traj.y
        traj.f_add_result('z',z=z, comment='Im the product of two reals!')


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
    env.run(multiply)



And now let's go through it one by one. At first we have a job to do, that is multiplying two real
values:



    def multiply(traj):
        z=traj.x * traj.y
        traj.f_add_result('z',z=z)

This is our function multiply. The function gets a so called :class:`~pypet.trajectory.Trajectory`
container which manages our parameters. We can access the parameters simply by natural naming,
as seen above via `traj.x` and `traj.y`. The result `z` is simply added as a result to the `traj` object.

After the definition of the job that we want to simulate, we create an environment which
will run the simulation.



    # Create an environment that handles running
    env = Environment(trajectory='Example1_01',filename='./HDF/example_01.hdf5',
                      file_title='Example_01', log_folder='./LOGS/',
                      comment = 'I am the first example!')


The environment uses some parameters, that is the name of the new trajectory, a filename to
store the trajectory into, the title of the file, a folder for the log files, and a
comment that is added to the trajectory.
The environment will automatically generate a trajectory for us which we can access via:


    # Get the trajectory from the environment
    traj = env.v_trajectory

Now we need to populate our trajectory with our parameters. They are added with the default values
of :math:`x=y=1.0`



    # Add both parameters
    traj.f_add_parameter('x', 1.0, comment='Im the first dimension!')
    traj.f_add_parameter('y', 1.0, comment='Im the second dimension!')

Well, calculating :math:`1.0*1.0` is quite boring, we want to figure out more products, that is
the results of the cartesian product set :math:`\{1.0,2.0,3.0,4.0\} \times \{6.0,7.0,8.0\}`.
Therefore we use :func:`~pypet.trajectory.Trajectory.explore` in combination with the builder function
:func:`~pypet.utils.explore.cartesian_product`.

Finally, we need to tell the environment to run our job `multiply`



    # Run the simulation
    env.run(multiply)

And that's it. The environment and the storage service will have taken care about the storage
of our trajectory and the results we have computed.

So have fun using this tool!

Cheers,
Robert