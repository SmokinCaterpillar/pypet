:: Runs either all single core or all multicore tests
ECHO "------> TESTING <------"
cd ..\..\pypet\tests

IF "%EXAMPLES%"=="ON" (
    ECHO "#### Running the examples #####"
    python run_all_examples.py
)
IF ERRORLEVEL 1 (
    ECHO "### Examples failed ###
    EXIT /b 1
) ELSE (
    ECHO "### Examples successful ###
)

IF "%MULTIPROC%"=="ON" (
    ECHO "##### Running multiproc tests #####"
    python all_multi_core_tests.py
)
IF ERRORLEVEL 1 (
    ECHO "### Multiproc failed ###
    EXIT /b 1
) ELSE (
    ECHO "### Multiproc successful ###
)

IF "%SINGLECORE%"=="ON" (
    ECHO "##### Running all single core tests #####"
    python all_single_core_tests.py
)
IF ERRORLEVEL 1 (
    ECHO "### Single core failed ###
    EXIT /b "1
) ELSE (
    ECHO "### Single core successful ###
)


