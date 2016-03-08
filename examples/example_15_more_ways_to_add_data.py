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

# What happens if our new parameter's name does not match the name passed to the constructor?
traj.parameters.subgroup = Parameter('v', 2, comment='Fourth dimension')
# Well, since 'subgroup' != 'v', 'subgroup' becomes just another group node created on the fly
print(traj.parameters.subgroup)
# This even works for already existing groups and with the well known *dot* notation:
traj.parameters = Parameter('subgroup.subsubgroup.w', 2)
# See
print('w='+str(traj.par.subgroup.subsubgroup.w))


# Finally, there's one more thing. Using this notation we can also add links.
# Simply use the `=` assignment with objects that already exist in your trajectory:
traj.mylink = traj.f_get('x')
# now `mylink` links to parameter `x`, also fast access works:
print('Linking to x gives: ' + str(traj.mylink))


