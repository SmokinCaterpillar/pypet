
.. _tutorial:

================
pypet Tutorial
================

--------------------------------------------
Conceptualization of A Numerical Experiment
--------------------------------------------

I will give a simple but comprehensive tutorial on *pypet* and how to use it for parameter
exploration of numerical experiments in python.

*pypet* is designed to support your numerical simulations in two ways: Allow
**a)** easy exploration of the parameter space of your simulations and **b)** easy storage of
the results.

We will assume that usually a numerical experiments consist of two to four different stages:

    1. Pre-processing
        a) Parameter definition
        b) Preparation of the experiment
    2. The *run phase* of your experiment
        Fan-out structure, usually parallel running of different parameter settings, and
        gathering of individual results for each single run
    3. Post-processing (optional)
        Cleaning up of the experiment, and sorting results
    4. Analysis of results (optional)
        Plotting, doing statistics etc.

The first stage can be further divided into two sub-stages.
In the beginning the definition of parameters (either directly in the source code
or by parsing a configuration file) and, next, the appropriate setup of your experiment.
This might involve creating particular python objects or pre-computing some expensive
functions etc. Moreover, here you also decide if you want to deviate from your default
set of parameters and explore the parameter space and try a bunch of different settings.
Probably you want to do a sensitivity analysis and determine the effect of changing
a critical subset of your parameters.

The second stage, the *run phase* is the actual execution of your numerical simulation.
Here, you perform the search or exploration of the parameter space. You try all
different parameter settings you have specified before for exploration and obtain the
corresponding results. Since this stage is most likely the computational expensive one, you
probably want to parallelize your simulations! I will refer to an individual simulation run
with one particular parameter combination as **single run** of your simulation.
Since these **single runs** are different individual simulation with different parameter
settings, they are completely independent of each other. The results and outcomes of
one **single run** should not influence another. Sticking to this assumption makes the
parallelization of your experiments much easier.

Thirdly, after all individual **single runs** are completed you might have a phase of post-processing.
This could encompass merging or collecting of results of individual single runs, or deconstructing some
sensitive python objects, etc.

Finally, you have a phase where you do further analysis of the results of your numerical
simulation. Like generating plots, etc. Personally, I would strictly separate this phase from
the first three. Thus, using a complete different python script than for the phases before, for example.

.. image:: figures/experiment_phases.png
    :width: 850


*pypet* gives is your tool to make stages 1a) and 2 much easier to handle. *pypet*
offers a novel tree data container called :class:`~pypet.trajectory.Trajectory`
that can be used to store all parameters and results of your numerical simulation.
Moreover, *pypet* has an :class:`~pypet.envrionemnt.Environment` that takes care about stage 2
and allows easy parallel exploration of the parameter space.

We will see how we can use both in our numerical experiment and the different stages.
In this tutorial we will simulate a simple neuron model. We will numerically integrate the
equation:

.. math::

    \frac{dV}{dt} = -\frac{1}{\tau_V} V + I


With an additional reset rule :math:`V \leftarrow 0` if :math:`V \geq 1` and we will have
an additional refractory period of :math:`\tau_{ref}`. This means if we detect a so called
action potential, i.e. :math:`V \geq V_T`, we will keep the voltage :math:`V` clamped at 0
for this period of time after the threshold crossing and freeze the differential equation.

Regarding parameter exploration, we will hold the
neuron's time constant :math:`\frac{1}{\tau_V}=10ms` fixed and explore the parameter space
by varying different input currents :math:`I` and different length of the refractory periods
:math:`\tau_{ref}`.

During the single runs, we will record the development of the variable
:math:`V` over time and count the number of threshold crossing to estimate the so called
firing rate of the neuron.
In the post processing phase we will collect these firing rates and write them into a pandas_
DataFrame to plot later on during the analysis the neuron's rate as a function of the
input current :math:`I`.
Don't worry if you are not familiar with pandas, basically a pandas_ DataFrame instantiates
a table, like a 2D numpy array, but we can index into the table by more than just integers.

-------------------
Naming convention
-------------------

To avoid confusion with natural naming scheme (see below)
and the functionality provided by the environment, trajectory,
parameter containers, and so on, I followed the idea by PyTables to use prefixes:
`f_` for functions and `v_` for python variables/attributes/properties.

For instance, given a *pypet* result conteiner `myresult`, `myresult.v_comment` is the object's
comment attribute and
`myresult.f_set(mydata=42)` is the function for adding data to the result container.
Whereas `myresult.mydata` might refer to a data item named `mydata` added by the user.

-------------------------
#1 Pre-processing
-------------------------

Your experiment usually starts with the creation of an :class:`~pypet.environment.Environment`.
Don't worry about the huge amount of parameters you can pass to the constructor,
these are more for tweaking of your experiment and the default settings are usually
suitable.

Yet, we will shortly discuss the most important ones here.

* `trajectory`

    Here you can either pass an already existing trajectory container or simply a string
    specifying the name of a new trajectory. The environment will create a trajectory
    container for you than.

* `add_time`

    If `True` and the environment creates a new trajectory container, it will add the current time
    to the name in the format *_XXXX_XX_XX_XXhXXmXXs*.
    So for instance if you set `trajectory='Gigawatts_Experiment'` and `add_time=true`,
    your trajectory's name will be `Gigawatts_Experiment_2015_10_21_04h23m00s`).

* `comment`

    A nice descriptive comment about what you are going to do in your experiment.

* `log_folder`

    The environment makes use of logging. You can specify a folder where all
    log-files should be stored. Default is `current_working_directory/logs/`.

* `log_level`

    The level of logging. For more information see the logging_ module.

* `log_stdout`:

    *pypet* will log all console output. So even if you don't use the logging module
    but simple `print` statements in your python script, *pypet* can write these statements
    into the log files if you enable `log_stdout`.

* `multiproc`

    If we want to use multiprocessing. We sure do so, so we set this to `True`.

* `ncores`

    The number of cpu cores we want to utilize. More precisely the number of processes we
    start at the same time to calculate the single runs. Btw, there's usually no benefit to
    setting this value higher than the actual number of cores your computer has.

* `filename`

    We can specify the name of the resulting HDF5 file where all data will be stored.
    We don't have to give a filename per se, we can also specify a folder `'./results/'` and
    the new file will have the name of the trajectory.

* `git_repository`

    If your code base is under git_ version control (it's not? Stop reading and get git_ NOW!),
    you can specify the path to your root git
    folder here. If you do this, *pypet* will a) trigger a new commit if it detects changes
    of in working copy of your code and b) write the corresponding commit code into
    your trajectory so you can immediately see with which version you did your experiments.

* `sumatra_project`

    If your experiments are recorded with sumatra_ you can specify the path to your sumatra_
    root folder here. *pypet* will automatically trigger the recording of your experiments
    if you use :func:`~pypet.environment.f_run`, :func:`~pypet.environment.f_continue` or
    :func:`~pypet.environment.f_pipeline` to start your single runs or whole experiment.
    If you use *pypet* + git_ + sumatra_ there's no doubt that you ensure
    the repeatability of your experiments!

Ok, so let's start with creating an environment:

.. code-block::python

    env = Environment(trajectory='FiringRate',
                      comment='Experiment to measure the firing rate '
                            'of a leaky integrate and fire neuron. '
                            'Exploring different input currents, '
                            'as well as refractory periods',
                      add_time=False, # We don't want to add the current time to the name,
                      log_folder='./logs/',
                      log_level=logging.INFO,
                      log_stdout=True,
                      multiproc=True,
                      ncores=2, #My laptop has 2 cores ;-)
                      filename='./hdf5/', # We only pass a folder here, so the name is chosen
                      # automatically to be the same as the Trajectory
                      )


The environment has created a new trajectory container for us:

.. code-block::python

    traj = env.v_trajectory

-------------------------
The Trajectory container
-------------------------

A :class:`~pypet.trajectory.Trajectory` is the container for your parameters and results.
It's basically instantiates a tree.

This tree hase four major branches: *config* (parameters), *parameters*,
*derived_parameters* and *results*.

Parameters stored under *config* do not specify the outcome of your simulations but
only the way how the simulations are carried out. For instance, this might encompass
the number of cpu cores for multiprocessing. In fact, the environment from above did add
the config data we specified before to the trajectory:

    >>> traj.config.multiproc
    True

Parameters in the *parameters* branch are the fundamental building blocks of your simulations.
Changing a parameter
usually effects the results you obtain in the end. The set of parameters should be
complete and sufficient to characterize a simulation. Running a numerical simulation
twice with the very same parameter settings should give also the very same results.

Derived parameters are specifications of your simulations that, as the name says, depend
on your original parameters but are still used to carry out your simulation.
They are somewhat too premature to be considered as final results.
We won't have any of these in the tutorial so you can ignore this branch for the moment.

Anything found under *results* is, as expected, a result of your numerical simulation.

^^^^^^^^^^^^^^^^^^^^^^^^
Adding of Parameters
^^^^^^^^^^^^^^^^^^^^^^^^

Ok, for the moment let's fill the trajectory with parameters for our simulation.

Let's fill it with parameters for our simulation using the
:func:`~pypet.naturalnaming.NNGroupNode.f_add_parameter` function:

.. code-block::python

    traj.f_add_parameter('neuron.V_init', 0.0,
                         comment='The initial condition for the '
                                    'membrane potential')
    traj.f_add_parameter('neuron.I', 0.0,
                         comment='The externally applied current.')
    traj.f_add_parameter('neuron.tau_V', 10.0,
                         comment='The membrane time constant in milliseconds')
    traj.f_add_parameter('neuron.tau_ref', 5.0,
                        comment='The refractory period in milliseconds '
                                'where the membrane potnetial '
                                'is clamped.')

    traj.f_add_parameter('simulation.duration', 1000.0,
                         comment='The duration of the experiment in '
                                'milliseconds.')
    traj.f_add_parameter('simulation.dt', 0.1,
                         comment='The step size of an Euler integration step.')


Again we can provide descriptive comments.
All these parameters will be added to the branch *parameters*.

Note that we can *group* the parameters. For instance, we have a group `neuron` that contains
parameters defining our neuron model and *simulation* that define the details of the simulation,
like the euler step size and the whole runtime.
These groups are created on the fly in the tree.

There's no limit to grouping, and it can be nested

    >>> traj.f_add_parameter('brian.hippocampus.nneurons', 99999, comment='Number of neurons in my model hippocampus')

Ok, this last parameter can be ignored, since we only model a single neuron.

There are analogue functions for *config* data, *results* and *derived_parameters*:

* :func:`~pypet.naturalnaming.NNGroupNode.f_add_config`
* :func:`~pypet.naturalnaming.NNGroupNode.f_add_result`
* :func:`~pypet.naturalnaming.NNGroupNode.f_add_derived_parameters`

If you don't want to stick to these four major branches there is the generic addition

* :func:`~pypet.naturalnaming.NNGroupNode.f_add_leaf`

Btw you can add particular groups directly with:

* :func:`~pypet.naturalnaming.NNGroupNode.f_add_parameter_group`
* :func:`~pypet.naturalnaming.NNGroupNode.f_add_config_group`
* :func:`~pypet.naturalnaming.NNGroupNode.f_add_result_group`
* :func:`~pypet.naturalnaming.NNGroupNode.f_add_derived_parameters_group`

and the generic one:

* :func:`~pypet.naturalnaming.NNGroupNode.f_add_group`

As said before the tree contains two types of nodes, group nodes
and leaf nodes. Group nodes can, as you have seen, contain other group or leaf nodes, whereas
leaf nodes are terminal and do not contain more groups or leaves.

The leaf nodes are abstract containers for your actual data. Basically,
there exist two sub-types of these leaves :class:`~pypet.parameter.Parameter`
containers for your config data and
parameters and :class:`~pypet.parameter.Result` for your results.

A :class:`~pypet.parameter.Parameter` can only contain a single data item plus potentially
a range or list of different values describing how the parameter should be explored in
different runs.

A :class:`~pypet.parameter.Result` container can manage several results. You can think of it
as non-nested dictionary. Actual data can also be accessed via natural naming or squared
brackets.

Both leaf containers (:class:`~pypet.parameter.Parameter`, :class:`~pypet.parameter.Result`)
support a rich variety of data types. There also exist also more specialized versions if the
standard ones cannot hold your data, just take
a look at :ref:`more-on-parameters`. Btw if you are still missing some functionality for
your particular needs you can simply
implement your own leaf containers and put them into the *trajectory*.


^^^^^^^^^^^^^^^^^^^^^^^^^
Accessing Data
^^^^^^^^^^^^^^^^^^^^^^^^^

Data can be accessed in several ways.

You can, for instance, access data via *natural naming*:
``traj.parameters.neuron.tau_ref`` or square brackets ``traj['parameters']['neuron']['tau_ref']``
or ``traj['parameters.neuron.tau_ref']``, or use the
:func:`~pypet.naturalnaming.NNGroupNode.f_get` method.

As long as your tree nodes are unique, you can shortcut through the tree. If there's only
one parameter `tau_ref`, ``traj.tau_ref`` is equivalent to ``traj.parameters.neuron.tau_ref``.

Moreover, since a :class:`~pypet.parameter.Parameter` only contains a single value (apart
from the range),
*pypet* will assume that you usually don't care about the actual container but just about
the data. Thus, ``traj.parameters.neuron.tau_ref`` will immediatly return the data value
for `tau_ref` and not the corresponding :class:`~pypet.parameter.Parameter` container.
To learn more about this *fast access* of data look at :ref:`more-on-access`.


^^^^^^^^^^^^^^^^^^^^^^^^
Exploring the Data
^^^^^^^^^^^^^^^^^^^^^^^^

Next, we can tell the trajectory which parameters we want to explore. We simply need
need to pass a dictionary of lists (or other iterables) of the **same length** with
arbitrary entries to
:func:`~pypet.trajectory.Trajectory.f_explore`.

Every single run in the run phase will contain one after the other the pairings of parameters
in the list. For instance, if our dictionary looks like
``{'x':[1,2,3], 'y':[1,1,2]}`` the first run will be with parameter `x` set to 1 and `y` to 1,
the second with `x` set to 2 and `y` set to 1 and the final third one with `x=3` and `y=2`.

If you want to explore the cartesion product of two iterables not having the same length
you can use the :func:`~pypet.utils.explore.cartesian_product` builder function.
This will return a dictionary of lists of the same length and all combinations of
the parameters.

Here is our exploration, we try dimensionless currents `I` from 0 to 1.5 in steps of 0.02 for three
different refractory periods `tau_ref`:

.. code-block::python

    explore_dict = {'neuron.I': np.arange(0, 1.5, 0.02).tolist(),
                    'neuron.tau_ref': [5.0, 7.5, 10.0]}

    explore_dict = cartesian_product(explore_dict, ('neuron.tau_ref', 'neuron.I'))
    # The second argument, the tuple, specifies the order of the cartesian product,
    # The variable on the right most side changes fastest and defines the
    # 'inner for-loop' of the cartesian product

    traj.f_explore(explore_dict)


Note that in case we explore some parameters their default values that we passed before
via :func:`~pypet.naturalnaming.NNGroupNode.f_add_parameter` are no longer used.
If you still want to simulate these, make sure they are part of the lists in the
exploration dictionary.

-------------------------
#2 The Run Phase
-------------------------

Next, we define a job or top-level simulation function (that
not necessarily has to be a real python function, any callable object will do the job).
This function will be called and executed with every parameter combination we specified before
with :func:`~pypet.trajectory.Trajectory.f_explore` in
the trajectory, as in the figure above indicated by the *fan-out* structure.

We will have 225 different runs of our simulation and each run has particual index
rainging from 0 to 224 and a particular name that follows the structure `run_XXXXXXXX`
where `XXXXXXXX` is replaced with the index and some trailing zeros. Our runs will have the
names `run_00000000` tp `run_00000224`.

To emphasize this, we start counting with 0, so the second run is called
`run_00000001` and has index 1!

So here is our top-level simulation function:

.. code-block::python

    def run_neuron(traj):
        """Runs a simulation of a model neuron.

        :param traj:

            Container with all parameters.

        :return:

            An estimate of the firing rate of the neuron

        """

        # Extract all parameters from `traj`
        V_init = traj.par.neuron.V_init
        I = traj.par.neuron.I
        tau_V = traj.par.neuron.tau_V
        tau_ref = traj.par.neuron.tau_ref
        dt = traj.par.simulation.dt
        duration = traj.par.simulation.duration

        steps = int(duration / float(dt))
        # Create some containers for the Euler integration
        V_array = np.zeros(steps)
        V_array[0] = V_init
        spiketimes = []

        # Do the Euler integration:
        print 'Starting Euler Integration'
        for step in range(1, steps):
            if V_array[step-1] >= 1:
                # The membrane potential crossed the threshold and we mark this as
                # an action potential
                V_array[step] = 0
                spiketimes.append((step-1)*dt)
            elif spiketimes and step * dt - spiketimes[-1] <= tau_ref:
                # We are in the refractory period, so we simply clamp the voltage
                # to 0
                V_array[step] = 0
            else:
                # Euler Integration step:
                dV = -1/tau_V * V_array[step-1] + I
                V_array[step] = V_array[step-1] + dV*dt

        print 'Finished Euler Integration'

        # Add the voltage trace and spike times
        traj.f_add_result('neuron.$', V=V_array, nspikes=len(spiketimes),
                      comment='Contains the development of the membrane potential over time '
                              'as well as the number of spikes.')
        # This result will be renamed to `traj.results.neuron.run_XXXXXXXX`.


        # And finally we return the estimate of the firing rate
        return len(spiketimes) / float(traj.par.simulation.duration) *1000
        # *1000 since we have defined duration in terms of milliseconds




Our function has to except at least one argument and this is our `traj` container.
To be precise here the `traj` variable here refers no longer to the full
:class:`~pypet.trajectory.Trajectory` but instead is a
:class:`~pypet.trajectory.SingleRun` container. The differences are rather small. This
type of container has a little less functionality than a full :class:`~pypet.trajectory.Trajectory`
and all explored parameters are set to the values for this particular run.
Thus, if we currently execute the second run (aka `run_00000001`)
all parameters will contain their default values, except `tau_ref` and `I`, they will
be set to 5.0 and 0.02, respectively.
For simplicity, I will stick to the variable name `traj` here.

Let's take a look at the first few instructions

.. code-block::python

    # Extract all parameters from `traj`
    V_init = traj.par.neuron.V_init
    I = traj.par.neuron.I
    tau_V = traj.par.neuron.tau_V
    tau_ref = traj.par.neuron.tau_ref
    dt = traj.par.simulation.dt
    duration = traj.par.simulation.duration


So here we will simply extract the parameter values from `traj`.
As said before *pypet* is smart to directly return the data value instead of
a :class:`~pypet.parameter.Parameter` container. Moreover, remember all parameters
will have their default values except `tau_ref` and `I`.

Next, we create a numpy array and a python list and compute the number of steps. This is
not specific to *pypet* but simply needed for our neuron simulation:

.. code-block::python

    steps = int(duration / float(dt))
    # Create some containers for the Euler integration
    V_array = np.zeros(steps)
    V_array[0] = V_init
    spiketimes = []


Also the following steps have nothing to do with *pypet*, so don't worry if you not
fully understand what's going on here.
This is the core of our neuron simulation:

.. code-block::python

    # Do the Euler integration:
    print 'Starting Euler Integration'
    for step in range(1, steps):
        if V_array[step-1] >= 1:
            # The membrane potential crossed the threshold and we mark this as
            # an action potential
            V_array[step] = 0
            spiketimes.append((step-1)*dt)
        elif spiketimes and step * dt - spiketimes[-1] <= tau_ref:
            # We are in the refractory period, so we simply clamp the voltage
            # to 0
            V_array[step] = 0
        else:
            # Euler Integration step:
            dV = -1/tau_V * V_array[step-1] + I
            V_array[step] = V_array[step-1] + dV*dt

    print 'Finished Euler Integration'

That is simply the python description of the following set of equations:

.. math::

    \frac{dV}{dt} = -\frac{1}{\tau_V} V + I

and :math:`V \leftarrow 0 \text{if} V \geq 1 \ŧext{or} t-t_s \leq \ŧau_{ref}`.

Ok now we have finished one particular run ouf our simulation. We computed the development
of the membrane potential `V` over time and put it in `V_array`.

Next, we hand over this data to our trajectory, since we want to keep them and write them
into the final HDF5 file:

.. code-block::python

    traj.f_add_result('neuron.$', V=V_array, nspikes=len(spiketimes),
                      comment='Contains the development of the membrane potential over time '
                              'as well as the number of spikes.')


This statement looks similar to the addition of parameters we had before. Yet, there
are some subtle differences. As we can see, a result can contain several data items.
If we pass them via `NAME=value`, we can later on recall them from the result with `result.NAME`.
Secondly there is this odd `'$'` character in the name.
Well, recall that we are currently operating in the run phase, accordingly the `run_neuron`
function will be executed many times. Accordingly, we also gather the
data `V_array` data many times. Hence,
we need to store this every time under a different
name in our trajectory tree. `'$'` is a wildcard character that is replaced by the name
of the current run. Thus, if we were in the second run, we would store everything under
`traj.results.neuron.run_00000001` and the in the third run under
`traj.results.neuron.run_00000002` and so on and so forth.
Consequently, `traj.results.neuron.run_00000001.V` will return our membrane voltage array
of the second run.


You are not limited to place the `'$'` at the end, for example:

.. code-block::python

   traj.f_add_result('fundamental.wisdom.$.answer', 42, comment='The answer')

would be possible as well.

As a side remark, if you add a result or derived parameter during the run phase but
**not** use the `'$'` wildcard. *pypet* will add `runs.'$'` to the beginning of your
result or derived parameter name.

So executing the following statement during the run phase

.. code-block::python

    traj.f_add_result('fundamental.wisdom.answer', 42, comment='The answer')

will yield a renaming to `results.runs.run_XXXXXXXXX.fundamental.wisdom.answer`.
Where `run_XXXXXXXXX` is the name of the corresponding run, of course.

Moreover, it's worth noticing that you don't have to explicitly write the trajectory to disk.
Everything you add during pre-processing, post-processing (see below) is
automatically stored at
the end of the experiment. Everything you add
during the run phase under a group node called `run_XXXXXXXX` (where this is the name of the
current run) will be stored at the end of this particular run.

-------------------
#3 Post-processing
-------------------

Each single run of our `run_neuron` function returned an estimate of the firing rate.
In the post processing phase we want to collect these estimates and sort them into a
table according to the value of `I` and `tau_ref. As an appropriate table we choose a
pandas_ DataFrame. Again this is not *pypet* specific but pandas_ offers neat
containers for series data, tables and multidimensional panel data.
The neat thing about pandas_ containers is, that they except all forms of indices, and not
only integer indices like python lists or numpy arrays.

So this is our post processing function, it has to take at least two arguments.
First one is the trajectory, second one is the list of results.
This list actually contains two-dimensional tuples. First entry of the tuple is the index
of the run as an integer, and second entry is the result returned by our job-function
`run_neuron` in the corresponding run. Be aware that since we use multiprocessing,
the list is not ordered according to the run indices, but according to the time the
single runs did finish.


.. code-block::python

    def neuron_postproc(traj, result_list):
        """Postprocessing, sorts computed firing rates into a table

        :param traj:

            Container for results and parameters

        :param result_list:

            List of tuples, where first entry is the run index and second is the actual
            result of the corresponding run.

        :return:
        """

        # Let's create a pandas DataFrame to sort the computed firing rate according to the
        # parameters. We could have also used a 2D numpy array.
        # But a pandas DataFrame has the advantage that we can index into directly with
        # the parameter values without translating these into integer indices.
        I_range = traj.par.neuron.f_get('I').f_get_range()
        ref_range = traj.par.neuron.f_get('tau_ref').f_get_range()

        I_index = sorted(set(I_range))
        ref_index = sorted(set(ref_range))
        rates_frame = pd.DataFrame(columns=ref_index, index=I_index)
        # This frame is basically a two dimensional table that we can index with our
        # parameters

        # Now iterate over the results. The result list is a list of tuples, with the
        # run index at first position and our result at the second
        for result_tuple in result_list:
            run_idx = result_tuple[0]
            firing_rates = result_tuple[1]
            I_val = I_range[run_idx]
            ref_val = ref_range[run_idx]
            rates_frame.loc[I_val, ref_val] = firing_rates # Put the firing rate into the
            # data frame

        # Finally we going to store our new firing rate table into the trajectory
        traj.f_add_result('summary.firing_rates', rates_frame=rates_frame,
                          comment='Contains a pandas data frame with all firing rates.')


Ok, we will go through it one by one.
At first we extract the range of parameters we used:

.. code-block::python



.. _logging: https://docs.python.org/2/library/logging.html

.. _git: http://git-scm.com/

.. _sumatra: http://neuralensemble.org/sumatra/

.. _pandas: http://pandas.pydata.org/