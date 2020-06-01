__author__ = 'Robert Meyer'

import numpy as np
import itertools as itools
import hashlib
from collections import deque


class Universe(object):
    """Contains everything"""
    def __contains__(self, item):
        return True


class IteratorChain(object):
    """Helper class that chains arbitrary generators and iterators and iterables.

    Preferably used over itertools.chain to avoid recursive calls.

    You can already pass some `iterators` on creation.

    """
    def __init__(self, *iterables):
        # Deque containing the iterators to come
        self._chain = deque()
        # The current iterator providing the next elements
        self._current = iter([])

        self.add(*iterables)

    def add(self, *iterables):
        """Adds `iterables` to the chain"""
        self._chain.extend(iterables)

    def next(self):
        """Returns next element from chain.

        More precisely, it returns the next element of the
        foremost iterator. If this iterator is empty it moves iteratively
        along the chain of available iterators to pick the new foremost one.

        Raises StopIteration if there are no elements left.

        """
        while True:
            # We need this loop because some iterators may already be empty.
            # We keep on popping from the left until next succeeds and as long
            # as there are iterators available
            try:
                return next(self._current)
            except StopIteration:
                try:
                    self._current = iter(self._chain.popleft())
                except IndexError:
                    # If we run out of iterators we are sure that
                    # there can be no more element
                    raise StopIteration('Reached end of iterator chain')

    def __next__(self):
        """For python 3 compatibility"""
        return self.next()

    def __iter__(self):
        while True:
            try:
                yield self.next()
            except StopIteration:
                # new behavior since PEP479
                # one should return to stop iteration
                return


class ChainMap(object):
    """Combine multiple mappings for sequential lookup.
    """

    def __init__(self, *maps):
        self._maps = maps

    def __getitem__(self, key):
        for mapping in self._maps:
            try:
                return mapping[key]
            except KeyError:
                pass
        raise KeyError(key)

    def __len__(self):
        length = 0

        for mapping in self._maps:
            length += len(mapping)

        return length

    def __iter__(self):
        iter_list = [mapping.keys() for mapping in self._maps]
        return itools.chain(*iter_list)


class HashArray(object):
    """Hashable wrapper for numpy arrays"""

    def __init__(self, ndarray):
        """Creates a new hashable object encapsulating an ndarray.

            :param ndarray: The wrapped ndarray.

        """
        self._ndarray = ndarray

    def __eq__(self, other):

        try:
            return np.all(self._ndarray == other._ndarray)
        except AttributeError:
            return False

    def __hash__(self):
        return int(hashlib.sha1(self._ndarray.view(np.uint8)).hexdigest(), 16)


class TrajectoryMock(object):
    """Helper class that mocks properties of a trajectory.

    The full trajectory is not needed to rename a log file.
    In order to avoid copying the full trajectory during pickling
    this class is used.

    """
    def __init__(self, traj):
        self.v_environment_name = traj.v_environment_name
        self.v_name = traj.v_name
        self.v_crun_ = traj.v_crun_
        self.v_crun = traj.v_crun
        self.v_idx = traj.v_idx
