JS_DIR=antlr_tsql/js

.PHONY: clean

all: clean test

build:
	antlr4 -Dlanguage=Python3 -visitor antlr_tsql/tsql.g4
	antlr4 -Dlanguage=JavaScript -o $(JS_DIR) antlr_tsql/tsql.g4 && mv $(JS_DIR)/antlr_tsql/* $(JS_DIR)

clean:
	find . \( -name \*.pyc -o -name \*.pyo -o -name __pycache__ \) -prune -exec rm -rf {} +
	rm -rf antlr_tsql.egg-info

test: clean
	pytest

deploy: build
	travis/setup-git.sh
	travis/deploy-builds.sh
