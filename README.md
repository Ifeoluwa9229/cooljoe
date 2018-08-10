# Survive

[![PyPI version](https://badge.fury.io/py/survive.svg)](https://badge.fury.io/py/survive)
[![Documentation Status](https://readthedocs.org/projects/survive-python/badge/?version=latest)](https://survive-python.readthedocs.io/?badge=latest)

Survival analysis in Python.

## Installation

The latest version of Survive can be installed directly after cloning from GitHub:

    git clone https://github.com/artemmavrin/survive.git
    cd survive
    make install

Moreover, Survive is on the [Python Package Index (PyPI)](https://pypi.org/project/survive/), so a recent version of it can be installed with the `pip` utility:

    pip install survive

## Dependencies

* [NumPy](http://www.numpy.org)
* [SciPy](https://www.scipy.org)
* [pandas](https://pandas.pydata.org)
* [Matplotlib](https://matplotlib.org)

## Case Studies

* [Leukemia remission time dataset.](https://survive-python.readthedocs.io/examples/Leukemia_Remission_Time_Dataset.html)
  A small dataset (42 total observations) separated into two groups with heavy right-censoring in one and none in the other.
* [Channing House dataset.](https://survive-python.readthedocs.io/examples/Channing_House_Dataset.html)
  A slightly larger dataset (462 total observations) separated into two groups with right-censoring and left truncation in both.


## Documentation

The complete API Reference for Survive is available on [Read the Docs](https://survive-python.readthedocs.io/api.html).
