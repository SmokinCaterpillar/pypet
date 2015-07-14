from pypet import Environment, cartesian_product

def multiply(traj):
    """Example of a sophisticated numerical experiment
    that involves multiplying two integer values.

    :param traj:
        Trajectory containing the parameters in a particular
        combination, it also serves as a container for results.
    """
    z = traj.x * traj.y
    traj.f_add_result('z', z, comment='Result of x*y')

# Create an environment that handles running the experiment
env = Environment(trajectory='Multiplication',
                  filename='multiply.hdf5',
                  comment='A simulation of multiplication')
# The environment provides a trajectory container for us
traj = env.v_trajectory
# Add two parameters, both with default value 0
traj.f_add_parameter('x', 0, comment='First dimension')
traj.f_add_parameter('y', 0, comment='Second dimension')
# Explore the Cartesian product of x in {1,2,3,4} and y in {6,7,8}
traj.f_explore(cartesian_product({'x': [1, 2, 3, 4],
                                 'y': [6, 7, 8]}))
# Run simulation function `multiply` with all parameter combinations
env.f_run(multiply)