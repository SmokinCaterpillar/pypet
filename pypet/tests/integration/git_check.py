import sys
import os
import getopt

try:
    import pypet
except ImportError:
    # Check if pypet is installed otherwise append /pypet folder
    # this is important for travis-ci
    path = os.path.abspath('../../../')
    print('Adding pypet path:`%s`' % path)
    sys.path.append(path)


from pypet import Environment
from pypet import cartesian_product, GitDiffError


def multiply(traj):
    z=traj.x*traj.y
    traj.f_add_result('z',z, comment='Im the product of two reals!')


def get_opt():
    opt_list, _ = getopt.getopt(sys.argv[1:],'fn')
    opt_dict = {}
    for opt, arg in opt_list:
        if opt == '-f':
            opt_dict['fail'] = True
            print('I will try to fail on diffs.')
        if opt == '-n':
            opt_dict['no_fail'] = True
            print('I will try to fail on diffs, but there should not be any.')

    return opt_dict


def fail_on_diff():
    try:
        Environment(trajectory='fail',
                 filename=os.path.join('fail',
                                       'HDF5',),
                  file_title='failing',
                  git_repository='.', git_message='Im a message!',
                  git_fail=True)
        raise RuntimeError('You should not be here!')
    except GitDiffError as exc:
        print('I expected the GitDiffError: `%s`' % repr(exc))


def main(fail=False):
    try:
        sumatra_project = '.'

        if fail:
            print('There better be not any diffs.')

        # Create an environment that handles running
        with Environment(trajectory='Example1_Quick_And_Not_So_Dirty',
                         filename=os.path.join('experiments',
                                               'HDF5',),
                          file_title='Example1_Quick_And_Not_So_Dirty',
                          comment='The first example!',
                          complib='blosc',
                          small_overview_tables=False,
                          git_repository='.', git_message='Im a message!',
                          git_fail=fail,
                          sumatra_project=sumatra_project, sumatra_reason='Testing!') as env:

            # Get the trajectory from the environment
            traj = env.v_trajectory

            # Add both parameters
            traj.f_add_parameter('x', 1, comment='Im the first dimension!')
            traj.f_add_parameter('y', 1, comment='Im the second dimension!')

            # Explore the parameters with a cartesian product:
            traj.f_explore(cartesian_product({'x':[1,2,3], 'y':[6,7,8]}))

            # Run the simulation
            env.f_run(multiply)

            # Check that git information was added to the trajectory
            assert 'config.git.hexsha' in traj
            assert 'config.git.committed_date' in traj
            assert 'config.git.message' in traj
            assert 'config.git.name_rev' in traj

            print("Python git test successful")

            # traj.f_expand({'x':[3,3],'y':[42,43]})
            #
            # env.f_run(multiply)
    except Exception as exc:
        print(repr(exc))
        sys.exit(1)


if __name__ == '__main__':
    opt_dict = get_opt()
    test_fail = opt_dict.get('fail', False)
    if test_fail:
        fail_on_diff()
    test_no_fail = opt_dict.get('no_fail', False)
    main(test_no_fail)