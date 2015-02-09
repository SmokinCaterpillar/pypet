__author__ = 'Robert Meyer'

import sys
import getopt
import tables as pt
import shutil
import os


class FileUpdater(object):
    def __init__(self, filename, backup):
        self.filename = filename

        if filename is None:
            raise RuntimeError('Please specifiy a filename with `--filename=`.'
                               'If you want to backup your file add `-b` to the arguments.')

        if backup:
            print('Backing Up...')
            head, tail = os.path.split(filename)

            name, ext = os.path.splitext(tail)

            outfilename = name + '_BACKUP' + ext

            outfilename = os.path.join(head, outfilename)

            shutil.copy(filename, outfilename)

            print('...Done!')

        self.hdf5file = None


    def update_file(self):

        self.hdf5file = pt.openFile(self.filename, mode='r+')

        root_node = self.hdf5file.root

        for traj_node in root_node:
            self._update_traj(traj_node)

        self.hdf5file.flush()
        self.hdf5file.close()


    def _update_traj(self, traj_node):

        print('*** UPDATING TRAJECTORY %s ***' % traj_node._v_name)

        overview_node = traj_node.overview

        print('Updating Overview Tables')
        for overview_table in overview_node:
            print('Updating Table %s ...' % overview_table._v_name)

            if 'location' in overview_table.colnames:
                nrows = overview_table.nrows

                for row in range(nrows):
                    location = overview_table.cols.location[row]

                    split_name = location.split('.')
                    if len(split_name) > 1:
                        new_location = ''
                        if split_name[1] == 'trajectory':
                            del split_name[1]
                            new_location = '.'.join(split_name)

                        elif split_name[1].startswith('run_'):
                            split_name.insert(1, 'runs')
                            new_location = '.'.join(split_name)

                        if new_location:
                            overview_table.cols.location[row] = new_location
                overview_table.flush()
            print('... Done!')

        print('Updating Derived Parameters ...')

        self._change_subtree(traj_node, 'derived_parameters')

        print('... Done!')

        print('Updating Results ...')

        self._change_subtree(traj_node, 'results')

        print('... Done!')


    def _change_subtree(self, traj_node, where):

        if where in traj_node._v_children:

            res_node = traj_node._v_children[where]

            for node_name in res_node._v_children.keys():
                if node_name.startswith('run_'):
                    if not 'runs' in res_node._v_children:
                        self.hdf5file.createGroup(where=res_node, name='runs', title='runs')

                    print('    Moving node %s' % node_name)
                    runs_node = res_node._v_children['runs']

                    to_move_node = res_node._v_children[node_name]
                    self.hdf5file.moveNode(where=to_move_node, newparent=runs_node)

                if node_name == 'trajectory':
                    inner_traj_node = res_node._v_children['trajectory']

                    for move_node_name in inner_traj_node._v_children.keys():
                        to_move_node = inner_traj_node._v_children[move_node_name]

                        print('    Moving node %s' % move_node_name)

                        self.hdf5file.moveNode(where=to_move_node, newparent=res_node)

                    self.hdf5file.removeNode(where=inner_traj_node)


if __name__ == '__main__':

    opt_list, _ = getopt.getopt(sys.argv[1:], 'b', ['filename='])
    filename_ = None
    backup = False
    for opt, arg in opt_list:
        if opt == '-b':
            backup = True
            print('I will make a backup.')

        if opt == '--filename':
            filename_ = arg
            print('I will rework `%s`.' % filename_)

    FileUpdater(filename_, backup).update_file()