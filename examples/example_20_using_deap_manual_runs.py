""" An example showing how to use DEAP optimization (http://pythonhosted.org/deap/).

DEAP can be combined with *pypet* to keep track of all the data and the full trajectory
of points created by a genetic algorithm.

Note that *pypet* adds quite some overhead to the optimization algorithm.
Using *pypet* in combination with DEAP is only suitable in case the
evaluation of an individual (i.e. a single run) takes a considerable amount of time
(i.e. 1 second or longer) and, thus, pypet's overhead is only marginal.

This *OneMax* problem serves only as an example and is not a well suited problem.
Suitable would be the genetic optimization of neural networks where running and evaluating
the network may take a few seconds.

Here we avoid using an Environment and *manually* execute runs using multiprocessing.

"""

__author__ = 'Robert Meyer'

import random

import os
import multiprocessing as multip
try:
    from itertools import izip
except ImportError:
    # For Python 3
    izip = zip

from deap import base
from deap import creator
from deap import tools

from pypet import Trajectory, cartesian_product, manual_run, MultiprocContext


@manual_run(store_meta_data=True)   # Important decorator for manual execution of runs
def eval_one_max(traj, individual):
    """The fitness function"""
    traj.f_add_result('$set.$.individual', list(individual))
    fitness = sum(individual)
    traj.f_add_result('$set.$.fitness', fitness)
    traj.f_store()
    return (fitness,)  # DEAP wants a tuple here!


def eval_wrapper(the_tuple):
    """Wrapper function that unpacks a single tuple as arguments to the fitness function.

    The pool's map function only allows a single iterable so we need to zip it first
    and then unpack it here.

    """
    return eval_one_max(*the_tuple)


def main():

    # No environment here ;-)
    filename = os.path.join('experiments', 'example_20.hdf5')
    traj = Trajectory('onemax', filename=filename, overwrite_file=True)


    # ------- Add parameters ------- #
    traj.f_add_parameter('popsize', 100)
    traj.f_add_parameter('CXPB', 0.5)
    traj.f_add_parameter('MUTPB', 0.2)
    traj.f_add_parameter('NGEN', 20)

    traj.f_add_parameter('generation', 0)
    traj.f_add_parameter('ind_idx', 0)
    traj.f_add_parameter('ind_len', 50)

    traj.f_add_parameter('indpb', 0.005)
    traj.f_add_parameter('tournsize', 3)

    traj.f_add_parameter('seed', 42)
    traj.f_store(only_init=True)


    # ------- Create and register functions with DEAP ------- #
    creator.create("FitnessMax", base.Fitness, weights=(1.0,))
    creator.create("Individual", list, fitness=creator.FitnessMax)

    toolbox = base.Toolbox()
    # Attribute generator
    toolbox.register("attr_bool", random.randint, 0, 1)
    # Structure initializers
    toolbox.register("individual", tools.initRepeat, creator.Individual,
        toolbox.attr_bool, traj.ind_len)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    # Operator registering
    toolbox.register("mate", tools.cxTwoPoint)
    toolbox.register("mutate", tools.mutFlipBit, indpb=traj.indpb)
    toolbox.register("select", tools.selTournament, tournsize=traj.tournsize)
    toolbox.register("evaluate", eval_wrapper)

    pool = multip.Pool(4)
    toolbox.register("map", pool.map)  # We use the pool's map function!


    # ------- Initialize Population -------- #
    random.seed(traj.seed)

    pop = toolbox.population(n=traj.popsize)
    CXPB, MUTPB, NGEN = traj.CXPB, traj.MUTPB, traj.NGEN


    start_idx = 0  # We need to count executed runs

    print("Start of evolution")
    for g in range(traj.NGEN):
        print("-- Generation %i --" % g)

        # Determine individuals that need to be evaluated
        eval_pop = [ind for ind in pop if not ind.fitness.valid]

        # Add as many explored runs as individuals that need to be evaluated
        traj.f_expand(cartesian_product({'generation': [g], 'ind_idx': range(len(eval_pop))}))

        # We need to make the storage service multiprocessing safe
        mc = MultiprocContext(traj, wrap_mode='QUEUE')
        mc.f_start()

        # Create a single iterable to be passed to our fitness function (wrapper).
        # `yields='copy'` is important, the pool's `map` function will
        # go over the whole iterator at once and store it in memory.
        # So for every run we need a copy of the trajectory.
        # Alternatively, you could use `yields='self'` and use the pool's `imap` function.
        zip_iterable = izip(traj.f_iter_runs(start_idx, yields='copy'), eval_pop)

        fitnesses = toolbox.map(eval_wrapper, zip_iterable)
        # fitnesses is just a list of tuples [(fitness,), ...]
        for idx, fitness in enumerate(fitnesses):
            # Update fitnesses
            eval_pop[idx].fitness.values = fitness

        # Finalize the multiproc wrapper
        mc.f_finalize()

        # Update start index
        start_idx += len(eval_pop)

        print("  Evaluated %i individuals" % len(eval_pop))

        # Gather all the fitnesses in one list and print the stats
        fits = [ind.fitness.values[0] for ind in pop]

        length = len(pop)
        mean = sum(fits) / length
        sum2 = sum(x*x for x in fits)
        std = abs(sum2 / length - mean**2)**0.5

        print("  Min %s" % min(fits))
        print("  Max %s" % max(fits))
        print("  Avg %s" % mean)
        print("  Std %s" % std)


        # ------- Create the next generation by crossover and mutation -------- #
        if g < traj.NGEN -1:   # not necessary for the last generation
            # Select the next generation individuals
            offspring = toolbox.select(pop, len(pop))
            # Clone the selected individuals
            offspring = list(map(toolbox.clone, offspring))

            # Apply crossover and mutation on the offspring
            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < CXPB:
                    toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values

            for mutant in offspring:
                if random.random() < MUTPB:
                    toolbox.mutate(mutant)
                    del mutant.fitness.values

            # The population is entirely replaced by the offspring
            pop[:] = offspring

    # Stop the multiprocessing pool
    pool.close()
    pool.join()

    print("-- End of (successful) evolution --")
    best_ind = tools.selBest(pop, 1)[0]
    print("Best individual is %s, %s" % (best_ind, best_ind.fitness.values))

    traj.f_store()  # And store all the rest of the data


if __name__ == "__main__":
    main()