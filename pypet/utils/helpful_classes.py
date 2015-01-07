__author__ = 'Robert Meyer'

import numpy as np
import itertools as itools
import hashlib
import pypet.compat as compat


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
        iter_list = [compat.iterkeys(mapping) for mapping in self._maps]
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


