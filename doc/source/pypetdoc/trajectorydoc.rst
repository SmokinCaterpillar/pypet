============================================
The Trajectory and Group Nodes
============================================


----------------
Quicklinks
----------------
Here are some links to important functions:

.. currentmodule:: pypet


.. autosummary::
    :nosignatures:

    ~trajectory.Trajectory
    ~naturalnaming.ParameterGroup.f_add_parameter
    ~naturalnaming.DerivedParameterGroup.f_add_derived_parameter
    ~naturalnaming.ResultGroup.f_add_result
    ~naturalnaming.NNGroupNode.f_add_link
    ~naturalnaming.NNGroupNode.f_add_leaf
    ~naturalnaming.NNGroupNode.f_iter_leaves
    ~naturalnaming.NNGroupNode.f_iter_nodes
    ~naturalnaming.NNGroupNode.f_get
    ~naturalnaming.NNGroupNode.f_store_child
    ~naturalnaming.NNGroupNode.f_store
    ~naturalnaming.NNGroupNode.f_load_child
    ~naturalnaming.NNGroupNode.f_load
    ~trajectory.Trajectory.f_explore
    ~trajectory.Trajectory.f_store
    ~trajectory.Trajectory.f_load
    ~trajectory.Trajectory.f_load_skeleton
    ~trajectory.Trajectory.f_preset_parameter
    ~trajectory.Trajectory.f_get_from_runs
    ~trajectory.Trajectory.f_load_items
    ~trajectory.Trajectory.f_store_items
    ~trajectory.Trajectory.f_remove_items
    ~trajectory.Trajectory.f_delete_items
    ~trajectory.Trajectory.f_find_idx
    ~trajectory.Trajectory.f_get_run_information
    ~trajectory.Trajectory.v_crun
    ~trajectory.Trajectory.v_idx
    ~trajectory.Trajectory.v_standard_parameter
    ~trajectory.Trajectory.v_standard_result
    ~naturalnaming.NNGroupNode.v_annotations
    ~trajectory.load_trajectory


--------------------
Trajectory
--------------------
.. autoclass:: pypet.trajectory.Trajectory
    :members:

.. autofunction:: pypet.trajectory.load_trajectory

-------------------
NNGroupNode
-------------------

.. autoclass:: pypet.naturalnaming.NNGroupNode
    :members:
    :inherited-members:


-------------------
ParameterGroup
-------------------

.. autoclass:: pypet.naturalnaming.ParameterGroup
    :members:


-------------------
ConfigGroup
-------------------

.. autoclass:: pypet.naturalnaming.ConfigGroup
    :members:

-----------------------
DerivedParameterGroup
-----------------------

.. autoclass:: pypet.naturalnaming.DerivedParameterGroup
    :members:

-------------------
ResultGroup
-------------------

.. autoclass:: pypet.naturalnaming.ResultGroup
    :members:

