'''
Created on 20.05.2013

@author: robert
'''
from mypet.parameter import *
from mypet.trajectory import *
import numpy as np


def main():
    
    logging.basicConfig(level=logging.DEBUG)
    traj = Trajectory('MyTrajectory')
    
    traj.add_parameter('test.testparam', {'Fuechse':np.array([[1,2],[3.3,2]]),'Homo':1,'Comment':'ladida'}, param_type=Parameter)

    traj.add_parameter('test.testparam', {'Fuechse':np.array([[1,2],[3.3,2]]),'Homo':1,'Comment':'ladida'}, param_type=Parameter)


    arr= traj.Parameters.test.testparam.Fuechse
    
    traj.Parameters.test.testparam.Peter = 4
    
    
    print traj.Parameters.test.testparam.Peter
    
    















if __name__ == '__main__':
    main()