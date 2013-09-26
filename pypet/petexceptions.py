'''
Created on 17.05.2013
'''

__version__ = '3'

class ParameterLockedException(TypeError):
    '''Exception raised if someone tries to modify a locked ParameterSet'''
    def __init__(self,msg):
        self._msg=msg
        
    def __str__(self):
        return repr(self._msg)
    
class ParameterNotArrayException(TypeError):
    '''Exception raised if someone tries to treat the Parameter as an Parameter Array if it is not'''
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
    
class NoSuchServiceError(TypeError):
    '''Exception raised by the Storage Service if a specific operation is not supported, i.e. the message is not understood.
    '''
    def __init__(self,msg):
        self._msg=msg

    def __str__(self):
        return repr(self._msg)


class NotUniqueNodeError(AttributeError):
    '''Exception raised by the Natural Naming if a node can be found more than once.
    '''
    def __init__(self,msg):
        self._msg=msg

    def __str__(self):
        return repr(self._msg)

class TooManyGroupsError(TypeError):
    '''Exception raised by natural naming fast search if fast search cannot be applied
    '''
    def __init__(self,msg):
        self._msg=msg

    def __str__(self):
        return repr(self._msg)