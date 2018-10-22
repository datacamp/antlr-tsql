import pytest
import os
from antlr_ast import AntlrException
from antlr_tsql import ast


def test_ast_parse_strict():
    with pytest.raises(AntlrException):
        ast.parse("SELECT x FROM ____!", strict=True)  # ____! is ungrammatical


# def test_ast_parsing_unshaped():
#     sql_txt = "INSERT INTO sometable VALUES (1, 2, 3);"
#     tree = ast.parse(sql_txt)
#     assert isinstance(tree, ast.Script)
#     assert sql_txt.replace(" ", "") == tree.batch[0].replace(
#         " ", ""
#     )  # currently is just raw text


@pytest.mark.parametrize(
    "fname",
    [
        pytest.mark.dependency(name="d1")("visual_checks.yml"),
        pytest.mark.dependency(name="d2")("v0.3.yml"),
        pytest.mark.dependency(name="d3")("v0.4.yml"),
    ],
)
def test_ast_examples_parse(fname):
    # just make sure they don't throw error for now..
    import yaml

    dirname = os.path.dirname(__file__)
    data = yaml.load(open(dirname + "/" + fname))
    res = {}
    for start, cmds in data["code"].items():
        res[start] = []
        for cmd in cmds:
            res[start].append([cmd, repr(ast.parse(cmd, start, strict=True))])
    print(res)
    with open(dirname + "/dump_" + fname, "w") as out_f:
        yaml.dump(res, out_f)


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
        *map(
            lambda case: pytest.mark.dependency(name="r1", depends=["d1"])(case),
            load_dump("dump_visual_checks.yml"),
        ),
        *map(
            lambda case: pytest.mark.dependency(name="r2", depends=["d2"])(case),
            load_dump("dump_v0.3.yml"),
        ),
        *map(
            lambda case: pytest.mark.dependency(name="r3", depends=["d3"])(case),
            load_dump("dump_v0.4.yml"),
        ),
    ],
)
def test_dump(start, cmd, res):
    assert repr(ast.parse(cmd, start, strict=True)) == res
