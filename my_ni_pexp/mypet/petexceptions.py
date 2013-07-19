'''
Created on 17.05.2013

@author: robert
'''
class ParameterLockedException(Exception):
    '''Exception raised if someone tries to modify a locked Parameter'''
    def __init__(self,msg):
        self._msg=msg
        
    def __str__(self):
        return repr(self._msg)
    
class ParameterNotArrayException(Exception):
    '''Exception raised if someone tries to treat the Parameter as an Parameter Array if it is not'''
    def __init__(self,msg):
        self._msg=msg
        
    def __str__(self):
        return repr(self._msg)
    
# class OperationNotSupportedException(Exception):
#     '''Exception raised if someone tries to use a method that is only supported in the parents class'''
#     def __init__(self,msg):
#         self._msg=msg
#          
#     def __str__(self):
#         return repr(self._msg)
    
# class ParameterModifyExcpetion(Exception):
#     '''Exception raised if someone tries to modify a Parameter Array Value which is not existent or does not fit'''
#     def __init__(self,msg):
#         self._msg=msg
#         
#     def __str__(self):
#         return repr(self._msg)
    