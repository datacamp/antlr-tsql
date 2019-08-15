# TODO: create speaker
import yaml
import pkg_resources
import inspect

from antlr_ast.ast import (
    parse as parse_ast,
    process_tree,
    AliasNode,
    BaseNodeTransformer,
    get_alias_nodes,
    Speaker,
    # references for export:  # TODO: put package exports in __init__?
    Terminal,
    BaseNode as AstNode,
    AntlrException as ParseError,
    dump_node,  # TODO only used in tests
    BaseAstVisitor)

from . import grammar


def parse(sql_text, start="tsql_file", strict=False):
    antlr_tree = parse_ast(grammar, sql_text, start, strict)
    simple_tree = process_tree(
        antlr_tree, base_visitor_cls=AstVisitor, transformer_cls=Transformer
    )

    return simple_tree


# AliasNodes


class Script(AliasNode):
    _fields_spec = ["batch"]
    _rules = ["tsql_file"]
    _priority = 0


class Batch(AliasNode):
    _fields_spec = ["statements=sql_clauses"]
    _rules = ["batch"]
    _priority = 0


class SelectStmt(AliasNode):
    _fields_spec = [
        "pref",
        "target_list=select_list",
        "top_clause",
        "into_clause=table_name",
        "from_clause=table_sources",
        "where_clause=where",
        "group_by_clause=group_by_item",
        "having",
        "with_expr=with_expression",
        "order_by_clause",
        "for_clause",
        "option_clause",
        "group_by_grouping_sets"
    ]

    _rules = ["query_specification", ("select_statement", "_from_select_rule")]

    @classmethod
    def _from_select_rule(cls, node, helper):
        # This node may be a Union
        query_node = node
        while query_node.query_expression and not helper.isinstance(
            query_node, "Union_query_expression"
        ):
            query_node = query_node.query_expression

        if query_node.query_specification:
            query_node = cls.from_spec(query_node.query_specification)

            # combine with fields from outer node
            outer = cls.from_spec(node)
            for field in cls._fields:
                value = getattr(outer, field)
                if value:
                    setattr(query_node, field, value)

            return query_node
        else:
            return query_node


class InsertStmt(AliasNode):
    _fields_spec = [
        "with_expr=with_expression",
        "top_clause=top_clause_dm",
        "into=INTO",
        "target=ddl_object",
        "target=rowset_function_limited",  # TODO make these own rule in grammar?
        "table_hints=insert_with_table_hints",
        "column_names=column_name_list",
        "output_clause",
        "values_clause=insert_statement_value",
        "for_clause",
        "option_clause",
    ]

    _rules = ["insert_statement"]


class ValueList(AliasNode):
    _fields_spec = ["values=expression_list"]
    _rules = ["value_list"]


class DeleteStmt(AliasNode):
    _fields_spec = [
        "with_expr=with_expression",
        "top_clause=top_clause_dm",
        "from_clause",
        "from_clause=delete_statement_from",
        "table_hints=insert_with_table_hints",
        "output_clause",
        "from_source=table_sources",
        "where_clause=where_clause_dml",
        "for_clause",
        "option_clause",
    ]

    _rules = ["delete_statement"]


class UpdateStmt(AliasNode):
    _fields_spec = [
        "with_expr=with_expression",
        "top_clause=top_clause_dm",
        "target=ddl_object",
        "target=rowset_function_limited",  # TODO make these own rule in grammar?
        "table_hints=insert_with_table_hints",
        "set_clause=update_elem",
        "output_clause",
        "from_source=table_sources",
        "where_clause=where_clause_dml",
        "for_clause",
        "option_clause",
    ]

    _rules = ["update_statement"]


class UpdateElem(AliasNode):
    _fields_spec = ["name=full_column_name", "name", "expression"]
    _rules = ["update_elem"]


class DeclareStmt(AliasNode):
    _fields_spec = [
        "variable=LOCAL_ID",
        "variable=cursor_name",
        "value=declare_set_cursor_common",
        "declare_local",
        "table_type_definition",  # TODO: improve
    ]
    _rules = ["declare_statement", "declare_cursor"]


class DeclareLocal(AliasNode):
    _fields_spec = ["name=LOCAL_ID", "type=data_type", "value=expression"]
    _rules = ["declare_local"]


class CursorStmt(AliasNode):
    _fields_spec = ["type", "variable=cursor_name"]
    _rules = [("cursor_statement", "_from_cursor")]

    @classmethod
    def _from_cursor(cls, node):
        has_own_cursor_alias = node.declare_cursor or node.fetch_cursor
        if has_own_cursor_alias:
            return has_own_cursor_alias
        alias = cls.from_spec(node)
        # TODO: combine() instead of children + keyword case convention
        alias.type = node.children[0].get_text().upper()
        return alias


class FetchStmt(AliasNode):
    _fields_spec = ["type=FETCH", "source=cursor_name", "vars=LOCAL_ID"]
    _rules = ["fetch_cursor"]


# TODO FetchType(type, number)

# TODO primitive expression


# TODO
class SetStmt(AliasNode):
    _fields_spec = ['type=set_special.set_type',
                    'key=set_special.key',
                    'value=set_special.value',
                    'value=set_special.constant_LOCAL_ID',
                    'value=set_special.on_off'
                    ]
    _rules = ["set_statement"]


# TODO
class PrintStmt(AliasNode):
    _fields_spec = []
    _rules = ["print_statement"]


class Union(AliasNode):
    _fields_spec = ["left", "op", "right"]
    _rules = ["union_query_expression"]


class Identifier(AliasNode):
    # should have server, database, schema, table, name
    _fields_spec = ["server", "database", "schema", "table", "name", "name=procedure"]
    _rules = [
        "full_table_name",
        "table_name",
        "func_proc_name",
        ("full_column_name", "_from_full_column_name"),
    ]

    @classmethod
    def _from_full_column_name(cls, node):
        if node.table:
            ident = cls.from_spec(node.table)
            ident.name = node.name
            return ident

        return cls.from_spec(node)


class WhileStmt(AliasNode):
    _fields_spec = ["search_condition", "body=sql_clause"]
    _rules = ["while_statement"]


class Body(AliasNode):
    _fields_spec = ["statements=sql_clauses"]
    _rules = ["block_statement"]


class TableAliasExpr(AliasNode):
    _fields_spec = ["alias=r_id", "alias_columns=column_name_list", "select_statement"]
    _rules = ["common_table_expression"]


class AliasExpr(AliasNode):
    _fields_spec = ["expr=expression", "alias=table_alias.r_id", "alias=column_alias"]
    _rules = [
        (
            "table_source_item_name",
            "_from_source_table_item",
        ),  # TODO: vs TableAliasExpr?
        ("select_list_elem", "_from_select_list_elem"),
    ]

    @classmethod
    def _from_select_list_elem(cls, node):
        if node.alias:
            return cls.from_spec(node)
        elif node.a_star:
            tab = node.table_name
            ident = tab or Identifier.from_spec(node)
            ident.name = node.a_star
            return ident
        else:
            return node.expression  # TODO visitChildren -> fields

    @classmethod
    def _from_source_table_item(cls, node):
        if node.with_table_hints:
            return node  # TODO visitChildren -> fields

        if node.table_alias:
            alias = cls.from_spec(node)
            alias.expr = node.children[0]
            return alias
        else:
            return node  # TODO visitChildren -> fields


class Star(AliasNode):
    _fields_spec = []


class BinaryExpr(AliasNode):
    _fields_spec = [
        "left",
        "op",
        "op=comparison_operator",
        "right",
        "right=subquery",
        "right=expression_list",
    ]

    _rules = [
        "binary_operator_expression",
        "binary_operator_expression2",
        "search_cond_and",
        "search_cond_or",
        ("binary_mod_expression", "_from_mod"),
        ("binary_in_expression", "_from_mod"),
    ]

    @classmethod
    def _from_mod(cls, node):
        bin_expr = BinaryExpr.from_spec(node)
        if node.NOT:
            return UnaryExpr(node, {"op": node.NOT, "expr": bin_expr})

        return bin_expr


class UnaryExpr(AliasNode):
    _fields_spec = ["op", "expr=expression"]
    _rules = ["unary_operator_expression%s" % ii for ii in ("", 2, 3)]


class TopExpr(AliasNode):
    _fields_spec = ["expr=expression", "percent=PERCENT", "with_ties=WITH"]
    _rules = ["top_clause", "top_clause_dm"]


class OrderByExpr(AliasNode):
    _fields_spec = ["expr=order_by_expression", "offset", "fetch=fetch_expression"]
    _rules = ["order_by_clause"]


class GroupByGroupingSets(AliasNode):
    _fields_spec = ["grouping_set"]
    _rules = ["group_by_grouping_sets"]


class SortBy(AliasNode):
    _fields_spec = ["expr=expression", "direction"]
    _rules = ["order_by_expression"]


class TimeZoneConversion(AliasNode):
    _fields_spec = ["expr=left", "timezone=right"]
    _rules = ["conversion_expression"]


class JoinExpr(AliasNode):
    _fields_spec = [
        "left",
        "join_type=op",
        "join_type",
        "right" "source=table_source",
        "cond=search_condition",
    ]
    _rules = ["standard_join", "cross_join", ("apply_join", "_from_apply")]

    @classmethod
    def _from_apply(cls, node):
        join_expr = JoinExpr.from_spec(node)
        if node.APPLY:  # TODO convention for keywords
            join_expr.join_type = str(join_expr.join_type) + " APPLY"

        return join_expr

    @classmethod
    def _from_table_source_item_joined(cls, node):
        return node.join_part  # TODO: no return before?


class Case(AliasNode):
    _fields_spec = [
        "input=caseExpr",
        "switches=switch_search_condition_section",
        "switches=switch_section",
        "else_expr=elseExpr",
    ]
    _rules = ["case_expression"]


class CaseWhen(AliasNode):
    _fields_spec = ["when=whenExpr", "then=thenExpr"]
    _rules = ["switch_section", "switch_search_condition_section"]


class IfElse(AliasNode):
    _fields_spec = ["search_condition", "if_expr", "else_expr"]
    _rules = ["if_statement"]


class OverClause(AliasNode):
    _fields_spec = [
        "partition=expression_list",
        "order_by_clause",
        "row_or_range_clause",
    ]
    _rules = ["over_clause"]


class Sublink(AliasNode):
    _fields_spec = ["test_expr", "op", "pref", "select=subquery"]
    _rules = ["sublink_expression"]


from collections.abc import Sequence


class Call(AliasNode):
    _fields_spec = [
        "name",
        "pref=all_distinct",
        "args=expression_list",
        "args=expression",
        "over_clause",
        "using"
    ]

    _rules = [
        ("standard_call", "_from_standard"),
        ("simple_call", "_from_simple"),
        ("aggregate_windowed_function", "_from_aggregate"),
        ("ranking_windowed_function", "_from_aggregate"),
        ("next_value_for_function", "_from_aggregate"),
        ("cast_call", "_from_cast"),
        ("expression_call", "_from_expression"),
    ]

    @classmethod
    def _from_standard(cls, node):
        alias = cls.from_spec(node)
        alias.name = node.children[0]

        # calls where the expression_list rule handles the args
        if node.expression_list:
            alias.args = node.expression_list
        # calls where args are explicitly comma separated
        else:
            # TODO use combine()?
            # find commas
            alias.args = []
            for ii, c in enumerate(node.children[2:-1], 2):  # skip name and '('
                if not c == ",":
                    alias.args.append(c)

        return alias

    @staticmethod
    def get_name(node):  # TODO
        return node.children[0]

    @classmethod
    def _from_simple(cls, node):
        return cls(node, {"name": cls.get_name(node), "args": []})

    @classmethod
    def _from_aggregate(cls, node):
        alias = cls.from_spec(node)
        alias.name = cls.get_name(node)

        if alias.args is None:
            alias.args = []
        elif not isinstance(alias.args, Sequence):
            alias.args = [alias.args]
        return alias

    @classmethod
    def _from_cast(cls, node):
        return cls(
            node,
            {
                "name": cls.get_name(node),
                "args": [
                    AliasExpr(node, {"expr": node.expression, "alias": node.alias})
                ],
            },
        )

    @classmethod
    def _from_expression(cls, node):
        return cls(
            node,
            {
                "name": cls.get_name(node),
                "args": [
                    AliasExpr(node, {"expr": node.left, "alias": node.alias})
                ],
                "using": node.right
            }
        )


# PARSE TREE VISITOR ----------------------------------------------------------


class Transformer(BaseNodeTransformer):
    @staticmethod
    def visit_Constant(node):
        return node

    @staticmethod
    def visit_Sign(node):
        # TODO strip + sign from int?
        return Terminal.from_text(node.get_text(), node._ctx)

    @staticmethod
    def visit_Comparison_operator(node):
        return Terminal.from_text(node.get_text(), node._ctx)

    @staticmethod
    def visit_With_expression(node):
        return node.common_table_expression

    @staticmethod
    def visit_Table_value_constructor(node):
        return node.value_list


# TODO: port from remove_terminal:
#  - "where_clause_dml",
#  - "declare_set_cursor_common",


# Add visit methods to Transformer for all nodes (in _rules) that convert to AliasNode instances

alias_nodes = get_alias_nodes(globals().values())
Transformer.bind_alias_nodes(alias_nodes)


class AstVisitor(BaseAstVisitor):
    def visitTerminal(self, ctx):
        """Converts case insensitive keywords and identifiers to lowercase
           Identifiers in quotes are not lowercased even though there is case sensitivity in quotes for identifiers,
            to prevent lowercasing quoted values.
        """
        text = str(super().visitTerminal(ctx))
        quotes = ["'", '"']
        if not (text[0] in quotes and text[-1] in quotes):
            text = text.lower()
        return Terminal.from_text(text, ctx)


if __name__ == "__main__":
    query = """
SELECT id FROM artists WHERE id > 100
    """
    parse(query)
