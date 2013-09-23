__author__ = 'robert'

from pypet import globally
import numpy as np


class Annotations(object):
    ''' Simple container class for annotations.

    Every tree node (*leaves* and *group* nodes) can be annotated.
    These annotations are stored in the attributes of the hdf5 nodes in the hdf5 file,
    you might wanna take a look at pytables attributes_.

    Annotations should be small (short strings or basic python data types). Since there storage
    and retrieval is quite slow!

    .. _attributes: http://pytables.github.io/usersguide/libref/declarative_classes.html#the-attributeset-class

    '''

    def f_to_dict(self,copy=True):
        '''Returns annotations as dictionary.

        :param copy: Whether to returner a shallow copy or the real thing (aka __dict__).
        '''
        if copy:
            return self.__dict__.copy()
        else:
            return self.__dict__

    def f_is_empty(self):
        '''Checks if annotations are empty'''
        return len(self.__dict__)==0

    def f_get(self,*args):
        '''Returns annotations.

        If len(args)>1, then returns a list of annotations.

        `f_get(X)` with *X* integer will return the annotation with name `ann_X`.
        '''
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
        ''' Sets annotations.

        Items in args are added with the names `ann_X` where *X* is the index in the args list.
        '''
        for idx,arg in enumerate(args):
            valstr = 'ann_'+str(idx)
            self.f_set_single(valstr,arg)

        for key, arg in kwargs.items():
            self.f_set_single(key,arg)

    def f_set_single(self,name,data):
        ''' Sets a single annotation '''
        setattr(self,name,data)

    def f_ann_to_str(self):
        '''Returns all annotations as a concatenated string.

        Truncates string if longer than maximum comment length.
        '''
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
        ''' Annotation feature of a trajectory node.

        Store some short additional information about your nodes here.
        If you use the standard HDF5 storage service, they will be stored as hdf5 node
        attributes_.

        For example:

        >>> traj._c

        .. _attributes: http://pytables.github.io/usersguide/libref/declarative_classes.html#the-attributeset-class

        '''
        return self._annotations

    def f_set_annotations(self,*args,**kwargs):
        '''Sets Annotations

        Eqivalent to calling `v_annotations.f_set(*args,**kwargs)`
        '''
        self._annotations.f_set(*args,**kwargs)

    def f_get_annotations(self,*args):
        '''Returns annotations

        Equivalent to `v_annotations.f_get(*args)`
        '''
        return self._annotations.f_get(*args)

    def f_ann_to_string(self):
        '''Returns annotations as string.

        Equivalent to `v_annotations.f_ann_to_str()`
        '''
        return self._annotations.f_ann_to_str()



