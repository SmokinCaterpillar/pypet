""" Module providing the functionality to allow automatic git commits.

* :func:`~pypet.gitintegration.make_git_commit` performs the git commit

* :func:`~pypet.gitintegration.add_commit_variables` adds some information about the commit to a
  :class:`~pypet.trajectory.Trajectory`.


"""

__author__ = 'Robert Meyer'

import time

def add_commit_variables(traj, new_commit, message):
    """Adds commit information to the trajectory."""

    # Namings of the config variables
    git_hexhsa= 'hexsha'
    git_name_rev = 'name_rev'
    git_committed_date = 'committed_date'
    git_message = 'message'

    git_time_value = time.strftime('%Y_%m_%d_%Hh%Mm%Ss', time.localtime(new_commit.committed_date))

    git_short_name = str( new_commit.hexsha[0:7])
    git_commit_name = 'commit_%s_' % git_short_name
    git_commit_name = 'git.' + git_commit_name + git_time_value +'.'

    # Add the hexsha
    traj.f_add_config(git_commit_name+git_hexhsa, new_commit.hexsha,
                          comment='SHA-1 hash of commit')

    # Add the description string
    traj.f_add_config(git_commit_name+git_name_rev, new_commit.name_rev,
            comment='String describing the commits hex sha based on the closest Reference')

    # Add unix epoch
    traj.f_add_config(git_commit_name+git_committed_date,
                           new_commit.committed_date, comment='Date of commit as unix epoch seconds')

    # Add commit message
    traj.f_add_config(git_commit_name+git_message, message,
                            comment='The commit message')




def make_git_commit(environment, git_repository, user_message):
    """ Makes a commit returns the SHA_1 code of the commit."""

    # Import GitPython, we do it here to allow also users not having GitPython installed
    # to use the normal environment
    import git

    # Open the repository
    repo = git.Repo(git_repository)
    index = repo.index

    traj = environment.v_trajectory

    # Create the commit message and append the trajectory name and comment
    if traj.v_comment:
        commentstr = ', Comment: `%s`' % traj.v_comment
    else:
        commentstr = ''

    if user_message:
       user_message += ' -- '

    message = '%sTrajectory: `%s`, Time: `%s`%s' % \
              (user_message, traj.v_name, traj.v_time, commentstr)


    # Make the commit
    repo.git.add('-u')
    new_commit = index.commit(message)

    # Add the commit info to the trajectory
    add_commit_variables(traj, new_commit, message)

    return new_commit.hexsha