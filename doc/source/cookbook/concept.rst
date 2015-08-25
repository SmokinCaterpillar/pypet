
.. _more-on-concept:

=====================================
How to Structure your Simulations
=====================================

This project was born out of the need for a tool to manage and store results of spiking neural
network simulations. In particular, to manage results obtained with the BRIAN_ neural network
simulator (yet, this does not mean this project is restricted to BRIAN, you can use the
package for any simulation or numerical experiment in python).
The more complex simulations become the more complicated are the sets of parameters
and the harder it gets to qualitatively compare results obtained from different
simulation runs. There was a huge need to standardize the simulations and parameter
exploration, to structure and group different parameters, and especially to entangle the
scientific simulation from the environment that runs it. So when I designed
this tool I always had in mind how I wanted to used it later on in my project.
I do not want to spare these conceptual ideas from you.

So, I would like to present you some remarks on how to effectively use this tool.
I would divide any numerical simulations into 3 phases:

    1. Parameter Definition Phase

        Here you will only add parameters (see :func:`pypet.naturalnaming.ParameterNode.f_add_parameter`,
        and :ref:`more-on-adding`) to your trajectory, no results, no derived parameters,
        no building of other objects used during your simulation.
        **ONLY parameters**. You could write a `conf.py`
        file that adds all parameters to your trajectory. To exclude parameter sets and
        to allow some control flow, you can consider :ref:`more-on-presetting`.

    2. Preparation Phase

        Here you will prepare stuff before the actual runtime,
        e.g. create objects needed in your simulations.
        This encompasses stuff that only needs to be build once and is used
        during all individual runs.
        Here you can also start adding derived parameters.

        At the end of your preparation phase you define which parameters should be explored and
        how via :func:`pypet.trajectory.f_explore` (and take a look at :ref:`parameter-exploration`).

    3. The Run Phase

        This is the phase where individual parameter space points along the trajectory that you
        explore are evaluated. Here you produce your main numerical results and maybe some
        derived parameters.
        You have a top-level function that uses a single run object (maybe called `traj`)
        and accesses the parameters needed during the single run
        to make some calculations (see :ref:`more-on-single-runs`).

        This top level function is handed over to the runtime environment in addition with
        some other arguments (like some objects not managed by your trajectory) to carry out the
        simulation (see :func:`pypet.environment.Environment.run`, and :ref:`more-on-running`).

        Usually to speed up your simulations and to compute several runs in parallel, you can
        use multiprocessing at this stage, see :ref:`more-on-multiprocessing`.


After your parameter exploration is finished you might have a 4th stage of post processing.
For instance, calculating summary statistics over all your simulation runs.
Yet, I would separate this phase entirely from the previous ones. You can do this in a separate
program that loads the trajectory.


Well, that's it, so thanks for using *pypet*,

    Robert

..
    PS: If you use *pypet* for your research, I would be grateful if you
    follow the :ref:`citation_policy`.

PS: If you use *pypet* for BRIAN_ simulations, also check out
:ref:`brian-framework`.


.. _BRIAN: http://briansimulator.org/