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

from deap import base
from deap import creator
from deap import tools

from pypet import Environment, cartesian_product

def eval_one_max(traj, individual):
    """The fitness function"""
    traj.f_add_result('$set.$.individual', list(individual))
    fitness = sum(individual)
    traj.f_add_result('$set.$.fitness', fitness)
    return fitness,

def main():

    env = Environment(overwrite_file=True, multiproc=True, ncores=4, log_level=50,
                      log_stdout=False, wrap_mode='QUEUE')
    traj = env.v_traj

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
    toolbox.register("evaluate", lambda pop: env.f_run_map(eval_one_max, pop))

    random.seed(traj.seed)

    pop = toolbox.population(n=traj.popsize)
    CXPB, MUTPB, NGEN = traj.CXPB, traj.MUTPB, traj.NGEN

    print("Start of evolution")
    for g in range(traj.NGEN):
        print("-- Generation %i --" % g)

        eval_pop = [ind for ind in pop if not ind.fitness.valid]
        traj.f_expand(cartesian_product({'generation': [g], 'ind_idx': range(len(eval_pop))}))

        start_idx = env.v_current_idx
        fitnesses = toolbox.evaluate(eval_pop)#env.f_run_map(eval_one_max, eval_pop)
        traj.res.f_remove()

        for idx, fitness in fitnesses:
            pop_idx = idx - start_idx
            eval_pop[pop_idx].fitness.values = fitness

        print("  Evaluated %i individuals" % len(fitnesses))


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

    print("-- End of (successful) evolution --")

    best_ind = tools.selBest(pop, 1)[0]
    print("Best individual is %s, %s" % (best_ind, best_ind.fitness.values))

if __name__ == "__main__":
    main()