__author__ = 'Henri Bunting'

# import brian2
import brian2.numpy_ as np
from pypet.parameter import Parameter, ObjectTable
from brian2.units.fundamentalunits import Quantity, get_unit_fast
from pypet.utils.helpful_classes import HashArray
#from pypet.tests.testutils.ioutils import get_root_logger
#from brian2.units.fundamentalunits import is_dimensionless, get_dimensions
#from brian2.core.variables import get_value_with_unit

import pypet.pypetexceptions as pex

try:
    from brian2.units.allunits import *
except TypeError:
    pass

class Brian2Parameter(Parameter):
    #_logger = get_root_logger()

    IDENTIFIER = '__brn2__'
    ''' Identification string stored into column title of hdf5 table'''

    __slots__ = ()

    def __init__(self, full_name, data=None, comment=''):
        #print("b2parameter.init data:"+str(data)+" supported?:"+str(self.f_supports(data)))
        super(Brian2Parameter, self).__init__(full_name, data, comment)

    def f_supports(self, data):
        """ Simply checks if data is supported """
        #print("f_supports data.type:"+str(type(data)))
        if isinstance(data, Quantity):
            return True
        elif isinstance(data, list):
            for value in data:
                if not self.f_supports(value):
                    return False
            return True
        elif super(Brian2Parameter, self).f_supports(data):
            return True
        return False


    def _set_parameter_access(self, idx=0):
        print("b2p._set_parameter_access 1 self._data",self._data)
        if idx >= len(self) and self.f_has_range():
            print("b2p._set_parameter_access 2 self._data",self._data)
            raise ValueError('You try to access data item No. %d in the parameter range, '
                             'yet there are only %d potential items.' % (idx, len(self)))
        elif self.f_has_range():
            print("b2p._set_parameter_access 3 self._data",self._data)
            self._data = self._explored_range[idx]
            print("b2p._set_parameter_access 3-1 self._data",self._data)
        else:
            print("b2p._set_parameter_access 4 self._data",self._data)
            self._logger.warning('You try to change the access to a parameter range of parameter'
                                 ' `%s`. The parameter has no range, your setting has no'
                                 ' effect.')

    '''
    def _data_sanity_checks(self, explore_iterable):
        """Checks if data values are valid.

        Checks if the data values are supported by the parameter and if the values are of the same
        type as the default value.

        """
        data_tuple = []
        #print("b2parameter _data_sanity_checks:"+str(explore_iterable))

        #first_unit = get_unit_fast(explore_iterable[0])
        #print("b2parameter _data_sanity_checks first unit:"+str(repr(first_unit)))

        for val in explore_iterable:

            #first_unit = get_unit_fast(explore_iterable[0])
            #print("b2parameter _data_sanity_checks val:"+str(val))
            #val_unit = get_unit_fast(val)
            #print("b2parameter _data_sanity_checks valunit:"+str(val_unit)+" equal?:"+str(val_unit==first_unit))
            #print("b2parameter _data_sanity_checks val:"+str(repr(first_unit)))

            newval = self._convert_data(val)
            #print("b2parameter _data_sanity_checks val:"+str(val)+" newval:"+str(newval)+" _default:"+str(self._default))
            #print("b2parameter _data_sanity_checks val.type:"+str(type(val))+" newval.type:"+str(type(newval))+" self._default.type:"+str(type(self._default)))

            if not self.f_supports(newval):
                raise TypeError('%s is of not supported type %s.' % (repr(val), str(type(newval))))

            #print("b2parameter _data_sanity_checks before _values_of_same_type")

            if not self._values_of_same_type(newval, self._default) and not self._each_value_of_same_type(newval, self._default):
                raise TypeError(
                    'Data of `%s` is not of the same type as the original entry value, '
                    'new type is %s vs old type %s.' %
                    (self.v_full_name, str(type(newval)), str(type(self._default))))

            data_tuple.append(newval)

        if len(data_tuple) == 0:
            raise ValueError('Cannot explore an empty list!')

        return tuple(data_tuple)
    '''

    '''
    def _each_value_of_same_type(self, val1, val2):
        #print("b2parameter _each_value_of_same_type")
        #print("\t"+str(val1))
        #print("\t"+str(val2))

        if isinstance(val1, list):
            for list_val in val1:
                if not self._each_value_of_same_type(list_val, val2):
                    return False
        if isinstance(val2, list):
            for list_val in val2:
                if not self._each_value_of_same_type(list_val, val1):
                    return False

        if not isinstance(val1, list) and not isinstance(val2, list) and not self._values_of_same_type(val1, val2):
            return False

        return True
    '''

    def _values_of_same_type(self, val1, val2):
        #print("b2parameter _values_of_same_type")
        #print("\t"+str(val1))
        #print("\t"+str(val2))

        if isinstance(val2, list) and not isinstance(val1, list):
            return self._values_of_same_type([val1], val2)
        if isinstance(val1, list) and not isinstance(val2, list):
            return self._values_of_same_type(val1, [val2])

        if isinstance(val1, Quantity):
            try:
                if not val1.has_same_dimensions(val2):
                    return False
            except TypeError:
                return False

        elif isinstance(val2, Quantity):
            try:
                if not val2.has_same_dimensions(val1):
                    return False
            except TypeError:
                return False

        elif not super(Brian2Parameter, self)._values_of_same_type(val1, val2):
            return False

        return True

    '''
    def f_get(self):
        #print("b2p.f_get self._data:",self._data)
        return super(Brian2Parameter, self).f_get()
    '''

    def _store(self):
        print("--- store START---")
        print("self._data:"+str(self._data))

        if type(self._data) not in [Quantity, list]:
            self._logger.debug("Brian2Parameter._store Unknown type: "+str(type(self._data)))
            print("--- store ENDB ---")
            return super(Brian2Parameter, self)._store()
        store_dict = {}

        unit = get_unit_fast(self._data)
        unitstr = repr(unit)
        value = self._data/unit
        store_dict['data' + Brian2Parameter.IDENTIFIER] = ObjectTable(
            data={'value': [value], 'unit': [unitstr]})

        if self.f_has_range():
            value_list = []
            for val in self._explored_range:
                value = val/unit
                value_list.append(value)

            store_dict['explored_data' + Brian2Parameter.IDENTIFIER] = \
                ObjectTable(data={'value': value_list})

        self._locked = True

        return store_dict

    def _load(self, load_dict):
        if self.v_locked:
            raise pex.ParameterLockedException('Parameter `%s` is locked!' % self.v_full_name)

        try:
            data_table = load_dict['data' + Brian2Parameter.IDENTIFIER]


            # Recreate the brain units from the vale as float and unit as string:
            unit = eval(data_table['unit'][0])
            value = data_table['value'][0]
            self._data = value * unit

            if 'explored_data' + Brian2Parameter.IDENTIFIER in load_dict:
                explore_table = load_dict['explored_data' + Brian2Parameter.IDENTIFIER]

                value_col = explore_table['value']
                explore_list = []
                for value in value_col:
                    brian_quantity = value * unit
                    explore_list.append(brian_quantity)

                self._explored_range = tuple(explore_list)
                self._explored = True


        except KeyError:
            super(Brian2Parameter, self)._load(load_dict)

        self._default = self._data
        self._locked = True
    '''
    def _store(self):
        """Creates a storage dictionary for the storage service.

        If the data is not a numpy array, a numpy matrix, or a tuple, the
        :func:`~pypet.parameter.Parmater._store` method of the parent class is called.

        Otherwise the array is put into the dictionary with the key 'data__rr__'.

        Each array of the exploration range is stored as a separate entry named
        'xa__rr__XXXXXXXX' where 'XXXXXXXX' is the index of the array. Note if an array
        is used more than once in an exploration range (for example, due to cartesian product
        exploration), the array is stored only once.
        Moreover, an :class:`~pypet.parameter.ObjectTable` containing the references
        is stored under the name 'explored_data__rr__' in order to recall
        the order of the arrays later on.

        """
        print(" ~~~ store ~~~ ")
        print("self.data:"+str(self._data)+" type:"+str(type(self._data)))
        print(" ~~~~~~~~~~~~~ ")


        if isinstance(self._data, list):
            is_list = True
            unitstr = repr(get_unit_fast(self._data[0]))
            for listvalue in self._data:
                print(str(listvalue)+" : "+str(type(listvalue)))+" : "+str(type(listvalue.tolist()))
                if type(listvalue.tolist()) is list:
                    self._logger.debug("_store got a list of lists")
                    is_list_in_list = True
                    values = [float(subvalue) for subvalue in listvalue]
                else:
                    is_list_in_list = False
                    self._logger.debug("_store got a list")

        else:
            is_list = False
            unitstr = repr(get_unit_fast(self._data))
            if type(self._data.tolist()) is list:
                self._logger.debug("_store got a single list")
                is_single_list = True
                values = [float(subvalue) for subvalue in self._data]
            else:
                is_single_list = False
                self._logger.debug("_store got single")

        print("values:"+str(values))
        print("unitstr:"+str(unitstr))
        print(" ~~~~~~~~~~~~~ ")
        store_dict = {'data' + Brian2Parameter.IDENTIFIER: self._data}

        print("store:"+str(store_dict))

        # Supports smart storage by hashable arrays
        # Keys are the hashable arrays or tuples and values are the indices
        smart_dict = {}

        store_dict['values' + Brian2Parameter.IDENTIFIER] = ObjectTable(columns=['idx'], index=list(range(len(values))))
        print("store:"+str(store_dict))

        count = 0
        for idx, elem in enumerate(values):
            print("==============")
            print("idx: "+str(idx)+" elem:"+str(elem))
            hash_elem = elem
            print("hash_elem:"+str(hash_elem))

            # Check if we have used the array before,
            # i.e. element can be found in the dictionary
            if hash_elem in smart_dict:
                name_idx = smart_dict[hash_elem]
                add = False
            else:
                name_idx = count
                add = True
            print("name_idx: "+str(name_idx)+" add:"+str(add))

            name = self._build_name(name_idx)
            print("name:"+str(name))

            # Store the reference to the array
            store_dict['values' + Brian2Parameter.IDENTIFIER]['idx'][idx] = name_idx

            # Only if the array was not encountered before,
            # store the array and remember the index
            if add:
                store_dict[name] = elem
                smart_dict[hash_elem] = name_idx
                count += 1
            print("==============")
        print("store:"+str(store_dict))
        print("smart:"+str(smart_dict))

        ''
            # First we need to distinguish between tuples and array and extract a
            # hashable part of the array
            if isinstance(elem, np.ndarray):
                # You cannot hash numpy arrays themselves, but if they are read only
                # you can hash array.data
                hash_elem = HashArray(elem)
            else:
                hash_elem = elem

            # Check if we have used the array before,
            # i.e. element can be found in the dictionary
            if hash_elem in smart_dict:
                name_idx = smart_dict[hash_elem]
                add = False
            else:
                name_idx = count
                add = True

            name = self._build_name(name_idx)
            # Store the reference to the array
            store_dict['values' + Brian2Parameter.IDENTIFIER]['idx'][idx] = name_idx

            # Only if the array was not encountered before,
            # store the array and remember the index
            if add:
                store_dict[name] = elem
                smart_dict[hash_elem] = name_idx
                count += 1
            ''
        self._locked = True

        return store_dict


        ''
        if not type(self._data) in [np.ndarray, tuple, np.matrix]:
            return super(Brian2Parameter, self)._store()
        else:
            store_dict = {'data' + Brian2Parameter.IDENTIFIER: self._data}

            print("store:"+str(store_dict))

            if self.f_has_range():
                # Supports smart storage by hashable arrays
                # Keys are the hashable arrays or tuples and values are the indices
                smart_dict = {}

                store_dict['explored_data' + Brian2Parameter.IDENTIFIER] = ObjectTable(columns=['idx'], index=list(range(len(self))))

                count = 0
                for idx, elem in enumerate(self._explored_range):

                    # First we need to distinguish between tuples and array and extract a
                    # hashable part of the array
                    if isinstance(elem, np.ndarray):
                        # You cannot hash numpy arrays themselves, but if they are read only
                        # you can hash array.data
                        hash_elem = HashArray(elem)
                    else:
                        hash_elem = elem

                    # Check if we have used the array before,
                    # i.e. element can be found in the dictionary
                    if hash_elem in smart_dict:
                        name_idx = smart_dict[hash_elem]
                        add = False
                    else:
                        name_idx = count
                        add = True

                    name = self._build_name(name_idx)
                    # Store the reference to the array
                    store_dict['explored_data' + Brian2Parameter.IDENTIFIER]['idx'][idx] = \
                        name_idx

                    # Only if the array was not encountered before,
                    # store the array and remember the index
                    if add:
                        store_dict[name] = elem
                        smart_dict[hash_elem] = name_idx
                        count += 1

            self._locked = True

            return store_dict
    ''
    def _load(self, load_dict):
        """Reconstructs the data and exploration array.

        Checks if it can find the array identifier in the `load_dict`, i.e. '__rr__'.
        If not calls :class:`~pypet.parameter.Parameter._load` of the parent class.

        If the parameter is explored, the exploration range of arrays is reconstructed
        as it was stored in :func:`~pypet.parameter.ArrayParameter._store`.

        """
        if self.v_locked:
            raise pex.ParameterLockedException('Parameter `%s` is locked!' % self.v_full_name)

        try:
            self._data = load_dict['data' + Brian2Parameter.IDENTIFIER]

            if 'explored_data' + Brian2Parameter.IDENTIFIER in load_dict:
                explore_table = load_dict['explored_data' + Brian2Parameter.IDENTIFIER]

                idx = explore_table['idx']

                explore_list = []

                # Recall the arrays in the order stored in the ObjectTable 'explored_data__rr__'
                for name_idx in idx:
                    arrayname = self._build_name(name_idx)
                    explore_list.append(load_dict[arrayname])

                self._explored_range = tuple([self._convert_data(x) for x in explore_list])
                self._explored = True

        except KeyError:
            super(Brian2Parameter, self)._load(load_dict)

        self._default = self._data
        self._locked = True

    @staticmethod
    def _build_name(name_idx):
        """Formats a name for storage

        :return:

            'xa__rr__XXXXXXXX' where 'XXXXXXXX' is the index of the array

        """
        return 'xa%s%08d' % (Brian2Parameter.IDENTIFIER, name_idx)

    ''
    '''
