__author__ = 'Robert Meyer'

import os # To allow pathnames under Windows and Linux

from pypet import Trajectory, NotUniqueNodeError


# We first generate a new Trajectory
filename = os.path.join('hdf5', 'example_02.hdf5')
traj = Trajectory('Example', filename=filename,
                  overwrite_file=True,
                  comment='Access and Storage!')


# We add our first parameter with the data 'Harrison Ford'
traj.f_add_parameter('starwars.characters.han_solo', 'Harrison Ford')

# This automatically added the groups 'starwars' and the subgroup 'characters'
# Let's get the characters subgroup
characters = traj.parameters.starwars.characters

# Since characters is unique we could also use shortcuts
characters = traj.characters

# Or the get method
characters = traj.f_get('characters')

# Or square brackets
characters = traj['characters']

# Lets add another character
characters.f_add_parameter('luke_skywalker', 'Mark Hamill', comment='May the force be with you!')

#The full name of luke skywalker is now `parameters.starwars.characters.luke_skywalker`:
print('The full name of the new Skywalker Parameter is %s' %
      traj.f_get('luke_skywalker').v_full_name)

#Lets see what happens if we have not unique entries:
traj.f_add_parameter_group('spaceballs.characters')

# Now our shortcuts no longer work, since we have two character groups!
try:
    traj.characters
except NotUniqueNodeError as exc:
    print('Damn it, there are two characters groups in the trajectory: %s' % repr(exc))

# But if we are more specific we have again a unique finding
characters = traj.starwars.characters

# Now let's see what fast access is:
print('The name of the actor playing Luke is %s.' % traj.luke_skywalker)

# And now what happens if you forbid it
traj.v_fast_access=False
print('The object found for luke_skywalker is `%s`.' % str(traj.luke_skywalker))

#Let's store the trajectory:
traj.f_store()

# That was easy, let's assume we already completed a simulation and now we add a veeeery large
# result that we want to store to disk immediately and than empty it
traj.f_add_result('starwars.gross_income_of_film', amount=10.1 ** 11, currency='$$$',
                  comment='George Lucas is rich, dude!')

# This is a large number, we better store it and than free the memory:
traj.f_store_item('gross_income_of_film')
traj.gross_income_of_film.f_empty()

# Moreover, if you don't like prefixes `f_` and `v_` you can also use `func` and `vars`:
traj.func.add_result('starwars.robots', c3p0='android', r2d2='beeep!', comment='Help me Obiwan!')
print(traj.results.starwars.robots.vars.comment)

# Now lets reload the trajectory
del traj
traj = Trajectory(filename=filename)
# We want to load the last trajectory in the file, therefore index = -1
# We want to load the parameters, therefore load_parameters=2
# We only want to load the skeleton of the results, so load_results=1
traj.f_load(index=-1, load_parameters=2, load_results=1)

# Let's check if our result is really empty
if traj.gross_income_of_film.f_is_empty():
    print('Nothing there!')
else:
    print('I found something!')

# Ok, let's manually reload the result
traj.f_load_item('gross_income_of_film')
if traj.gross_income_of_film.f_is_empty():
    print('Still empty :-(')
else:
    print('George Lucas earned %s%s!' %(str(traj.gross_income_of_film.amount),
                                         traj.gross_income_of_film.currency))

# And that's how it works! If you wish, you can inspect the
# experiments/example_02/HDF5/example_02.hdf5 file to take a look at the tree structure