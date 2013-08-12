'''
Created on 17.05.2013

@author: robert
'''
class ParameterLockedException(Exception):
    '''Exception raised if someone tries to modify a locked ParameterSet'''
    def __init__(self,msg):
        self._msg=msg
        
    def __str__(self):
        return repr(self._msg)
    
class ParameterNotArrayException(Exception):
    '''Exception raised if someone tries to treat the ParameterSet as an ParameterSet Array if it is not'''
    def __init__(self,msg):
        self._msg=msg
        
    def __str__(self):
        return repr(self._msg)
    
class DefaultReplacementError(Exception):
    '''Exception raised if added parameters should actually replace default settings, but have not probably due to a type.'''
    def __init__(self,msg):
        self._msg=msg

    def __str__(self):
        return repr(self._msg)

