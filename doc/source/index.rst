.. pypet documentation master file, created by
   sphinx-quickstart on Wed Sep  4 12:12:59 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

==================================
Welcome to pypet's documentation!
==================================

The new python parameter exploration toolkit:
*pypet* manages exploration of the parameter space
of any numerical simulation in python,
thereby storing your data into HDF5_ files for you.
Moreover, *pypet* offers a new data container which
lets you access all your parameters and results
from a single source. Data I/O of your simulations and
analyses becomes a piece of cake!

Latest version: `0.1b.8`_

.. _`0.1b.8`: https://pypi.python.org/pypi/pypet

.. _HDF5: http://www.hdfgroup.org/HDF5/

===========================
IMPORTANT!
===========================

The program is currently under development,
please keep that in mind and use it very carefully.

Before publishing the official *0.1.0* release I will integrate *pypet* first in my own research
project. Thus, I have a more profound testing environment than only using
unittests. Accordingly, you still have to deal with the naming *0.1b.X* for a little while.
However, unless it is really, really, really necessary I do not plan to change the API anymore.
So feel free to use this beta version and feel free to give feedback,
suggestions, and report bugs. Use **github** (https://github.com/SmokinCaterpillar/pypet) issues or
write to the `pypet Google Group`_ :-)

Thanks!

.. _`pypet Google Group`: https://groups.google.com/forum/?hl=de#!forum/pypet

============================
Requirements
============================

Python 2.6, 2.7, 3.3, 3.4 [#pythonversion]_

* tables >= 2.3.1

* pandas >= 0.12.0 [#pandasversion]_

* numpy >= 1.6.1

* scipy >= 0.9.0

If you use Python 2.6 you also need

* ordereddict_ >= 1.1

.. _ordereddict: https://pypi.python.org/pypi/ordereddict

For git integration you additionally need

* GitPython_ >= 0.3.1 [#gitpythonversion]_

.. _GitPython: http://pythonhosted.org/GitPython/0.3.1/index.html

To utilize the cap feature for :ref:`more-on-multiprocessing` you need

* psutil_ >= 2.0.0

.. _psutil: http://pythonhosted.org/psutil/

To utilize the continuing of crashed trajectories you need

* dill_ >= 0.2.1

.. _dill: https://pypi.python.org/pypi/dill

Automatic sumatra records are supported for

* Sumatra_ >= 0.6.0

.. _Sumatra: http://neuralensemble.org/sumatra/

.. rubric:: Footnotes

.. [#pythonversion]

    *pypet* might also work under python 3.0-3.2 but has not been tested.

.. [#pandasversion]

    Preferably use pandas 0.14.1 or 0.12.0 since there are some
    upcasting issues with version 0.13.x (see https://github.com/pydata/pandas/issues/6526/).
    *pypet* works under 0.13.x but not all features are fully supported.
    For instance, these upcasting issues may prevent you from storing
    Trajectories containing ArrayParameters to disk.
    These unwanted upcastings did not happen in previous pandas versions and will be, or more
    precisely, have already been removed in the next pandas version.
    So please up or downgrade your pandas distribution if your current installation is 0.13.x.

.. [#gitpythonversion]

    Keep in mind that GitPython currently does not support python 3.

==========================
ToC
==========================

.. toctree::
   :maxdepth: 2

   introduction
   tutorial
   cookbook
   examples
   faqs
   code


=====================
Publications
=====================

..
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
8 GB of disk space. The test suite encompasses more than **400** tests
(including the BRIAN based tests) and has a code coverage of about *90%*!

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






