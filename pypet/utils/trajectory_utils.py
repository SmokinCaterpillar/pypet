__author__ = 'Robert Meyer'

import os
from pypet.trajectory import load_trajectory


def merge_all_in_folder(folder, ext='.hdf5',
                        dynamic_imports=None,
                        storage_service=None,
                        force=False,
                        ignore_data=(),
                        move_data=False,
                        delete_other_files=False,
                        keep_info=True,
                        keep_other_trajectory_info=True,
                        merge_config=True,
                        backup=True):
    """Merges all files in a given folder.

    IMPORTANT: Does not check if there are more than 1 trajectory in a file. Always
    uses the last trajectory in file and ignores the other ones.

    Trajectories are merged according to the alphabetical order of the files,
    i.e. the resulting merged trajectory is found in the first file
    (according to lexicographic ordering).

    :param folder: folder (not recursive) where to look for files
    :param ext: only files with the given extension are used
    :param dynamic_imports: Dynamic imports for loading
    :param storage_service: storage service to use, leave `None` to use the default one
    :param force: If loading should be forced.
    :param delete_other_files: Deletes files of merged trajectories

    All other parameters as in `f_merge_many` of the trajectory.

    :return: The merged traj

    """
    in_dir = os.listdir(folder)
    all_files = []
    # Find all files with matching extension
    for file in in_dir:
        full_file = os.path.join(folder, file)
        if os.path.isfile(full_file):
            _, extension = os.path.splitext(full_file)
            if extension == ext:
                all_files.append(full_file)
    all_files = sorted(all_files)

    # Open all trajectories
    trajs = []
    for full_file in all_files:
        traj = load_trajectory(index=-1,
                               storage_service=storage_service,
                               filename=full_file,
                               load_data=0,
                               force=force,
                               dynamic_imports=dynamic_imports)
        trajs.append(traj)

    # Merge all trajectories
    first_traj = trajs.pop(0)
    first_traj.f_merge_many(trajs,
                ignore_data=ignore_data,
                move_data=move_data,
                delete_other_trajectory=False,
                keep_info=keep_info,
                keep_other_trajectory_info=keep_other_trajectory_info,
                merge_config=merge_config,
                backup=backup)

    if delete_other_files:
        # Delete all but the first file
        for file in all_files[1:]:
            os.remove(file)

    return first_traj
