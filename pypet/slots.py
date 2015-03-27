"""Module containing the superclass having slots"""

__author__ = 'Robert Meyer'


class HasSlots(object):
    """Top-class that allows mixing of classes with and without slots"""

    __slots__ = ['__weakref__']  # We want to allow weak references to the objects

    def __getstate__(self):
        if hasattr(self, '__dict__'):
            #  We don't require that all sub-classes also define slots
            statedict = self.__dict__.copy()
        else:
            statedict = {}

        # Get all slots of potential parent classes!
        for slots in [getattr(cls, '__slots__', []) for cls in self.__class__.__mro__]:
            for slot in slots:
                if not slot.startswith('__'):  # We don't want class attributes
                    try:
                        value = getattr(self, slot)
                        statedict[slot] = value
                    except AttributeError:
                        pass
        return statedict

    def __setstate__(self, state):
        for key, value in state.items():
            setattr(self, key, value)