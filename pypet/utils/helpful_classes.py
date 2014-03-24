__author__ = 'Robert Meyer'


import UserDict
import itertools as itools


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

        return  length

    def iterkeys(self):

        iter_list = [mapping.iterkeys() for mapping in self._maps]
        return itools.chain(*iter_list)
