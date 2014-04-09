
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
        Fan-out structure, usually parallel running of different parameter settings,
        gathering of individual results for each single run
    3. Post-processing (optional)
        Cleaning up of the experiment
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

    \frac{dV}{dt} = -\frac{1}{\tau_V} + I


With an additional reset rule :math:`V \leftarrow 0` if :math`V \geq 1` and we will have
an additional refractory period of :math:`\tau_{ref}`. This means if we detect a so called
action potential, i.e. math:`V \geq V_T`, we will keep the voltage :math:`V` clamped at 0
for this period of time after the threshold crossing and freeze the differential equation.
We will keep the
neuron's time constant :math:`\frac{1}{\tau_V}=10ms` fixed and explore the parameter space
by varying different input currents :math:`I` and different length of the refractory periods
:math:`\tau_{ref}`. During the single runs, we will record the development of the variable
:math:`V` over time and count the number of threshold crossing to estimate the so called
firing rate of the neuron.
In the post processing phase we will collect these firing rates and write them into a numpy
array to compute a 2D heat map of firing rates depending on the input current and the refractory
period.



^^^^^^^^^^^^^^^^^^^
Naming convention
-------------------------

To avoid confusion with natural naming scheme (see below)
and the functionality provided by the environemnt, trajectory,
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


.. _logging: https://docs.python.org/2/library/logging.html

.. _git: http://git-scm.com/

.. _sumatra: http://neuralensemble.org/sumatra/

-------------------------
The Trajectory container
-------------------------

A :class:`~pypet.trajectory.Trajectory` is the container for your parameters and results.
It's basically instantiates a tree and data can be accessed in several ways. Let's assume
we already have a trajectory container called `traj` with some nested data in it.

You can, for instance, access data via *natural naming*:
``traj.parameters.neuron.tau_ref`` or square brackets ``traj['parameters']['neuron']['tau_ref']``
or ``traj['parameters.neuron.tau_ref']``, or use the
:func:`~pypet.naturalnaming.NNGroupNode.f_get` method.

As long as your tree nodes are unique, you can shortcut through the tree. If there's only
one parameter `tau_ref`, ``traj.tau_ref`` is equivalent to ``traj.parameters.neuron.tau_ref``.

The tree contains two types of nodes, group nodes
(here for example `parameters`, `neuron`) and leaf nodes
(here `tau_ref`). Group nodes can, as you have seen, contain other group or leaf nodes, whereas
leaf nodes are terminal and do not contain more groups or leaves.
The leaf nodes are abstract containers for your actual data. Basically,
there exist two sub-types of these leaves :class:`~pypet.parameter.Parameter`
containers for your config data and
parameters and :class:`~pypet.parameter.Result` for your results.

A :class:`~pypet.parameter.Parameter` can only contain a single data item plus potentially
a range or list of different values describing how the parameter should be explored in
different runs.

Moreover, since a :class:`~pypet.parameter.Parameter` only contains a single value (apart
from the range),
*pypet* will assume that you usually don't care about the actual container but just about
the data. Thus, ``traj.parameters.neuron.tau_ref`` will immediatly return the data value
for `tau_ref` and not the corresponding :class:`~pypet.parameter.Parameter` container.

A :class:`~pypet.parameter.Result` container can manage several results. You can think of it
as non-nested dictionary. Actual data can also be accessed via natural naming or squared
brackets.

Both leaf containers (:class:`~pypet.parameter.Parameter`, :class:`~pypet.parameter.Result`)
support a rich variety of data types. There also exist also more specialized versions if the
standard ones cannot hold your data, just take
a look at :ref:`more-on-parameters`. Btw if you are still missing some functionality for
your particular needs you can simply
implement your own leaf containers and put them into the *trajectory*.

