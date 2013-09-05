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
    
    #traj.load_trajectory(trajectoryname='MyTrajectory_2013_05_23_14h29m26s')
    
    traj.adp('frrrr')
    traj.adp('humus', peter = 4.9, mama = '15')
    traj.add_parameter('test.testparam', **{'Fuechse':np.array([[1,2],[3.3,2]]),'Sapiens':1,'Comment':'ladida'})

    traj.add_parameter('test.testparam', **{'Fuechse':np.array([[1,2],[3.3,2]]),'Sapiens':1,'Comment':'ladida'})

    traj.add_parameter(full_parameter_name='honky',param_type=ParameterSet, **{'mirta':np.array([[1,2,7],[3,2,17]])})

    arr= traj.Parameters.test.testparam.Fuechse
    
    traj.Parameters.test.testparam.Peter = 4
    
    print arr
    print type(ParameterSet)
    print traj.Parameters.test.testparam.Peter
    
    traj.Parameters.test.testparam.become_array()
    
    traj.Parameters.test.testparam.add_items_as_dict( {'Fuechse' : [np.array([[2,2],[3.3,2]]), np.array([[1,1],[3.3,2]])]} )
    
    traj.Parameters.test.testparam.add_items_as_list([{'Sapiens' : 2}, {'Sapiens':3}])
    
    
    traj.Parameters.test.testparam.add_comment('_honk')
    
    traj.Parameters.test.testparam.set({'Madam':'is_broke', 'Papa' : 0.0})
    
    traj.Parameters.test.testparam.set('Fuechse', np.array([1,2,3.6]))

    traj.Parameters.test.testparam._explore({'Sapiens': [0,1,2,3],  'Finka' : ['1','3','fuenf','sieben']})

    traj.Parameters.test.testparam.change_values_in_array('Finka' , ['2', '22'],[1,3])

    print traj.Parameters.test.testparam.to_dict()
    
    print traj.Parameters.test.testparam.to_dict_of_lists()
    
    print traj.Parameters.test.testparam.to_list_of_dicts()
    
    print traj.Parameters.test.testparam.get_classname()
    
    lilma = spsp.lil_matrix((10000,1000))
    lilma[0,100] = 555
    lilma[9999,999] = 11
    traj.add_parameter('test.sparseparam', Fuechse2=lilma, param_type=SparseParameter)
    
    print traj.Parameters.test.sparseparam.get_classname()
    
    
    traj.add_derived_parameter('test.sparseparam', Fuechse2=lilma*2, param_type=SparseParameter)
    
    sparseparam = traj.DerivedParameters.pwt.test.sparseparam
    
    sparseparam.become_array()

    sparseparam.add_items_as_dict({'Fuechse2' : [lilma*3, lilma*4]})

    print sparseparam.Fuechse2
    
    print len(sparseparam)
    
    traj.store_to_hdf5()
    
    print type(sparseparam)

if __name__ == '__main__':
    main()