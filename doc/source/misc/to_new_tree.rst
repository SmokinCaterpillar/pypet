
.. _tree-migrating:

-------------------------------------------------
Migrating from Old Tree-Structure to the New One
-------------------------------------------------

The trajectory underwent a small change from version 0.1b.3 to
0.1b.4. It came clear that the current default tree structure with
`traj.results.trajectory` and `traj.results.run_00000000` (etc. for more single runs)
is less useful than having all single run results in one group to make browsing the tree easier.

So now everything that is computed in a single run is found under the new subbranch `runs`. Thus
`traj.results.run_00000000` becomes `traj.results.runs.run_00000000`, etc.

This also renders the subbranch `trajectory` obsolete. Thus, everything that was originally
stored under `traj.results.trajectory` is now moved one node up in the hierarchy to
`traj.results`. All this, of course, happens analogously for derived parameters as well.

If you have many trajectories computed with the old-style structure you can use the following
file to change their structure:

Download: :download:`to_new_tree.py <../../../pypet/utils/to_new_tree.py>`


Just execute
``python to_new_tree.py -b --file=myhdf5file.hdf5``
within the terminal and the file will automatically be converted to the new structure.
``--file=`` to specify the filename and ``-b`` to backup the file before updating it
(omit ``-b`` is you don't want a backup of the original file).


