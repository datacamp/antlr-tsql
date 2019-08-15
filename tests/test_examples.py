import pytest
import os
from antlr_tsql import ast
from tests.test_ast import ast_examples_parse


def load_dump(fname):
    import yaml

    dirname = os.path.dirname(__file__)
    dump_data = yaml.safe_load(open(dirname + "/" + fname))

    all_cmds = []
    for start, cmds in dump_data.items():
        for cmd, res in cmds:
            all_cmds.append((start, cmd, res))
    return all_cmds


@pytest.mark.parametrize(
    "start,cmd,res",
    [
        *load_dump(ast_examples_parse("visual_checks.yml")),
        *load_dump(ast_examples_parse("v0.3.yml")),
        *load_dump(ast_examples_parse("v0.4.yml")),
        *load_dump(ast_examples_parse("test_datetime.yml")),
        *load_dump(ast_examples_parse("test_parser_convert.yml")),
        *load_dump(ast_examples_parse("test_grouping_sets.yml")),
        *load_dump(ast_examples_parse("test_additional_lang_support.yml"))
    ],
)
def test_dump(start, cmd, res):
    assert repr(ast.parse(cmd, start, strict=True)) == res
