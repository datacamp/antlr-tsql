import pytest
from antlr_tsql import ast

def test_ast_parse_strict():
    with pytest.raises(ast.AntlrException):
        ast.parse("SELECT x FROM ____!", strict = True)   # ____! is ungrammatical

def test_ast_parsing_unshaped():
    sql_txt = "INSERT INTO sometable VALUES (1, 2, 3);"
    tree = ast.parse(sql_txt)
    assert isinstance(tree, ast.Script)
    assert sql_txt.replace(' ', '') == tree.batch[0].replace(' ','')   # currently is just raw text
