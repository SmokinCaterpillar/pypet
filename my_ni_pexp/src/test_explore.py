'''
Created on 20.05.2013

@author: robert
'''
from mypet.parameter import *
from mypet.trajectory import *
import numpy as np
import scipy.sparse as spsp
import mypet.utils.explore as ut



def main():
    
    logging.basicConfig(level=logging.DEBUG)
    traj = Trajectory('MyTrajectory','../experiments/test.hdf5')
    
    #traj.load_trajectory(trajectoryname='MyTrajectory_2013_05_23_14h29m26s')
    traj.adp(full_parameter_name='foo', value_dict={'bar' : -1}).moo = 'zip'
    
    traj.add_parameter('test.testparam', {'Fuechse':1,'Sapiens':1,'Comment':'ladida'}, param_type=Parameter)

    
    traj.last.foo = 'bar'
    
    traj.add_parameter('Network.Cm')
    
    traj.Network.Cm.value= 1.0
    traj.Network.Cm.unit = 'pF'
    
    traj.Network.Cm()
    
    
    traj.last.herbert = 4.5
    
    traj.Parameters.test.testparam.Konstantin = 'Konstantin'
    
    print traj.last.herbert

    traj.add_parameter(full_parameter_name='honky', value_dict={'mirta':np.array([[1,2,7],[3,2,17]])}, param_type=Parameter)

    traj.add_parameter('flonky',{'val' : 10})
    
    param1 = traj.Parameters.test.testparam
    param2 = traj.Parameters.honky
    param3 = traj.last
    
    print param1()
    
    print param3('val')
    
    exp2_list = range(30)
    exp1_list = range(30)
    exp3_list = range(30)
    explore_dict = { param1.gfn('Sapiens') : exp1_list,
                     param2.get_fullname('mirta'):exp2_list,
                     param3.gfn('val') : exp3_list}
    
    cmb_list=[(param3.gfn('val'),param1.gfn('Sapiens'))]
    
    traj.explore(ut.cartesian_product,explore_dict,cmb_list)

    traj.store_to_hdf5()
    

if __name__ == '__main__':
    main()