'''
Created on 20.05.2013

@author: robert
'''
from mypet.parameter import *
from mypet.trajectory import *
import numpy as np
import scipy.sparse as spsp



def main():
    
    logging.basicConfig(level=logging.DEBUG)
    traj = Trajectory('MyTrajectory','../experiments/test.hdf5')
    
    traj.load_trajectory(trajectoryname='MyTrajectory_2013_05_24_16h32m01s',filename='../experiments/load.hdf5')
    
    print type(traj.Parameters.test.testparam)

    print 'test'
    
    
    traj.store_to_hdf5()
    
    
    
 

if __name__ == '__main__':
    main()