__author__ = 'Robert Meyer'


import os # For path names being viable under Windows and Linux
import getopt
import sys

from pypet import merge_all_in_folder
from the_task import FunctionParameter


def get_folder():
    optlist, args = getopt.getopt(sys.argv[1:], '', longopts='folder=')
    folder = None
    for o, a in optlist:
        if o == '--folder':
            folder = a
            print 'Found folder %s' % folder

    return folder


# And here goes our main function
def main():
    folder = get_folder()
    full_folder = os.path.join(os.getcwd(), folder)
    print('Merging all files')
    merge_all_in_folder(full_folder, delete_other_files=True,
                        dynamic_imports=FunctionParameter,
                        backup=False)
    print('Done')


if __name__ == '__main__':
    main()
