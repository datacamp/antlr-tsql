from antlr4.tree import Tree

from antlr_ast.ast import (
    parse as parse_ast,
    bind_to_visitor,
    AstNode,
    AntlrException as ParseError,
)

from . import grammar


def parse(sql_text, start="tsql_file", strict=False):
    tree = parse_ast(grammar, sql_text, start, strict)
    return AstVisitor().visit(tree)


import yaml


def parse_from_yaml(fname):
    data = yaml.load(open(fname)) if isinstance(fname, str) else fname
    out = {}
    for start, cmds in data.items():
        out[start] = [parse(cmd, start) for cmd in cmds]
    return out


class Unshaped(AstNode):
    _fields_spec = ["arr"]

    def __init__(self, ctx, arr=tuple()):
        self.arr = arr
        self._ctx = ctx


class Script(AstNode):
    _fields_spec = ["batch"]
    _priority = 0
    _rules = ["tsql_file"]


class Batch(AstNode):
    _fields_spec = ["sql_clauses->statements"]
    _priority = 0
    _rules = ["batch"]


class SqlClauses(AstNode):
    """This helper prevents an unshaped clause from visiting sibling clauses.
    This AstNode does not occur in the final ast.
    TODO: Inheriting from a helper class can help to classify these helper nodes
    """

    _rules = [("sql_clauses", "_from_clauses")]

    @classmethod
    def _from_clauses(cls, visitor, ctx):
        child_result = visitor.visitChildren(ctx)
        if isinstance(child_result, Unshaped):
            if all(isinstance(res, AstNode) for res in child_result.arr):
                child_result = child_result.arr
        return child_result


class SelectStmt(AstNode):
    _fields_spec = [
        "pref",
        "select_list->target_list",
        "top_clause",
        "table_name->into_clause",
        "table_sources->from_clause",
        "where->where_clause",
        "group_by_item->group_by_clause",
        "having",
    ]

    _rules = ["query_specification", ("select_statement", "_from_select_rule")]

    @classmethod
    def _from_select_rule(cls, visitor, ctx):
        fields = [
            "with_expression->with_expr",
            "order_by_clause",
            "for_clause",
            "option_clause",
        ]

        # This node may be a Union
        q_node = visitor.visit(ctx.query_expression())
        # q_node may be None if there was a parsing error
        if q_node:
            outer_sel = cls._from_fields(visitor, ctx, fields)

            for k in [el.split("->")[-1] for el in fields]:
                attr = getattr(outer_sel, k, None)
                if attr is not None:
                    setattr(q_node, k, attr)

            q_node._fields = q_node._fields + fields

            return q_node
        else:
            return visitor.visitChildren(ctx)


class InsertStmt(AstNode):
    _fields_spec = [
        "with_expression->with_expr",
        "top_clause_dm->top_clause",
        "INTO->into",
        "ddl_object->target",
        "rowset_function_limited->target",  # TODO make these own rule in grammar?
        "insert_with_table_hints->table_hints",
        "column_name_list->column_names",
        "output_clause",
        "insert_statement_value->values_clause",
        "for_clause",
        "option_clause",
    ]

    _rules = ["insert_statement"]


class ValueList(AstNode):
    _fields_spec = ["expression_list->values"]
    _rules = ["value_list"]


class DeleteStmt(AstNode):
    _fields_spec = [
        "with_expression->with_expr",
        "top_clause_dm->top_clause",
        "from_clause",
        "delete_statement_from->from_clause",
        "insert_with_table_hints->table_hints",
        "output_clause",
        "table_sources->from_source",
        "where_clause_dml->where_clause",
        "for_clause",
        "option_clause",
    ]

    _rules = ["delete_statement"]


class UpdateStmt(AstNode):
    _fields_spec = [
        "with_expression->with_expr",
        "top_clause_dm->top_clause",
        "ddl_object->target",
        "rowset_function_limited->target",  # TODO make these own rule in grammar?
        "insert_with_table_hints->table_hints",
        "update_elem->set_clause",
        "output_clause",
        "table_sources->from_source",
        "where_clause_dml->where_clause",
        "for_clause",
        "option_clause",
    ]

    _rules = ["update_statement"]


class UpdateElem(AstNode):
    _fields_spec = ["full_column_name->name", "name", "expression"]
    _rules = ["update_elem"]


class DeclareStmt(AstNode):
    # TODO sort out all forms of declare statements
    #      this configuration is to allow AST node selection in the meantime
    _fields_spec = [
        "cursor_name->variable",
        "declare_set_cursor_common->value",
        "declare_local",
    ]
    _rules = ["declare_statement", "declare_cursor"]


class DeclareLocal(AstNode):
    _fields_spec = ["LOCAL_ID->name", "data_type->type"]
    _rules = ["declare_local"]


class CursorStmt(AstNode):
    _fields_spec = ["type", "variable"]
    _rules = [("cursor_statement", "_from_cursor")]

    @classmethod
    def _from_cursor(cls, visitor, ctx):
        if ctx.declare_cursor() or ctx.fetch_cursor():
            return visitor.visitChildren(ctx)
        statement_type = ctx.children[0].getText().upper()
        variable = ctx.cursor_name().accept(visitor)
        return cls(ctx, type=statement_type, variable=variable)


class FetchStmt(AstNode):
    _fields_spec = ["type", "source", "vars"]
    _rules = [("fetch_cursor", "_from_standard")]

    @classmethod
    def _from_standard(cls, visitor, ctx):
        fetch_type = ctx.children[1].getText().upper()
        source = ctx.cursor_name().accept(visitor)

        variables_offset = (
            list(map(lambda child: child.getText(), ctx.children)).index("INTO") + 1
        )
        variables = []
        for variable in ctx.children[variables_offset:]:
            if variable.getText() == ",":
                continue
            variableResult = Identifier(variable, name=variable.getText())
            variables.append(variableResult)

        return cls(ctx, type=fetch_type, source=source, vars=variables)


# TODO FetchType(type, number)

# TODO primitive expression


class SetStmt(AstNode):
    _fields_spec = ["placeholder_do_not_use"]


class PrintStmt(AstNode):
    _fields_spec = ["placeholder_do_not_use"]


class Union(AstNode):
    _fields_spec = ["left", "op", "right"]
    _rules = ["union_query_expression"]


class Identifier(AstNode):
    # should have server, database, schema, table, name
    _fields_spec = ["server", "database", "schema", "table", "name", "procedure->name"]
    _rules = [
        "full_table_name",
        "table_name",
        "func_proc_name",
        ("full_column_name", "_from_full_column_name"),
    ]

    @classmethod
    def _from_full_column_name(cls, visitor, ctx):
        if ctx.table:
            ident = cls._from_fields(visitor, ctx.table)
            ident.name = visitor.visit(ctx.name)
            return ident

        return cls._from_fields(visitor, ctx)


class WhileStmt(AstNode):
    _fields_spec = ["search_condition", "sql_clause->body"]
    _rules = ["while_statement"]


class Body(AstNode):
    _fields_spec = ["sql_clauses->statements"]
    _rules = ["block_statement"]


class TableAliasExpr(AstNode):
    _fields_spec = ["r_id->alias", "column_name_list->alias_columns", "select_statement"]
    _rules = ["common_table_expression"]


class AliasExpr(AstNode):
    _fields_spec = ["expression->expr", "alias"]
    _rules = [
        ("table_source_item_name", "_from_source_table_item"),
        ("select_list_elem", "_from_select_list_elem"),
    ]

    @classmethod
    def _from_select_list_elem(cls, visitor, ctx):
        if ctx.alias:
            return cls._from_fields(visitor, ctx)
        elif ctx.a_star():
            tab = ctx.table_name()
            ident = visitor.visit(tab) if tab else Identifier(ctx)
            ident.name = visitor.visit(ctx.a_star())
            return ident
        else:
            return visitor.visitChildren(ctx)

    @classmethod
    def _from_source_table_item(cls, visitor, ctx):
        if ctx.with_table_hints():
            return visitor.visitChildren(ctx)

        ctx_alias = ctx.table_alias()
        if ctx_alias:
            expr = visitor.visit(ctx.children[0])
            alias = visitor.visit(ctx_alias)
            return cls(ctx_alias, expr=expr, alias=alias)
        else:
            return visitor.visitChildren(ctx)


class Star(AstNode):
    _fields_spec = []


class BinaryExpr(AstNode):
    _fields_spec = ["left", "op", "comparison_operator->op", "right"]

    _rules = [
        "binary_operator_expression",
        "binary_operator_expression2",
        "search_cond_and",
        "search_cond_or",
        ("binary_mod_expression", "_from_mod"),
        ("binary_in_expression", "_from_mod"),
    ]

    @classmethod
    def _from_mod(cls, visitor, ctx):
        fields = ["left", "op", "right", "subquery->right", "expression_list->right"]
        bin_expr = BinaryExpr._from_fields(visitor, ctx, fields)
        ctx_not = ctx.NOT()
        if ctx_not:
            return UnaryExpr(ctx, op=visitor.visit(ctx_not), expr=bin_expr)

        return bin_expr


class UnaryExpr(AstNode):
    _fields_spec = ["op", "expression->expr"]
    _rules = ["unary_operator_expression%s" % ii for ii in ("", 2, 3)]


class TopExpr(AstNode):
    _fields_spec = ["expression->expr", "PERCENT->percent", "WITH->with_ties"]
    _rules = ["top_clause", "top_clause_dm"]


class OrderByExpr(AstNode):
    _fields_spec = ["order_by_expression->expr", "offset", "fetch_expression->fetch"]
    _rules = ["order_by_clause"]


class SortBy(AstNode):
    _fields_spec = ["expression->expr", "direction"]
    _rules = ["order_by_expression"]


class JoinExpr(AstNode):
    _fields_spec = [
        "left",
        "op->join_type",
        "join_type",
        "right" "table_source->source",
        "search_condition->cond",
    ]
    _rules = ["standard_join", "cross_join", ("apply_join", "_from_apply")]

    @classmethod
    def _from_apply(cls, visitor, ctx):
        join_expr = JoinExpr._from_fields(visitor, ctx)
        if ctx.APPLY():
            join_expr.join_type += " APPLY"

        return join_expr

    @classmethod
    def _from_table_source_item_joined(cls, visitor, ctx):
        visitor.visit(ctx.join_part())


class Case(AstNode):
    _fields_spec = [
        "caseExpr->input",
        "switch_search_condition_section->switches",
        "switch_section->switches",
        "elseExpr->else_expr",
    ]
    _rules = ["case_expression"]


class CaseWhen(AstNode):
    _fields_spec = ["whenExpr->when", "thenExpr->then"]
    _rules = ["switch_section", "switch_search_condition_section"]


class IfElse(AstNode):
    _fields_spec = ["search_condition", "if_expr", "else_expr"]
    _rules = ["if_statement"]


class OverClause(AstNode):
    _fields_spec = ["expression_list->partition", "order_by_clause", "row_or_range_clause"]
    _rules = ["over_clause"]


class Sublink(AstNode):
    _fields_spec = ["test_expr", "op", "pref", "subquery->select"]
    _rules = ["sublink_expression"]


from collections.abc import Sequence


class Call(AstNode):
    _fields_spec = [
        "name",
        "all_distinct->pref",
        "expression_list->args",
        "expression->args",
        "over_clause",
    ]

    _rules = [
        ("standard_call", "_from_standard"),
        ("simple_call", "_from_simple"),
        ("aggregate_windowed_function", "_from_aggregate"),
        ("ranking_windowed_function", "_from_aggregate"),
        ("next_value_for_function", "_from_aggregate"),
        ("cast_call", "_from_cast"),
    ]

    @classmethod
    def _from_standard(cls, visitor, ctx):
        name = ctx.children[0].getText()

        # calls where the expression_list rule handles the args
        if ctx.expression_list():
            args = ctx.expression_list().accept(visitor)
        # calls where args are explicitly comma separated
        else:
            # find commas
            args = []
            prev_comma = 0
            for ii, c in enumerate(ctx.children[2:-1], 2):  # skip name and '('
                if not (isinstance(c, Tree.TerminalNodeImpl) and c.getText() == ","):
                    childResult = c.accept(visitor)
                    args.append(childResult)

        return cls(ctx, name=name, args=args)

    @staticmethod
    def get_name(ctx):
        return ctx.children[0].getText().upper()

    @classmethod
    def _from_simple(cls, visitor, ctx):
        return cls(ctx, name=cls.get_name(ctx), args=[])

    @classmethod
    def _from_aggregate(cls, visitor, ctx):
        obj = cls._from_fields(visitor, ctx)
        obj.name = cls.get_name(ctx)

        if obj.args is None:
            obj.args = []
        elif not isinstance(obj.args, Sequence):
            obj.args = [obj.args]
        return obj

    @classmethod
    def _from_cast(cls, visitor, ctx):
        args = [
            AliasExpr(
                ctx,
                expr=ctx.expression().accept(visitor),
                alias=ctx.alias.accept(visitor),
            )
        ]
        return cls(ctx, name=cls.get_name(ctx), args=args)


# PARSE TREE VISITOR ----------------------------------------------------------
import inspect
from functools import partial


class AstVisitor(grammar.Visitor):
    def visitChildren(self, node, predicate=None):
        """Default ParseTreeVisitor subtree visiting method

        :param node: Tree subclass (Context, Terminal...)
        :param predicate: skip child nodes that fulfill the predicate
        :return: AstNode
        """
        result = self.defaultResult()
        n = node.getChildCount()
        for i in range(n):
            if not self.shouldVisitNextChild(node, result):
                return

            c = node.getChild(i)
            # TODO: clean up grammar, and then remove hacky semicolon discarder below
            if isinstance(c, Tree.TerminalNodeImpl) and c.getText() == ";":
                continue
            if predicate and not predicate(c):
                continue

            childResult = c.accept(self)
            result = self.aggregateResult(result, childResult)
        return self.result_to_ast(node, result)

    @staticmethod
    def result_to_ast(node, result):
        if len(result) == 1:
            return result[0]
        elif len(result) == 0:
            return None
        elif all(isinstance(res, str) for res in result):
            return " ".join(result)
        elif all(
            isinstance(res, AstNode) and not isinstance(res, Unshaped) for res in result
        ):
            return result
        else:
            return Unshaped(node, result)

    def defaultResult(self):
        return list()

    def aggregateResult(self, aggregate, nextResult):
        aggregate.append(nextResult)
        return aggregate

    def visitTerminal(self, ctx):
        return ctx.getText()

    def visitConstant(self, ctx):
        res = self.visitChildren(ctx)
        return res if not res.startswith("+") else res[1:]

    def visitSet_statement(self, ctx):
        return SetStmt(ctx, placeholder_do_not_use=self.visitChildren(ctx))

    def visitPrint_statement(self, ctx):
        return PrintStmt(ctx, placeholder_do_not_use=self.visitChildren(ctx))

    def visitExpression_list(self, ctx):
        # return list of args, ignoring ',' for constructing function calls
        args = [
            c.accept(self) for c in ctx.children if not isinstance(c, Tree.TerminalNode)
        ]
        return args

    def visitColumn_name_list(self, ctx):
        return [
            Identifier(c, name=c.accept(self))
            for c in ctx.children
            if not isinstance(c, Tree.TerminalNode)
        ]

    # simple dropping of tokens -----------------------------------------------

    _remove_terminal = [
        "select_list",
        "bracket_expression",
        "subquery_expression",
        "bracket_search_expression",
        "bracket_query_expression",
        "bracket_table_source",
        "table_alias",
        "table_value_constructor",
        "where_clause_dml",
        "declare_set_cursor_common",
        "with_expression",
    ]


# Override visit methods in AstVisitor for all nodes (in _rules) that convert to the AstNode classes
for item in list(globals().values()):
    if inspect.isclass(item) and issubclass(item, AstNode):
        item._bind_to_visitor(AstVisitor)

# Override node visiting methods to add terminal child skipping in AstVisitor
for rule in AstVisitor._remove_terminal:
    # f = partial(AstVisitor.visitChildren, predicate = lambda n: not isinstance(n, Tree.TerminalNode))
    def skip_terminal_child_nodes(self, ctx):
        return self.visitChildren(
            ctx, predicate=lambda n: not isinstance(n, Tree.TerminalNode)
        )

    bind_to_visitor(AstVisitor, rule, skip_terminal_child_nodes)


if __name__ == "__main__":
    parse("SELECT id FROM artists WHERE id > 100")

