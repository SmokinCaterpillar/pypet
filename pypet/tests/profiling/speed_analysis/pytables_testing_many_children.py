import os
import time

import tables as pt
import tables.parameters

from pypet.tests.testutils.ioutils import make_temp_dir


def create_children_dfs(hdf5_file, group_node, current_children):
    if len(current_children) == 0:
        return 1
    nchildren = current_children[0]
    child_count = 0
    for irun in range(nchildren):
        name = f"child{irun}"
        hdf5_file.create_group(where=group_node, name=name)
        child = group_node._f_get_child(name)
        child_count += create_children_dfs(hdf5_file, child, current_children[1:])
    return child_count


def main():
    start = time.time()
    filename = os.path.join(make_temp_dir("tmp"), "children.hdf5")
    dirs = os.path.dirname(filename)
    if not os.path.isdir(dirs):
        os.makedirs(dirs)
    if os.path.isfile(filename):
        os.remove(filename)
    # children_structure=(250000,1,1)
    children_structure = (500, 500, 1)
    myfile = pt.open_file(filename, mode="w")
    cc = create_children_dfs(myfile, myfile.root, children_structure)
    end = time.time()
    runtime = end - start
    print(f"\nCreated {cc} children {children_structure} in {runtime:f} seconds")


if __name__ == "__main__":
    main()
