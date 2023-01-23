from jack_parser import *
from functools import singledispatchmethod
from typing import TextIO
import sys


class Analyzer:
    def __init__(self, f: TextIO = None):
        self.f: TextIO = f
        self.indent: int = 0
        self.in_term: bool = False

    def write(self, txt: str) -> None:
        self.f.write(f"{' ' * self.indent}{txt}\n")

    def open_tag(self, tag: str) -> None:
        self.write(f"<{tag}>")
        self.indent = self.indent + 2

    def close_tag(self, tag: str) -> None:
        self.indent = self.indent - 2
        self.write(f"</{tag}>")

    def tag(self, tag: str, txt: str) -> None:
        txt = txt.replace("&", "&amp;")
        txt = txt.replace("<", "&lt;")
        txt = txt.replace(">", "&gt;")
        self.write(f"<{tag}> {txt} </{tag}>")

    @singledispatchmethod
    def analyze(self, node) -> None:
        raise NotImplementedError(f"Cannot analyze {type(node)}")

    @analyze.register
    def _(self, node: Program) -> None:
        for c in node.classes:
            self.analyze(c)

    @analyze.register
    def _(self, node: Class) -> None:
        self.open_tag("class")
        self.tag("keyword", "class")
        self.tag("identifier", node.name)
        self.tag("symbol", "{")

        for cvar in node.cvars:
            self.analyze(cvar)
        for sub in node.subs:
            self.analyze(sub)

        self.tag("symbol", "}")
        self.close_tag("class")

    @analyze.register
    def _(self, node: Decl) -> None:
        match node.ty:
            case Name():
                self.tag("identifier", node.ty.value)
            case Tok():
                self.tag("keyword", node.ty.value)
        self.tag("identifier", node.names[0])
        for name in node.names[1:]:
            self.tag("symbol", ",")
            self.tag("identifier", name)

    @analyze.register
    def _(self, node: ClassVar) -> None:
        self.open_tag("classVarDec")
        self.tag("keyword", node.scope.value)
        self.analyze(node.decl)
        self.tag("symbol", ";")
        self.close_tag("classVarDec")

    @analyze.register
    def _(self, node: Subroutine) -> None:
        self.open_tag("subroutineDec")
        self.tag("keyword", node.mtype.value)
        self.analyze(node.decl)
        self.tag("symbol", "(")
        self.open_tag("parameterList")
        for (i, arg) in enumerate(node.args):
            if i > 0:
                self.tag("symbol", ",")
            self.analyze(arg)
        self.close_tag("parameterList")
        self.tag("symbol", ")")
        self.open_tag("subroutineBody")
        self.tag("symbol", "{")
        for loc in node.locs:
            self.open_tag("varDec")
            self.tag("keyword", "var")
            self.analyze(loc)
            self.tag("symbol", ";")
            self.close_tag("varDec")
        self.open_tag("statements")
        for stmt in node.stmts:
            self.analyze(stmt)
        self.close_tag("statements")
        self.tag("symbol", "}")
        self.close_tag("subroutineBody")
        self.close_tag("subroutineDec")

    @analyze.register
    def _(self, node: LetStmt) -> None:
        self.open_tag("letStatement")
        self.tag("keyword", "let")
        self.analyze(node.lvalue)
        self.tag("symbol", "=")
        self.analyze(node.expr)
        self.tag("symbol", ";")
        self.close_tag("letStatement")

    @analyze.register
    def _(self, node: DoStmt) -> None:
        self.open_tag("doStatement")
        self.tag("keyword", "do")
        self.analyze(node.call)
        self.tag("symbol", ";")
        self.close_tag("doStatement")

    @analyze.register
    def _(self, node: IfStmt) -> None:
        self.open_tag("ifStatement")
        self.tag("keyword", "if")
        self.tag("symbol", "(")
        self.analyze(node.expr)
        self.tag("symbol", ")")
        self.tag("symbol", "{")
        self.open_tag("statements")
        for stmt in node.true:
            self.analyze(stmt)
        self.close_tag("statements")
        self.tag("symbol", "}")
        if node.false is not None:
            self.tag("keyword", "else")
            self.tag("symbol", "{")
            self.open_tag("statements")
            for stmt in node.false:
                self.analyze(stmt)
            self.close_tag("statements")
            self.tag("symbol", "}")
        self.close_tag("ifStatement")

    @analyze.register
    def _(self, node: WhileStmt) -> None:
        self.open_tag("whileStatement")
        self.tag("keyword", "while")
        self.tag("symbol", "(")
        self.analyze(node.expr)
        self.tag("symbol", ")")
        self.tag("symbol", "{")
        self.open_tag("statements")
        for stmt in node.stmts:
            self.analyze(stmt)
        self.close_tag("statements")
        self.tag("symbol", "}")
        self.close_tag("whileStatement")

    @analyze.register
    def _(self, node: RetStmt) -> None:
        self.open_tag("returnStatement")
        self.tag("keyword", "return")
        if node.expr:
            self.analyze(node.expr)
        self.tag("symbol", ";")
        self.close_tag("returnStatement")

    @analyze.register
    def _(self, node: Expr) -> None:
        self.open_tag("expression")
        self.analyze(node.terms[0])
        for op, term in zip(node.ops, node.terms[1:]):
            self.tag("symbol", op.value)
            self.analyze(term)
        self.close_tag("expression")

    @analyze.register
    def _(self, node: Term) -> None:
        self.open_tag("term")
        if node.unary:
            self.tag("symbol", node.unary)
            self.open_tag("term")
        if node.grouped:
            self.tag("symbol", "(")
        self.analyze(node.expr)
        if node.grouped:
            self.tag("symbol", ")")
        if node.unary:
            self.close_tag("term")
        self.close_tag("term")

    @analyze.register
    def _(self, node: Var) -> None:
        self.tag("identifier", node.name.value)

    @analyze.register
    def _(self, node: Subscript) -> None:
        self.tag("identifier", node.name.value)
        self.tag("symbol", "[")
        self.analyze(node.idx)
        self.tag("symbol", "]")

    @analyze.register
    def _(self, node: Call) -> None:
        self.tag("identifier", node.names[0].value)
        if len(node.names) > 1:
            self.tag("symbol", ".")
            self.tag("identifier", node.names[1].value)
        self.tag("symbol", "(")
        self.open_tag("expressionList")
        for i, param in enumerate(node.params):
            if i > 0:
                self.tag("symbol", ",")
            self.analyze(param)
        self.close_tag("expressionList")
        self.tag("symbol", ")")

    @analyze.register
    def _(self, node: Const) -> None:
        match node.type:
            case "int":
                self.tag("integerConstant", node.val)
            case "str":
                self.tag("stringConstant", node.val)
            case _:
                self.tag("keyword", node.val)


def main():
    from pathlib import Path

    usage = f"usage: {sys.argv[0]} [input_file.jack | input_dir]"
    args = sys.argv[1:]
    if not args or len(args) > 1:
        return usage
    path = Path(args[0])
    if path.is_dir():
        src = path.glob("*.jack")
    elif path.suffix == ".jack":
        src = [path]
    else:
        return usage

    for file in src:
        prog = Program()
        with open(file) as f:
            lines = f.readlines()
        prog.parse_module(file.stem, lines)
        dst = Path(file.stem).with_suffix(".xml")
        with open(dst, "w") as f:
            a = Analyzer(f)
            a.analyze(prog)


if __name__ == "__main__":
    sys.exit(main())
