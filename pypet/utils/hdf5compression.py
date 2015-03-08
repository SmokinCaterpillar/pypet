"""Module to allow hdf5 compression via ptrepack directly within python scripts"""

__author__ = 'Robert Meyer'

import os
import subprocess

from pypet.trajectory import load_trajectory
from pypet import pypetconstants


def compact_hdf5_file(filename, name=None, index=None, keep_backup=True):
    """Can compress an HDF5 to reduce file size.

    The properties on how to compress the new file are taken from a given
    trajectory in the file.
    Simply calls ``ptrepack`` from the command line.
    (Se also https://pytables.github.io/usersguide/utilities.html#ptrepackdescr)

    Currently only supported under Linux, no guarantee for Windows usage.

    :param filename:

        Name of the file to compact

    :param name:

        The name of the trajectory from which the compression properties are taken

    :param index:

        Instead of a name you could also specify an index, i.e -1 for the last trajectory
        in the file.

    :param keep_backup:

        If a back up version of the original file should be kept.
        The backup file is named as the original but `_backup` is appended to the end.

    :return:

        The return/error code of ptrepack

    """
    if name is None and index is None:
        index = -1

    tmp_traj = load_trajectory(name, index, as_new=False, load_all=pypetconstants.LOAD_NOTHING,
                               force=True, filename=filename)
    service = tmp_traj.v_storage_service
    complevel = service.complevel
    complib = service.complib
    shuffle = service.shuffle
    fletcher32 = service.fletcher32

    name_wo_ext, ext = os.path.splitext(filename)
    tmp_filename = name_wo_ext + '_tmp' + ext

    abs_filename = os.path.abspath(filename)
    abs_tmp_filename = os.path.abspath(tmp_filename)

    command = ['ptrepack', '-v',
               '--complib', complib,
               '--complevel', str(complevel),
               '--shuffle', str(int(shuffle)),
               '--fletcher32', str(int(fletcher32)),
               abs_filename, abs_tmp_filename]
    str_command = ' '.join(command)
    print('Executing command `%s`' % str_command)

    retcode = subprocess.call(command)
    if retcode != 0:
        print('#### ERROR: Compacting `%s` failed with errorcode %s! ####' %
              (filename, str(retcode)))
    else:
        print('#### Compacting successful ####')
        print('Renaming files')
        if keep_backup:
            backup_file_name = name_wo_ext + '_backup' + ext
            os.rename(filename, backup_file_name)
        else:
            os.remove(filename)
        os.rename(tmp_filename, filename)
        print('### Compacting and Renaming finished ####')

    return retcode