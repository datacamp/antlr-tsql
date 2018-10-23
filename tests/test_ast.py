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
