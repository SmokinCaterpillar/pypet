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
    
    traj.load_trajectory(trajectoryname='MyTrajectory_2013_05_23_14h29m26s')
    
    
    traj.store_to_hdf5()
    
    print type(traj.Parameters.test.testparam)

if __name__ == '__main__':
    main()