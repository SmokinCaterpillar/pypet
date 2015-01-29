__author__ = 'Robert Meyer'

from pypet import Trajectory, Result, Parameter


traj = Trajectory()

# There are more ways to add data,
# 1st the standard way:
traj.f_add_parameter('x', 1, comment='I am the first dimension!')
# 2nd by providing a new parameter/result instance, be aware that the data is added where
# you specify it. There are no such things as shortcuts for parameter creation:
traj.parameters.y = Parameter('y', 1, comment='I am the second dimension!')
# 3rd as before, but if our new leaf has NO name it will be renamed accordingly:
traj.parameters.t = Parameter('', 1, comment='Third dimension')
# See:
print('t=' + str(traj.t))
# 4th there's a neat shortcut for this, if you pass a tuple of exactly length 2
# and the second entry is a string, i.e. your comment. This is interpreted as adding a
# new leaf to your trajectory:
traj.parameters.u = 1, 'Fourth dimension'
# See
print('u=' + str(traj.u))
# However, if you pass anything else than an already instantiated Parameter or Result
# or a tuple of length 2 including a comment, this is interpreted as CHANGING an
# existing leaf. Here shortcuts do work:
traj.f_get('u').f_unlock() # We accessed the value above in the print statement,
# so in order to change `u` we need to unlock it
traj.u = 2
# See:
print('u=' + str(traj.par.u))
# So providing a novel result or parameter instance or a tuple of exactly length 2
# containing a string comment will always add new leaves to your trajectory.
# Whereas the other assignment simply changes an existing leaf.
# Accordingly this fails, since there's already a parameter named `u`
try:
    traj.parameters.u = 3, 'Hey I`m a new comment'
except AttributeError:
    print('Sorry u already exists!')
# But this works in case u is unlocked
traj.f_get('u').f_unlock()
traj.parameters.u = 3
# since we simply change `u` to be 3

# What happens if our new parameter's name does not match the name passed to the constructor?
traj.parameters.subgroup = Parameter('v', 2, comment='Fourth dimension')
# Well, since 'subgroup' != 'v', 'subgroup' becomes just another group node created on the fly
print(traj.parameters.subgroup)
# This even works for already existing groups and with the well known *dot* notation:
traj.parameters = Parameter('subgroup.subsubgroup.w', 2)
# See
print('w='+str(traj.par.subgroup.subsubgroup.w))

# All of the above do, of course, apply to results as well:
traj.results.z = 1234, 'I am a result comment!'
print('z=' + str(traj.z) + ', and now I am a ' + str(type(traj.f_get('z'))))
# What would happen if you want to change a result to contain a tuple of length 2
# including a string? Well, there you would need the `f_set` method:
traj.f_get('z').f_set((42, 'I am NOT a comment, I am value!'))
# See
print('z=' + str(traj.z), ', but the comment still is:' + traj.f_get('z').v_comment)

# Finally, there's one more thing. Using this notation we can also add links.
# Simply use the `=` assignment with objects that already exist in your trajectory:
traj.mylink = traj.f_get('x')
# now `mylink` links to parameter `x`, also fast access works:
print('Linking to x gives: ' + str(traj.mylink))


