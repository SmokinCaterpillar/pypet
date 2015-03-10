""" Module providing the functionality to allow automatic git commits.

* :func:`~pypet.gitintegration.make_git_commit` performs the git commit

* :func:`~pypet.gitintegration.add_commit_variables` adds some information about the commit to a
  :class:`~pypet.trajectory.Trajectory`.


"""

__author__ = 'Robert Meyer'

import time

try:
    import git
except ImportError:
    git = None

import pypet.pypetexceptions as pex


def add_commit_variables(traj, commit):
    """Adds commit information to the trajectory."""

    git_time_value = time.strftime('%Y_%m_%d_%Hh%Mm%Ss', time.localtime(commit.committed_date))

    git_short_name = str(commit.hexsha[0:7])
    git_commit_name = 'commit_%s_' % git_short_name
    git_commit_name = 'git.' + git_commit_name + git_time_value

    if not traj.f_contains('config.'+git_commit_name, shortcuts=False):

        git_commit_name += '.'
        # Add the hexsha
        traj.f_add_config(git_commit_name+'hexsha', commit.hexsha,
                          comment='SHA-1 hash of commit')

        # Add the description string
        traj.f_add_config(git_commit_name+'name_rev', commit.name_rev,
                          comment='String describing the commits hex sha based on '
                                  'the closest Reference')

        # Add unix epoch
        traj.f_add_config(git_commit_name+'committed_date',
                          commit.committed_date, comment='Date of commit as unix epoch seconds')

        # Add commit message
        traj.f_add_config(git_commit_name+'message', str(commit.message),
                          comment='The commit message')

        # # Add commit author
        # traj.f_add_config(git_commit_name+'committer', str(commit.committer.name),
        #                   comment='The committer of the commit')
        #
        # # Add author's email
        # traj.f_add_config(git_commit_name+'committer_email', str(commit.committer.email),
        #                   comment='Email of committer')


def make_git_commit(environment, git_repository, user_message, git_fail):
    """ Makes a commit and returns if a new commit was triggered and the SHA_1 code of the commit.

    If `git_fail` is `True` program fails instead of triggering a new commit given
    not committed changes. Then a `GitDiffError` is raised.

    """

    # Import GitPython, we do it here to allow also users not having GitPython installed
    # to use the normal environment

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

    message = '%sTrajectory: `%s`, Time: `%s`, %s' % \
              (user_message, traj.v_name, traj.v_time, commentstr)

    # Detect changes:
    diff = index.diff(None)

    if diff:
        if git_fail:
            # User requested fail instead of a new commit
            raise pex.GitDiffError('Found not committed changes!')
        # Make the commit
        repo.git.add('-u')
        commit = index.commit(message)
        new_commit = True

    else:
        # Take old commit
        commit = repo.commit(None)
        new_commit = False

    # Add the commit info to the trajectory
    add_commit_variables(traj, commit)

    return new_commit, commit.hexsha
