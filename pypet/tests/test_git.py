import sys
import os

try:
    import pypet
except ImportError:
    # Check if pypet is installed otherwise append /pypet folder
    # this is important for travis-ci
    path = os.path.abspath('../../../')
    print('Adding pypet path:`%s`' % path)
    sys.path.append(path)


from pypet import Environment
from pypet import cartesian_product


def multiply(traj):
    z=traj.x*traj.y
    traj.f_add_result('z',z, comment='Im the product of two reals!')


def main():
    try:
        # Create an environment that handles running
        with Environment(trajectory='Example1_Quick_And_Not_So_Dirty',
                         filename=os.path.join('experiments',
                                               'example_01',
                                               'HDF5',),
                          file_title='Example1_Quick_And_Not_So_Dirty',
                          log_folder=os.path.join('experiments', 'example_01', 'LOGS'),
                          comment='The first example!',
                          complib='blosc',
                          small_overview_tables=False,
                          git_repository='.', git_message='Im a message!',
                          sumatra_project='.', sumatra_reason='Testing!') as env:

            # Get the trajectory from the environment
            traj = env.v_trajectory

            # Add both parameters
            traj.f_add_parameter('x', 1, comment='Im the first dimension!')
            traj.f_add_parameter('y', 1, comment='Im the second dimension!')

            # Explore the parameters with a cartesian product:
            traj.f_explore(cartesian_product({'x':[1,2,3], 'y':[6,7,8]}))

            # Run the simulation
            env.f_run(multiply)

            print("Python git test successful")

            # traj.f_expand({'x':[3,3],'y':[42,43]})
            #
            # env.f_run(multiply)
    except Exception as e:
        print(repr(e))
        sys.exit(1)


if __name__ == '__main__':
    main()