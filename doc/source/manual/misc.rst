=======================
Publication Information
=======================

---------------
Citation Policy
---------------

If you use *pypet* in your research,
it would be very kind of you to cite this in your amazing work.
A research article about *pypet* is currently in preparation which will be the basis
for citations in the future.
In the meantime you can cite the software as given below. For *bibtex* you can use:

::

    @misc{rmeyer2016,
        author = {Robert Meyer and Klaus Obermayer},
        year = {2016},
        title = {pypet: {T}he {P}ython {P}arameter {E}xploration {T}oolkit},
        note = {\url{http://pypet.readthedocs.org/}},
        institution = {Technische Universität Berlin, Neural Information Processing Group}
    }


Otherwise you can cite it as:

*   Robert Meyer and Klaus Obermayer. *pypet*: The Python Parameter
    Exploration Toolkit, 2016. http://pypet.readthedocs.org/.


--------------------------------
Brain Days and EuroPython Poster
--------------------------------

There is a poster about *pypet* that was shown at the `Berlin Brain Days 2013`_ and
the `EuroPython 2014`_.

.. image:: ../bbd_2013_poster/meyer_bbd_2013_small.png

Download:

* :download:`CLICK ME for PDF DOWNLOAD <../bbd_2013_poster/meyer_bbd_2013.pdf>`

* :download:`CLICK ME for PNG DOWNLOAD <../bbd_2013_poster/meyer_bbd_2013.png>`


.. _`Berlin Brain Days 2013`: http://www.neuroscience-berlin.de/bbd/

.. _`EuroPython 2014`: https://ep2014.europython.eu/en/

===============
Acknowledgments
===============

* Thanks to Robert Pröpper and Philipp Meier for answering all my python questions

    You might want to check out their SpykeViewer_ tool for visualization of
    MEA recordings and NEO_ data

*

    Thanks to Owen Mackwood for his SNEP toolbox which provided the initial ideas
    for this project

* Thanks to Mehmet Nevvaf Timur for his work on the SCOOP integration and the ``'NETQUEUE'`` feature

* Thanks to Henri Bunting for his work on the BRIAN2 subpackage

*

    Thanks to the `BCCN Berlin`_, the Research Training Group GRK 1589/1, and the
    `Neural Information Processing Group`_ for support

.. _SpykeViewer: https://github.com/rproepp/spykeviewer

.. _NEO: http://pythonhosted.org/neo/index.html

.. _`BCCN Berlin`: http://www.bccn-berlin.de/Home

.. _`Neural Information Processing Group`: http://www.ni.tu-berlin.de/

=====
Tests
=====

Tests can be found in `pypet/tests`.
Note that they involve heavy file IO and you need privileges
to write files to a temporary folder.
The test suites will make use of the ``tempfile.gettempdir()`` function to
create such a temporary folder.

Each test module can be run individually, for instance ``$ python trajectory_test.py``.

You can run **all** tests with ``$ python all_tests.py`` which can also be found under
`pypet/tests`.
You can pass additional arguments as ``$ python all_tests.py -k --folder=myfolder/``
with ``-k`` to keep the HDF5 and log files created by the tests
(if you want to inspect them, otherwise they will be deleted after the completed tests),
and ``--folder=`` to specify a folder where to store the HDF5 files instead of the temporary one.
If the folder cannot be created, the program defaults to ``tempfile.gettempdir()``.

If you do not want to browse to your installation folder, you can also download the
:download:`all_tests.py <../../../pypet/tests/all_tests.py>` script.

Running all tests can take up to 20 minutes and might temporarily take up to
1 GB of disk space. The test suite encompasses more than **1000** tests
and has a code coverage of about **90%**!

*pypet* is constantly tested with Python 2.6, 2.7, 3.3, 3.4, and 3.5 for **Linux** using
Travis-CI_. Testing for **Windows** platforms is performed via Appveyor_.
The source code is available at `github.com/SmokinCaterpillar/pypet`_.

.. _Travis-CI: https://travis-ci.org/SmokinCaterpillar/pypet

.. _Appveyor: https://ci.appveyor.com/project/SmokinCaterpillar/pypet

.. _`github.com/SmokinCaterpillar/pypet`: https://github.com/SmokinCaterpillar/pypet
