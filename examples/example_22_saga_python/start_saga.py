"""Example how to use pypet with SAGA python

The example is based on `ssh` but using a cluster is almost analogous.
For examples on how to submit jobs to cluster with SAGA python check
the documentation: http://saga-python.readthedocs.org/en/latest/

We run `the_task` in batches and create several trajectories,
later on we simply merge the batches into a single trajectory.

"""

import sys
import saga
from saga.filesystem import OVERWRITE
import os
import traceback


ADDRESS = '12345.fake.street'  # Address of your server
USER = 'user'  # Username
PASSWORD = '12345'  # That's amazing I got the same combination on my luggage!
WORKING_DIR = '/myhome/'  # Your working directory


def upload_file(filename, session):
    """ Uploads a file """
    print('Uploading file %s' % filename)
    outfilesource = os.path.join(os.getcwd(), filename)
    outfiletarget = 'sftp://' + ADDRESS + WORKING_DIR
    out = saga.filesystem.File(outfilesource, session=session, flags=OVERWRITE)
    out.copy(outfiletarget)
    print('Transfer of `%s` to `%s` successful' % (filename, outfiletarget))


def download_file(filename, session):
    """ Downloads a file """
    print('Downloading file %s' % filename)
    infilesource = os.path.join('sftp://' + ADDRESS + WORKING_DIR,
                                 filename)
    infiletarget = os.path.join(os.getcwd(), filename)
    incoming = saga.filesystem.File(infilesource, session=session, flags=OVERWRITE)
    incoming.copy(infiletarget)
    print('Transfer of `%s` to `%s` successful' % (filename, infiletarget))


def create_session():
    """ Creates and returns a new SAGA session """
    ctx = saga.Context("UserPass")
    ctx.user_id = USER
    ctx.user_pass = PASSWORD

    session = saga.Session()
    session.add_context(ctx)

    return session


def merge_trajectories(session):
    """ Merges all trajectories found in the working directory """
    jd = saga.job.Description()

    jd.executable      = 'python'
    jd.arguments       = ['merge_trajs.py']
    jd.output          = "mysagajob_merge.stdout"
    jd.error           = "mysagajob_merge.stderr"
    jd.working_directory = WORKING_DIR

    js = saga.job.Service('ssh://' + ADDRESS, session=session)
    myjob = js.create_job(jd)
    print("\n...starting job...\n")

    # Now we can start our job.
    myjob.run()
    print("Job ID    : %s" % (myjob.id))
    print("Job State : %s" % (myjob.state))

    print("\n...waiting for job...\n")
    # wait for the job to either finish or fail
    myjob.wait()

    print("Job State : %s" % (myjob.state))
    print("Exitcode  : %s" % (myjob.exit_code))


def start_jobs(session):
    """ Starts all jobs and runs `the_task.py` in batches. """

    js = saga.job.Service('ssh://' + ADDRESS, session=session)

    batches = range(3)
    jobs = []

    for batch in batches:
        print('Starting batch %d' % batch)

        jd = saga.job.Description()

        jd.executable      = 'python'
        jd.arguments       = ['the_task.py --batch=' + str(batch)]
        jd.output          = "mysagajob.stdout" + str(batch)
        jd.error           = "mysagajob.stderr" + str(batch)
        jd.working_directory = WORKING_DIR

        myjob = js.create_job(jd)

        print("Job ID    : %s" % (myjob.id))
        print("Job State : %s" % (myjob.state))

        print("\n...starting job...\n")

        myjob.run()
        jobs.append(myjob)

    for myjob in jobs:
        print("Job ID    : %s" % (myjob.id))
        print("Job State : %s" % (myjob.state))

        print("\n...waiting for job...\n")
        # wait for the job to either finish or fail
        myjob.wait()

        print("Job State : %s" % (myjob.state))
        print("Exitcode  : %s" % (myjob.exit_code))


def main():
    try:
        session = create_session()
        upload_file('the_task.py', session)
        upload_file('merge_trajs.py', session)
        # download_file('saga_0.hdf5', session)  # currently buggy, wait for SAGA python update
        # To see the resulting file manually download it from the server!

        start_jobs(session)
        merge_trajectories(session)
        return 0

    except saga.SagaException as ex:
        # Catch all saga exceptions
        print("An exception occured: (%s) %s " % (ex.type, (str(ex))))
        # Trace back the exception. That can be helpful for debugging.
        traceback.print_exc()
        return -1


if __name__ == "__main__":
    sys.exit(main())