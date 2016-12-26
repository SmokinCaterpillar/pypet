"""Module containing the superclass having slots"""

__author__ = 'Robert Meyer'


def get_all_slots(cls):
    """Iterates through a class' (`cls`) mro to get all slots as a set."""
    slots_iterator = (getattr(c, '__slots__', ()) for c in cls.__mro__)
    # `__slots__` might only be a single string,
    # so we need to put the strings into a tuple.
    slots_converted = ((slots,) if isinstance(slots, str) else slots
                                for slots in slots_iterator)
    all_slots = set()
    all_slots.update(*slots_converted)
    return all_slots


class MetaSlotMachine(type):
    """Meta-class that adds the attribute `__all_slots__` to a class.

    `__all_slots__`  is a set that contains all unique slots of a class,
    including the ones that are inherited from parents.

    """
    def __init__(cls, name, bases, dictionary):
        super(MetaSlotMachine, cls).__init__(name, bases, dictionary)
        cls.__all_slots__ = get_all_slots(cls)


class HasSlots(object, metaclass=MetaSlotMachine):
    """Top-class that allows mixing of classes with and without slots.

    Takes care that instances can still be pickled with the lowest
    protocol. Moreover, provides a generic `__dir__` method that
    lists all slots.

    """
    __slots__ = ('__weakref__',)

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
        """Recalls state for items with slots"""
        for key in state:
            setattr(self, key, state[key])

    def __dir__(self):
        """Includes all slots in the `dir` method"""
        result = set()
        result.update(dir(self.__class__), self.__all_slots__)
        if hasattr(self, '__dict__'):
            result.update(self.__dict__.keys())
        return list(result)
