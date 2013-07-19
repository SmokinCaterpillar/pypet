'''
Created on 12.07.2013

@author: robert
'''


class BuggyObject(object):

    
    def __init__(self):   
        self._test_dict = {}

    def _add(self,key, data):
        
        self._test_dict[key] = data
        
        pass

    def __getattr__(self,name):
        
        keys = self.find(name)
        if not keys:
            raise AttributeError('ERR')
        else:
            return self._test_dict[keys[0]]
 
    def find(self,regexp):
        return self._find_keys(regexp)
    
    def _find_keys(self, regexp):
         
        comp_regexp = compile(regexp)
         
        keys = self._test_dict.keys()
        
        matched_keys = []
        for string in keys:
            match = comp_regexp.match(string)
            if not match == None:
                matched_keys.append(string)
            
         
        return matched_keys
        


def main():
    
    buggy_obj = BuggyObject()
    
    buggy_obj._add('I_am_so_short!', 42)
    buggy_obj._add('_root.DerivedParameters.WeightDist_STDP_Trajectory_2013_07_12_14h09m54s.Sim.dummy2', 42)
   
    

if __name__ == '__main__':
    main()