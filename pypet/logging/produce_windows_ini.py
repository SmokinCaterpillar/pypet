
__author__ = 'Robert Meyer'

import os

def main():
    this_dir = os.path.abspath(os.path.dirname(__file__))
    os.chdir(this_dir)

    for filename in os.listdir(this_dir):
        if 'windows' not in filename and filename.endswith('.ini'):
            with open(filename, mode='r') as fh:
                all_text = fh.read()

            windows_text = all_text.replace('/', '\\\\')

            path, filename = os.path.split(filename)
            windows_filename = 'windows_' + filename

            print('Creating new file `%s`' % windows_filename)
            with open(windows_filename, mode='w') as fh:
                fh.write(windows_text)


if __name__ == '__main__':
    main()