.. pypet documentation master file, created by
   sphinx-quickstart on Wed Sep  4 12:12:59 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

==================================
Welcome to *pypet*'s documentation
==================================

.. image:: https://travis-ci.org/SmokinCaterpillar/pypet.svg?branch=master
   :target: https://travis-ci.org/SmokinCaterpillar/pypet
.. image:: https://ci.appveyor.com/api/projects/status/9amhj3iyf105xa2y/branch/master?svg=true
   :target: https://ci.appveyor.com/project/SmokinCaterpillar/pypet/branch/master
.. image:: https://coveralls.io/repos/github/SmokinCaterpillar/pypet/badge.svg?branch=master
   :target: https://coveralls.io/github/SmokinCaterpillar/pypet?branch=master

The new python parameter exploration toolkit:
*pypet* manages exploration of the parameter space
of any numerical simulation in python,
thereby storing your data into HDF5_ files for you.
Moreover, *pypet* offers a new data container which
lets you access all your parameters and results
from a single source. Data I/O of your simulations and
analyses becomes a piece of cake!

Latest version: `0.2b.0`_

.. _`0.2b.0`: https://pypi.python.org/pypi/pypet

.. _HDF5: http://www.hdfgroup.org/HDF5/

--------------------
IMPORTANT DISCLAIMER
--------------------

The program is currently under development,
please keep that in mind and use it very carefully.

Before publishing the official *0.1.0* release I will integrate *pypet* first in my own research
project. Thus, I have a more profound testing environment than only using
unittests. Accordingly, you still have to deal with the naming *0.1b.X* for a little while.
However, unless it is really, really, really necessary I do not plan to introduce
drastic API changes anymore.
So feel free to use this beta version and even more so feel free to give feedback,
suggestions, and report bugs. Use **github** (https://github.com/SmokinCaterpillar/pypet) issues or
write to the `pypet Google Group`_.

Thanks!

.. _`pypet Google Group`: https://groups.google.com/forum/?hl=de#!forum/pypet


-------------
Documentation
-------------

.. toctree::
   :maxdepth: 2

   manual/manual_toc
   manual/misc_toc
   manual/code_toc


The documentation is also available for `download in PDF format`_.

.. _download in PDF format: https://media.readthedocs.org/pdf/pypet/latest/pypet.pdf


.. include:: contact_license.rst


-----
Index
-----

* :ref:`genindex`






