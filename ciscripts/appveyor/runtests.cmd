:: Runs a particular test suite
ECHO "------> TESTING <------"
cd ..\..\pypet\tests

IF "%EXAMPLES%"=="ON" (
    ECHO "#### Running the examples #####"
    python all_examples.py

    IF ERRORLEVEL 1 (
        ECHO "### Examples failed ###
        EXIT /b 1
    ) ELSE (
        ECHO "### Examples successful ###
    )
)


IF "%SINGLECORE%"=="ON" (
    ECHO "##### Running all single core tests #####"
    python all_single_core_tests.py

    IF ERRORLEVEL 1 (
        ECHO "### Single core failed ###
        EXIT /b "1
    ) ELSE (
        ECHO "### Single core successful ###
    )
)

IF "%SINGLECORE%"=="1" (
    ECHO "##### Running single core test suite 1 #####"
    python all_single_core_tests.py --suite=1

    IF ERRORLEVEL 1 (
        ECHO "### Single core failed ###
        EXIT /b "1
    ) ELSE (
        ECHO "### Single core successful ###
    )
)

IF "%SINGLECORE%"=="2" (
    ECHO "##### Running single core test suite 2 #####"
    python all_single_core_tests.py --suite=2

    IF ERRORLEVEL 1 (
        ECHO "### Single core failed ###
        EXIT /b "1
    ) ELSE (
        ECHO "### Single core successful ###
    )
)

IF "%SINGLECORE%"=="3" (
    ECHO "##### Running single core test suite 3 #####"
    python all_single_core_tests.py --suite=3

    IF ERRORLEVEL 1 (
        ECHO "### Single core failed ###
        EXIT /b "1
    ) ELSE (
        ECHO "### Single core successful ###
    )
)


IF "%MULTIPROC%"=="ON" (
    ECHO "##### Running multiproc tests #####"
    python -m scoop -n 2 all_multi_core_tests.py

    IF ERRORLEVEL 1 (
        ECHO "### Multiproc failed ###
        EXIT /b 1
    ) ELSE (
        ECHO "### Multiproc successful ###
    )
)

IF "%MULTIPROC%"=="1" (
    ECHO "##### Running multiproc test suite 1 #####"
    python -m scoop -n 2 all_multi_core_tests.py --suite=1

    IF ERRORLEVEL 1 (
        ECHO "### Multiproc failed ###
        EXIT /b 1
    ) ELSE (
        ECHO "### Multiproc successful ###
    )
)

IF "%MULTIPROC%"=="2" (
    ECHO "##### Running multiproc test suite 2 #####"
    python -m scoop -n 2 all_multi_core_tests.py --suite=2

    IF ERRORLEVEL 1 (
        ECHO "### Multiproc failed ###
        EXIT /b 1
    ) ELSE (
        ECHO "### Multiproc successful ###
    )
)

IF "%MULTIPROC%"=="3" (
    ECHO "##### Running multiproc test suite 2 #####"
    python -m scoop -n 2 all_multi_core_tests.py --suite=3

    IF ERRORLEVEL 1 (
        ECHO "### Multiproc failed ###
        EXIT /b 1
    ) ELSE (
        ECHO "### Multiproc successful ###
    )
)

IF "%MULTIPROC%"=="4" (
    ECHO "##### Running multiproc test suite 2 #####"
    python -m scoop -n 2 all_multi_core_tests.py --suite=4

    IF ERRORLEVEL 1 (
        ECHO "### Multiproc failed ###
        EXIT /b 1
    ) ELSE (
        ECHO "### Multiproc successful ###
    )
)



