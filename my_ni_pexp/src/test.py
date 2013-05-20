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
    
    traj.add_parameter('test.testparam', {'Fuechse':np.array([[1,2],[3.3,2]]),'Sapiens':1,'Comment':'ladida'}, param_type=Parameter)

    traj.add_parameter('test.testparam', {'Fuechse':np.array([[1,2],[3.3,2]]),'Sapiens':1,'Comment':'ladida'}, param_type=Parameter)


    arr= traj.Parameters.test.testparam.Fuechse
    
    traj.Parameters.test.testparam.Peter = 4
    
    
    print traj.Parameters.test.testparam.Peter
    
    traj.Parameters.test.testparam.become_array()
    
    traj.Parameters.test.testparam.add_items_as_dict( {'Fuechse' : [np.array([[2,2],[3.3,2]]), np.array([[1,1],[3.3,2]])]} )
    
    traj.Parameters.test.testparam.add_items_as_list([{'Sapiens' : 2}, {'Sapiens':3}])
    
    
    traj.Parameters.test.testparam.add_comment('_honk')
    
    traj.Parameters.test.testparam.set({'Madam':'is_broke', 'Papa' : 0.0})
    
    traj.Parameters.test.testparam.set('Fuechse', np.array([1,2,3]))

    traj.Parameters.test.testparam.explore({'Sapiens': [0,1,2,3], 'Fuechse' : [0,1,2,3], 'Finka' : ['1','3','fuenf','sieben']})

    traj.Parameters.test.testparam.change_values_in_array('Finka' , ['2', '22'],[1,3])

    print traj.Parameters.test.testparam.to_dict()
    
    print traj.Parameters.test.testparam.to_dict_of_lists()
    
    print traj.Parameters.test.testparam.to_list_of_dicts()

if __name__ == '__main__':
    main()