.. P37 documentation master file, created by
   sphinx-quickstart on Wed Sep  4 12:12:59 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

==================================
Welcome to pypet's documentation!
==================================

The new python parameter exploration toolbox. *pypet* manages exploration of the parameter space
and data storage into HDF5_ files for you.

.. _HDF5: http://www.hdfgroup.org/HDF5/

===========================
IMPORTANT!
===========================


The current program is currently still under development,
please treat it as such and use very carefully.


Note that there still might be changes to the API. Yet, i will try to keep it as stable as possible.

I decided to integrate pypet first in my own research project before publishing the
official 0.1.0 release. Thus, I have a more profound testing environment than only using
unittests. The official 0.1.0 release is postponed to beginning of next year or end of
this year.
However, feel free to use this beta version and feel free to give feedback,
suggestions, and report bugs. Either write my an email (robert.meyer (at) ni.tu-berlin.de)
or preferably use github (https://github.com/SmokinCaterpillar/pypet) issues :-)

Thanks!

============================
Requirements
============================

Python 2.6 or 2.7

* tables >= 2.3.1

* pandas >= 0.12.0

* numpy >= 1.6.1

* scipy >= 0.9.0

For git integration you additionally need

* GitPython


==========================
ToC
==========================

Contents:

.. toctree::
   :maxdepth: 2

   introduction
   cookbook
   examples
   code




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

====================
Tests
====================

Tests can be found in `pypet/tests`.
Note that they involve heavy file IO and it might not be the case
that you have privileges on your system to write files to a temporary folder.
The tests suite will make use of the `tempfile.gettempdir()` function to
access a temporary folder.

You can run all tests with `$ python all_tests.py` which can also be found under
`pypet/tests`.
You can pass additional arguments as `$ python all_tests.py -k --folder=myfolder/` with
`-k` to keep the hdf5 files created by the tests (if you want to inspect them, otherwise
they will be deleted after the completed tests)
and `--folder=` to specify a folder where to store the hdf5 files instead of the temporary one.
If the folder cannot be created the program defaults to `tempfile.gettempdir()`.

If you do not want to browse to your installation folder, you can also download
:download:`all_tests.py <../../pypet/tests/all_tests.py>`.

===================
Indices and Tables
===================

* :ref:`genindex`
* :ref:`search`

===================
License
===================

.. literalinclude:: ../../LICENSE

