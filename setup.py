#!/usr/bin/env python

import re
import ast
from setuptools import setup

_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('antlr_tsql/__init__.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))

setup(
	name = 'antlr-tsql',
	version = version,
	packages = ['antlr_tsql'],
	install_requires = ['antlr-ast', 'antlr4-python3-runtime', 'pyyaml'],
        description = 'A transact sql parser, written in Antlr4',
        author = 'Michael Chow',
        author_email = 'michael@datacamp.com',
        url = 'https://github.com/datacamp/antlr-tsql',
        include_package_data = True)
