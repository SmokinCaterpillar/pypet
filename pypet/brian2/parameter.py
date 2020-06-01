"""Module containing results and parameters that can be used to store `BRIAN2 data`_.

Parameters handling BRIAN2 data are instantiated by the
:class:`~pypet.brian2.parameter.Brian2Parameter` class for any BRIAN2 Quantity.

The :class:`~pypet.brian2.parameter.Brian2Result` can store BRIAN2 Quantities
and the :class:`~pypet.brian2.parameter.Brian2MonitorResult` extracts data from
BRIAN2 Monitors.

.. _`BRIAN2 data`: http://brian2.readthedocs.org/

"""

__author__ = ['Henri Bunting', 'Robert Meyer']

import ast

import brian2.numpy_ as np
from brian2.units.fundamentalunits import Quantity, get_dimensions
from brian2.monitors import SpikeMonitor, StateMonitor, PopulationRateMonitor
import brian2.units.allunits as allunits

import pypet.pypetexceptions as pex
from pypet.parameter import Parameter, Result, ObjectTable


ALLUNITS = {}
for name in allunits.__all__:
    ALLUNITS[name] =  getattr(allunits, name)


def get_unit_fast(x):
    """ Return a `Quantity` with value 1 and the same dimensions. """
    return Quantity.with_dimensions(1, get_dimensions(x))


def unit_from_expression(expr):
    """Takes a unit string like ``'1. * volt'`` and returns the BRIAN2 unit."""
    if expr == '1':
        return get_unit_fast(1)
    elif isinstance(expr, str):
        mod = ast.parse(expr, mode='eval')
        expr = mod.body
        return unit_from_expression(expr)
    elif expr.__class__ is ast.Name:
        return ALLUNITS[expr.id]
    elif expr.__class__ is ast.Num or expr.__class__ is ast.Constant:
        return expr.n
    elif expr.__class__ is ast.UnaryOp:
        op = expr.op.__class__.__name__
        operand = unit_from_expression(expr.operand)
        if op=='USub':
            return -operand
        else:
            raise SyntaxError("Unsupported operation "+op)
    elif expr.__class__ is ast.BinOp:
        op = expr.op.__class__.__name__
        left = unit_from_expression(expr.left)
        right = unit_from_expression(expr.right)
        if op=='Add':
            u = left+right
        elif op=='Sub':
            u = left-right
        elif op=='Mult':
            u = left*right
        elif op=='Div':
            u = left/right
        elif op=='Pow':
            n = unit_from_expression(expr.right)
            u = left**n
        elif op=='Mod':
            u = left % right
        else:
            raise SyntaxError("Unsupported operation "+op)
        return u
    else:
        raise RuntimeError('You shall not pass')


class Brian2Parameter(Parameter):
    """A Parameter class that supports BRIAN2 Quantities.

    Note that only scalar BRIAN2 quantities are supported, lists, tuples or dictionaries
    of BRIAN2 quantities cannot be handled.

    Supports data for the standard :class:`~pypet.parameter.Parameter`, too.

    """

    IDENTIFIER = '__brn2__'
    ''' Identification string stored into column title of hdf5 table'''

    __slots__ = ()

    def __init__(self, full_name, data=None, comment=''):
        super(Brian2Parameter, self).__init__(full_name, data, comment)

    def f_supports(self, data):
        """ Simply checks if data is supported """
        if isinstance(data, Quantity):
            return True
        elif super(Brian2Parameter, self).f_supports(data):
            return True
        return False

    def _values_of_same_type(self, val1, val2):

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

    def _store(self):

        if not isinstance(self._data, Quantity):
            return super(Brian2Parameter, self)._store()
        else:
            store_dict = {}
            unit = get_unit_fast(self._data)

            value = self._data/unit
            store_dict['data' + Brian2Parameter.IDENTIFIER] = ObjectTable(data={'value': [value], 'unit': [repr(unit)]})

            if self.f_has_range():
                value_list = [value_with_unit/unit for value_with_unit in self._explored_range]
                store_dict['explored_data' + Brian2Parameter.IDENTIFIER] = ObjectTable(data={'value': value_list})

            self._locked = True

            return store_dict

    def _load(self, load_dict):
        if self.v_locked:
            raise pex.ParameterLockedException('Parameter `%s` is locked!' % self.v_full_name)

        try:
            data_table = load_dict['data' + Brian2Parameter.IDENTIFIER]

            unitstring = data_table['unit'][0]
            unit = unit_from_expression(unitstring)
            value = data_table['value'][0]
            self._data = value * unit

            if 'explored_data' + Brian2Parameter.IDENTIFIER in load_dict:
                explore_table = load_dict['explored_data' + Brian2Parameter.IDENTIFIER]

                value_col = explore_table['value']
                explore_list = [value * unit for value in value_col]

                self._explored_range = explore_list
                self._explored = True

        except KeyError:
            super(Brian2Parameter, self)._load(load_dict)

        self._default = self._data
        self._locked = True


class Brian2Result(Result):
    """ A result class that can handle BRIAN2 quantities.

    Note that only scalar BRIAN2 quantities are supported, lists, tuples or dictionaries
    of BRIAN2 quantities cannot be handled.

    Supports also all data supported by the standard :class:`~pypet.parameter.Result`.

    """

    IDENTIFIER = Brian2Parameter.IDENTIFIER
    ''' Identifier String to label brian result '''

    __slots__ = ()

    def __init__(self, full_name, *args, **kwargs):
        super(Brian2Result, self).__init__(full_name, *args, **kwargs)


    def f_set_single(self, name, item):
        if Brian2Result.IDENTIFIER in name:
            raise AttributeError('Your result name contains the identifier for brian data,'
                                 ' please do not use %s in your result names.' %
                                 Brian2Result.IDENTIFIER)
        else:
            super(Brian2Result, self).f_set_single(name, item)

    def _supports(self, data):
        """ Simply checks if data is supported """
        if isinstance(data, Quantity):
            return True
        elif super(Brian2Result, self)._supports(data):
            return True
        return False

    def _store(self):

        store_dict = {}

        for key in self._data:
            val = self._data[key]
            if isinstance(val, Quantity):
                unit = get_unit_fast(val)
                value = val/unit
                # Potentially the results are very big in contrast to small parameters
                # Accordingly, an ObjectTable might not be the best choice after all for a result
                if isinstance(val, np.ndarray) and len(val.shape) == 0:
                    # Convert 0-dimensional arrays to regular numpy floats
                    value = np.float(value)
                store_dict[key + Brian2Result.IDENTIFIER + 'value'] = value
                store_dict[key + Brian2Result.IDENTIFIER + 'unit'] = repr(unit)

            else:
                store_dict[key] = val

        return store_dict

    def _load(self, load_dict):

        for key in load_dict:
            if Brian2Result.IDENTIFIER in key:

                new_key = key.split(Brian2Result.IDENTIFIER)[0]

                if new_key in self._data:
                    # We already extracted the unit/value pair
                    continue

                # Recreate the brain units from the vale as float and unit as string:
                unitstring = load_dict[new_key + Brian2Result.IDENTIFIER + 'unit']
                unit = unit_from_expression(unitstring)
                value = load_dict[new_key + Brian2Result.IDENTIFIER +'value']
                self._data[new_key] = value * unit
            else:
                self._data[key] = load_dict[key]


class Brian2MonitorResult(Brian2Result):
    """ A Result class that supports BRIAN2 monitors.

    Monitor attributes are extracted and added as results with the attribute names.
    Note the original monitors are NOT stored, only their attribute/property values are kept.

    Add monitor on `__init__` via `monitor=` or via `f_set(monitor=brian_monitor)`

    **IMPORTANT**: You can only use 1 result per monitor. Otherwise a 'TypeError' is thrown.


    Example:

    >>> brian_result = BrianMonitorResult('example.brian_test_test.mymonitor',
                                            monitor=SpikeMonitor(...),
                                            comment='Im a SpikeMonitor Example!')
    >>> brian_result.num_spikes
    1337


    Following monitors are supported and the following values are extraced:

    * PopulationRateMonitor

        * t

            The times of the bins.

        * rate

            An array of rates in Hz

        * source

            String representation of source

        * name

            The name of the monitor


    * SpikeMonitor

        * t

            The times of the spikes

        * i

            The neuron indices of the spikes

        * num_spikes

            Total number of spikes

        * record_variables

            If variables are recorded at spike time, this is the list of their names

        * "varname"

            Array of variable recorded at spike time

        * source

            String representation of source

        * name

            The name of the monitor


    * StateMonitor

        * t

            Recording times

        * record_variables

            List of recorded variable names

        * "varname"

            Array of variable recorded

        * source

            String representation of source

        * name

            The name of the monitor

    """

    __slots__ = ('_monitor_type',)

    def __init__(self, full_name, *args, **kwargs):
        self._monitor_type = None
        super(Brian2MonitorResult, self).__init__(full_name, *args, **kwargs)

    def _store(self):
        store_dict = super(Brian2MonitorResult, self)._store()

        if self._monitor_type is not None:
            store_dict['monitor_type'] = self._monitor_type

        return store_dict

    def _load(self, load_dict):
        if 'monitor_type' in load_dict:
            self._monitor_type = load_dict.pop('monitor_type')
        super(Brian2MonitorResult, self)._load(load_dict)

    @property
    def v_monitor_type(self):
        """ The type of the stored monitor. Each MonitorResult can only manage a single Monitor.
        """
        return self._monitor_type

    def f_set_single(self, name, item):
        """ To add a monitor use `f_set_single('monitor', brian_monitor)`.

        Otherwise `f_set_single` works similar to :func:`~pypet.parameter.Result.f_set_single`.
        """
        if type(item) in [SpikeMonitor, StateMonitor, PopulationRateMonitor]:
            if self.v_stored:
                self._logger.warning('You are changing an already stored result. If '
                                     'you not explicitly overwrite the data on disk, '
                                     'this change might be lost and not propagated to disk.')

            self._extract_monitor_data(item)
        else:
            super(Brian2MonitorResult, self).f_set_single(name, item)

    def _extract_monitor_data(self, monitor):

        if self._monitor_type is not None:
            raise TypeError('Your result `%s` already extracted data from a `%s` monitor.'
                             ' Please use a new empty result for a new monitor.')

        self._monitor_type = monitor.__class__.__name__

        if isinstance(monitor, SpikeMonitor):
            self._extract_spike_monitor(monitor)

        elif isinstance(monitor, StateMonitor):
            self._extract_state_monitor(monitor)

        elif isinstance(monitor, PopulationRateMonitor):
            self._extract_population_rate_monitor(monitor)

        else:
            raise ValueError('Monitor Type %s is not supported (yet)' % str(type(monitor)))

    def _extract_state_monitor(self, monitor):

        self.f_set(record_variables=monitor.record_variables)
        self.f_set(record=monitor.record)
        self.f_set(when=monitor.when)
        self.f_set(source=str(monitor.source))
        self.f_set(name=monitor.name)

        times=np.array(monitor.t[:])
        if len(times) > 0:
            self.f_set(t=times)

            for varname in monitor.record_variables:
                val = getattr(monitor, varname)
                self.f_set(**{varname: val})

    def _extract_spike_monitor(self, monitor):

        self.f_set(source=str(monitor.source))
        self.f_set(num_spikes=monitor.num_spikes)
        self.f_set(when=monitor.when)
        self.f_set(name=monitor.name)

        if len(monitor.record_variables) > 0:
            self.f_set(record_variables=list(monitor.record_variables))

        times = monitor.t[:]

        if len(times) > 0:
            self.f_set(t=times)
            self.f_set(i=monitor.i[:])

            for varname in monitor.record_variables:
                val = getattr(monitor, varname)
                self.f_set(**{varname: val[:]})

    def _extract_population_rate_monitor(self, monitor):

        times = monitor.t[:]
        self.f_set(source=str(monitor.source))
        self.f_set(name=monitor.name)

        if len(times) > 0:
            self.f_set(t=times)
            self.f_set(rate=monitor.rate[:])
