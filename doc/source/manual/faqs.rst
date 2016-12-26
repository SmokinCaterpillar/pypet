=====================
FAQs and Known Issues
=====================

--------------------
Tools and Extensions
--------------------

**Q:** Does *pypet* support Python 2.6 and 2.7?

    **A:** Python 2.6 and 2.7 are no longer supported. Still if you
    need *pypet* for these versions check out the legacy `0.3.0`_ package.
    You can pip install it via ``pip install pypet==0.3.0``.


.. _0.3.0: https://pypi.python.org/pypi/pypet/0.3.0


**Q:** How can I open and inspect an HDF5 file created by *pypet*?

    **A:** For inspection I mostly use these two tools: HDFview_ and ViTables_.

.. _HDFview: http://www.hdfgroup.org/products/java/hdfview/

.. _ViTables: http://vitables.org/


**Q:** Can I use *pypet* on my computing cluster or can I distribute *pypet* runs among
different servers?

    **A:** Yes, you can, either by combining *pypet* with SCOOP_ or with
    `SAGA Python`_ (see also :ref:`pypet-and-scoop`). Examples are provided here:
    :ref:`example-21` and :ref:`example-22`.


.. _SCOOP: https://scoop.readthedocs.org/

.. _SAGA Python: http://saga-python.readthedocs.org/


**Q:** I not only need to explore but also tune parameters. Are there any optimization methods
available in *pypet*?

    **A:** Not directly, but you can easily combine *pypet* with the evolutionary optimization
    toolkit DEAP_. :ref:`example-19` shows you how.

.. _DEAP: http://deap.readthedocs.org/


------------------
Performance Issues
------------------

**Q:** Exploring many runs (10k+) *pypet* becomes incredibly slow when it comes to
loading and storing data!?

    **A:** HDF5 has a hard time managing nodes with many children. To avoid this
    simply group your result into buckets using the `'$set'` wildcard. See also the
    :ref:`optimization-tips`.


**Q:** *pypet* produces enormously large files of several Gigabytes despite them containing
almost no data!?

    **A:** Your HDF5 version is too old (most likely you are using 1.8.5). Please update
    to 1.8.9 or newer.


--------------
Infinite Loops
--------------

**Q:** My program does not terminate
(i.e. it does not crash but runs forever)
when I use *pypet* in multiprocessing mode
in combination with *matplotlib* and *savefig*!?

    **A:** *Matplotlib* uses *numpy* for linear algebra operations,
    these operations are often necessary when plotting.
    So, to solve the issues take a look at the next question.


**Q:** My program does not terminate
(i.e. it does not crash but runs forever)
when I use *pypet* in multiprocessing mode
in combination with *numpy* and *linalg.inv*
or some similar function!?

    **A:** Numpy uses openBLAS (http://www.openblas.net/) to
    solve linear algebra operations. Yet, there are many
    issues with openBLAS and Python multiprocessing. To resolve this set the
    environment variables ``OPENBLAS_NUM_THREADS=1`` and ``OMP_NUM_THREADS=1``.


------------------
Crashes and Errors
------------------

**Q:**  GitPython does not work. If I specify my repository ``git_repository='./myrepo'``,
pypet crashes with an ``AttributeError: 'Repo' object has no attribute 'index'``.
What should I do?

    **A:** You probably have an older version of GitPython (likely 0.1.7), install a newer one.
    If ``pip install GitPython`` still downloads the old version, try ``pip install --pre GitPython``
    or if you simply want to upgrade, use ``pip install --upgrade --pre GitPython``.

**Q:**  My program crashes with
``TypeError: [..]  dtype: float64 its type is <class 'pandas.core.series.Series'>.``!?

    **A:**  You are using pandas version ``0.13.x``.
    Unfortunately, pandas performs some unwanted upcasting that
    cannot be handled by *pypet* (see https://github.com/pydata/pandas/issues/6526/).
    This unwanted upcasting has already been removed in the next pandas version.
    So upgrade to ``0.14.1`` or newer.

**Q:** My program crashes if I try to store a Trajectory containing an ArrayParameter!?

    **A:** Look at the previous answer,
    you are using pandas ``0.13.x``, please upgrade your
    pandas package to at least ``0.14.1``.

**Q:** My program crashes with a ``ValueError: unknown type: 'object'``!?

    **A:** Look at the previous answer,
    you are using pandas ``0.13.x``, please upgrade your
    pandas package to at least ``0.14.1``.


--------------
Other Problems
--------------

**Q:**  If I create and environment in an *IPython* console everything becomes gibberish!?

    **A:** Pypet will redirect ``stdout`` to files. Unfortunately, this messes with
    the *IPython* console. To avoid this simply disable logging of this stream setting the
    ``log_stdout`` option to ``False``: ``env = Environment( ..., log_stdout=False, ...)``.


**Q:** I have large data sets that are not stored if I use multiprocessing and the lock wrapping!?

    **A:** Probably, you use an older HDF5 version (``< 1.8.7``) that does not allow
    simultaneous openings of a single HDF5 file. Either install a newer version or switch to
    queue wrapping.


**Q:** I already have a rather evolved simulator can I integrate it with pypet or do I need to
start from scratch?

   **A:** No, of course you don't neet to start from scratch. T
   here are ways to integrate or wrap *pypet* around
   your project. Example :ref:`example-17` shows you how to do that or
   take a look at section :ref:`wrap-project`.