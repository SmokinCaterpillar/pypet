:: Runs either all single core or all multicore tests

IF "%MULTIPROC%"=="ON" (
    ECHO "##### Running multiproc tests #####"
    cd ..\..\tests
    python all_multi_core_tests.py
) ELSE (
    ECHO "##### Running all single core tests #####"
    cd ..\..\tests
    python all_single_core_tests.py
)