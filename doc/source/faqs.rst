======================
FAQs and Known Issues
======================

**Q:** My program does not terminate
(i.e. it does not crash but runs forever)
when I use *pypet* in multiprocessing mode
in combination with *matplotlib* and *savefig*!?

    **A:** *Matlpotlib* uses *numpy* for linear algebra operations,
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
