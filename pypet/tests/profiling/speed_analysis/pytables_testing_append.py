__author__ = 'robert'

from pypet.tests.testutils.ioutils import make_temp_dir
import tables as pt
import tables.parameters
import time
import os
import numpy as np
import matplotlib.pyplot as plt

def appendtime(table, length):

    runtimes = []
    for irun in range(length):
        start = time.time()

        row = table.row
        row['test'] = 'testing'
        row.append()
        table.flush()

        end = time.time()

        runtime = end-start
        runtimes.append(runtime)
    return np.mean(runtimes)

def make_table(hdf5_file, length):
    description = {'test' : pt.StringCol(42)}
    table = hdf5_file.create_table(where='/', name='t%d' % length, description=description)
    return table

def table_runtime(filename, length):
    hdf5_file = pt.open_file(filename, mode='w')
    table = make_table(hdf5_file, length)
    appendtimes = appendtime(table, length)
    hdf5_file.close()
    return appendtimes

def compute_runtime():
    filename = os.path.join(make_temp_dir('tests'), 'iterrow.hdf5')
    dirs = os.path.dirname(filename)
    if not os.path.isdir(dirs):
        os.makedirs(dirs)
    if os.path.isfile(filename):
        os.remove(filename)


    lengths = [1, 10, 100, 1000, 10000, 100000, 1000000]
    times = []
    for length in lengths:
        print('Testing %d' % length)
        times.append(table_runtime(filename, length))
        print('Done')
    plt.semilogx(lengths, times)
    plt.show()


def main():
    compute_runtime()

if __name__ == '__main__':
    main()
