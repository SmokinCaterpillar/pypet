__author__ = 'robert'

from mypet import globally
import numpy as np

class Annotations(object):
    ''' Simple container class for annotations in Parameters and Results and the Trajectory'''
    def __init__(self,annotations=None):
        if not annotations is None:
            for key,val in annotations.items():
                if isinstance(key,int):
                    key = 'ann_%d' % key

                self.set_single(key,val)


    def _supports(self,data):
        if isinstance(data, (tuple,list)):
            for item in data:
                old_type = None
                if not type(item) in globally.PARAMETER_SUPPORTED_DATA:
                    return False
                if not old_type is None and old_type != type(item):
                    return False
                old_type = type(item)
            return True

        if isinstance(data, np.ndarray):
            dtype = data.dtype
            if np.issubdtype(dtype,np.str):
                dtype = np.str
        else:
            dtype=type(data)

        return dtype in globally.PARAMETER_SUPPORTED_DATA

    def __setattr__(self,name,data):
        self.set_single(name,data)


    def to_dict(self):
        return self.__dict__.copy()



    def get(self,*args):
        result_list = []
        for name in args:
            if isinstance(name,int):
                name = 'ann_%d' % name

            result_list.append(getattr(self,name))

        if len(args)>1:
            return result_list[0]
        else:
            return tuple(result_list)

    def set(self,*args,**kwargs):
        for idx,arg in enumerate(args):
            valstr = 'ann_'+str(idx)
            self.set_single(valstr,arg)

        for key, arg in kwargs.items():
            self.set_single(key,arg)

    def _set_dirty(self,state_dict):

        for key in self.__dict__:
            delattr(self,key)

        self.__dict__.update(state_dict)



    def set_single(self,name,data):
        if not self._supports(data):
            raise AttributeError('Annotations not supported for >>%s<<, its type >>%s<< cannot be'
                                 'handled.' % (name, str(type(data))))
        else:
            self.__dict__[name] = data

    def ann2str(self):
        resstr = ''
        for key in sorted(self.__dict__.keys()):
            resstr+='%s=%s, ' % (key,self.__dict__[key])
            if len(resstr) >= globally.HDF5_STRCOL_MAX_COMMENT_LENGTH:
                resstr=resstr[0:globally.HDF5_STRCOL_MAX_COMMENT_LENGTH-3]+'...'
                return resstr

        resstr=resstr[0:-2]
        return resstr

    def __str__(self):
        return self.ann2str()







class WithAnnotations(object):

    def get_annotations(self,*args):
        if len(args) == 0:
            return self._annotations
        else:
            return self._annotations.get(*args)

    @property
    def annotations_(self):
        ''' Annotations to an object
        '''
        return self._annotations

    def set_annotations(self,*args,**kwargs):
        '''Sets Annotations'''
        self._annotations.set(*args,**kwargs)

    def ann2str(self):
        return self._annotations.ann2str()

