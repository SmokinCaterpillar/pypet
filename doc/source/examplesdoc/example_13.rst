
.. _example-13:

==================================================
Post-Processing and Pipelining (from the Tutorial)
==================================================

Here you find an example of post-processing.

It consists of a main script `main.py` for the three phases
*pre-processing*, *run phase* and *post-processing* of a single neuron
simulation and a `analysis.py` file
giving an example of a potential data analysis encompassing plotting the results.
Moreover, there exists a `pipeline.py` file to crunch all first three phases into
a single function.

A detail explanation of the example can be found in the :ref:`tutorial` section.


Download: :download:`main.py <../../../examples/example_13_post_processing/main.py>`

Download: :download:`analysis.py <../../../examples/example_13_post_processing/analysis.py>`

Download: :download:`pipeline.py <../../../examples/example_13_post_processing/pipeline.py>`

------------
Main
------------

.. literalinclude:: ../../../examples/example_13_post_processing/main.py


----------
Analysis
----------

.. literalinclude:: ../../../examples/example_13_post_processing/analysis.py


-----------
Pipelining
-----------

Additionally, you can use pipelining.

Since these three steps pre-processing, run-phase, post-processing define a common pipeline,
you can actually also make *pypet* supervise all three steps at once.

You can define a pipeline function, that does the pre-processing and returns
the job function plus some optional arguments and the post-processing function
with some other optional arguments.

So, you could define the following pipeline function.
The pipeline function has to only accept the trajectory as first argument and
has to return 2 tuples, one for the run function and one for the
post-processing. Since none of our functions takes any other arguments than the trajectory
(and the pos-processing function the result list) we simply return an empty
tuple ``()`` for no arguments and an empty dictionary ``{}`` for no keyword arguments.


And that's it, than everything including the pre-processing and addition of parameters
is supervised by *pypet*. Check out the source code below:

.. literalinclude:: ../../../examples/example_13_post_processing/pipeline.py