""" Module defining annotations.

This module contains two classes:

    1. :class:`~pypet.annotations.Annotations`

        Container class for annotations. There are no restrictions regarding what is considered
        to be an annotation. In principle, this can be any python object. However,
        if using the standard :class:`~pypet.storageservice.HDF5StorageService`,
        these annotations are stored as hdf5 node attributes.
        Accordingly, annotations should be rather small since reading
        and writing these attributes to disk is slow.

    2. :class:`~pypet.annotations.WithAnnotations`

        Abstract class to subclass from. Instances that subclass `WithAnnotations`
        have the `v_annotations` property which is an instance of the `Annotations` class
        to handle annotations. They also acquire some functions to put annotations directly
        into the `v_annotations` object like `f_set_annotations`.

"""

__author__ = 'Robert Meyer'

from pypet.pypetlogging import HasLogger
from pypet.slots import HasSlots

class Annotations(HasSlots):
    """ Simple container class for annotations.

    Every tree node (*leaves* and *group* nodes) can be annotated.
    In case you use the standard :class:`~pypet.storageservice.HDF5StorageService`,
    these annotations are stored in the attributes of the hdf5 nodes in the hdf5 file,
    you might wanna take a look at pytables attributes_.

    Annotations should be small (short strings or basic python data types) since their storage
    and retrieval is quite slow!

    .. _attributes: http://pytables.github.io/usersguide/libref/declarative_classes.html#the-attributeset-class

    """
    __slots__ = ('_dict_',)

    def __init__(self):
        self._dict_ = None

    @property
    def _dict(self):
        if self._dict_ is None:
            self._dict_ = {}
        return self._dict_


    def __iter__(self):
        return self._dict.__iter__()

    def __getitem__(self, item):
        """Equivalent to calling f_get()"""
        return self.f_get(item)

    def __setitem__(self, key, value):
        """Almost equivalent to calling __setattr__.

        Treats integer values as `f_get`.

        """
        self.f_set(**{key: value})

    def __delitem__(self, key):
        self.f_remove(key)

    def f_to_dict(self, copy=True):
        """Returns annotations as dictionary.

        :param copy: Whether to return a shallow copy or the real thing (aka _dict).

        """
        if copy:
            return self._dict.copy()
        else:
            return self._dict

    def f_is_empty(self):
        """Checks if annotations are empty"""
        return len(self._dict) == 0

    def f_empty(self):
        """Removes all annotations from RAM """
        self._dict_ = None

    def __setattr__(self, key, value):
        if key.startswith('_'):
            # We set a private attribute
            super(Annotations, self).__setattr__(key, value)
        else:
            self.f_set_single(key, value)

    def __getattr__(self, item):
        return self.f_get(item)

    def __delattr__(self, item):
        self.f_remove(item)

    def _translate_key(self, key):
        if isinstance(key, int):
            if key == 0:
                key = 'annotation'
            else:
                key = 'annotation_%d' % key
        return key

    def f_get(self, *args):
        """Returns annotations

        If len(args)>1, then returns a list of annotations.

        `f_get(X)` with *X* integer will return the annotation with name `annotation_X`.

        If the annotation contains only a single entry you can call `f_get()` without arguments.
        If you call `f_get()` and the annotation contains more than one element a ValueError is
        thrown.

        """

        if len(args) == 0:
            if len(self._dict) == 1:
                return self._dict[list(self._dict.keys())[0]]
            elif len(self._dict) > 1:
                raise ValueError('Your annotation contains more than one entry: '
                                 '`%s` Please use >>f_get<< with one of these.' %
                                 (str(list(self._dict.keys()))))
            else:
                raise AttributeError('Your annotation is empty, cannot access data.')

        result_list = []
        for name in args:
            name = self._translate_key(name)
            try:
                result_list.append(self._dict[name])
            except KeyError:
                raise AttributeError('Your annotation does not contain %s.' % name)

        if len(args) == 1:
            return result_list[0]
        else:
            return tuple(result_list)

    def f_set(self, *args, **kwargs):
        """Sets annotations

        Items in args are added as `annotation` and `annotation_X` where
        'X' is the position in args for following arguments.

        """
        for idx, arg in enumerate(args):
            valstr = self._translate_key(idx)
            self.f_set_single(valstr, arg)

        for key, arg in kwargs.items():
            self.f_set_single(key, arg)

    def f_remove(self, key):
        """Removes `key` from annotations"""
        key = self._translate_key(key)
        try:
            del self._dict[key]
        except KeyError:
            raise AttributeError('Your annotations do not contain %s' % key)


    def f_set_single(self, name, data):
        """ Sets a single annotation. """
        self._dict[name] = data

    def f_ann_to_str(self):
        """Returns all annotations lexicographically sorted as a concatenated string."""
        resstr = ''
        for key in sorted(self._dict.keys()):
            resstr += '%s=%s; ' % (key, str(self._dict[key]))
        return resstr[:-2]

    def __str__(self):
        return self.f_ann_to_str()


class WithAnnotations(HasLogger):

    __slots__ = ('_annotations',)

    def __init__(self):
        self._annotations = Annotations()  # The annotation object to handle annotations

    @property
    def v_annotations(self):
        """ Annotation feature of a trajectory node.

        Store some short additional information about your nodes here.
        If you use the standard HDF5 storage service, they will be stored as hdf5 node
        attributes_.

        .. _attributes: http://pytables.github.io/usersguide/libref/declarative_classes.html#the-attributeset-class

        """
        return self._annotations

    def f_set_annotations(self, *args, **kwargs):
        """Sets annotations

        Equivalent to calling `v_annotations.f_set(*args,**kwargs)`

        """
        self._annotations.f_set(*args, **kwargs)

    def f_get_annotations(self, *args):
        """Returns annotations

        Equivalent to `v_annotations.f_get(*args)`

        """
        return self._annotations.f_get(*args)

    def f_ann_to_str(self):
        """Returns annotations as string

        Equivalent to `v_annotations.f_ann_to_str()`

        """
        return self._annotations.f_ann_to_str()
