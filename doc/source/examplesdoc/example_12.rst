
.. _example-12:

===================================
Sharing Data during Multiprocessing
===================================

Here we show how data can be shared among multiple processes.
Mind however, that this is conceptually a rather bad design
since the single runs are no longer independent of each other.
A better solution would be to simply return the data and
sort it into a list during post-processing.

Download: :download:`example_12_sharing_data_between_processes.py <../../../examples/example_12_sharing_data_between_processes.py>`


.. literalinclude:: ../../../examples/example_12_sharing_data_between_processes.py