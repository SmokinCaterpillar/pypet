__author__ = 'robert'


from pypet.trajectory import Trajectory
from pypet.pypetexceptions import NotUniqueNodeError



# We first generate a new Trajectory
traj = Trajectory('Example',filename='experiments/example_02/HDF5/example_02.hdf5',
                  file_title='Example02', comment='Access and Storage!')


# We add our first parameter with the data 'Harrison Ford'
traj.f_add_parameter('starwars.characters.han_solo', 'Harrison Ford')

# This automatically added the groups 'starwars' and the subgroup 'characters'
# Let's get this group
characters = traj.parameters.starwars.characters

#Since characters is unique we could also use shortcuts
characters = traj.characters

#Or the get method
characters = traj.f_get('characters')

#Lets add another character
characters.f_add_parameter('luke_skywalker', 'Mark Hamill', comment='May the force be with you!')

#The full name of luke skywalker is now `parameters.starwars.characters.luke_skywalker:
print 'The full name of the new Skywalker Parameter is %s' % traj.f_get('luke_skywalker').v_full_name

#Lets see what happens if we have not unique entries:
traj.f_add_parameter_group('spaceballs.characters')

#We can still use shortcuts
characters = traj.characters

#But we cannot be sure which characters we have, to be on the safe side, let's check if
# we perform unique search
traj.v_check_uniqueness=True

try:
    traj.characters
except NotUniqueNodeError as e:
    print 'Damn it there are two characters groups in the trajectory: %s' % e._msg

# But if we are more specific we have again a unique finding
characters = traj.starwars.characters

#Now let's see what fast access is:
print 'The name of the actor playing Luke is %s.' % traj.luke_skywalker

#And now what happens if you forbid it
traj.v_fast_access=False
print 'The object found for luke_skywalker is `%s`.' % str(traj.luke_skywalker)

#Let's store the trajectory:
traj.f_store()

#That was easy, let's assume we already completed a simulation and now we add a veeeery large
#result that we want to store to disk immediatly and than empty it
traj.f_add_result('starwars.gross_income_of_film', amount=10.1 ** 11, currency='$$$',
                  comment='George Lucas is rich, dude!')

#This is a large number, we better store it and than free the memory:
traj.f_store_item('gross_income_of_film')
traj.gross_income_of_film.f_empty()


# Now lets reload the trajectory
del traj
traj = Trajectory(filename='experiments/example_02/HDF5/example_02.hdf5')
#We want to load the last trajectory in the file, therefore index =-1
#We want to load the parameters therefore load_parameters=2
#We only want to load the skeleton of the result
traj.f_load(index=-1,load_parameters=2,load_results=1)

##Let's check if our result is in fact empty
if traj.gross_income_of_film.f_is_empty():
    print 'Nothing there!'
else:
    print 'I found something!'

#Ok, let's manually reload the result
traj.f_load_item('gross_income_of_film')
if traj.gross_income_of_film.f_is_empty():
    print 'Still empty :-('
else:
    print 'George Lucas earned %s %s!' %(str(traj.gross_income_of_film.amount),
                                         traj.gross_income_of_film.currency)


## And that's how it works! If you wish, you can inspect the
# experiments/example_02/HDF5/example_02.hdf5 file to take a look at the tree structure