"""Module containing the superclass having slots"""

__author__ = 'Robert Meyer'


import pypet.compat as compat

class MetaSlotMachine(type):
    """Meta-class that adds the attribute `__all_slots__` to a class.

    `__all_slots__` contains each and every slot of a class,
    including the ones that are inherited from parents.

    """
    def __init__(cls, name, bases, dct):
        super(MetaSlotMachine, cls).__init__(name, bases, dct)
        cls.__all_slots__ = MetaSlotMachine._get_all_slots(cls)

    @staticmethod
    def _get_all_slots(cls):
        """Returns all slots as set"""
        all_slots = (getattr(cls_, '__slots__', []) for cls_ in cls.__mro__)
        return list(set(slot for slots in all_slots for slot in slots))

def add_metaclass(metaclass):
    """Adds a metaclass to a given class.

    This decorator is used instead of `__metaclass__` to allow for
    Python 2 and 3 compatibility.

    """
    def wrapper(cls):
        cls_dict = cls.__dict__.copy()
        slots = cls_dict.get('__slots__', None)
        if slots is not None:
            if isinstance(slots, compat.base_type):
                slots = [slots]
            for slot in slots:
                cls_dict.pop(slot)
        cls_dict.pop('__dict__', None)
        cls_dict.pop('__weakref__', None)
        return metaclass(cls.__name__, cls.__bases__, cls_dict)
    return wrapper

@add_metaclass(MetaSlotMachine)
class HasSlots(object):
    """Top-class that allows mixing of classes with and without slots.

    Takes care that instances can still be pickled with the lowest
    protocol. Moreover, provides a generic `__dir__` method that
    lists all slots.

    """
    __slots__ = ['__weakref__']

    def _get_all_slots(self):
        """Returns all slots as set"""
        return self.__all_slots__
        # all_slots = (getattr(cls, '__slots__', []) for cls in self.__class__.__mro__)
        # return set(slot for slots in all_slots for slot in slots)

    def __getstate__(self):
        if hasattr(self, '__dict__'):
            # We don't require that all sub-classes also define slots,
            # so they may provide a dictionary
            statedict = self.__dict__.copy()
        else:
            statedict = {}
        # Get all slots of potential parent classes
        for slot in self.__all_slots__:
            try:
                value = getattr(self, slot)
                statedict[slot] = value
            except AttributeError:
                pass
        # Pop slots that cannot or should not be pickled
        statedict.pop('__dict__', None)
        statedict.pop('__weakref__', None)
        return statedict

    def __setstate__(self, state):
        for key, value in state.items():
            setattr(self, key, value)

    def __dir__(self):
        result = dir(self.__class__)
        result.extend(self.__all_slots__)
        if hasattr(self, '__dict__'):
            result.extend(compat.iterkeys(self.__dict__))
        return result
