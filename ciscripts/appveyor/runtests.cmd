:: Runs either all single core or all multicore tests
ECHO "------> TESTING <------"
cd ..\..\pypet\tests

IF "%EXAMPLES%"=="ON" (
    ECHO "#### Running the examples #####"
    python run_all_examples.py
    ECHO "#### Examples completed #####"
)
IF ERRORLEVEL 1 (
    ECHO "### Examples failed ###
    EXIT /b "%ERRORLEVEL%"
) ELSE (
    ECHO "### Examples successful ###
)

IF "%MULTIPROC%"=="ON" (
    ECHO "##### Running multiproc tests #####"
    python all_multi_core_tests.py
    ECHO "#### Multiproc completed #####"
)
IF ERRORLEVEL 1 (
ECHO "### Multiproc failed ###
    EXIT /b "%ERRORLEVEL%"
) ELSE (
    ECHO "### Multiproc successful ###
)

IF "%SINGLECORE%"=="ON" (
    ECHO "##### Running all single core tests #####"
    python all_single_core_tests.py
    ECHO "#### ESingle core completed #####"
)
IF ERRORLEVEL 1 (
    ECHO "### Single core failed ###
    EXIT /b "%ERRORLEVEL%"
) ELSE (
    ECHO "### Single core successful ###
)


