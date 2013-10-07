
.. _more-on-trajectories:

======================================================
More on Trajectories and Single Runs (and Annotations)
======================================================

------------------------------------
Trajectory
------------------------------------

For some example code on on topics dicussed here
see the :ref:`example-02`.

The :class:`~pypet.trajectory.Trajectory` is the standard container for all results and parameters
(see :ref:`more-on-parameters`) of your numerical experiments.


The trajectory container instantiates a tree with *groups* and *leaf* nodes.
There are two types of objects that can be *leaves*, *parameters* and *results*.
Both follow particular APIs (see :class:`~pypet.parameters.Parameter` and :class:
:class:`~pypet.parameters.Result` as well as their abstract base classes
:class:`~pypet.parameter.BaseParameter`, :class:`~pypet.parameter.BaseResult`).

A trajectory contains 4 major branches of its tree.

* config

    Parameters stored under config, do not specify the outcome of your simulations but
    only the way how the simulation is carried out. For instance, this might encompass
    the number of cpu cores for multiprocessing. If you use and generate a trajectory
    with an environment (:ref:`more-on-environment`), the environment will add some
    config data to your trajectory. Any leaf added under *config*
    is a :class:`~pypet.parameter.Parameter` object (or descendant of the corresponding
    base class :class:`~pypet.parameter.BaseParameter`).

    As normal parameters, config parameters can only be specified before the actual single runs.

* parameters

    Parameters are the fundamental building blocks of your simulations. Changing a parameter
    usually effects the results you obtain in the end. The set of parameters should be
    complete and sufficient to characterize a simulation. Running a numerical simulation
    twice with the very same parameter settings should give also the very same results.
    Therefore, it is recommenced to also incorporate seeds for random number generators in
    your parameter set. Any leaf added under *parameters*
    is a :class:`~pypet.parameter.Parameter` object (or descendant of the corresponding
    base class :class:`~pypet.parameter.BaseParameter`).

    Parameters can only be introduced to the trajectory before the actual simulation runs.

* derived_parameters

    Derived parameters are specifications of your simulations that, as the name says, depend
    on your original parameters but are still used to carry out your simulation. They are
    somewhat
    too premature to be considered as final results. For example, assume a simulation of a neural network,
    a derived parameter could be the connection matrix specifying how the neurons are linked
    to each other. Of course, the matrix is completely determined
    by some parameters, one could think of some kernel parameters and a random seed, but still
    you actually need the connection matrix to build the final network.

    Derived parameters can be introduced at any time during your simulation. If you add
    a derived parameter before starting individual runs that explore the parameter space,
    they will be sorted into the subbranches`derived_parameters.trajectory`. If you
    introduce a derived parameter within a single run, they are sorted into:
    `derived_parameters.run_XXXXXXXX`, where *XXXXXXXX* is the index of the single run.
    Any leaf added under *derived_parameters*
    is a :class:`~pypet.parameter.Parameter` object (or descendant of the corresponding
    base class :class:`~pypet.parameter.BaseParameter`).

* results

    I guess, results are rather self explanatory. Any leaf added under *results*
    is a :class:`~pypet.parameters.Results` object (or descendant of the corresponding
    base class :class:`~pypet.parameter.BaseResult`).

Note that all *leaf* nodes provide the field 'v_comment', which can be filled manually or on
construction via `'comment='`. To allow others to understand your simulations it is very
helpful to provide such a comment and explain what your parameter is good for. For *parameters*
this comment will actually be shown in the parameter overview table (to reduce file size
it is not shown in the result and derived parameter overview tables, see also
:ref:`more-on-overview`). It can also be found
as an hdf5 attribute of the corresponding nodes in the hdf5 file (this is true for all *leaves*).

----------------------------
Naming Convention
----------------------------


To avoid confusion with natural naming scheme (see below) and the functionality provided
by the trajectory and parameters, I followed the idea by pytables to use the prefix
`f_` for functions and `v_` for python variables/attributes/properties.

.. _more-on-adding:

--------------------------------------------------
Addition of groups and leaves (results/parameters)
--------------------------------------------------

Addition of *leaves* can be achieved via the functions:

    * :func:`~pypet.naturalnaming.ConfigGroup.f_add_config`

    * :func:`~pypet.naturalnaming.ParameterGroup.f_add_parameter`

    * :func:`~pypet.naturalnaming.DerivedParameterGroup.f_add_derived_parameter`

    * :func:`~pypet.naturalnaming.ResultGroup.f_add_result`

*Leaves* can be added to any group, including the root group, i.e. the trajectory or the single
run object themselves. Note that if you operate in the *parameters* subbranch of the tree,
you can only add parameters (i.e. `traj.parameters.f_add_parameter(...)` but
`traj.parameters.f_add_result(...)` does not work). For other subbranches
this is analogous.

There are two ways to add these objects, either you already have an instantiation of the
object, i.e. you add a given parameter:

    >>> my_param = Parameter('subgroup1.subgroup2.myparam', data = 42, comment='I am an example')
    >>> traj.f_add_parameter(my_param)

Or you let the trajectory create the parameter, where the name is the first positional argument:

    >>> traj.f_add_parameter('subgroup1.subgroup2.myparam', data = 42, comment='I am an example')

There exists a standard constructor that is called in case you let the trajectory create the
parameter. The standard constructor can be changed via the `v_standard_parameter` property.
Default is the :class:`~pypet.parameter.Parameter` constructor.

If you only want to add a different type of parameter once, but not change the standard
constructor in general, you can add the constructor as
the first positional argument followed by the name as the second argument:

    >>> traj.f_add_parameter(PickleParameter, 'subgroup1.subgroup2.myparam', data = 42, comment='I am an example')


Derived parameters, config and results work analogously.


You can sort *parameters/results* into groups by colons in the names.
For instance, `traj.f_add_parameter('traffic.mobiles.ncars', data = 42)` would create a parameter
that is added to the subbrunch `parameters`, of course, and this will automatically create
the subgroups `traffic` and inside there the group `mobiles`.
If you would now add the parameter `traj.f_add_parameter('traffic.mobiles.ncycles', data = 11)`,
you can find this also in the group `traj.parameters.traffic.ncycles`.



Besides *leaves* you can also add empty *groups* to the trajectory (and to all subgroups, of course) via:

* :func:`~pypet.naturalnaming.NNGroupNode.f_add_config_group`

* :func:`~pypet.naturalnaming.NNGroupNode.f_add_parameter_group`

* :func:`~pypet.naturalnaming.NNGroupNode.f_add_derived_parameter_group`

* :func:`~pypet.naturalnaming.NNGroupNode.f_add_result_group`

As before, if you create the group `groupA.groupB.groupC` and
if group A and B were non existent before, they will be created on the way.

Note that I distinguish between three different types of name, the *full name* which would be,
for instance, `parameters.groupA.groupB.myparam`, the (short) *name* `myparam` and the
*location* `parameters.groupA.groupB`, all these properties are accessible from each group and
result/parameter via:

* `v_full_name`

* `v_location`

* `v_name`

*Location* and *full name* are relative to the root node, since a trajectory object (and single runs)
is the root, it's *full_name* is `''` the empty string. Yet, the *name* property is not empty
but contains the user chosen name of the trajectory.

Note that if you add a parameter/result/group with `f_add_xxxxx` the (full name)
the full name will be extended by the *full name* of the group you added it to:

>>> traj.parameters.traffic.f_add_parameter('street.nzebras')

The *full name* of the new parameter is going to be `parameters.traffic.street.nzebras`.
If you add anything directly to the *root* group, i.e. the trajectory object (or a single run),
the group names `parameters`, `config`, `derived_parameters.trajectory`, `derived_parameters.run_XXXXXXX`,
`results.trajectory`, or  `results.run_XXXXXXX` will be automatically added (of course,
depending on what you add, config, a parameter etc.).

.. _more-on-access:

----------------------
Natural Naming
----------------------


As said before *trajectories* instantiate trees and the tree can be browsed via natural naming.

For instance, if you add a parameter via `traj.f_add_parameter('traffic.street.nzebras', data=4)`,
you can access it via

    >>> traj.parameters.street.nzebras
    4

Here comes also the concept of *fast access* instead of the parameter object you directly
access the *data* value 4.
Whether or not you want fast access is determined by the value of `v_fast_access`
(default is True):

    >>> traj.v_fast_access = False
    >>> traj.parameters.street.nzebras
    <Parameter object>

Note that fast access only works for parameter objects (i.e. for everything you store under *parameters*,
*derived_parameters*, and *config*) that are non empty. If you say for instance `traj.x` and `x`
is an empty parameter, you will get in return the parameter object. Fast access works
in one particular case also for results, and that is, if the result contains exactly one item
with the name of the parameter.
For isntance if you add the result `traj.f_add_result('z',10), you can fast access it, since
the first positional argument is mapped to the name 'z'.
If it is empty or contains more than 1 item you will always get in return the result object.



^^^^^^^^^^^^^^^^^
Shortcuts
^^^^^^^^^^^^^^^^^

As a user you are encouraged to nicely group and structure your results as fine grain as
possible. Yet, you might think that you will inevitably have to type a
lot to access your values and always state the *full name* of an item.
This is, however, not true. There are two ways to work around that.
First, you can request the group above the parameters, and then access the variables one by one:

    >>> mobiles = traj.parameters.traffic.mobiles
    >>> mobiles.ncars
    42
    >>> mobiles.ncycles
    11

Or you can make use of shortcuts. If you leave out intermediate groups in your natural naming
request, a breadth first search [#]_ is applied to find the corresponding group/leaf.

    >>> traj.mobiles
    42
    >>> traj.traffic.mobiles
    42
    >>> traj.parameters.ncycles
    11

Search is established with very fast look up and usually needs much less then :math:`O(n)`
[most often :math:`O(1)` or :math:`O(d)`, where :math:`d` is the depth of the tree
and `n` the total number of nodes, i.e. *groups* + *leaves*)

However, sometimes your shortcuts are not unique and you might find several solutions for
your natural naming search in the tree. To speed up the lookup, the search is stopped after the
first result. So you will not be notified whether your result is actually unique. Yet, you
can set `v_check_uniqueness=True` at your trajectory object and it will be checked for these
circumstances. Nonetheless, enabling `v_check_uniqueness=True` will require always :math:`O(n)` for
your lookups. So do that
for debugging purposes once and switch it off during your real simulation runs to save time!

The method that performs the natural naming search in the tree can be called directly, it is
:func:`~pypet.naturalnaming.NNGroupNode.f_get`. Here fast access (default `False`),
search strategy (default `'BFS'`) and whether
to check for uniqueness (default `False`) can be passed as parameters.

    >>> traj.parameters.f_get('mobiles.ncars')
    <Parameter object ncars>
    >>> traj.parameters.f_get('mobiles.ncars', fast_access=True)
    42


There exist also nice shortcuts for already present groups:

*

    `'par'` and `'param'` is mapped to `'parameters'`, i.e. `traj.parameters` is the same
    group as `traj.par`

* `'dpar'` and `'dparam'` is mapped to `derived_parameters`

* `'res'` is mapped to `'results'`

* `'conf'` is mapped to `'config'`

* `'traj'` and `'tr'` are mapped to `'trajectory'`

*

    `'cr'`, `'current_run'`, `'current_run'` are mapped to the name of the current
    run (for example `'run_00000002'`)

*

    `'r_X'` and `'run_X'` are mapped to the corresponding run name, e.g. `'r_3'` is
    mapped to `'run_00000003'`

.. _parameter-exploration:

----------------------------------
Parameter Exploration
----------------------------------

Exploration can be prepared with the function :func:`~pypet.trajectory.Trajectory.f_explore`.
This function takes a dictionary with parameter names
(not necessarily the full names, they are searched) as keys and iterables specifying
how the parameter changes for each run as the argument. Note that all iterables
need to be of the same length. For example:

>>> traj.f_explore({'ncars':[42,44,45,46], 'ncycles' :[1,4,6,6]})

This would create a trajectory of length 4 and explore the four parameter space points
:math:`(42,1),(44,4),(45,6),(46,6)`. If you want to explore the cartesian product of
variables, you can take a look at the :func:`~pypet.utils.explore.cartesian_product` function.

You can extend or expand an already explored trajectory to explore the parameter further with
the function :func:`~pypet.trajectory.Trajectory.f_expand`.

.. _more-on-storage:

---------------------------------
Storing
---------------------------------

Storage of the trajectory container and all it's content is not carried out by the
trajectory itself but by a service. The service is known to the trajectory and can be
changed via the `v_storage_service` property. The standard storage service (and the only one
so far, you don't bother write an SQL one? :-) is the `~pypet.storageserivce.HDF5StorageService`.

You don't have to interact with the service directly, storage can initiated by several methods
of the trajectory and it's groups and subbranches (which format and hand over the request to the
service).
There is a general scheme to storage, which is *whatever is stored to disk is the ground truth and
therefore cannot be changed*. So basically as soon as you store parts of your trajectory to disk
they will stay there!
So far there is no real support for changing data that was stored to disk once (you can
delete some of it, see below). Why being so restrictive? Well, first of all, if you do
simulations, they are like numerical *scientific experiments*, so you run them and then you collect your
data and keep it. There is usually no need to modify the first raw data after collecting it.
You may analyze it and create novel results from the raw data, but you usually should have
no incentive to modify your original raw data.
Second of all, HDF5 is bad for modifying and especially deletion of data which usually leads
to fragmented HDF5 files and does not free memory on your hard drive. So there are already
constraints by the file system used (but trust me this is minor compared to the awesome
advantages of using HDF5, and as I said, why the heck do you wanna change your results, anyway?).

Just to state that again, if you save stuff to disk, it is set in stone! So if you modify
data in RAM and store it again, the HDF5 storage service will simply ignore these modifications!

The most straightforward way to store everything is to say:

    >>> traj.store()

and that's it. In fact if you use the trajectory in combination with the environment (see
:ref:`more-on-environment`) you
do not need to do this call by yourself at all, this is done by the environment.

More interesting is the approach to store individual items.
Assume you computed a result that is extremely large. So you want to store it to disk,
than free the result and forget about it for the rest of your simulation:

    >>> large_result = traj.results.large_result
    >>> traj.f_store_item(large_result)
    >>> large_result.f_empty()

Note that in order to allow storage of single items, you need to have stored the trajectory at
least once. If you operate during a single run, this has been done before, if not,
simply call `traj.store()` once before.

To avoid re-opneing an closing of the hdf5 file over and over again there is also the
possibility to store a list of items via :func:`~pypet.trajectory.SingleRun.f_store_items`
or whole subtrees via :func:`~pypet.naturalnaming.NNGroupNode.f_store_child`.

OF NOTE: If you want to store single items you should prefer
:func:`~pypet.trajectory.SingleRun.f_store_items` over
:func:`~pypet.naturalnaming.NNGroupNode.f_store_child` simply because for the latter the
storage service only needs to know the individual item, whereas the former requires the
service to know the entire trajectory. This can be painful in case of multiprocessing
and using a queue plus a single storage process. Accordingly, the whole trajectory
needs to be pickled and is sent over the queue!

If you never heard about pickling or object serialization, you might want to take a loot at the
pickle_ module.


If you store a trajectory to disk it's tree structure can be again found in the structure of
the HDF5 file!
In addition, there will be some overview tables summarizing what you stored into the hdf5 file.
They can be found under the top-group `overview`.

* An `info` listing general information about your trajectory

* A `runs` summarizing the single runs

* The instance tables:

    `parameters`

        Containing all parameters, and some information about comments, length etc.

    `config`,

        As above, but config parameters

    `results_runs`

        All results of all individual runs, to reduce memory size only a short value
        summary and the name is given.


    `results_runs_summary`

        Only the very first result with a particular name is listed. For instance
        if you create the result 'my_result' in all runs only the result of run_00000000
        is listed with detailed information.

        If you use this table, you can purge duplicate comments, see :ref:`more-on-duplicate-comments`.


    `results_trajectroy`

        All results created directly with the trajectory and not within single runs are listed.

    `derived_parameters_trajectory`

    `derived_parameters_runs`

    `derived_parameters_runs_summary`

        All three are analogous to the result overviews above.

* The `explored_parameters` overview over you parameters explored in the single runs

* In each subtree *results.run_XXXXXXXX* there will be another explored parameter table summarizing the values in each run.

Btw, you can switch the creation of these tables off (See :ref:`more-on-overview`) to reduce the
size of the final hdf5 file.

.. _pickle: http://docs.python.org/2/library/pickle.html

.. _loading:

------------------------------------
Loading
------------------------------------
Sometimes you start your session not running an experiment, but loading an old trajectory.
The first step in order to do that is to create a new empty trajectory and call
`~pypet.trajectory.Trajectory.f_load` on it.
There are two load modes depending on the argument `as_new`

* `as_new=True`

    You load an old trajectory into you new one, and only load everything stored under
    *parameters* in order to rerun an old experiment. You could hand this loaded
    trajectory over to the runtime environment and carry out another the simulation again.

* `as_new=False`

    You want to load and old trajectory and analyze results you have obtained. The current name
    of your newly created trajectory will be changed to the name of the loaded one.

If you choose tha latter load mode, you can specify how the individual subtrees *config*,*parameters*,
*derived_parameters*, and *results* are loaded:

* :const:`pypet.globally.LOAD_NOTHING`: (0)

    Nothing is loaded.

* :const:`pypet.globally.LOAD_SKELETON`: (1)

    The skeleton is loaded including annotations (See :ref:`more-on-annotations`).
    That means that only empty
    *parameter* and *result* objects will
    be created  and you can manually load the data into them afterwards.
    Note that :class:`pypet.annotations.Annotations` do not count as data and they will be loaded
    because they are assumed to be small.

* :const:`pypet.globally.LOAD_DATA`: (2)

    The whole data is loaded.

* :const:`pypet.globally.UPDATE_SKELETON`: (-1)

    The skeleton and annotations are updated, i.e. only items that are not currently part of your trajectory
    in RAM are loaded empty.

* :const:`pypet.globally.UPDATE_DATA`: (-2)

     Like (2) but only items that are currently not in your trajectory are loaded.


As for storage, you can load single items manually by
:func:`~pypet.trajectory.Trajectory.f_load_item`. If you load a large result with many entries
you might consider loading only parts of it (see :func:`~pypet.trajectory.Trajectory.f_load_items`)
Note in order to load a parameter, result or group, it
must exist in the current trajectory in RAM, if it does not
you can always bring your skeleton of your trajectory tree up to date
with :`func:`~pypet.trajectory.Trajectory.f_update_skeleton`. This will load all items stored
to disk and create empty instances. After a simulation is completed, you need to call this function
to get the whole trajectory tree containing all new results and derived parameters.

And last but not least there is also :func:`~pypet.naturalnaming.NNGroupNode.f_store_child`.



-------------------------------------
Removal of items
-------------------------------------

If you want to solely remove items from RAM (after storing them to disk),
you can also of whole subbranches via `~pypet.naturalnameing.f_remove_child`.

But usually it is enough to simply free the data and keep empty results by using
the `f_empty()` function of a result or parameter. This will remain the actual skeleton
of the trajectory untouched.

Although I made it pretty clear, that in general what is stored to disk is set in stone,
there are a functions to remove items not only from RAM but also from disk:
`~pypet.trajectory.f_remove_item` and `~pypet.trajectory.f_remove_items` and calling them
with `remove_from_storage=True`.
Note that you cannot remove explored parameters. And I would not recommend not using this
function at all.


------------------------------------
Merging and Backup
------------------------------------

You can backup a trajectory with the function :func:`pypet.trajectory.Trajectory.f_backup`.

If you have two trajectories that live in the same space you can merge them into one
via :func:`pypet.trajectory.Trajectory.f_merge`.
There are a variety of options how to merge them. You can even discard parameter space points
that are equal in both trajectories. Or you can simply add more trials to a given trajectory
if both contain a *trial parameter*, an integer parameter that simply runs from
0 to N1-1 and 0 to N2-1, respectively. After merging your the trial parameter in your
merged trajectory runs form 0 to N1+N2-1, and you added N2 trials.

Also checkout the example in :ref:`example-03`.


.. _more-on-single-runs:

-------------------------------------
Single Runs
-------------------------------------

A :class:`~mypet.trajectory.SingleRun` is like a smaller version of a trajectory.
If you explore the parameter space,
a single run is exactly one parameter space point that you visit on your trajectory during
your numerical simulations. It is also the root node of your tree and offers slightly less
functionality as the full trajectory.

How do I get single runs?
They are the object returned if you iterate over the trajectory:

    >>> for run in traj:


A run is identified by it's index and position in your trajectory, you can access this via
`v_idx`. As a proper informatics guy, if you have N runs, than your first run's idx is 0
and the last has idx N-1!

Or if you use the run environment (see :ref:`more-on-environment`), they are the containers
that are passed to your run function and that you can use to access your parameters.
As said before, they are not much different from trajectories, the best is you treat them
as you would treat a trajectory object.

Yet, they lack some functionality compared to trajectories:

* You can no longer add *config* and *parameters*

*

    You cannot load stuff from disk (maybe this will be changed in later versions, let's see how
    restrictive this ist.)

*

    You can usually not access the full exploration array of parameters but only the current
    value that corresponds to the idx of the run.

-------------------------------------------
Iterating over Loaded Data in a Trajectory
-------------------------------------------

The trajectory offers a way to iteratively look into the data you have obtained from several runs.
Assume you have computed the value `z` with `z=traj.x*traj.x` and added `z` to the trajectory
in each run `traj.f_add_result('z',z)`. Accordingly, you can find a couple of
`traj.results.run_XXXXXXXX.z` in your trajectory (where `XXXXXXXX` is the index
of a particular run like `00000003`). To access these one after the other it
is quite tedious to write `run_XXXXXXXX` each time.

There is a way to tell the trajectory
to only consider the subbranches that are associated with a single run and blind out everything else.
You can use the function `~pypet.trajectory.Trajectory.f_as_run` to make the
trajectory only consider a particular run (it accepts run indices as well as names).
Alternatively you can set the run idx via changing
`v_idx` of your trajectory object. In addition to blinding out all branches that are
not part of this run, all explored parameters within the trajectory are also set to the
value associated with the corresponding index. Note that blinding out will also affect
the functions `~pypet.naturalnaming.NNGroupNode.f_iter_leaves` and
`~pypet.naturalnaming.NNGroupNode.f_iter_nodes`.

In order to set everything back to normal call `~pypet.trajectory.Trajectory.f_restore_default` or
set `v_idx` to `-1`.

For example, consider your trajectory contains the parameters `x` and `y` and both have been
explored with :math:`x \in \{1.0,2.0,3.0,4.0\}` and :math:`y \in \{3.0,3.0,4.0,4.0\}` and
their product is stored as `z`. The following
code snippet will iterate over all four runs and print the result of each run:

.. code-block:: python

    for run_name in traj.f_get_run_names():
        traj.f_as_run(run_name)
        x=traj.x
        y=traj.y
        z=traj.z
        print '%s: x=%f, y=%f, z=%f' % (run_name,x,y,z)

    # Don't forget to reset you trajectory to the default settings, to release its belief to
    # be the last run:
    traj.f_restore_default()


This will print the following statement:

    run_00000000: x=1.000000, y=3.000000, z=3.000000

    run_00000001: x=2.000000, y=3.000000, z=6.000000

    run_00000002: x=3.000000, y=4.000000, z=12.000000

    run_00000003: x=4.000000, y=4.000000, z=16.000000

To see this in action you might want to check out :ref:`example-03`.

.. _more-on-presetting:

----------------------------------
Presetting of Parameters
----------------------------------

I suggest that before you calculate any results or derived parameters,
you should define all parameters used during your simulations.
Usually you could do this by parsing a config file (Write your own parser or hope that I'll
develop one soon :-D), or simply by executing some sort of a config file in python that
simply adds the parameters to your trajectory.
(see also :ref:`more-on-concept`)

If you have some complex simulations where you might use only parts of your parameters or
you want to exclude a set of parameters and include some others, there you can make use
of the presetting of parameters (see :func:`pypet.trajectory.f_preset_parameter`).
This allows you to add control flow on the setting or parameters. Let's consider an example:

.. code-block:: python

    traj.f_add_parameter('traffic.mobiles.add_cars',True , comment='Whether to add some cars or '
                                                            'bicycles in the traffic simulation')
    if traj.add_cars:
        traj.f_add_parameter('traffic.mobiles.ncars', 42, comment='Number of cars in Rome')
    else:
        traj.f_add_parameter('traffic.mobiles.ncycles', 13, comment'Number of bikes, in case '
                                                                    'there are no cars')


There you have some control flow. If the variable `add_cars` is True, you will add
42 cars otherwise 13 bikes. Yet, by your definition one line before `add_cars` will always be True.
To switch between the use cases you can rely on presetting
of parameters. If you have the following statement somewhere before in your main function,
you can make the trajectory change the value of `add_cars` right after the parameter was
added:

.. code-block:: python

    traj.f_preset_parameter('traffic.mobiles.add_cars',False)


So when it comes to the execution of the first line in example above, i.e.
`traj.f_add_parameter('traffic.mobiles.add_cars',True , comment='Whether to add some cars or bicycles in the traffic simulation')`

The parameter will be added with the default value `add_cars=True` but immediately afterwards
the :func:`pypet.parameter.Parameter.f_set` function will be called with the value
False. Accordingly, `if traj.add_cars:` will evaluate to False and the bicycles will be added.


Note that in order to preset a parameter you need to state its full name (except the prefix
*parameters*) and you cannot shortcut through the tree. Don't worry about typos, before the running
of your simulations it will be checked if all parameters marked for presetting where reached,
if not an DefaultReplacementError will be thrown

.. _more-on-annotations:

----------------------------------
Annotations
----------------------------------

:class:`~pypet.annotations.Annotations` are a small extra feature. Every group node
(including your trajectory, but not single runs) and every leaf has a property called
`v_annotations`. These are other container objects (accessible via natural naming of course),
where you can put whatever you want! So you can mark your items in a specific way
beyond simple comments:

    >>> ncars_obj = traj.f_get('ncars')
    >>> ncars_obj.v_annotations.my_special_annotation = ['peter','paul','mary']
    >>> print ncars_obj.v_annotations.my_special_annotation
    ['peter','paul','mary']

So here you added a list of strings as an annotation called `my_special_annotation`.
These annotations map one to one to the attributes_ of your hdf5 nodes in your final hdf5 file.
The high flexibility of annotating your items comes with the downside that storage and retrieval of annotations
from the hdf5 file is very slow. So only use short and small annotations.
Consider annotations as a neat additional feature, but I don't recommend using the
annotations for large machine written stuff or storing large results in them (use the regular
result items to do that!)

For storage of annotations holds the same as for items, whatever is stored to disk is set in stone!

.. _attributes: http://pytables.github.io/usersguide/libref/declarative_classes.html#the-attributeset-class



.. [#]

    The search strategy can be changed via the property `v_search_strategy` between
    breadth first search (`'BFS'`) and depth first search (`'DFS'`).