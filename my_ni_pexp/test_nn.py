'''
Created on 12.07.2013

@author: robert
'''

from pypet.trajectory import NaturalNamingInterface
def main():
    nnint = NaturalNamingInterface(working_trajectory_name='1', parent_trajectory_name='2')
    
    
    
    nnint._add_to_nninterface('dummy2', '_root_instance.DerivedParameters.WeightDist_STDP_Trajectory_2013_07_12_14h09m54s.Sim.dummy2, data',42)
    
    print dir(nnint)
    
    
    
    
    
    
    
    
    
    
    
    

if __name__ == '__main__':
    main()