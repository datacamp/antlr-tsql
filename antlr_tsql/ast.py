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

def dump_node(obj):
    if isinstance(obj, AstNode):
        fields = {}
        for name in obj._get_field_names():
            attr = getattr(obj, name)
            if   isinstance(attr, AstNode): fields[name] = attr._dump()
            elif isinstance(attr, list):    fields[name] = [dump_node(x) for x in attr]
            else:                           fields[name] = attr
        return {'type': obj.__class__.__name__, 'data': fields}
    else:
        return obj

class AstNode(AST):         # AST is subclassed only so we can use ast.NodeVisitor...
    _fields = []            # contains child nodes to visit
    _priority = 1           # whether to descend for selection (greater descends into lower)

    # default visiting behavior, which uses fields
    def __init__(self, ctx, visitor):
        self._ctx = ctx

        for mapping in self._fields:
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
                setattr(self, name, [visitor.visit(el) for el in child])
            elif child:
                setattr(self, name, visitor.visit(child))
            else:
                setattr(self, name, child)

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
        els = [k for k in self._get_field_names() if getattr(self, k) is not None]
        return "{}: {}".format(self.__class__.__name__, ", ".join(els))

    def __repr__(self):
        field_reps = {k: repr(getattr(self, k)) for k in self._get_field_names() if getattr(self, k) is not None}
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

# PARSE TREE VISITOR ----------------------------------------------------------

class AstVisitor(tsqlVisitor):
    def visitChildren(self, node, predicate=None):
        result = self.defaultResult()
        n = node.getChildCount()
        for i in range(n):
            if not self.shouldVisitNextChild(node, result):
                return

            c = node.getChild(i)
            if predicate and not predicate(c): continue

            childResult = c.accept(self)
            result = self.aggregateResult(result, childResult)

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
        return Script(ctx, self)


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
