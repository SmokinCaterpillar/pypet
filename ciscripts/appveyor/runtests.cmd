:: Runs either all single core or all multicore tests
ECHO "------> TESTING <------"
cd ..\..\pypet\tests

IF "%EXAMPLES%"=="ON" (
    ECHO "#### Running the examples #####"
    python run_all_examples.py
    ECHO "#### Examples completed #####"
)
IF NOT "%errorlevel%" == 0 (
    ECHO "### Examples failed ###
    EXIT /b "%errorlevel%"
) ELSE (
    ECHO "### Examples successful ###
)

IF "%MULTIPROC%"=="ON" (
    ECHO "##### Running multiproc tests #####"
    python all_multi_core_tests.py
    ECHO "#### Multiproc completed #####"
)
IF NOT "%errorlevel%" == 0 (
ECHO "### Multiproc failed ###
    EXIT /b "%errorlevel%"
) ELSE (
    ECHO "### Multiproc successful ###
)

IF "%SINGLECORE%"=="ON" (
    ECHO "##### Running all single core tests #####"
    python all_single_core_tests.py
    ECHO "#### ESingle core completed #####"
)
IF NOT "%errorlevel%" == 0 (
    ECHO "### Single core failed ###
    EXIT /b "%errorlevel%"
) ELSE (
    ECHO "### Single core successful ###
)


