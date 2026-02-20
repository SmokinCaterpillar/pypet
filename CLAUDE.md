# CLAUDE.md - pypet

## Project Overview

pypet (Python Parameter Exploration Toolkit) is a library for managing numerical simulations with easy parameter exploration and HDF5 data storage. Parameters and results are organized in a tree structure called a **Trajectory**.

- **Version**: 0.6.1
- **License**: BSD
- **Author**: Robert Meyer
- **Python**: `>=3.6` (classifiers list 3.6-3.8; 3.6 and 3.7 are EOL)
- **Repo**: https://github.com/SmokinCaterpillar/pypet

## Project Structure

```
pypet/                  # Main package
  environment.py        # Environment: top-level experiment runner
  trajectory.py         # Trajectory: tree container for parameters & results
  parameter.py          # Parameter types (Parameter, ArrayParameter, SparseParameter, etc.)
  naturalnaming.py      # Natural naming / attribute access on tree nodes
  storageservice.py     # HDF5 storage via PyTables
  pypetconstants.py     # Constants and wrap modes
  pypetlogging.py       # Logging utilities, HasLogger mixin
  pypetexceptions.py    # Custom exception classes
  annotations.py        # WithAnnotations mixin
  slots.py              # HasSlots / MetaSlotMachine (memory-efficient __slots__ support)
  shareddata.py         # Shared data for multiprocessing
  brian2/               # Brian2 neural simulator integration
  utils/                # Helper functions, decorators, comparisons, explore
  tests/                # Test suite
    unittests/          # Unit tests (including brian2tests/)
    integration/        # Integration tests (including brian2tests/)
    testutils/          # Test infrastructure (data.py, ioutils.py)
    profiling/          # Performance profiling tests
examples/               # Example scripts
doc/                    # Sphinx documentation
```

## Architecture & Patterns

### Trajectory Tree

The core data structure is a tree with four main branches:
- **config** - configuration parameters (not explored)
- **parameters** - parameters that can be explored across runs
- **derived_parameters** - computed from parameters
- **results** - simulation outputs

### Naming Conventions

- `f_*` prefix: public methods (e.g., `f_add_parameter`, `f_store`)
- `v_*` prefix: properties (e.g., `v_name`, `v_full_name`)
- These prefixes avoid name collisions with the natural naming tree access

### Mixin Hierarchy

- `HasSlots` (`slots.py`) - metaclass-based `__slots__` management
- `HasLogger` (`pypetlogging.py`) - logging mixin (inherits HasSlots)
- `WithAnnotations` (`annotations.py`) - annotation support (inherits HasLogger)

### Storage

HDF5 storage via PyTables with multiple serialization protocols. The `storageservice.py` module handles loading/storing trajectory trees to HDF5 files.

### Multiprocessing Wrap Modes

Defined in `pypetconstants.py`:
- `QUEUE` / `PIPE` / `LOCK` / `LOCAL` - standard multiprocessing modes
- `NETLOCK` / `NETQUEUE` - network-based (ZMQ) for distributed runs

## Dependencies

**Core** (in setup.py `install_requires`):
- `tables` (PyTables - HDF5 interface)
- `pandas`, `numpy`, `scipy`

**Optional**:
- `scoop` - distributed computing
- `GitPython` - git integration for versioning runs
- `psutil` - process monitoring
- `dill` - enhanced pickling
- `brian2` - neural simulator integration
- `zmq` (pyzmq) - network multiprocessing modes
- `sumatra` - experiment tracking

**System**: HDF5 dev libraries (required by PyTables)

## Development Commands

```bash
# Install
python setup.py install

# Run single-core tests
python ./pypet/tests/all_single_core_tests.py

# Run all tests (including multiprocessing)
python ./pypet/tests/all_tests.py

# Build docs
cd doc && make html
```

## Testing

- **Framework**: unittest
- **Test discovery**: `LambdaTestDiscoverer` (`pypet/tests/testutils/ioutils.py`) - tag-based filtering using lambda predicates
- **Tags**: `unittest`, `integration`, `multiproc`, `hdf5`, `hdf5_settings`, `merge`, `links`
- **Base class**: `TrajectoryComparator(unittest.TestCase)` in `pypet/tests/testutils/data.py`
- **CI**: GitHub Actions (`tests.yml`) - Python 3.8 (multiproc suite) and 3.10 (singlecore suite), conda-based

## Modernization Notes

Areas needing updates for modern Python:
- **Build system**: `setup.py` with distutils fallback -> `pyproject.toml`
- **Python version**: `python_requires='>=3.6'` but 3.6/3.7 are EOL; classifiers only go to 3.8
- **Python 2 remnants**: `FileNotFoundError = IOError` compat stub in `pypetlogging.py:5-9`
- **CI**: Uses `setup-miniconda@v2`, `actions/checkout@v3` (outdated)
- **No type annotations** anywhere in the codebase
- **No pre-commit hooks**, no modern formatter (black/ruff), no linter config
- **No pyproject.toml** - all config in `setup.py`
- **`object` base classes**: e.g., `HasSlots(object, metaclass=...)` - unnecessary in Python 3
- **m2r** for README conversion - deprecated, use `m2r2` or just set `long_description_content_type`
