from antlr4.tree import Tree
from antlr4.InputStream import InputStream
from antlr4 import FileStream, CommonTokenStream

from .tsqlLexer import tsqlLexer
from .tsqlParser import tsqlParser
from .tsqlVisitor import tsqlVisitor

def parse(sql_text, start='tsql_file', strict=False):
    input_stream = InputStream(sql_text)

    lexer = tsqlLexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = tsqlParser(token_stream)
    visitor = AstVisitor()

    if strict:
        error_listener = CustomErrorListener()
        parser.addErrorListener(error_listener)

    return visitor.visit(getattr(parser, start)())


import yaml
def parse_from_yaml(fname):
    data = yaml.load(open(fname)) if isinstance(fname, str) else fname
    out = {}
    for start, cmds in data.items():
        out[start] = [parse(cmd, start) for cmd in cmds]
    return out

from antlr_ast import AstNode

class Unshaped(AstNode):
    _fields = ['arr']

    def __init__(self, ctx, arr=tuple()):
        self.arr = arr
        self._ctx = ctx

class Script(AstNode):
    _fields = ['batch']
    _priority = 0

class Batch(AstNode):
    _fields = ['sql_clauses->statements']
    _priority = 0

class SelectStmt(AstNode):
    _fields = ['pref',
               'select_list->target_list',
               'top_clause',
               'table_name->into_clause', 
               'table_sources->from_clause', 
               'where->where_clause',
               'group_by_item->group_by_clause', 
               'having']

    @classmethod
    def _from_select_rule(cls, visitor, ctx):
        fields = ['with_expression->with_expr', 
                  'order_by_clause', 'for_clause', 'option_clause']
        
        q_node = visitor.visit(ctx.query_expression())
        # q_node may be None if there was a parsing error
        if q_node:
            outer_sel = cls._from_fields(visitor, ctx, fields)

            for k in [el.split('->')[-1] for el in fields]:
                attr = getattr(outer_sel, k, None)
                if attr is not None: setattr(q_node, k, attr)

            q_node._fields = q_node._fields + fields

            return q_node
        else: return visitor.visitChildren(ctx)

class InsertStmt(AstNode):
    _fields = ['with_expression->with_expr', 'top_clause_dm->top_clause', 
               'INTO->into',
               'ddl_object->target', 'rowset_function_limited->target',    # TODO make these own rule in grammar?
               'insert_with_table_hints->table_hints',
               'column_name_list->column_names', 'output_clause', 'insert_statement_value->values_clause',
               'for_clause', 'option_clause']

class ValueList(AstNode):
    _fields = ['expression_list->values']

class DeleteStmt(AstNode):
    _fields = ['with_expression->with_expr', 'top_clause_dm->top_clause',
               'from_clause', 
               'delete_statement_from->from_clause',
               'insert_with_table_hints->table_hints',
               'output_clause', 
               'table_sources->from_source', 'where_clause_dml->where_clause',
               'for_clause', 'option_clause']

class UpdateStmt(AstNode):
    _fields = ['with_expression->with_expr', 'top_clause_dm->top_clause',
               'ddl_object->target', 'rowset_function_limited->target',    # TODO make these own rule in grammar?
               'insert_with_table_hints->table_hints',
               'update_elem->set_clause',
               'output_clause', 
               'table_sources->from_source', 'where_clause_dml->where_clause',
               'for_clause', 'option_clause']

class DeclareStmt(AstNode):
    # TODO sort out all forms of declare statements
    #      this configuration is to allow AST node selection in the meantime
    _fields = ['placeholder_do_not_use']

class SetStmt(AstNode):
    _fields = ['placeholder_do_not_use']

class Union(AstNode):
    _fields = ['left', 'op', 'right']        


class Identifier(AstNode):
    # should have server, database, schema, table, name
    _fields = ['server', 'database', 'schema', 'table', 'name', 'procedure->name']

class AliasExpr(AstNode):
    _fields = ['expression->expr', 'alias']

    @classmethod
    def _from_source_table_item(cls, visitor, ctx):
        if ctx.with_table_hints(): return visitor.visitChildren(ctx)

        ctx_alias = ctx.table_alias()
        if ctx_alias:
            expr  = visitor.visit(ctx.children[0])
            alias = visitor.visit(ctx_alias)
            return cls(ctx_alias, expr=expr, alias=alias)
        else:
            return visitor.visitChildren(ctx)

class Star(AstNode):
    _fields = []

class BinaryExpr(AstNode):
    _fields = ['left', 'op', 'comparison_operator->op', 'right']
    

    @classmethod
    def _from_mod(cls, visitor, ctx, fields):
        bin_expr = BinaryExpr._from_fields(visitor, ctx, fields)
        ctx_not = ctx.NOT()
        if ctx_not:
            return UnaryExpr(ctx, op=visitor.visit(ctx_not), expr=bin_expr)

        return bin_expr

class UnaryExpr(AstNode):
    _fields = ['op', 'expression->expr']

class TopExpr(AstNode):
    _fields = ['expression->expr', 'PERCENT->percent', 'WITH->with_ties']

class OrderByExpr(AstNode):
    _fields = ['order_by_expression->expr', 'offset', 'fetch_expression->fetch']

class SortBy(AstNode):
    _fields = ['expression->expr', 'direction']

class JoinExpr(AstNode):
    _fields = ['left', 'op->join_type', 'join_type', 'right'
               'table_source->source', 'search_condition->cond']

    @classmethod
    def _from_apply(cls, visitor, ctx):
        join_expr = JoinExpr._from_fields(visitor, ctx)
        if ctx.APPLY(): join_expr.join_type += ' APPLY'

        return join_expr

    @classmethod
    def _from_table_source_item_joined(cls, visitor, ctx):
        visitor.visit(ctx.join_part())

class Case(AstNode):
    _fields = ['caseExpr->input', 'switch_search_condition_section->switches', 'switch_section->switches', 'elseExpr->else_expr']

class CaseWhen(AstNode):
    _fields = ['whenExpr->when', 'thenExpr->then']

class IfElse(AstNode):
    _fields = ['search_condition', 'if_expr', 'else_expr']

class OverClause(AstNode):
    _fields = ['expression_list->partition', 'order_by_clause', 'row_or_range_clause']

class Sublink(AstNode):
    _fields = ['test_expr', 'op', 'pref', 'subquery->select']

from collections.abc import Sequence
class Call(AstNode):
    _fields = ['name', 'all_distinct->pref',
               'expression_list->args', 'expression->args',
               'over_clause']

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
            for ii, c in enumerate(ctx.children[2:-1], 2):    # skip name and '('
                if not (isinstance(c, Tree.TerminalNodeImpl) and c.getText() == ','):
                    childResult = c.accept(visitor)
                    args.append(childResult)
        
        return cls(ctx, name=name, args=args)

    @staticmethod
    def get_name(ctx): return ctx.children[0].getText().upper()

    @classmethod
    def _from_simple(cls, visitor, ctx):
        return cls(ctx, name = cls.get_name(ctx), args = [])

    @classmethod
    def _from_aggregate(cls, visitor, ctx):
        obj = cls._from_fields(visitor, ctx)
        obj.name = cls.get_name(ctx)

        if obj.args is None: obj.args = []
        elif not isinstance(obj.args, Sequence): obj.args = [obj.args]
        return obj

    @classmethod
    def _from_cast(cls, visitor, ctx):
        args = [AliasExpr(ctx, expr = ctx.expression().accept(visitor), alias=ctx.alias.accept(visitor))]
        return cls(ctx, name = cls.get_name(ctx), args = args)





# PARSE TREE VISITOR ----------------------------------------------------------

class AstVisitor(tsqlVisitor):
    def visitChildren(self, node, predicate=None):
        result = self.defaultResult()
        n = node.getChildCount()
        for i in range(n):
            if not self.shouldVisitNextChild(node, result):
                return

            c = node.getChild(i)
            # TODO: clean up grammar, and then remove hacky semicolon discarder below
            if isinstance(c, Tree.TerminalNodeImpl) and c.getText() == ';': continue
            if predicate and not predicate(c): continue

            childResult = c.accept(self)
            result = self.aggregateResult(result, childResult)
        return self.result_to_ast(node, result)

    @staticmethod
    def result_to_ast(node, result):
        if len(result) == 1: return result[0]
        elif len(result) == 0: return None
        elif all(isinstance(res, str) for res in result): return " ".join(result)
        elif all(isinstance(res, AstNode) and not isinstance(res, Unshaped) for res in result): return result
        else: return Unshaped(node, result)

    def defaultResult(self):
        return list()

    def aggregateResult(self, aggregate, nextResult):
        aggregate.append(nextResult)
        return aggregate

    def visitTerminal(self, ctx):
        return ctx.getText()

    def visitTsql_file(self, ctx):
        return Script._from_fields(self, ctx)

    def visitBatch(self, ctx):
        return Batch._from_fields(self, ctx)

    def visitSelect_statement(self, ctx):
        return SelectStmt._from_select_rule(self, ctx)

    def visitQuery_specification(self, ctx):
        return SelectStmt._from_fields(self, ctx)

    def visitInsert_statement(self, ctx):
        return InsertStmt._from_fields(self, ctx)

    def visitDelete_statement(self, ctx):
        return DeleteStmt._from_fields(self, ctx)

    def visitUpdate_statement(self, ctx):
        return UpdateStmt._from_fields(self, ctx)

    def visitUnion_query_expression(self, ctx):
        return Union._from_fields(self, ctx)

    def visitFull_column_name(self, ctx):
        if ctx.table:
            ident = Identifier._from_fields(self, ctx.table)
            ident.name = self.visit(ctx.name)
            return ident

        return Identifier._from_fields(self, ctx)
    
    def visitFunc_proc_name(self, ctx):
        return Identifier._from_fields(self, ctx)

    def visitFull_table_name(self, ctx):
        return Identifier._from_fields(self, ctx)

    def visitTable_name(self, ctx):
        return Identifier._from_fields(self, ctx)

    def visitBinary_operator_expression(self, ctx):
        return BinaryExpr._from_fields(self, ctx)

    def visitBinary_operator_expression2(self, ctx):
        return BinaryExpr._from_fields(self, ctx)

    def visitSearch_cond_and(self, ctx):
        return BinaryExpr._from_fields(self, ctx)

    def visitSearch_cond_or(self, ctx):
        return BinaryExpr._from_fields(self, ctx)

    def visitBinary_mod_expression(self, ctx):
        return BinaryExpr._from_mod(self, ctx, BinaryExpr._fields)

    def visitBinary_in_expression(self, ctx):
        fields = ['left', 'op', 'subquery->right', 'expression_list->right']
        return BinaryExpr._from_mod(self, ctx, fields)

    def visitUnary_operator_expression(self, ctx):
        return UnaryExpr._from_fields(self, ctx)
    
    def visitUnary_operator_expression2(self, ctx):
        return UnaryExpr._from_fields(self, ctx)

    def visitUnary_operator_expression3(self, ctx):
        return UnaryExpr._from_fields(self, ctx)

    def visitSublink_expression(self, ctx):
        return Sublink._from_fields(self, ctx)

    def visitSelect_list_elem(self, ctx):
        if ctx.alias:
            return AliasExpr._from_fields(self, ctx)
        elif ctx.a_star():
            tab = ctx.table_name()
            ident = self.visit(tab) if tab else Identifier(ctx)
            ident.name = self.visit(ctx.a_star())
            return ident
        else:
            return self.visitChildren(ctx)

    def visitTable_source_item_name(self, ctx):
        return AliasExpr._from_source_table_item(self, ctx)

    def visitTop_clause(self, ctx):
        return TopExpr._from_fields(self, ctx)

    def visitTop_clause_dm(self, ctx):
        return TopExpr._from_fields(self, ctx)

    def visitOrder_by_clause(self, ctx):
        return OrderByExpr._from_fields(self, ctx)

    def visitOrder_by_expression(self, ctx):
        return SortBy._from_fields(self, ctx)

    def visitFetch_expression(self, ctx):
        return self.visit(ctx.expression())

    def visitStandard_join(self, ctx):
        return JoinExpr._from_fields(self, ctx)

    def visitCross_join(self, ctx):
        return JoinExpr._from_fields(self, ctx)

    def visitApply_join(self, ctx):
        return JoinExpr._from_apply(self, ctx)

    def visitOver_clause(self, ctx):
        return OverClause._from_fields(self, ctx)

    def visitConstant(self, ctx):
        res = self.visitChildren(ctx)
        return res if not res.startswith('+') else res[1:]

    def visitCase_expression(self, ctx):
        return Case._from_fields(self, ctx)

    def visitSwitch_search_condition_section(self, ctx):
        return CaseWhen._from_fields(self, ctx)

    def visitSwitch_search_condition_section(self, ctx):
        return CaseWhen._from_fields(self, ctx)

    def visitIf_statement(self, ctx):
        return IfElse._from_fields(self, ctx)

    def visitDeclare_statement(self, ctx):
        return DeclareStmt(ctx, placeholder_do_not_use=self.visitChildren(ctx))

    def visitSet_statement(self, ctx):
        return SetStmt(ctx, placeholder_do_not_use=self.visitChildren(ctx))

    # Function calls ---------------

    def visitSimple_call(self, ctx):
        return Call._from_simple(self, ctx)

    def visitStandard_call(self, ctx):
        return Call._from_standard(self, ctx)

    def visitExpression_list(self, ctx):
        args = [c.accept(self) for c in ctx.children if not isinstance(c, Tree.TerminalNode)]
        return args

    def visitValue_list(self, ctx):
        return ValueList._from_fields(self, ctx)

    def visitAggregate_windowed_function(self, ctx):
        return Call._from_aggregate(self, ctx)

    def visitRanking_windowed_function(self, ctx):
        return Call._from_aggregate(self, ctx)

    def visitNext_value_for_function(self, ctx):
        return Call._from_aggregate(self, ctx)

    def visitCast_call(self, ctx):
        return Call._from_cast(self, ctx)

    # simple dropping of tokens -----------------------------------------------
    # Note can't filter out TerminalNodeImpl from some currently as in something like
    # "SELECT a FROM b WHERE 1", the 1 will be a terminal node in where_clause

    def visitSql_clauses(self, ctx):
        return self.visitChildren(ctx, predicate = lambda n: not isinstance(n, Tree.TerminalNode) )

    def visitSelect_list(self, ctx):
        return self.visitChildren(ctx, predicate = lambda n: not isinstance(n, Tree.TerminalNode) )

    def visitBracket_expression(self, ctx): 
        return self.visitChildren(ctx, predicate = lambda n: not isinstance(n, Tree.TerminalNode) )

    def visitSubquery_expression(self, ctx): 
        return self.visitChildren(ctx, predicate = lambda n: not isinstance(n, Tree.TerminalNode) )

    def visitBracket_search_expression(self, ctx): 
        return self.visitChildren(ctx, predicate = lambda n: not isinstance(n, Tree.TerminalNode) )

    def visitBracket_query_expression(self, ctx):
        return self.visitChildren(ctx, predicate = lambda n: not isinstance(n, Tree.TerminalNode) )

    def visitBracket_table_source(self, ctx):
        return self.visitChildren(ctx, predicate = lambda n: not isinstance(n, Tree.TerminalNode) )

    def visitTable_alias(self, ctx):
        return self.visitChildren(ctx, predicate = lambda n: not isinstance(n, Tree.TerminalNode) )

    def visitTable_value_constructor(self, ctx):
        return self.visitChildren(ctx, predicate = lambda n: not isinstance(n, Tree.TerminalNode) )

    def visitWhere_clause_dml(self, ctx):
        return self.visitChildren(ctx, predicate = lambda n: not isinstance(n, Tree.TerminalNode) )

    def visitColumn_name_list(self, ctx):
        return [Identifier(c, name=c.accept(self)) for c in ctx.children if not isinstance(c, Tree.TerminalNode)]




from antlr4.error.ErrorListener import ErrorListener
from antlr4.error.Errors import RecognitionException
class AntlrException(Exception):
    def __init__(self, msg, orig):
        self.msg, self.orig = msg, orig

class CustomErrorListener(ErrorListener):
    def syntaxError(self, recognizer, badSymbol, line, col, msg, e):
        if e is not None:
            msg = "line {line}: {col} {msg}".format(line=line, col=col, msg=msg)
            raise AntlrException(msg, e)
        else:
            raise AntlrException(msg, None)

    #def reportAmbiguity(self, recognizer, dfa, startIndex, stopIndex, exact, ambigAlts, configs):
    #    raise Exception("TODO")

    #def reportAttemptingFullContext(self, recognizer, dfa, startIndex, stopIndex, conflictingAlts, configs):
    #    raise Exception("TODO")

    #def reportContextSensitivity(self, recognizer, dfa, startIndex, stopIndex, prediction, configs):
    #    raise Exception("TODO")
