.. P37 documentation master file, created by
   sphinx-quickstart on Wed Sep  4 12:12:59 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

==================================
Welcome to pypet's documentation!
==================================

The new python parameter exploration toolbox. *pypet* manages exploration of the parameter space and
data storage for you. Currently supported storage is HDF5!

Contents:

.. toctree::
   :maxdepth: 2

   introduction
   cookbook
   examples
   code

============================
Requirements
============================

pandas >= 0.12.0
numpy >= 1.5.0
tables >= 3.0.0

Before the official release of version 0.1.0
I will include support for PyTables 2.X.
So you won't have the hassle with manually updating your
tables package!

--------------------------------
Tests
--------------------------------

Test can be found in pypet.tests.
Note that they involve heavy file IO and it might not be the case
that you have privileges on your system to write files to the particular folder.
So I would recommend either downloading pypet from github
and run the tests in your IDE.
Or you still might want to wait for some time for the official 0.1.0
release because I am trying to work around that in the meantime.

=====================
Contact
=====================

Robert Meyer

robert.meyer (at) ni.tu-berlin.de

Marchstr. 23

MAR 5.046

D-10587 Berlin

===================
Acknowledgments
===================

* Thanks to Robert Pröpper and Philipp Meier for answering all my Python Questions.

    You might wanna check out their SpykeViewer_ tool for visualization of
    MEA recordings and NEO_ data

*

    Thanks to Owen Mackwood for his SNEP toolbox which provided the initial ideas
    for this project

*

    Thanks to the `BCCN Berlin`_, the Research Training Group GRK 1589/1, and the
    `Neural Information Processing Group`_ for support

.. _SpykeViewer: https://github.com/rproepp/spykeviewer

.. _NEO: http://pythonhosted.org/neo/index.html

.. _`BCCN Berlin`: http://www.bccn-berlin.de/Home

.. _`Neural Information Processing Group`: http://www.ni.tu-berlin.de/



===================
Indices and Tables
===================

* :ref:`genindex`
* :ref:`search`

===================
License
===================

.. literalinclude:: ../../LICENSE

