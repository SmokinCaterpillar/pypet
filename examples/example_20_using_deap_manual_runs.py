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

"""


__author__ = 'Robert Meyer'

import random
import os
import itertools as itools
import time
import multiprocessing as multip

from deap import base
from deap import creator
from deap import tools

import logging
logging.basicConfig()

multip.log_to_stderr(0)


from pypet import Trajectory, cartesian_product, manual_run, MultiprocContext

@manual_run(store_meta_data=True, automatic_storing=True)
def eval_one_max(traj, individual):
    """The fitness function"""
    #print traj.v_storage_service.queue
    traj.f_add_result('$set.$.individual', list(individual))
    fitness = sum(individual)
    traj.f_add_result('$set.$.fitness', fitness)
    return fitness,

def eval_wrapper(the_tuple):
    return eval_one_max(*the_tuple)

def main():

    st = time.time()

    filename = os.path.join('experiments', 'example_20.hdf5')
    traj = Trajectory('onemax', filename=filename, overwrite_file=True)

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
    traj.f_store()


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
    toolbox.register("map", pool.imap)

    random.seed(traj.seed)

    pop = toolbox.population(n=traj.popsize)
    CXPB, MUTPB, NGEN = traj.CXPB, traj.MUTPB, traj.NGEN

    start_idx = 0
    print("Start of evolution")
    for g in range(traj.NGEN):
        print("-- Generation %i --" % g)

        eval_pop = [ind for ind in pop if not ind.fitness.valid]
        traj.f_expand(cartesian_product({'generation': [g], 'ind_idx': range(len(eval_pop))}))

        mc = MultiprocContext(traj, wrap_mode='QUEUE')
        mc.f_start()
        #print traj.v_storage_service.queue
        zip_iterable = itools.izip(traj.f_iter_runs(start_idx, yields='self'), eval_pop)
        #print next(zip_iterable)

        fitnesses = toolbox.map(eval_wrapper, zip_iterable)
        for idx, fitness in enumerate(fitnesses):
            eval_pop[idx].fitness.values = fitness
            #print fitness

        mc.f_finalize()

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

        if g < traj.NGEN -1:
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

    pool.close()
    pool.join()



    print("-- End of (successful) evolution --")

    best_ind = tools.selBest(pop, 1)[0]
    print("Best individual is %s, %s" % (best_ind, best_ind.fitness.values))

    print time.time() - st




if __name__ == "__main__":
    main()