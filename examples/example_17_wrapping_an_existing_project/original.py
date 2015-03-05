""" This module contains a simulation of 1 dimensional cellular automata

We also simulate famous rule 110: http://en.wikipedia.org/wiki/Rule_110

"""

__author__ = 'Robert Meyer'

import numpy as np
import os
import matplotlib.pyplot as plt
import pickle

from pypet import progressbar #  I don't want to write another progressbar, so I use this here


def convert_rule(rule_number):
    """ Converts a rule given as an integer into a binary list representation.

    It reads from left to right (contrary to the Wikipedia article given below),
    i.e. the 2**0 is found on the left hand side and 2**7 on the right.

    For example:

        ``convert_rule(30)`` returns [0, 1, 1, 1, 1, 0, 0, 0]


    The resulting binary list can be interpreted as
    the following transition table:

         neighborhood  new cell state
                000     0
                001     1
                010     1
                011     1
                100     1
                101     0
                110     0
                111     0

    For more information about this rule
    see: http://en.wikipedia.org/wiki/Rule_30

    """
    binary_rule = [(rule_number // pow(2,i)) % 2 for i in range(8)]
    return np.array(binary_rule)


def make_initial_state(name, ncells, seed=42):
    """ Creates an initial state for the automaton.

    :param name:

        Either ``'single'`` for a single live cell in the middle of the cell ring,
        or ``'random'`` for uniformly distributed random pattern of zeros and ones.

    :param ncells: Number of cells in the automaton

    :param seed: Random number seed for the ``#random'`` condition

    :return: Numpy array of zeros and ones (or just a one lonely one surrounded by zeros)

    :raises: ValueError if the ``name`` is unknown

    """
    if name == 'single':
        just_one_cell = np.zeros(ncells)
        just_one_cell[int(ncells/2)] = 1.0
        return just_one_cell
    elif name == 'random':
        np.random.seed(seed)
        random_init = np.random.randint(2, size=ncells)
        return random_init
    else:
        raise ValueError('I cannot handel your initial state `%s`.' % name)


def plot_pattern(pattern, rule_number, filename):
    """ Plots an automaton ``pattern`` and stores the image under a given ``filename``.

    For axes labels the ``rule_number`` is also required.

    """
    plt.figure()
    plt.imshow(pattern)
    plt.xlabel('Cell No.')
    plt.ylabel('Time Step')
    plt.title('CA with Rule %s' % str(rule_number))
    plt.savefig(filename)
    #plt.show()
    plt.close()


def cellular_automaton_1D(initial_state, rule_number, steps):
    """ Simulates a 1 dimensional cellular automaton.

    :param initial_state:

        The initial state of *dead* and *alive* cells as a 1D numpy array.
        It's length determines the size of the simulation.

    :param rule_number:

        The update rule as an integer from 0 to 255.

    :param steps:

        Number of cell iterations

    :return:

        A 2D numpy array (steps x len(initial_state)) containing zeros and ones representing
        the automaton development over time.

    """

    ncells = len(initial_state)
    # Create an array for the full pattern
    pattern = np.zeros((steps, ncells))

    # Pass initial state:
    pattern[0,:] = initial_state

    # Get the binary rule list
    binary_rule = convert_rule(rule_number)

    # Conversion list to get the position in the binary rule list
    neighbourhood_factors = np.array([1, 2, 4])

    # Iterate over all steps to compute the CA
    all_cells = range(ncells)
    for step in range(steps-1):
        current_row = pattern[step, :]
        next_row = pattern[step+1, :]
        for irun in all_cells:
            # Get the neighbourhood
            neighbour_indices = range(irun - 1, irun + 2)
            neighbourhood = np.take(current_row, neighbour_indices, mode='wrap')
            # Convert neighborhood to decimal
            decimal_neighborhood = int(np.sum(neighbourhood * neighbourhood_factors))
            # Get next state from rule book
            next_state = binary_rule[decimal_neighborhood]
            # Update next state of cell
            next_row[irun] = next_state

    return pattern


def main():
    """ Main simulation function """
    rules_to_test = [10, 30, 90, 110, 184]  # rules we want to explore:
    steps = 250  # cell iterations
    ncells = 400  # number of cells
    seed = 100042  # RNG seed
    initial_states = ['single', 'random']  # Initial states we want to explore

    # create a folder for the plots and the data
    folder = os.path.join(os.getcwd(), 'experiments', 'ca_patterns_original')
    if not os.path.isdir(folder):
        os.makedirs(folder)
    filename = os.path.join(folder, 'all_patterns.p')

    print('Computing all patterns')
    all_patterns = []  # list containing the simulation results
    for idx, rule_number in enumerate(rules_to_test):
        # iterate over all rules
        for initial_name in initial_states:
            # iterate over the initial states

            # make the initial state
            initial_state = make_initial_state(initial_name, ncells, seed=seed)
            # simulate the automaton
            pattern = cellular_automaton_1D(initial_state, rule_number, steps)
            # keep the resulting pattern
            all_patterns.append((rule_number, initial_name, pattern))

        # Print a progressbar, because I am always impatient
        #  (ok that's already from pypet, but it's really handy!)
        progressbar(idx, len(rules_to_test), reprint=True)

    # Store all patterns to disk
    with open(filename, 'wb') as file:
        pickle.dump(all_patterns, file=file)

    # Finally print all patterns
    print('Plotting all patterns')
    for idx, pattern_tuple in enumerate(all_patterns):
        rule_number, initial_name, pattern = pattern_tuple
        # Plot the pattern
        filename = os.path.join(folder, 'rule_%s_%s.png' % (str(rule_number), initial_name))
        plot_pattern(pattern, rule_number, filename)
        progressbar(idx, len(all_patterns), reprint=True)


if __name__ == '__main__':
    main()

