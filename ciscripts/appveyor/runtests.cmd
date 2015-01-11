:: Runs either all single core or all multicore tests
ECHO "------> TESTING <------"
cd ..\..\pypet\tests

IF "%EXAMPLES%"=="ON" (
    ECHO "#### Running the examples #####"
    python run_all_examples.py
)
IF NOT "%errorlevel%" == 0 (
    EXIT /b "%errorlevel%"
)

IF "%MULTIPROC%"=="ON" (
    ECHO "##### Running multiproc tests #####"
    python all_multi_core_tests.py
)
IF NOT "%errorlevel%" == 0 (
    EXIT /b "%errorlevel%"
)

IF "%SINGLECORE%"=="ON" (
    ECHO "##### Running all single core tests #####"
    python all_single_core_tests.py
)
IF NOT "%errorlevel%" == 0 (
    EXIT /b "%errorlevel%"
)


