from ._lexer import Tok, Token
from ._parser import ParseError, Parser
from typing import Any, NamedTuple
from collections.abc import Iterable
from abc import ABC


class Name(NamedTuple):
    value: str
    line: int

    @staticmethod
    def fromTok(tok: Token) -> "Name":
        return Name(tok.txt, tok.lno)

    @staticmethod
    def get_type(tok: Token) -> "Name | Tok":
        if tok.tok is Tok.ID:
            return Name.fromTok(tok)
        else:
            return tok.tok


class Decl(NamedTuple):
    ty: Name | Tok
    names: list[str]


class Call(NamedTuple):
    names: list[Name]
    params: "list[Expr]"


class Const(NamedTuple):
    type: str
    val: str


class Subscript(NamedTuple):
    name: Name
    idx: "Expr"


class Program:
    def __init__(self):
        self.classes: list[Class] = []

    def parse_module(self, module: str, lines: Iterable[str]) -> None:
        p = Parser(lines)
        try:
            p.expect(Tok.CLS)
            self.classes.append(Class.parse(p, module))
            p.expect(Tok.EOF)
        except ParseError as e:
            raise ParseError(f"{module}: {str(e)}") from e


class Class(NamedTuple):
    module: str
    name: str
    cvars: "list[ClassVar]"
    subs: "list[Subroutine]"

    @staticmethod
    def parse(p: Parser, module: str) -> "Class":
        name = p.expect(Tok.ID).txt
        cvars: "list[ClassVar]" = []
        subs: "list[Subroutine]" = []
        p.expect(Tok.LC)
        while p.current().tok in [Tok.FIELD, Tok.STATIC]:
            cvars.append(ClassVar.parse(p))
        while p.current().tok in [Tok.CTOR, Tok.FN, Tok.METHOD]:
            subs.append(Subroutine.parse(p))
        p.expect(Tok.RC)
        return Class(module, name, cvars, subs)


class ClassVar(NamedTuple):
    scope: Tok
    decl: Decl

    @staticmethod
    def parse(p: Parser) -> "ClassVar":
        scope = p.read().tok
        ty = Name.get_type(p.expect(*p.TYPES, "type"))
        names = [(p.expect(Tok.ID).txt)]
        while p.maybe(Tok.COMMA):
            names.append(p.expect(Tok.ID).txt)
        p.expect(Tok.SEMI)
        return ClassVar(scope, Decl(ty, names))


class Subroutine(NamedTuple):
    mtype: Tok
    decl: Decl
    args: list[Decl]
    locs: list[Decl]
    stmts: Any

    @staticmethod
    def parse(p: Parser) -> "Subroutine":
        mtype = p.read().tok
        tok = p.expect(Tok.VOID, *p.TYPES, "type")
        decl = Decl(Name.get_type(tok), [p.expect(Tok.ID).txt])

        p.expect(Tok.LP)
        args: list[Decl] = []
        if not p.maybe(Tok.RP):
            tok = p.expect(*p.TYPES, "type")
            args.append(Decl(Name.get_type(tok), [p.expect(Tok.ID).txt]))
            while p.maybe(Tok.COMMA):
                tok = p.expect(*p.TYPES, "type")
                args.append(Decl(Name.get_type(tok), [p.expect(Tok.ID).txt]))
            p.expect(Tok.RP)

        p.expect(Tok.LC)
        locs: list[Decl] = []
        while p.maybe(Tok.VAR):
            ty = Name.get_type(p.expect(*p.TYPES, "type"))
            names = [p.expect(Tok.ID).txt]
            while p.maybe(Tok.COMMA):
                names.append(p.expect(Tok.ID).txt)
            p.expect(Tok.SEMI)
            locs.append(Decl(ty, names))

        stmts = _Statements.parse(p)
        p.expect(Tok.RC)
        return Subroutine(mtype, decl, args, locs, stmts)


class Statement(ABC):
    pass


class _Statements:
    @staticmethod
    def parse(p: Parser) -> list[Statement]:
        stmts: list[Statement] = []
        while True:
            if p.maybe(Tok.LET):
                stmt = LetStmt.parse(p)
            elif p.maybe(Tok.DO):
                stmt = DoStmt.parse(p)
            elif p.maybe(Tok.IF):
                stmt = IfStmt.parse(p)
            elif p.maybe(Tok.WHILE):
                stmt = WhileStmt.parse(p)
            elif p.maybe(Tok.RETURN):
                stmt = RetStmt.parse(p)
            else:
                break
            stmts.append(stmt)
        return stmts


class LetStmt(NamedTuple):
    lvalue: "Subscript | Var"
    expr: "Expr"

    @staticmethod
    def parse(p: Parser) -> "LetStmt":
        name = Name.fromTok(p.expect(Tok.ID))
        if p.maybe(Tok.LB):
            idx = Expr.parse(p)
            p.expect(Tok.RB)
            lvalue = Subscript(name, idx)
        else:
            lvalue = Var(name)

        p.expect(Tok.EQ)
        expr = Expr.parse(p)
        p.expect(Tok.SEMI)
        return LetStmt(lvalue, expr)


class DoStmt(NamedTuple):
    call: Call

    @staticmethod
    def parse(p: Parser) -> "DoStmt":
        call = Var.parse(p, True)
        p.expect(Tok.SEMI)
        return DoStmt(call)


class IfStmt(NamedTuple):
    expr: "Expr"
    true: list[Statement]
    false: list[Statement] | None

    @staticmethod
    def parse(p: Parser) -> "IfStmt":
        p.expect(Tok.LP)
        expr = Expr.parse(p)
        p.expect(Tok.RP)
        p.expect(Tok.LC)
        true = _Statements.parse(p)
        p.expect(Tok.RC)
        false = None
        if p.maybe(Tok.ELSE):
            p.expect(Tok.LC)
            false = _Statements.parse(p)
            p.expect(Tok.RC)
        return IfStmt(expr, true, false)


class WhileStmt(NamedTuple):
    expr: "Expr"
    stmts: list[Statement]

    @staticmethod
    def parse(p: Parser) -> "WhileStmt":
        p.expect(Tok.LP)
        expr = Expr.parse(p)
        p.expect(Tok.RP)
        p.expect(Tok.LC)
        stmts = _Statements.parse(p)
        p.expect(Tok.RC)
        return WhileStmt(expr, stmts)


class RetStmt(NamedTuple):
    expr: "Expr | None"

    @staticmethod
    def parse(p: Parser) -> "RetStmt":
        expr = None
        if not p.maybe(Tok.SEMI):
            expr = Expr.parse(p)
            p.expect(Tok.SEMI)
        return RetStmt(expr)


class Var(NamedTuple):
    name: Name

    @staticmethod
    def parse(p: Parser, is_call: bool) -> "Var":
        names = [Name.fromTok(p.expect(Tok.ID))]
        if p.maybe(Tok.DOT):
            is_call = True
            names.append(Name.fromTok(p.expect(Tok.ID)))
        if is_call:
            params: "list[Expr]" = []
            p.expect(Tok.LP)
            if not p.maybe(Tok.RP):
                params.append(Expr.parse(p))
                while p.maybe(Tok.COMMA):
                    params.append(Expr.parse(p))
                p.expect(Tok.RP)
            return Call(names, params)
        if p.maybe(Tok.LB):
            idx = Expr.parse(p)
            p.expect(Tok.RB)
            return Subscript(names[0], idx)
        return Var(names[0])


class Expr(NamedTuple):
    terms: "list[Term]"
    ops: list[Tok]

    @staticmethod
    def parse(p: Parser) -> "Expr":
        terms: list[Term] = []
        ops: list[Tok] = []
        terms.append(Term.parse(p))
        while tok := p.maybe(*Parser.BIN_OPS):
            ops.append(tok.tok)
            terms.append(Term.parse(p))
        return Expr(terms, ops)


class Term(NamedTuple):
    unary: str | None
    grouped: bool
    expr: Expr

    @staticmethod
    def parse(p: Parser) -> "Term":
        unary = None
        if tok := p.maybe(Tok.MINUS, Tok.NOT):
            unary = tok.txt

        if p.maybe(Tok.LP):
            expr = Expr.parse(p)
            p.expect(Tok.RP)
            return Term(unary, True, expr)

        if ty := Parser.CONST_TYPES.get(p.current().tok, None):
            tok = p.read()
            return Term(unary, False, Const(ty, tok.txt))

        return Term(unary, False, Var.parse(p, False))
