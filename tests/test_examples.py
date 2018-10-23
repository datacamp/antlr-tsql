import pytest
import os
from antlr_tsql import ast


def load_dump(fname):
    import yaml

    dirname = os.path.dirname(__file__)
    dump_data = yaml.load(open(dirname + "/" + fname))

    all_cmds = []
    for start, cmds in dump_data.items():
        for cmd, res in cmds:
            all_cmds.append((start, cmd, res))
    return all_cmds


@pytest.mark.parametrize(
    "start,cmd,res",
    [
        *load_dump("dump_visual_checks.yml"),
        *load_dump("dump_v0.3.yml"),
        *load_dump("dump_v0.4.yml"),
    ],
)
def test_dump(start, cmd, res):
    assert repr(ast.parse(cmd, start, strict=True)) == res
