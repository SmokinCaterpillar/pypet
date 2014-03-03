======================
FAQs and Known Issues
======================

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
    issues with openBLAS and multiprocessing. To resolve this set the
    environment variable `OPENBLAS_NUM_THREADS=1`.


**Q:** Pypet crashes with the a TypeError: I do not know how to handle `XXXXXXXX
Name: XXXXXX, dtype: XXXXX`, its type is `<class 'pandas.core.series.Series'>`!?

    **A:** This is an issue with pandas 0.13.1 (and maybe 0.13.0). Either you install another
    version of pandas or do not try to store numpy arrays in ObjectTables, dictionaries and/or
    normal Parameters (use ArrayParameters instead). As far as I know, this issue is known to the
    pandas development team and they will include a fix in future pandas versions.
