.. P37 documentation master file, created by
   sphinx-quickstart on Wed Sep  4 12:12:59 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

==================================
Welcome to pypet's documentation!
==================================

The new python parameter exploration toolkit: *pypet* manages exploration of the parameter space
and data storage into HDF5_ files for you.

.. _HDF5: http://www.hdfgroup.org/HDF5/

===========================
IMPORTANT!
===========================

The program is currently under development,
please keep that in mind and use it very carefully.

Before publishing the official *0.1.0* release I will integrate *pypet* first in my own research
project. Thus, I have a more profound testing environment than only using
unittests. Accordingly, you still have to deal with the naming *0.1b.X* probably until beginning
of next year.
However, unless it is really, really, really necessary I do not plan to change the API anymore.
So feel free to use this beta version and feel free to give feedback,
suggestions, and report bugs. Either write my an email (robert.meyer (at) ni.tu-berlin.de)
or preferably use **github** (https://github.com/SmokinCaterpillar/pypet) issues :-)

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

* GitPython_

.. _GitPython: http://pythonhosted.org/GitPython/0.3.1/index.html

==========================
ToC
==========================

Contents:

.. toctree::
   :maxdepth: 2

   introduction
   cookbook
   examples
   faqs
   code


=====================
Publications
=====================


.. _citation_policy:

---------------------
Citation Policy
---------------------

If you use *pypet*, it would be very kind of you to cite this in your amazing research article.
For *bibtex* you can use:

::

    @misc{rmeyer2014,
        author = {Robert Meyer and Klaus Obermayer},
        year = {2014},
        title = {pypet: {T}he {P}ython {P}arameter {E}xploration {T}oolkit},
        note = {\url{http://pypet.readthedocs.org/}},
        institution = {Technische Universität Berlin, Neural Information Processing Group}
    }


Otherwise you can cite it as:

*   Robert Meyer and Klaus Obermayer. pypet: The Python Parameter
    Exploration Toolkit, 2014. http://pypet.readthedocs.org/.


---------------------
BBD2013 Poster
---------------------

There is a poster about *pypet* that was shown at the `Berlin Brain Days 2013`_.

.. image:: bbd_2013_poster/meyer_bbd_2013_small.png

Download:

* :download:`CLICK ME for PDF DOWNLOAD <./bbd_2013_poster/meyer_bbd_2013.pdf>`

* :download:`CLICK ME for PNG DOWNLOAD <./bbd_2013_poster/meyer_bbd_2013.png>`


.. _`Berlin Brain Days 2013`: http://www.neuroscience-berlin.de/bbd/


===================
Acknowledgments
===================

* Thanks to Robert Pröpper and Philipp Meier for answering all my python questions

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
Note that they involve heavy file IO and you need privileges
to write files to a temporary folder.
The tests suite will make use of the `tempfile.gettempdir()` function to
create such a temporary folder.

You can run all tests with `$ python all_tests.py` which can also be found under
`pypet/tests`.
You can pass additional arguments as `$ python all_tests.py -k --folder=myfolder/` with
`-k` to keep the HDF5 files created by the tests (if you want to inspect them, otherwise
they will be deleted after the completed tests),
and `--folder=` to specify a folder where to store the HDF5 files instead of the temporary one.
If the folder cannot be created the program defaults to `tempfile.gettempdir()`.

If you do not want to browse to your installation folder, you can also download the
:download:`all_tests.py <../../pypet/tests/all_tests.py>` script.

Running all tests can take up to 15 minutes. The test suite encompasses more than **300** tests
(including the BRIAN based tests) and has a code coverage of more than **90%**!

=====================
Contact
=====================

Robert Meyer

robert.meyer (at) ni.tu-berlin.de

Marchstr. 23

MAR 5.046

D-10587 Berlin

===================
Indices
===================

* :ref:`genindex`


===================
License
===================

.. literalinclude:: ../../LICENSE

