__author__ = 'Robert Meyer'

import tables as pt
import os
import shutil
from pypet.parameter import ArrayParameter,PickleParameter
import getopt
import sys

def alpha2beta(filename):
    ''' Converts a hdf5 file with data generated from alpha version to the new format.

    IMPORTANT: Works only if you have NOT used pickle, sparse or briantests parameters!

    IMPORTANT: The overview tables will be rendered useless!

    :param filename: Filename of the file to convert
    :return: Stores the converted file in the same folder and adds the prefix beta_
    '''
    path, head_filename = os.path.split(filename)

    new_head_filename = 'beta_'+head_filename

    new_filename = os.path.join(path,new_head_filename)

    shutil.copyfile(filename,new_filename)

    hdf5_file = pt.openFile(new_head_filename,mode='a')

    for trajectory_group in hdf5_file.root._f_iterNodes():
        hdf5_file.createGroup(where=trajectory_group,name='overview')
        overview_group = hdf5_file.getNode(where=trajectory_group, name='overview')
        for overview_table in trajectory_group._f_iterNodes(classname='Table'):
            hdf5_file.moveNode(where=overview_table,newparent=overview_group)

        hdf5_file.renameNode(where=overview_group,name='info_table',newname='info')
        hdf5_file.renameNode(where=overview_group,name='run_table',newname='runs')

        for group in trajectory_group._f_walkGroups():
            attrs = group._v_attrs
            if 'SRVC_INIT_LENGTH' in attrs:
                if getattr(attrs, 'SRVC_INIT_LENGTH') == 1:
                    del attrs.SRVC_INIT_LENGTH



if __name__ == '__main__':
    opt_list, _ = getopt.getopt(sys.argv[1:],['filename='])

    for opt, arg in opt_list:

        if opt == '--filename':
            filename = arg
            print 'I will convert `%s`' % filename

    alpha2beta(filename)
