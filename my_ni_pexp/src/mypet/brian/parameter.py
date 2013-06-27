'''
Created on 10.06.2013

@author: robert
'''


from mypet.parameter import Parameter
from brian.units import *
from brian.stdunits import *
from brian.fundamentalunits import Unit, Quantity


class BrianParameter(Parameter):
    ''' The standard Brian Parameter that has a value and a unit
    
    The unit has to be set via param.unit = unit,
    e.g.
    >>> param.unit = mV
    
    the corresponding value is set as
    >>> param.value = 10
    
    If both have been specified
    a call to the param returns the corresponding brian quantity:
    >>> print param()
    >>> 10*mvolt
    
    The brian quantity can also be accessed via param.val
    
    '''
    def __init__(self,name,fullname,*value_list,**value_dict):
        value_list = list(value_list)
        unit = None
        
        if value_list and isinstance(value_list[0],Quantity):
            unit = value_list.pop(0)
    
        super(BrianParameter,self).__init__(name,fullname,*value_list,**value_dict)
    
        if unit:
            self._add_brian_quantity(unit)
            
    
    def _add_brian_quantity(self,unit):
        assert isinstance(unit, Quantity)
        unitstr = unit.in_best_unit(python_code=True)
        
        splitunit = unitstr.split('*')
        value = splitunit.pop(0)
        self.value=value
        unit = '*'.join(splitunit)
        self.unit = unit
        
       

    def __call__(self,valuename=None):
        if not valuename or valuename == 'val':
            if not self.has_value('unit') or  not self.has_value('value'):
                self._logger.info('Brian Parameter has no unit and value.')
                return None
            unit = eval(self.unit)
            value = self.value
            return value*unit   
        else:
            super(BrianParameter,self).__call__(valuename)
            
    def get(self, name):
        
        if name == 'val':
            return self()
            
        return super(BrianParameter,self).get(name)
    
    def _set_single(self,name,val):
        
        if name == 'val' and isinstance(val, Quantity):
            self._add_brian_quantity(val)
            return 
        
        ## Check if unit exists
        if name == 'unit':
            unit = eval(val)
            if not isinstance(unit, Unit):
                raise ValueError('Not a unit!')
        
        super(BrianParameter,self)._set_single(name,val)

    