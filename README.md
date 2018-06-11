# antlr-tsql

[![Build Status](https://travis-ci.org/datacamp/antlr-tsql.svg?branch=master)](https://travis-ci.org/datacamp/antlr-tsql)
[![PyPI version](https://badge.fury.io/py/antlr-tsql.svg)](https://badge.fury.io/py/antlr-tsql)

## Development

ANTLR requires Java, so we suggest you use Docker when building grammars. The `Makefile` contains directives to clean, build, test and deploy the ANTLR grammar. It does not run Docker itself, so run `make` inside Docker.

### Build the grammar

```
docker build -t antlr_tsql .
docker run -it -v ${PWD}:/usr/src/app antlr_tsql make build
```

### Develop

```
docker run -it -v ${PWD}:/usr/src/app antlr_tsql /bin/bash

make buildpy         # Build the grammar
make test            # Run the tests (does not automatically build)

# parse SQL with built grammar
python3
from antlr_tsql import ast
ast.parse("SELECT a from b")
```

## Travis deployment

- Builds the Docker image.
- Runs the Docker image to build the grammar, run the unit tests.
- Commits the generated grammar files to the `builds` (for `master`) and `builds-dev` (for `dev`) branches.
- Builds the grammar and deploys the resulting python and js files to PyPi when a new release is made.%

