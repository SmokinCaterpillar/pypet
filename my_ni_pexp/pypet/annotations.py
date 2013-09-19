__author__ = 'robert'

from pypet import globally
import numpy as np


class Annotations(object):
    ''' Simple container class for annotations in Parameters and Results and the Trajectory'''

    def f_to_dict(self,copy=True):
        if copy:
            return self.__dict__.copy()
        else:
            return seluf.__dict__

    def f_is_empty(self):
        return len(self.__dict__)==0

    def f_get(self,*args):
        result_list = []
        for name in args:
            if isinstance(name,int):
                name = 'ann_%d' % name

            result_list.append(getattr(self,name))

        if len(args)==1:
            return result_list[0]
        else:
            return tuple(result_list)

    def f_set(self,*args,**kwargs):
        for idx,arg in enumerate(args):
            valstr = 'ann_'+str(idx)
            self.f_set_single(valstr,arg)

        for key, arg in kwargs.items():
            self.f_set_single(key,arg)

    def f_set_single(self,name,data):
         setattr(self,name,data)

    def f_ann_to_str(self):
        resstr = ''
        for key in sorted(self.__dict__.keys()):
            resstr+='%s=%s, ' % (key,self.__dict__[key])
            if len(resstr) >= globally.HDF5_STRCOL_MAX_COMMENT_LENGTH:
                resstr=resstr[0:globally.HDF5_STRCOL_MAX_COMMENT_LENGTH-3]+'...'
                return resstr

        if len(resstr)>2:
            resstr=resstr[0:-2]
        return resstr

    def __str__(self):
        return self.f_ann_to_str()







class WithAnnotations(object):

    def __init__(self):
        self._annotations = Annotations()

    @property
    def v_annotations(self):
        ''' Annotations to an object
        '''

        return self._annotations

    def f_set_annotations(self,*args,**kwargs):
        '''Sets Annotations'''


        self._annotations.f_set(*args,**kwargs)

    def f_get_annotations(self,*args):
        return self._annotations.f_get(*args)

    def f_ann_to_string(self):
        return self._annotations.f_ann_to_str()



