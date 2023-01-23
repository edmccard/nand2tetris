import re
from typing import NamedTuple, Pattern
from collections.abc import Iterator, Iterable
from enum import Enum


class Tok(Enum):
    STR = "stringConstant"
    ID = "identifier"
    NUM = "integerConstant"
    EOF = "EOF"
    LC = "{"
    RC = "}"
    LB = "["
    RB = "]"
    LP = "("
    RP = ")"
    DOT = "."
    COMMA = ","
    SEMI = ";"
    PLUS = "+"
    MINUS = "-"
    MUL = "*"
    DIV = "/"
    AND = "&"
    OR = "|"
    NOT = "~"
    LT = "<"
    GT = ">"
    EQ = "="
    CLS = "class"
    CTOR = "constructor"
    FN = "function"
    METHOD = "method"
    FIELD = "field"
    STATIC = "static"
    VAR = "var"
    INT = "int"
    CHAR = "char"
    BOOL = "boolean"
    VOID = "void"
    TRUE = "true"
    FALSE = "false"
    NULL = "null"
    THIS = "this"
    LET = "let"
    DO = "do"
    IF = "if"
    ELSE = "else"
    WHILE = "while"
    RETURN = "return"


class TokTy(Enum):
    KWD = "keyword"
    STR = "stringConstant"
    NUM = "integerConstant"
    SYM = "symbol"
    ID = "identifier"
    EOF = "EOF"


class Token(NamedTuple):
    type: TokTy
    tok: Tok
    txt: str
    lno: int


class LineTokenizer:
    IDENT: Pattern[str] = re.compile(r"[A-Za-z]\w*", re.ASCII)
    WS: Pattern[str] = re.compile(r"\s+", re.ASCII)
    NUM: Pattern[str] = re.compile(r"\d+", re.ASCII)

    TOKENS: dict[str, Tok] = {t.value: t for t in Tok}

    def __init__(self, line: str, lno: int, in_cc: bool):
        self.line: str = line
        self.lno: int = lno
        self.p: int = 0
        self.in_cc: bool = in_cc

    def tokenize(self) -> Iterator[tuple[TokTy, Tok, str]]:
        in_cc = self.in_cc
        length = len(self.line)
        while self.p < length:
            if in_cc:
                if self.search("*/") is not None:
                    in_cc = False
                else:
                    break
            elif self.rmatch(self.WS):
                pass
            elif self.match("/*"):
                in_cc = True
            elif self.match("//"):
                break
            elif self.match('"'):
                if (txt := self.search('"')) is not None:
                    yield (TokTy.STR, Tok.STR, txt)
                else:
                    raise LexError(f"line {self.lno}: unterminated string")

            elif txt := self.rmatch(self.IDENT):
                if tok := self.TOKENS.get(txt, None):
                    yield (TokTy.KWD, tok, txt)
                else:
                    yield (TokTy.ID, Tok.ID, txt)
            elif txt := self.rmatch(self.NUM):
                yield (TokTy.NUM, Tok.NUM, txt)
            elif tok := self.TOKENS.get(txt := self.line[self.p], None):
                self.p = self.p + 1
                yield (TokTy.SYM, tok, txt)
            else:
                self.p = self.p + 1
                raise LexError("invalid character")
        self.in_cc = in_cc

    def match(self, s: str) -> bool:
        slen = len(s)
        if self.line[self.p : self.p + slen] == s:
            self.p = self.p + slen
            return True
        else:
            return False

    def search(self, s: str) -> str | None:
        idx = self.line.find(s, self.p)
        if idx != -1:
            txt = self.line[self.p : idx]
            self.p = idx + len(s)
            return txt

    def rmatch(self, pat: Pattern[str]) -> str | None:
        if mo := pat.match(self.line, self.p):
            self.p = mo.end()
            return mo.group()


def lexer(lines: Iterable[str]) -> Iterator[Token]:
    in_cc = False
    for lno, line in enumerate(lines, 1):
        tokenizer = LineTokenizer(line, lno, in_cc)
        yield from map(lambda t: Token(*t, lno), tokenizer.tokenize())
        in_cc = tokenizer.in_cc
    if in_cc:
        raise LexError(f"line {lno}: unterminated comment")
    yield Token(TokTy.EOF, Tok.EOF, "", lno)
    yield Token(TokTy.EOF, Tok.EOF, "", lno)


def test_xml(tokens: Iterable[Token]) -> None:
    with open("test.xml", "w") as f:
        f.write("<tokens>\n")
        for token in tokens:
            if token.tok is Tok.EOF:
                break
            ty = token.type.value
            txt = token.txt.replace("&", "&amp;")
            txt = txt.replace("<", "&lt;")
            txt = txt.replace(">", "&gt;")
            f.write(f"<{ty}> {txt} </{ty}>\n")
        f.write("</tokens>\n")


class LexError(Exception):
    pass
