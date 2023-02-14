echo "+++++++++++ Installing libraries +++++++++++++"
sudo apt-get install gfortran libopenblas-dev liblapack-dev libhdf5-serial-dev
echo "+++++++++++ Installing Stuff for Python $PYTHON_VERSION +++++++++++"
conda install pip numpy scipy numexpr cython pandas pytables
echo "+++++++ Conda Info and activate ++++++"
conda info -a
echo "+++++++++++ Installing Coveralls if coverage +++++++++++"
if [[ $COVERAGE == ON ]]; then pip install coveralls; fi
echo "+++++++++++ Installing Brian2 +++++++++++"
pip install brian2
echo "+++++++++++ Installing psutil +++++++++++"
pip install psutil
echo "+++++++++++ Installing dill ++++++++++++"
pip install dill
echo "+++++++++++ Installing GitPython and Sumatra if needed ++++++++++++"
if [[ $GIT_TEST == ON ]]; then chmod +x ./.github/scripts/install_gitpython.sh; ./.github/scripts/install_gitpython.sh; fi
echo "+++++++++++ Installing matplotlib and deap if needed ++++++++++++"
if [[ $EXAMPLES == ON ]]; then conda install matplotlib; pip install deap; fi
echo "++++++++++++ Installing SCOOP  +++++++++++++++++++++++++"
pip install scoop
echo "+++++++++++ Installing PYPET unless coverage +++++++++++"
python setup.py install -e
echo "+++++++++++ FINISHED INSTALL +++++++++++"
pip freeze