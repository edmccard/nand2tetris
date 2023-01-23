from ._lexer import lexer, LexError, Token, Tok, TokTy
from collections.abc import Iterable, Iterator


class Parser:
    TYPES: list[Tok] = [Tok.INT, Tok.BOOL, Tok.CHAR, Tok.ID]

    CONST_TYPES: dict[Tok, str] = {
        Tok.NUM: "int",
        Tok.STR: "str",
        Tok.TRUE: "bool",
        Tok.FALSE: "bool",
        Tok.NULL: "ref",
        Tok.THIS: "ref",
    }

    BIN_OPS: list[Tok] = [
        Tok.PLUS,
        Tok.MINUS,
        Tok.MUL,
        Tok.DIV,
        Tok.AND,
        Tok.OR,
        Tok.LT,
        Tok.GT,
        Tok.EQ,
    ]

    def __init__(self, lines: Iterable[str]):
        self.tokens: Iterator[str] = lexer(lines)
        self.curToken: Token = Token(TokTy.EOF, Tok.EOF, "", 0)
        self.read()

    def read(self) -> Token:
        cur = self.curToken
        try:
            self.curToken = next(self.tokens)
        except LexError as e:
            raise ParseError(str(e)) from e
        return cur

    def current(self) -> Token:
        return self.curToken

    def expect(self, *toks) -> Token:
        cur = self.curToken
        if cur.tok in toks:
            self.read()
            return cur
        else:
            raise ParseError(f"line {cur.lno}: expected {toks[-1]}, found {cur.tok}")

    def maybe(self, *toks) -> Token | None:
        cur = self.curToken
        if cur.tok in toks:
            self.read()
            return cur


class ParseError(Exception):
    pass
