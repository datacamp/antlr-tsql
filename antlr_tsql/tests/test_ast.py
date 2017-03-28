import pytest
from antlr_tsql import ast
import os

def test_ast_parse_strict():
    with pytest.raises(ast.AntlrException):
        ast.parse("SELECT x FROM ____!", strict = True)   # ____! is ungrammatical

#def test_ast_parsing_unshaped():
#    sql_txt = "INSERT INTO sometable VALUES (1, 2, 3);"
#    tree = ast.parse(sql_txt)
#    assert isinstance(tree, ast.Script)
#    assert sql_txt.replace(' ', '') == tree.batch[0].replace(' ','')   # currently is just raw text

@pytest.mark.parametrize('fname', [
        'visual_checks.yml',
        'v0.3.yml'
        ])
def test_ast_examples_parse(fname):
    # just make sure they don't throw error for now..
    import yaml
    dirname = os.path.dirname(__file__)
    data = yaml.load(open(dirname + '/' + fname))
    for start, cmds in data['code'].items():
        [ast.parse(cmd, start, strict=True) for cmd in cmds]

