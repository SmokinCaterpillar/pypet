__author__ = 'Henri Bunting'

from pypet.tests.testutils.data import TrajectoryComparator
from pypet.tests.testutils.ioutils import make_temp_dir, make_trajectory_name, get_log_config, parse_args, run_suite
from pypet import Environment, load_trajectory
from pypet.brian2.parameter import Brian2Parameter
from brian2.units.stdunits import mvolt
from brian2.units.fundamentalunits import Quantity
from pypet.pypetlogging import HasLogger
from pypet.storageservice import HDF5StorageService, StorageService

import os


class Brian2hdf5Test(TrajectoryComparator):

    tags = 'integration', 'brian2', 'parameter', 'hdf5', 'henri'

    def test_hdf5_store_load(self):
        traj_name = make_trajectory_name(self)
        file_name = make_temp_dir(os.path.join('brian2', 'tests', 'hdf5', 'test_%s.hdf5' % traj_name))
        env = Environment(trajectory=traj_name, filename=file_name, log_config=get_log_config(),
                            dynamic_imports=[Brian2Parameter], add_time=False, storage_service=Brian2HDF5StorageService)
        traj = env.v_trajectory
        traj.v_standard_parameter = Brian2Parameter
        traj.f_add_parameter('brian2.single.millivolts', 10*mvolt, comment='single value')
        traj.f_add_parameter('brian2.array.millivolts', [11, 12]*mvolt, comment='array')
        traj.f_store()

        traj2 = load_trajectory(filename=file_name, name=traj_name, dynamic_imports=[Brian2Parameter],
                                load_data=2)
        self.compare_trajectories(traj, traj2)


class Brian2HDF5StorageService(HDF5StorageService, HasLogger):
    @staticmethod
    def _all_set_attributes_to_recall_natives(data, ptitem, prefix):
        if type(data) is Quantity:
            HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_NDARRAY)
        else:
            HDF5StorageService._all_set_attributes_to_recall_natives(data, ptitem, prefix)
        #return HDF5StorageService._all_set_attributes_to_recall_natives(data, ptitem, prefix)
        '''
        if type(data) in (list, tuple):
            # If data is a list or tuple we need to remember the data type of the elements
            # in the list or tuple.
            # We do NOT need to remember the elements of `dict` explicitly, though.
            # `dict` is stored
            # as an `ObjectTable` and thus types are already conserved.
            if len(data) > 0:
                strtype = type(data[0]).__name__

                if not strtype in pypetconstants.PARAMETERTYPEDICT:
                    raise TypeError('I do not know how to handle `%s` its type is '
                                    '`%s`.' % (str(data), strtype))

                HDF5StorageService._all_set_attr(ptitem, prefix +
                                       HDF5StorageService.SCALAR_TYPE, strtype)
        elif (type(data) in (np.ndarray, np.matrix) and
                  np.issubdtype(data.dtype, compat.unicode_type)):
            HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.SCALAR_TYPE,
                                   compat.unicode_type.__name__)
        '''

        '''
        # If `data` is a container, remember the container type
        if type(data) is Quantity:
            HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_TUPLE)
        else:
            super(Brian2HDF5StorageService, self)._all_set_attributes_to_recall_natives(data, ptitem, prefix)


        elif type(data) is list:
            HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_LIST)

        elif type(data) is np.ndarray:
            HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_NDARRAY)

        elif type(data) is np.matrix:
            HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_MATRIX)

        elif type(data) in pypetconstants.PARAMETER_SUPPORTED_DATA:
            HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_SCALAR)

            strtype = type(data).__name__

            if not strtype in pypetconstants.PARAMETERTYPEDICT:
                raise TypeError('I do not know how to handle `%s` its type is `%s`.' %
                                (str(data), repr(type(data))))

            HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.SCALAR_TYPE, strtype)

        elif type(data) is dict:
            if len(data) > 0:
                HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_DICT)
            else:
                HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.COLL_TYPE,
                                   HDF5StorageService.COLL_EMPTY_DICT)
        else:
            raise TypeError('I do not know how to handle `%s` its type is `%s`.' %
                            (str(data), repr(type(data))))

        if type(data) in (list, tuple):
            # If data is a list or tuple we need to remember the data type of the elements
            # in the list or tuple.
            # We do NOT need to remember the elements of `dict` explicitly, though.
            # `dict` is stored
            # as an `ObjectTable` and thus types are already conserved.
            if len(data) > 0:
                strtype = type(data[0]).__name__

                if not strtype in pypetconstants.PARAMETERTYPEDICT:
                    raise TypeError('I do not know how to handle `%s` its type is '
                                    '`%s`.' % (str(data), strtype))

                HDF5StorageService._all_set_attr(ptitem, prefix +
                                       HDF5StorageService.SCALAR_TYPE, strtype)
        elif (type(data) in (np.ndarray, np.matrix) and
                  np.issubdtype(data.dtype, compat.unicode_type)):
            HDF5StorageService._all_set_attr(ptitem, prefix + HDF5StorageService.SCALAR_TYPE,
                                   compat.unicode_type.__name__)
        '''


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)