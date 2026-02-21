#!/bin/bash
set -e # Exit on any error

echo "+++++++++++ Installing libraries +++++++++++++"
sudo apt-get install -y gfortran libopenblas-dev liblapack-dev libhdf5-serial-dev
echo "+++++++++++ Installing Stuff for Python $PYTHON_VERSION +++++++++++"
if [[ ${DEPS:-latest} == "minimum" ]]; then
    conda install -y pip numexpr cython \
        numpy=1.26.0 scipy=1.12.0 pandas=2.1.0 pytables=3.9.0
else
    conda install -y pip numpy scipy numexpr cython pandas pytables
fi
echo "+++++++ Conda Info and activate ++++++"
conda info -a
echo "+++++++++++ Installing Coveralls if coverage +++++++++++"
if [[ $COVERAGE == ON ]]; then pip install coveralls; fi
echo "+++++++++++ Installing Brian2 +++++++++++"
pip install brian2
echo "+++++++++++ Installing psutil +++++++++++"
echo "+++++++++++ Installing dill ++++++++++++"
if [[ ${DEPS:-latest} == "minimum" ]]; then
    pip install psutil==5.9.6 dill==0.3.7
else
    pip install psutil dill
fi
echo "+++++++++++ Installing GitPython and Sumatra if needed ++++++++++++"
if [[ $GIT_TEST == ON ]]; then chmod +x ./.github/scripts/install_gitpython.sh; ./.github/scripts/install_gitpython.sh; fi
echo "+++++++++++ Installing matplotlib and deap if needed ++++++++++++"
if [[ $EXAMPLES == ON ]]; then conda install -y matplotlib; pip install deap; fi
echo "++++++++++++ Installing SCOOP  +++++++++++++++++++++++++"
pip install scoop
echo "+++++++++++ Installing PYPET +++++++++++"
if [[ $COVERAGE == OFF ]]; then pip install -e .; else export PATH="./:$PATH"; fi
echo "+++++++++++ FINISHED INSTALL +++++++++++"
pip freeze
