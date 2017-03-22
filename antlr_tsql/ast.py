from ast import AST
from antlr4.tree import Tree
from antlr4.Token import CommonToken
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


from collections import OrderedDict
def dump_node(obj):
    if isinstance(obj, AstNode):
        fields = OrderedDict()
        for name in obj._get_field_names():
            attr = getattr(obj, name, None)
            if attr is None: continue
            elif isinstance(attr, AstNode): fields[name] = attr._dump()
            elif isinstance(attr, list):    fields[name] = [dump_node(x) for x in attr]
            else:                           fields[name] = attr
        return {'type': obj.__class__.__name__, 'data': fields}
    elif isinstance(obj, list):
        return [dump_node(x) for x in obj]
    else:
        return obj

class AstNode(AST):         # AST is subclassed only so we can use ast.NodeVisitor...
    _fields = []            # contains child nodes to visit
    _priority = 1           # whether to descend for selection (greater descends into lower)

    def __init__(self, _ctx = None, **kwargs):
        # TODO: ensure key is in _fields?
        for k, v in kwargs.items(): setattr(self, k, v)
        self._ctx = _ctx

    # default visiting behavior, which uses fields
    @classmethod
    def _from_fields(cls, visitor, ctx, fields=None):

        fields = cls._fields if fields is None else fields

        field_dict = {}
        for mapping in fields:
            # parse mapping for -> and indices [] -----
            k, *name = mapping.split('->')
            name = k if not name else name[0]

            # get node -----
            #print(k)
            child = getattr(ctx, k, getattr(ctx, name, None))
            # when not alias needs to be called
            if callable(child): child = child()
            # when alias set on token, need to go from CommonToken -> Terminal Node
            elif isinstance(child, CommonToken):
                # giving a name to lexer rules sets it to a token,
                # rather than the terminal node corresponding to that token
                # so we need to find it in children
                child = next(filter(lambda c: getattr(c, 'symbol', None) is child, ctx.children))

            # set attr -----
            if isinstance(child, list):
                field_dict[name] = [visitor.visit(el) for el in child]
            elif child:
                field_dict[name] = visitor.visit(child)
            else:
                field_dict[name] = child
        return cls(ctx, **field_dict)

    def _get_field_names(self):
        return [el.split('->')[-1] for el in self._fields]

    def _get_text(self, text):
        return text[self._ctx.start.start: self._ctx.stop.stop + 1]

    def _dump(self):
        return dump_node(self)

    def _dumps(self):
        return json.dumps(self._dump())

    def _load(self):
        raise NotImplementedError()

    def _loads(self):
        raise NotImplementedError()

    def __str__(self):
        els = [k for k in self._get_field_names() if getattr(self, k, None) is not None]
        return "{}: {}".format(self.__class__.__name__, ", ".join(els))

    def __repr__(self):
        field_reps = {k: repr(getattr(self, k)) for k in self._get_field_names() if getattr(self, k, None) is not None}
        args = ", ".join("{} = {}".format(k, v) for k, v in field_reps.items())
        return "{}({})".format(self.__class__.__name__, args)
            

class Unshaped(AstNode):
    _fields = ['arr']

    def __init__(self, ctx, arr=tuple()):
        self.arr = arr
        self._ctx = ctx

class Script(AstNode):
    _fields = ['batch']
    _priority = 0

class SelectStmt(AstNode):
    _fields = ['select_list->target_list',
               'top_clause',
               'table_name->into_clause', 
               'table_sources->from_clause', 
               'where',
               'group_by_item->group_by_clause', 
               'having']

class Identifier(AstNode):
    # should have server, database, schema, table, name
    _fields = ['server', 'database', 'schema', 'table', 'name']


class AliasExpr(AstNode):
    _fields = ['expression->expr', 'alias']

class BinaryExpr(AstNode):
    _fields = ['left', 'op', 'right']

class UnaryExpr(AstNode):
    _fields = ['op', 'expression->expr']

class TopExpr(AstNode):
    _fields = ['expression->expr', 'PERCENT->percent', 'WITH->with_ties']

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

    @classmethod
    def _from_simple(cls, visitor, ctx):
        return cls(ctx, name = ctx.children[0].getText(), args = [])

    @classmethod
    def _from_aggregate(cls, visitor, ctx):
        obj = cls._from_fields(visitor, ctx)
        obj.name = ctx.children[0].getText()

        if obj.args is None: obj.args = []
        elif not isinstance(obj.args, Sequence): obj.args = [obj.args]
        return obj

    @classmethod
    def _from_cast(cls, visitor, ctx):
        args = [AliasExpr(expr = ctx.expression().accept(visitor), alias=ctx.alias.accept(visitor))]
        return cls(ctx, name = ctx.children[0].getText(), args = args)





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
        elif all(isinstance(res, AstNode) for res in result): return result
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

    def visitQuery_specification(self, ctx):
        return SelectStmt._from_fields(self, ctx)

    def visitFull_column_name(self, ctx):
        if ctx.table:
            ident = Identifier._from_fields(self, ctx.table)
            ident.name = self.visit(ctx.name)
            return ident

        return Identifier._from_fields(self, ctx)

    def visitFull_table_name(self, ctx):
        return Identifier._from_fields(self, ctx)

    def visitTable_name(self, ctx):
        return Identifier._from_fields(self, ctx)

    def visitBinary_operator_expression(self, ctx):
        return BinaryExpr._from_fields(self, ctx)

    def visitUnary_operator_expression(self, ctx):
        return UnaryExpr._from_fields(self, ctx)

    def visitSelect_list_elem(self, ctx):
        if ctx.alias:
            return AliasExpr._from_fields(self, ctx)
        else:
            return self.visitChildren(ctx)

    def visitTop_clause(self, ctx):
        return TopExpr._from_fields(self, ctx)

    # Function calls ---------------

    def visitSimple_call(self, ctx):
        return Call._from_simple(self, ctx)

    def visitStandard_call(self, ctx):
        return Call._from_standard(self, ctx)

    def visitExpression_list(self, ctx):
        return self.visitChildren(ctx, predicate = lambda n: not isinstance(n, Tree.TerminalNode))

    def visitAggregate_windowed_function(self, ctx):
        return Call._from_aggregate(self, ctx)

    def visitRanking_windowed_function(self, ctx):
        return Call._from_aggregate(self, ctx)

    def visitCast_call(self, ctx):
        return Call._from_cast(self, ctx)

    # simple dropping of tokens -----------------------------------------------
    # Note can't filter out TerminalNodeImpl from some currently as in something like
    # "SELECT a FROM b WHERE 1", the 1 will be a terminal node in where_clause
    def visitSelect_list(self, ctx):
        return self.visitChildren(ctx, predicate = lambda n: not isinstance(n, Tree.TerminalNode) )

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
