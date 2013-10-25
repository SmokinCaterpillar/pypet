__author__ = 'Robert Meyer'


import time

def add_commit_variables(traj, new_commit, repo_folder, message):
    '''Adds commit information to the trajectory'''

    git_hexhsa= 'hexsha'
    git_name_rev = 'name_rev'
    git_committed_date = 'committed_date'
    git_message = 'message'

    git_time_value = time.strftime('%Y_%m_%d_%Hh%Mm%Ss', time.localtime(new_commit.committed_date))

    git_short_name = str( new_commit.hexsha[0:7])
    git_commit_name = 'commit_%s_' % git_short_name
    git_commit_name = 'git.' + git_commit_name + git_time_value +'.'

    hex=traj.f_add_config(git_commit_name+git_hexhsa, new_commit.hexsha,
                          comment='SHA-1 hash of commit')

    rev=traj.f_add_config(git_commit_name+git_name_rev, new_commit.name_rev,
            comment='String describing the commits hex sha based on the closest Reference')


    date=traj.f_add_config(git_commit_name+git_committed_date,
                           new_commit.committed_date, comment='Date of commit as unix epoch seconds')


    msg = traj.f_add_config(git_commit_name+git_message, message,
                            comment='The commit message')


    #traj.f_store_items([hex,rev,repo,date,formatted_time,msg])

def make_git_commit(environment, git_repository, user_message):
    ''' Makes a commit returns the SHA_1 code of the commit otherwise False'''

    import git


    repo = git.Repo(git_repository)
    index = repo.index

    traj = environment.v_trajectory


    if traj.v_comment:
        commentstr = ', Comment: `%s`' % traj.v_comment
    else:
        commentstr = ''

    if user_message:
       user_message += ' -- '

    message = '%sTrajectory: `%s`, Time: `%s`%s' % \
              (user_message,traj.v_name, traj.v_time, commentstr)


    repo.git.add('-u')
    new_commit = index.commit(message)
    add_commit_variables(traj,new_commit, git_repository, message)





    return new_commit.hexsha