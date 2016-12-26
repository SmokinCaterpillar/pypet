
=====
Slots
=====

For performance reasons all tree nodes support slots_.
They all sub-class the ``HasSlots`` class, which is the top-level class of *pypet*
(its direct descendant is ``HasLogger``, see below).
This class provides an ``__all_slots__`` property
(with the help of the ``MetaSlotMachine`` metaclass)
that lists all existing ``__slots__`` of a class including the inherited ones.
Moreover, via ``__getstate__`` and ``__setstate__`` ``HasSlots`` takes care that all
sub-classes can be pickled with the lowest protocol and don't need to implement
``__getstate__`` and ``__setstate__`` themselves even when they have ``__slots__``.
However, sub-classes that still implement these
functions should call the parent ones via ``super``. Sub-classes are not required to
define ``__slots__``. If they don't, ``HasSlots`` wil also automatically
handle their ``__dict__`` in ``__getstate__`` and ``__setstate__``.

.. autoclass:: pypet.slots.HasSlots
    :members:
    :private-members:
    :special-members:


.. autofunction:: pypet.slots.get_all_slots

.. autoclass:: pypet.slots.MetaSlotMachine
    :members:
    :private-members:
    :special-members:


=======
Logging
=======

``HasLogger`` can be sub-classed to allow per class or even
per instance logging. The logger is initialized via ``_set_logger()`` and is available via
the ``_logger`` attribute.
``HasLogger`` also takes care that the logger does not get pickled when ``__getstate__`` and
``__setstate__`` are called.
Thus, you are always advised in sub-classes that also implement these functions
to call the parent ones via ``super``. ``HasLogger`` is a direct sub-class of ``HasSlots``.
Hence, support for ``__slots__`` is ensured.


.. autoclass:: pypet.pypetlogging.HasLogger
    :members:
    :private-members:
    :special-members:


.. autofunction:: pypet.pypetlogging.rename_log_file

.. _slots: https://docs.python.org/2/reference/datamodel.html#slots