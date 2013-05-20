'''
Created on 17.05.2013

@author: Robert Meyer
'''

import logging
import petexceptions as pex
import tables as pt
import numpy as np


class BaseParameter(object):
    
    
    def store_to_hdf5(self,hdf5file,hdf5group):
        raise NotImplementedError( "Should have implemented this" )
    
    def open_hdf5_and_create_group(self, filepath, pregroup):
        raise NotImplementedError( "Should have implemented this" )
    
    def __init__(self, name, fullname):
        raise NotImplementedError( "Should have implemented this" )
    
    def set(self, *args):
        raise NotImplementedError( "Should have implemented this" )
        
        
        
        

class Parameter(BaseParameter):
    ''' The standard Parameter that handles creation and access to Simulation Parameters '''
    
    
    class Data(object):
        '''The most fundamental entity that contains the actual data, it is separated to simplify the naming.
        It could also be used as dict but I'll stick to that use for now'''
        pass
    
    
    standard_comment = 'Dude, please explain a bit what your fancy parameter is good for!'

    
    def __init__(self, name, fullname):
        self._name=name
        self._fullname = fullname
        self._locked=False
        self._comment= Parameter.standard_comment
        self._data=[Parameter.Data()]
        self._isarray = False
        self._accesspointer = 0
        
        self._logger = logging.getLogger('mypet.parameter.Parameter=' + self._name)
        
        self._supported_data = self._get_supported_data()
        
        self._logger.debug('Created the Parameter ' + self._name)

    def _get_supported_data(self):
        ''' Simply returns the supported data types can be extended if wished '''
        return [np.ndarray, int, str, float, bool]
    
    def _values_of_same_type(self,val1, val2):
        if not type(val1) == type(val2):
            return False
        
        if type(val1) == np.array:
            if not val1.dtype == val2.dtype:
                return False
            
            if not np.shape(val1)==np.shape(val2):
                return False
        
        return True
        

    def addcomment(self,comment):
        ''' Extends the existing comment
        :param comment: The comment as string which is added to the existing comment'''
        if self._comment == Parameter.standard_comment:
            self._comment = comment
        else:
            self._comment = self._comment + '; ' + comment
            
    def add_attributes(self, attribute_dict):
        for key, val in attribute_dict.items():
            if hasattr(self._data[0], key):
                self._logger.warning('Parameter entry ' + key +' exists, I will replace it.')
            self.key = val
            
       
    def __setattr__(self,name,value):
        
        if name[0]=='_':
            self.__dict__[name] = value
        else:
            self._set_single(name,value)
        
    def set(self,*args):
        
        if len(args) == 1:
            valuedict = args[0]
            if not type(valuedict) is dict:
                raise AttributeError('Input is not a dictionary.')
            for key, val in valuedict.items():
                self._set_single(key, val)
        elif len(args) == 2:
            self._set_single(args[0], val[1])
        else:
            raise TypeError('Set takes at max two arguments, but ' +str(len(args)) + ' provided.')
    
    def _set_single(self,name,val):
        if self._locked:
            raise pex.ParamterLockedException('Parameter ' + self._name + ' is locked!')
        
        if name == 'Comment':
            self._comment = val
            return

        if not type(val) in self._supported_data:
            raise AttributeError('Unsupported data type: ' +str(type(val)))
        elif not self._isarray:
            self._data[0].__dict__[name] = val
        else:
            self._logger.warning('Redefinition of Parameter, the Array will be deleted.')
            self._data[0].__dict__[name] = val;
            del self._data[1:]
    
    def lock(self):
        self._locked = True;
        
    def change_values_in_array(self,name,values,positions):  
        
        if not self._isarray:
            raise pex.ParameterNotArrayException('Parameter ' + self._name + ' is not an array!')
        
        if self._locked:
            raise pex.ParameterNotArrayException('Parameter ' + self._name + ' is locked!') 
    
    
        if not type(positions) is list:
            positions = [positions];
            values = [values];
        else:
            if len(positions) == len(values):
                raise pex.ParameterModifyExcpetion('Parameter ' + self._name + ': List are not of equal length, positions has ' +len(positions)  +' entries and values ' + len(values) +'.')
        
        
        
        for idx, pos in enumerate(positions) :      
        
            val = values[idx]
            
            if not len(self._data) >= pos:
                raise pex.ParameterModifyExcpetion('Parameter ' + self._name + ' does not have ' +str(pos) +' data items.')
            
           
            if not hasattr(self._data[0], name):
                raise pex.ParameterModifyExcpetion('Parameter ' + self._name + ' does not have ' + name +' data.')
            
            if not val in self._supported_data:
                    raise AttributeError()
            
            default_val = self._data[0].name
            
            if not self._values_of_same_type(val,default_val):
                raise pex.ParameterModifyExcpetion('Parameter ' + self._name + ' has different default type for ' + name)
            
            self._data[pos]=val
            
    def full_parameter_to_dict(self):
        
        if not self._isarray:
            resultdict = self._data[0].__dict__
        
        else:
            resultdict = []
            for item in self._data:
                resultdict.append(item.__dict__)
        
        return resultdict
    
    
    def is_array(self):  
        return self._isarray
    
    def is_locked(self):
        return self._locked
        

#     def parameter_to_dict(self):
#         resultdict = self._data[0].__dict__
#         
#         if self._isarray:
#             for key in resultdict.iterkeys():
#                 resultdict[key] = [resultdict[key]]
#                 for dataitem in self._data[1:]:
#                     resultdict[key] = resultdict[key].append(dataitem.key)
#         return resultdict

    
    
    def add_item_to_array(self,itemdicts):
         
        if not self._isarray:
            raise pex.ParameterNotArrayException('Parameter ' + self._name + ' is not an array!')
        
        if not type(itemdicts) is list:
            itemdicts = [itemdicts]
        
        for key in itemdicts.keys:
            if not key in self._data[0]:
                self._logger.warning('Key ' + key + ' not found in Parameter, I am ignoring it.')
        
        for itemdict in itemdicts:
            newdata = Parameter.Data();
            
            for key, val in self._data[0].__dict__.items():
                if not itemdict.haskey(key):
                    itemdict[key] = val
                else:
                    newval = itemdict[key];
                    if not self._values_of_same_type(val,newval):
                        raise pex.ParameterModifyExcpetion('Parameter ' + self._name + ' has different default type for ' + key)
                    
                newdata.key = itemdict[key]
            
            self._data.append(newdata)
     
    def get_longest_stringsize(self,key):   

        maxlength = 0
        for dataitem in self._data:
            maxlength = max(len(dataitem.key),maxlength)
        
        return maxlength
        
          
    def make_descripion(self):
        
        descriptiondict={}
        
        for key, val in self._data[0].items():
            
            valtype = type(val)
                       
            if valtype is int:
                descriptiondict[key] = pt.IntCol()
            elif valtype is float:
                descriptiondict[key] = pt.Float64Col()
            elif valtype is bool:
                descriptiondict[key] = pt.BoolCol()
            elif valtype is str:
                itemsize = int(self.get_longest_stringsize(key) * 1.5)
                descriptiondict[key] = pt.StringCol(itemsize=itemsize)
            elif valtype is np.ndarray:
                valdtype = val.dtype
                valshape = np.shape(val)
                
                if valdtype == int:
                    descriptiondict[key] = pt.IntCol(shape=valshape)
                elif valdtype == float:
                    descriptiondict[key] = pt.Float64Col(shape=valshape)
                elif valdtype == bool:
                    descriptiondict[key] = pt.BoolCol(shape=valshape)
                else:
                    self._logger.error('You should NOT be here, something is wrong!')
            else:
                self._logger.error('You should NOT be here, something is wrong!')
                    
        
    def open_hdf5_and_create_group(self, filepath, pregroup):
        hdf5file = pt.File(filename=filepath, mode='a',rootUEP=pregroup)

        self.store_to_hdf5(hdf5file, '/') 
        
        hdf5file.close()       
    
    def store_to_hdf5(self,hdf5file,hdf5group):
        
        
        hdf5file = pt.File()
        
#         if not hdf5file is pt.File:
#             raise TypeError('File is not hdf5 file.')
#         
#         if not hdf5group is pt.Group:
#             raise TypeError('Group is not hdf5group.')
        
        hdf5paramgroup= hdf5file.createGroup(where=hdf5group, name=self._name, title=self._name)
        
        tabledict = self.make_descritpion()

        table = hdf5file.createTable(where=hdf5paramgroup, name=self._name, description=tabledict, title=self._name);
        
        for item in self._data:
            newrow = table.row()
            for key, val in item.__dict__.items():
                newrow[key] = val
            
            newrow.append()
        
        table.flush()
        
        commentlength = int(len(self._comment)*1.5)
        ctable=hdf5file.createTable(where=hdf5paramgroup, name='Comment', description={'Comment':pt.StringCol(commentlength)}, title='Comment')
        newrow = ctable.row();
        newrow['comment'] = self._comment
        newrow.append()
        
        ctable.flush()
        
                
    
    def parameter_to_dict(self):
        if self._accesspointer <= len(self._data):
            raise IndexError('Accesspointer of explored Parameter points to a wrong entity')
        
        return self._data[self._accesspointer].__dict__
        
    def get(self, name):
        if  not hasattr(self._data[0],name):
            raise AttributeError('Parameter ' + self._name + ' does not have attribute ' + name +'.')
        if self._accesspointer >= len(self._data):
            raise IndexError('Accesspointer is beyond the parameter values')
        
        return self._data[self._accesspointer].__dict__[name]
        
    
    def __getattr__(self,name):
        return self.get(name)
        
            
        
            
           
        