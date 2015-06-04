__author__ = 'Henri Bunting'

# import brian2
import brian2.numpy_ as np
from pypet.parameter import Parameter, ObjectTable
from brian2.units.fundamentalunits import Quantity, get_unit_fast
from pypet.utils.helpful_classes import HashArray
#from brian2.units.fundamentalunits import is_dimensionless, get_dimensions
#from brian2.core.variables import get_value_with_unit

import pypet.pypetexceptions as pex

try:
    from brian2.units.allunits import *
except TypeError:
    pass

class Brian2Parameter(Parameter):

    IDENTIFIER = '__brn2__'
    ''' Identification string stored into column title of hdf5 table'''

    FLOAT_MODE = 'FLOAT'
    '''Float storage mode'''

    __slots__ = ('_storage_mode',)

    def __init__(self, full_name, data=None, comment='', storage_mode=FLOAT_MODE):
        super(Brian2Parameter, self).__init__(full_name, data, comment)

        self._storage_mode = None
        self.v_storage_mode = storage_mode

    @property
    def v_storage_mode(self):
        """
        There is one storage mode:


        * :const:`~pypet.brian.parameter.BrianParameter.FLOAT_MODE`: ('FLOAT')

            The value is stored as a float and the unit as a sting.

            i.e. `12 mV` is stored as `12.0` and `'1.0 * mV'`

        """
        return self._storage_mode

    @v_storage_mode.setter
    def v_storage_mode(self, storage_mode):
        assert (storage_mode == Brian2Parameter.FLOAT_MODE)
        self._storage_mode = storage_mode

    def f_supports(self, data):
        """ Simply checks if data is supported """
        if isinstance(data, Quantity):
            return True
        if super(Brian2Parameter, self).f_supports(data):
            return True
        return False

    def _values_of_same_type(self, val1, val2):
        #print("--------------------")
        #print("_values_of_same_type", val1, val2)

        if isinstance(val1, Quantity):
            #print("iiv1 - val1", val1, is_dimensionless(val1))
            #print("iiv1 - val2", val2, is_dimensionless(val2))
            #print("iiv1 - isinstance(val1, Quantity)", isinstance(val1, Quantity))
            #print("iiv1 - isinstance(val2, Quantity)", isinstance(val2, Quantity))
            try:
                # Trigger AttributeError (it isn't caught in the if)
                #val1_dimensions = get_dimensions(val1)
                #print("iiv1 - val1 dimensions", val1_dimensions)
                #val2_dimensions = get_dimensions(val2)
                #print("iiv1 - val2 dimensions", val2_dimensions)
                if not val1.has_same_dimensions(val2):
                    return False
            #except AttributeError:
            #    print("iiv1 - caught attribute error 1")
            #    print("--------------------F")
            #    return False
            except TypeError:
                #print("iiv1 - caught type error 1")
                #print("--------------------F")
                return False

        elif isinstance(val2, Quantity):
            #print("iiv2 - val1", val1, is_dimensionless(val1))
            #print("iiv2 - val2", val2, is_dimensionless(val2))
            #print("iiv2 - isinstance(val1, Quantity)", isinstance(val1, Quantity))
            #print("iiv2 - isinstance(val2, Quantity)", isinstance(val2, Quantity))
            try:
                # Trigger AttributeError (it isn't caught in the if)
                #val1_dimensions = get_dimensions(val1)
                #print("iiv2 - val1 dimensions", val1_dimensions)
                #val2_dimensions = get_dimensions(val2)
                #print("iiv2 - val2 dimensions", val2_dimensions)
                if not val2.has_same_dimensions(val1):
                    return False
            #except AttributeError:
            #    print("iiv2 - caught attribute error 2")
            #    print("--------------------F")
            #    return False
            except TypeError:
                #print("iiv2 - caught type error 1")
                #print("--------------------F")
                return False

        elif not super(Brian2Parameter, self)._values_of_same_type(val1, val2):
            #print("--------------------F")
            return False


        #print("--------------------T")
        return True

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
        if not type(self._data) in [np.ndarray, tuple, np.matrix]:
            return super(Brian2Parameter, self)._store()
        else:
            store_dict = {'data' + Brian2Parameter.IDENTIFIER: self._data}

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

    '''
    def _store(self):
        #print("--- store START---")
        if isinstance(self._data, Quantity):
            store_dict = {}

            unitstr = repr(get_unit_fast(self._data))
            #print( "store self._data:", self._data.tolist() )
            #print( "store self._data type:", type(self._data.tolist()) )

            if type(self._data.tolist()) is list:
                is_array = True
                values = [float(value) for value in self._data.tolist()]
                #print("Got list")
            else:
                is_array = False
                values = [float(self._data)]
                #print("Got single")

            store_dict['data' + Brian2Parameter.IDENTIFIER] = ObjectTable(data={'value': [values],
                                                                                'unit': [unitstr],
                                                                                'is_array': [is_array]})

            #print("store_dict: "+str(store_dict))

            if self.f_has_range():
                value_list = []
                for val in self._explored_range:
                    value = float(val)
                    #print("store value:", value)
                    value_list.append(value)

                store_dict['explored_data' + Brian2Parameter.IDENTIFIER] = ObjectTable(data={'value': value_list})

            print(store_dict)

            self._locked = True

            #print("--- store ENDA ---")
            return store_dict
        else:
            #print("--- store ENDB ---")
            return super(Brian2Parameter, self)._store()

    def _load(self, load_dict):
        #print("--- load START ---")
        if self.v_locked:
            #print("--- load ENDA ---")
            raise pex.ParameterLockedException('Parameter `%s` is locked!' % self.v_full_name)

        try:
            data_table = load_dict['data' + Brian2Parameter.IDENTIFIER]

            # Recreate the brain units from the vale as float and unit as string:
            #print(data_table)

            #value = data_table['object_table']['value'].tolist() if data_table['is_array'] else data_table['object_table']['value'][0]
            value = data_table['value'][0]
            unit = eval(data_table['unit'][0])
            is_array = data_table['is_array'][0]
            #print("value:"+str(value))
            #print("unit:"+str(unit))
            #print("value*unit:"+str(value * unit))
            if is_array:
                self._data = value * unit
            else:
                self._data = value[0] * unit

            #print(self._data)

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
        #print("--- load ENDB ---")
    '''
