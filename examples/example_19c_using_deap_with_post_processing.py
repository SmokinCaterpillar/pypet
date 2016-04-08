""" An example showing how to use DEAP optimization (http://pythonhosted.org/deap/).

DEAP can be combined with *pypet* to keep track of all the data and the full trajectory
of points created by a genetic algorithm.

This is a version with less overhead added by *pypet*
and using the post processing functionality.

"""

__author__ = 'Robert Meyer'

import random

from deap import base
from deap import creator
from deap import tools

from pypet import Environment, cartesian_product

def eval_one_max(traj):
    """The fitness function"""
    fitness = sum(traj.individual)
    return (fitness,)  # DEAP wants a tuple here!


class Postprocessing(object):
    """Callable that implements postprocessing.

    It is realised as an object to be able to keep track of current generation
    and the population.

    """

    def __init__(self, pop, eval_pop, toolbox, g=0):
        self.g = g  # the current generation
        self.pop = pop  # the current population
        self.toolbox = toolbox  # the DEAP toolbox
        self.eval_pop = eval_pop  # the currently evaluated population

    def __call__(self, traj, fitnesses_results):
        """Implements post-processing"""
        CXPB, MUTPB, NGEN = traj.CXPB, traj.MUTPB, traj.NGEN

        while fitnesses_results:
            result = fitnesses_results.pop()
            # Update fitnesses
            run_index, fitness = result  # The environment returns tuples: [(run_idx, run), ...]
            # We need to convert the current run index into an ind_idx
            # (index of individual within one generation)
            traj.v_idx = run_index
            ind_index = traj.par.ind_idx
            # Use the ind_idx to update the fintess
            self.eval_pop[ind_index].fitness.values = fitness
        traj.v_idx = -1 # set the trajectory back to default

        # Append all fitnesses (note that DEAP fitnesses are tuples of length 1
        # but we are only interested in the value)
        traj.fitnesses.extend([x.fitness.values[0] for x in self.eval_pop])

        print("  Evaluated %i individuals" % len(fitnesses_results))
        # Gather all the fitnesses in one list and print the stats
        fits = [ind.fitness.values[0] for ind in self.pop]

        length = len(self.pop)
        mean = sum(fits) / length
        sum2 = sum(x*x for x in fits)
        std = abs(sum2 / length - mean**2)**0.5

        print("  Min %s" % min(fits))
        print("  Max %s" % max(fits))
        print("  Avg %s" % mean)
        print("  Std %s" % std)


        # ------- Create the next generation by crossover and mutation -------- #
        if self.g < traj.NGEN -1:  # not necessary for the last generation
            # Select the next generation individuals
            offspring = self.toolbox.select(self.pop, len(self.pop))
            # Clone the selected individuals
            offspring = list(map(self.toolbox.clone, offspring))

            # Apply crossover and mutation on the offspring
            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < CXPB:
                    self.toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values

            for mutant in offspring:
                if random.random() < MUTPB:
                    self.toolbox.mutate(mutant)
                    del mutant.fitness.values

            # The population is entirely replaced by the offspring
            self.pop[:] = offspring

            self.eval_pop = [ind for ind in self.pop if not ind.fitness.valid]

            # Add as many explored runs as individuals that need to be evaluated.
            # Furthermore, add the individuals as explored parameters.
            # We need to convert them to lists or write our own custom IndividualParameter ;-)
            # Note the second argument to `cartesian_product`:
            # This is for only having the cartesian product
            # between ``generation x (ind_idx AND individual)``,
            # so that every individual has just one
            # unique index within a generation.
            self.g += 1  # Update generation counter
            traj.f_expand(cartesian_product({'generation': [self.g],
                                             'ind_idx': range(len(self.eval_pop)),
                                             'individual':[list(x) for x in self.eval_pop]},
                                                [('ind_idx', 'individual'),'generation']))


def main():

    env = Environment(trajectory='postproc_deap',
                      overwrite_file=True,
                      log_stdout=False,
                      log_level=50,  # only display ERRORS
                      automatic_storing=True,  # Since we us post-processing, we
                      # can safely enable automatic storing, because everything will
                      # only be stored once at the very end of all runs.
                      comment='Using pypet and DEAP with less overhead'
                      )
    traj = env.traj


    # ------- Add parameters ------- #
    traj.f_add_parameter('popsize', 100, comment='Population size')
    traj.f_add_parameter('CXPB', 0.5, comment='Crossover term')
    traj.f_add_parameter('MUTPB', 0.2, comment='Mutation probability')
    traj.f_add_parameter('NGEN', 20, comment='Number of generations')

    traj.f_add_parameter('generation', 0, comment='Current generation')
    traj.f_add_parameter('ind_idx', 0, comment='Index of individual')
    traj.f_add_parameter('ind_len', 50, comment='Length of individual')

    traj.f_add_parameter('indpb', 0.005, comment='Mutation parameter')
    traj.f_add_parameter('tournsize', 3, comment='Selection parameter')

    traj.f_add_parameter('seed', 42, comment='Seed for RNG')


    # Placeholders for individuals and results that are about to be explored
    traj.f_add_derived_parameter('individual', [0 for x in range(traj.ind_len)],
                                 'An indivudal of the population')
    traj.f_add_result('fitnesses', [], comment='Fitnesses of all individuals')


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


    # ------- Initialize Population and Trajectory -------- #
    random.seed(traj.seed)
    pop = toolbox.population(n=traj.popsize)

    eval_pop = [ind for ind in pop if not ind.fitness.valid]
    traj.f_explore(cartesian_product({'generation': [0],
                                     'ind_idx': range(len(eval_pop)),
                                     'individual':[list(x) for x in eval_pop]},
                                        [('ind_idx', 'individual'),'generation']))

    # ----------- Add postprocessing ------------------ #
    postproc = Postprocessing(pop, eval_pop, toolbox)  # Add links to important structures
    env.add_postprocessing(postproc)

    # ------------ Run applying post-processing ---------- #
    env.run(eval_one_max)

    # ------------ Finished all runs and print result --------------- #
    print("-- End of (successful) evolution --")
    best_ind = tools.selBest(pop, 1)[0]
    print("Best individual is %s, %s" % (best_ind, best_ind.fitness.values))


if __name__ == "__main__":
    main()