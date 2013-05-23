'''
Created on 17.05.2013

@author: Robert Meyer
'''

import logging
import petexceptions as pex
import tables as pt
import numpy as np
import scipy.sparse as spsp
from numpy.numarray.numerictypes import IsType


class BaseParameter(object):
    
    
    def store_to_hdf5(self,hdf5file,hdf5group):
        raise NotImplementedError( "Should have implemented this" )
    
    def load_from_hdf5(self,hdf5group):
        raise NotImplementedError( "Should have implemented this" )
    
    def __init__(self, name, fullname):
        self._name=name
        self._fullname = fullname
    
    def set(self, *args):
        raise NotImplementedError( "Should have implemented this" )
    
    def explore(self, *args):
        raise NotImplementedError( "Should have implemented this" )
    
    def shrink(self):
        raise NotImplementedError( "Should have implemented this" )
    
    def get_next(self, n):
        raise NotImplementedError( "Should have implemented this" )
        
    def get_class_name(self):  
        return self.__class__.__name__

    def get_name(self):
        return (self._name,self._fullname)
    
class Parameter(BaseParameter):
    ''' The standard Parameter that handles creation and access to Simulation Parameters '''
    
    
    class Data(object):
        '''The most fundamental entity that contains the actual data, it is separated to simplify the naming.
        It could also be used as dict but I'll stick to that use for now'''
        pass
    
    
    standard_comment = 'Dude, please explain a bit what your fancy parameter is good for!'

    def __init__(self, name, fullname):
        super(Parameter,self).__init__(name,fullname)
        self._locked=False
        self._comment= Parameter.standard_comment
        self._data=[Parameter.Data()]
        self._isarray = False
        #self._accesspointer = 0
        #self._constructor='Parameter'
        
        #self._accessname = accessname
        
        #self._accessedfrom = None
        
        self._logger = logging.getLogger('mypet.parameter.Parameter=' + self._name)
        
        
        
        self._logger.debug('Created the Parameter ' + self._name)



    
    def become_array(self):
        self._isarray = True
    
    
    
    def _is_supported_data(self, data):
        ''' Simply checks if data is supported '''
        return type(data) in [np.ndarray, int, str, float, bool]
    
    def _values_of_same_type(self,val1, val2):
        if not type(val1) == type(val2):
            return False
        
        if type(val1) == np.array:
            if not val1.dtype == val2.dtype:
                return False
            
            if not np.shape(val1)==np.shape(val2):
                return False
        
        return True
        

    def add_comment(self,comment):
        ''' Extends the existing comment
        :param comment: The comment as string which is added to the existing comment'''
        if self._comment == Parameter.standard_comment:
            self._comment = comment
        else:
            self._comment = self._comment + '; ' + comment
            
            
       
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
            self._set_single(args[0], args[1])
        else:
            raise TypeError('Set takes at max two arguments, but ' +str(len(args)) + ' provided.')
    
    def _set_single(self,name,val):
        if self._locked:
            raise pex.ParamterLockedException('Parameter ' + self._name + ' is locked!')
        
        if name == 'Comment':
            self._comment = val
            return

        if not self._is_supported_data(val):
            raise AttributeError('Unsupported data type: ' +str(type(val)))
        elif not self._isarray:
            if name in self._data[0].__dict__:
                self._logger.warning('Redefinition of Parameter, the old value of ' + name + ' will be overwritten.')
            self._data[0].__dict__[name] = val
        else:
            self._logger.warning('Redefinition of Parameter, the array will be deleted.')
            if name in self._data[0].__dict__:
                self._logger.warning('Redefinition of Parameter, the old value of ' + name + ' will be overwritten.')
            self._data[0].__dict__[name] = val;
            del self._data[1:]
            self._isarray = False
    
    def lock(self):
        self._locked = True;
        
    
        
    def change_values_in_array(self,name,values,positions):  
        
        if not self._isarray:
            raise pex.ParameterNotArrayException('Parameter ' + self._name + ' is not an array!')
        
        if self._locked:
            raise pex.ParameterLockedException('Parameter ' + self._name + ' is locked!') 
    
    
        if not type(positions) is list:
            positions = [positions];
            values = [values];
        else:
            if not len(positions) == len(values):
                raise AttributeError('Parameter ' + self._name + ': List are not of equal length, positions has ' +len(positions)  +' entries and values ' + len(values) +'.')
        
        for idx, pos in enumerate(positions) :      
        
            val = values[idx]
            
            if not len(self._data) >= pos:
                raise AttributeError('Parameter ' + self._name + ' does not have ' +str(pos) +' data items.')
            
           
            if not hasattr(self._data[0], name):
                raise AttributeError('Parameter ' + self._name + ' does not have ' + name +' data.')
            
            if not self._is_supported_data(val):
                    raise AttributeError()
            
            default_val = self._data[0].__dict__[name]
            
            if not self._values_of_same_type(val,default_val):
                raise AttributeError('Parameter ' + self._name + ' has different default type for ' + name)
            
            self._data[pos].__dict__[name]=val
            
    def to_list_of_dicts(self):
        
        if not self._isarray:
            resultdict = self._data[0].__dict__.copy()
        
        else:
            resultdict = []
            for item in self._data:
                resultdict.append(item.__dict__.copy())
        
        return resultdict
    
    
    def is_array(self):  
        return self._isarray
    
    def is_locked(self):
        return self._locked
        

    def to_dict_of_lists(self):
        resultdict = self._data[0].__dict__.copy()
         
        if self._isarray:
            for key in resultdict.iterkeys():
                resultdict[key] = [resultdict[key]]
                for dataitem in self._data[1:]:
                    curr_list = resultdict[key]
                    curr_list.append(dataitem.__dict__[key])
                    resultdict[key] = curr_list
        return resultdict

    def explore(self, explore_dict):
        if self._locked:
            self._logger.warning('Parameter ' + self._name + 'is locked, but I will allow exploration.')
        for key,values in explore_dict.items():
            if not type(values) is list:
                raise AttributeError('Dictionary does not contain lists, thus no need for parameter exploration.')
            
            val=values[0]
            
            
            if not key in self._data[0].__dict__:
                self._logger.warning('Key ' + key + ' not found for parameter ' + self._name + ',\n I don not appreciate this but will add it to the parameter.')
            elif not self._values_of_same_type(val, self._data[0].__dict__[key]):
                self._logger.warning('Key ' + key + ' found for parameter ' + self._name + ', but the types are not matching.\n Previous type was ' + str(type( self._data[0].__dict__[key])) + ', type now is ' + str(type(val))+ '. I don not appreciate this but will overwrite the parameter.')
            if  key in self._data[0].__dict__:
                del self._data[0].__dict__[key]
            self._set_single(key, val)
        
        del self._data[1:]
        self.become_array()
        self.add_items_as_dict(explore_dict)
        self._data = self._data[1:]
    
    
    def add_items_as_dict(self,itemdict):
        
        if self._locked:
            raise pex.ParameterLockedException('Parameter ' + self._name + ' is locked!') 
        
        if not self._isarray:
            raise pex.ParameterNotArrayException('Parameter ' + self._name + ' is not an array!')
    
        if not type(itemdict[itemdict.keys()[0]]) is list:
            act_length = 1
        else:
            act_length = len(itemdict[itemdict.keys()[0]])
            
        for key in itemdict.keys():
            if not key in self._data[0].__dict__:
                self._logger.warning('Key ' + key + ' not found in Parameter, I am ignoring it.')
            if not type(itemdict[key]) is list:
                itemdict[key] = [list]
            if not act_length == len(itemdict[key]):
                raise AttributeError('The entries of the dictionary do not have the same length.')
        
        for idx in range(act_length):
            newdata = Parameter.Data();
            
            for key, val in self._data[0].__dict__.items():
                if not key in itemdict:
                    itemdict[key] = [val for idy in range(act_length)]
                else:
                    newval = itemdict[key][idx];
                    if not self._values_of_same_type(val,newval):
                        raise AttributeError('Parameter ' + self._name + ' has different default type for ' + key)
                    
                newdata.__dict__[key] = itemdict[key][idx]
            
            self._data.append(newdata) 
          
    
    def add_items_as_list(self,itemdicts):
        
        if self._locked:
            raise pex.ParameterLockedException('Parameter ' + self._name + ' is locked!') 
         
        if not self._isarray:
            raise pex.ParameterNotArrayException('Parameter ' + self._name + ' is not an array!')
        
        if not type(itemdicts) is list:
            itemdicts = [itemdicts]
    
        
        for itemdict in itemdicts:
            for key in itemdict.keys():
                if not key in self._data[0].__dict__:
                    self._logger.warning('Key ' + key + ' not found in Parameter, I am ignoring it.')
            newdata = Parameter.Data();
            
            for key, val in self._data[0].__dict__.items():
                if not key in itemdict:
                    itemdict[key] = val
                else:
                    newval = itemdict[key];
                    if not self._values_of_same_type(val,newval):
                        raise AttributeError('Parameter ' + self._name + ' has different default type for ' + key)
                    
                newdata.__dict__[key] = itemdict[key]
            
            self._data.append(newdata)
     
    def _get_longest_stringsize(self,key):   

        maxlength = 0
        for dataitem in self._data:
            maxlength = max(len(dataitem.__dict__[key]),maxlength)
        
        return maxlength
        
    def _get_table_col(self, key, val):
        if isinstance(val, int):
                return pt.IntCol()
        if isinstance(val, float):
                return pt.Float64Col()
        if isinstance(val, bool):
                return pt.BoolCol()
        if isinstance(val, str):
                itemsize = int(self._get_longest_stringsize(key) * 1.5)
                return pt.StringCol(itemsize=itemsize)
        if isinstance(val, np.ndarray):
            valdtype = val.dtype
            valshape = np.shape(val)
                
            if np.issubdtype(valdtype, int):
                    return pt.IntCol(shape=valshape)
            if np.issubdtype(valdtype, float):
                    return pt.Float64Col(shape=valshape)
            if np.issubdtype(valdtype, bool):
                    return pt.BoolCol(shape=valshape)
        
        return None
            
                
    def _make_description(self):
        
        descriptiondict={}
        
        for key, val in self._data[0].__dict__.items():
                       
            col = self._get_table_col(key, val)
            
            if col is None:
                raise TypeError('Entry ' + key + ' cannot be translated into pytables column')
            
            descriptiondict[key]=col
             
        return descriptiondict
                    
    def _store_single_item(self,row,key,val):
        row[key] = val
    
    def store_to_hdf5(self,hdf5file,hdf5group):
        
        tabledict = self._make_description()

        table = hdf5file.createTable(where=hdf5group, name=self._name, description=tabledict, title=self._name);
        
        for item in self._data:
            newrow = table.row
            for key, val in item.__dict__.items():
                self._store_single_item(newrow,key,val)
            
            newrow.append()
        
        table.flush()
        
        commentlength = int(len(self._comment)*1.5)
        infodict= {'Name':pt.StringCol(self._string_length_large(self._name)), 
                   'Full_Name': pt.StringCol(self._string_length_large(self._fullname)), 
                   'Comment':pt.StringCol(self._string_length_large(self._comment)),
                   'Type':pt.StringCol(self._string_length_large(str(type(self)))),
                   'Class_Name': pt.StringCol(self._string_length_large(self.__class__.__name__))}
        infotable=hdf5file.createTable(where=hdf5group, name='Info', description=infodict, title='Info')
        newrow = infotable.row
        newrow['Name'] = self._name
        newrow['Full_Name'] = self._fullname
        newrow['Comment'] = self._comment
        newrow['Type'] = str(type(self))
        newrow['Class_Name'] = self.__class__.__name__
        newrow.append()
        
        infotable.flush()
  
        
    def load_from_hdf5(self, hdf5group):
        
        assert isinstance(hdf5group,pt.Group)
        
        infotable = hdf5group.Info
        
        assert isinstance(infotable,pt.Table)
        
        inforow = infotable[0]

        self._comment = inforow['Comment']
        
        table = getattr(hdf5group,self._name)
        assert isinstance(table,pt.Table)
        
        nrows = table.nrows
        

        
        datanames = table.colnames
        #self.set(dataitem)
        
        dict_of_lists = {}
        
        for colname in datanames:
            dict_of_lists[colname] = self._load_single_col(table,colname)
            val = dict_of_lists[colname].pop(0)
            self._set_single(colname, val)
          
        if nrows > 1:
            self.become_array()  
        
        if self.is_array():
            self.add_items_as_dict(dict_of_lists)
            
    def _load_single_col(self,table,colname):
        assert isinstance(table, pt.Table)
        
        col_data = table.col(colname)
        if len(col_data.shape)==1:
            list_data = col_data.tolist()
        else:
            list_data  =[a for a in col_data]
        return list_data

#     def _convert_to_data(self,col_data):
#         assert isinstance(col_data,pt.Col)
#         
#         valdtype = col_data.dtype
#         value = col_data[:]
#         if col_data.shape
#         
#             if np.issubdtype(valdtype, int):
#                         if not=col_data.shape
#                             
#             if np.issubdtype(valdtype, float):###TODOOO
#                         return pt.Float64Col(shape=valshape)
#             if np.issubdtype(valdtype, bool):
#                         return pt.BoolCol(shape=valshape)
        
    
    def _string_length_large(self,string):  
        return  int(len(self._comment)*1.5)
                
    
    def to_dict(self):
        return self._data[0].__dict__.copy()
        
    def get(self, name):
        if  not hasattr(self._data[0],name):
            raise AttributeError('Parameter ' + self._name + ' does not have attribute ' + name +'.')
        
        return self._data[0].__dict__[name]
        
    
    def __getattr__(self,name):
        #self._accessedfrom = self._accessname
        return self.get(name)
 
    def shrink(self):
        self._isarray = False
        del self._data[1:]
 
    
     




class SparseParameter(Parameter):
    
    
    def _is_supported_data(self, data):
        ''' Simply checks if data is supported '''
        if type(data) in [np.ndarray, int, str, float, bool]:
            return True
        if spsp.issparse(data):
            return True
        return False
    
    def _get_table_col(self,key,val):
            
            if spsp.issparse(val):
                
                sparsedict={}
                #val = spsp.lil_matrix(100,100)
                valformat = val.format
                sparsedict['format']=pt.StringCol(3)
                val = val.tocsr()
                data_list= [ val.data,val.indptr,val.indices]
                idx_list = ['data', 'indptr','indices']
                for idx, dat in enumerate(data_list):
                    sidx = idx_list[idx]
                    valdtype = dat.dtype
                    valshape = dat.shape
                    if np.issubdtype(valdtype,int):
                        sparsedict[sidx] = pt.IntCol(shape=valshape)
                    elif np.issubdtype(valdtype, float):
                        sparsedict[sidx] = pt.Float64Col(shape=valshape)
                    elif np.issubdtype(valdtype, bool):
                        sparsedict[sidx] = pt.BoolCol(shape=valshape)
                    else:
                        self._logger.error('You should NOT be here, something is wrong!')
                        
                return sparsedict
                    
            return super(SparseParameter,self)._get_table_col(key,val)
                         
    def _store_single_item(self,row,key,val):
        val = val.tocsr()
        row[key+'/format'] = val.format
        row[key+'/data'] = val.data
        row[key+'/indptr'] = val.indptr
        row[key+'/indices'] = val.indices
    


    def _values_of_same_type(self,val1, val2):
        if not super(SparseParameter,self)._values_of_same_type(self,val1, val2):
            return False
        
        if spsp.issparse(val1):
            if not val1.format == val2.format:
                return False
            if not val1.dtype == val2.dtype:
                return False
            if not val1.shape == val2.shape:
                return False
            if not len(val1.nonzero()[0]) == len(val2.nonzero()[0]):
                return False

        return True
    
    
    def load_from_hdf5(self, hdf5group):
        pass
   





     

