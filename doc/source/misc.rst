=======================
Publication Information
=======================

---------------------
Citation Policy
---------------------

If you use *pypet*, it would be very kind of you to cite this in your amazing research article.
For *bibtex* you can use:

::

    @misc{rmeyer2015,
        author = {Robert Meyer and Klaus Obermayer},
        year = {2015},
        title = {pypet: {T}he {P}ython {P}arameter {E}xploration {T}oolkit},
        note = {\url{http://pypet.readthedocs.org/}},
        institution = {Technische Universität Berlin, Neural Information Processing Group}
    }


Otherwise you can cite it as:

*   Robert Meyer and Klaus Obermayer. pypet: The Python Parameter
    Exploration Toolkit, 2015. http://pypet.readthedocs.org/.


---------------------------------
Brain Days and EuroPython Poster
---------------------------------

There is a poster about *pypet* that was shown at the `Berlin Brain Days 2013`_ and
the `EuroPython 2014`_.

.. image:: bbd_2013_poster/meyer_bbd_2013_small.png

Download:

* :download:`CLICK ME for PDF DOWNLOAD <./bbd_2013_poster/meyer_bbd_2013.pdf>`

* :download:`CLICK ME for PNG DOWNLOAD <./bbd_2013_poster/meyer_bbd_2013.png>`


.. _`Berlin Brain Days 2013`: http://www.neuroscience-berlin.de/bbd/

.. _`EuroPython 2014`: https://ep2014.europython.eu/en/

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
The tests suite will make use of the ``tempfile.gettempdir()`` function to
create such a temporary folder.

You can run all tests with ``$ python all_tests.py`` which can also be found under
`pypet/tests`.
You can pass additional arguments as ``$ python all_tests.py -k --folder=myfolder/`` with
``-k`` to keep the HDF5 files created by the tests (if you want to inspect them, otherwise
they will be deleted after the completed tests),
and ``--folder=`` to specify a folder where to store the HDF5 files instead of the temporary one.
If the folder cannot be created the program defaults to ``tempfile.gettempdir()``.

If you do not want to browse to your installation folder, you can also download the
:download:`all_tests.py <../../pypet/tests/all_tests.py>` script.

Running all tests can take up to 15 minutes and might temporarily take up to
8 GB of disk space. The test suite encompasses more than **500** tests
(including the BRIAN based tests) and has a code coverage of almost *90%*!