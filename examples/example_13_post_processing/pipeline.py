__author__ = 'robert'
from main import add_parameters, add_exploration, run_neuron, neuron_postproc
from pypet import Environment
import logging

def mypipeline(traj):
    """A pipeline function that defines the entire experiment

    :param traj:

        Container for results and parameters

    :return:

        Two tuples. First tuple contains the actual run function plus additional
        arguments (yet we have none). Second tuple contains the
        postprocessing function including additional arguments.

    """
    add_parameters(traj)
    add_exploration(traj)
    return (run_neuron,(),{}), (neuron_postproc,(),{})

def main():

    env = Environment(trajectory='FiringRatePipeline',
                      comment='Experiment to measure the firing rate '
                            'of a leaky integrate and fire neuron. '
                            'Exploring different input currents, '
                            'as well as refractory periods',
                      add_time=False, # We don't want to add the current time to the name,
                      log_folder='./logs/',
                      log_level=logging.INFO,
                      log_stdout=True,
                      multiproc=True,
                      ncores=2, #My laptop has 2 cores ;-)
                      filename='./hdf5/', # We only pass a folder here, so the name is chosen
                      # automatically to be the same as the Trajectory
                      )

    env.f_pipeline(mypipeline)

if __name__ == '__main__':
    main()
