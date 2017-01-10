#!/bin/bash

echo "Converting conda package..."
conda convert --platform all $HOME/miniconda3/conda-bld/linux-64/gwf-*.tar.bz2 --output-dir conda-bld/

echo "Deploying to Anaconda.org..."
anaconda -t $ANACONDA_TOKEN upload conda-bld/**/gwf-*.tar.bz2

echo "Successfully deployed to Anaconda.org."
exit 0