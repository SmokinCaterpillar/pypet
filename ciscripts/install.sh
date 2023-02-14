echo "+++++++++++ Installing Stuff for Python $PYTHON_VERSION +++++++++++"
conda create -q -n test-environment python=$PYTHON_VERSION pip numpy scipy numexpr cython pandas pytables
conda activate test-environment
pip freeze
echo "+++++++++++ Installing Coveralls if coverage +++++++++++"
if [[ $COVERAGE == ON ]]; then pip install coveralls; fi
echo "+++++++++++ Installing Brian2 +++++++++++"
pip install brian2
echo "+++++++++++ Installing psutil +++++++++++"
pip install psutil
echo "+++++++++++ Installing dill ++++++++++++"
pip install dill
echo "+++++++++++ Installing GitPython and Sumatra if needed ++++++++++++"
if [[ $GIT_TEST == ON ]]; then chmod +x ./install_gitpython.sh; ./install_gitpython.sh; fi
echo "+++++++++++ Installing matplotlib and deap if needed ++++++++++++"
if [[ $EXAMPLES == ON ]]; then conda install matplotlib; pip install deap; fi
echo "++++++++++++ Installing SCOOP  +++++++++++++++++++++++++"
pip install scoop
echo "+++++++++++ Installing PYPET unless coverage +++++++++++"
if [[ $COVERAGE == OFF ]]; then python setup.py install; fi
echo "+++++++++++ FINISHED INSTALL +++++++++++"