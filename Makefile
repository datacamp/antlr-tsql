.PHONY: clean

all: clean test

build:
	antlr4 -Dlanguage=Python3 -visitor antlr_tsql/tsql.g4

clean:
	find . \( -name \*.pyc -o -name \*.pyo -o -name __pycache__ \) -prune -exec rm -rf {} +
	rm -rf antlr_tsql.egg-info

test: clean
	pytest

deploy: build
	travis/setup-git.sh
	travis/deploy-builds.sh
