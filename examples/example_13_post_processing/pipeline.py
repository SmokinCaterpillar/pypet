__author__ = 'robert'

import logging
import os # For path names working under Windows and Linux

from main import add_parameters, add_exploration, run_neuron, neuron_postproc
from pypet import Environment


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
    filename = os.path.join('hdf5', 'FiringRate.hdf5')
    env = Environment(trajectory='FiringRatePipeline',
                      comment='Experiment to measure the firing rate '
                            'of a leaky integrate and fire neuron. '
                            'Exploring different input currents, '
                            'as well as refractory periods',
                      add_time=False, # We don't want to add the current time to the name,
                      log_stdout=True,
                      multiproc=True,
                      ncores=2, #My laptop has 2 cores ;-)
                      filename=filename,
                      overwrite_file=True)

    env.pipeline(mypipeline)

    # Finally disable logging and close all log-files
    env.disable_logging()

if __name__ == '__main__':
    main()
