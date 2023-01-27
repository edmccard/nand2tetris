from jack_parser import *
from functools import singledispatchmethod
from typing import NamedTuple, TextIO
import sys


def redef_error(name: Name) -> ParseError:
    return ParseError(f"line {name.line}: {name.value} redefined")


def undef_error(name: Name) -> ParseError:
    return ParseError(f"line {name.line}: {name.value} undefined")


def array_error(name: Name) -> ParseError:
    return ParseError(f"line {name.line}: cannot subscript builtin {name.value}")


class SubSym(NamedTuple):
    cm_names: dict[str, int]
    im_names: dict[str, int]

    def conforms(self, other: "SubSym") -> bool:
        return (
            self.cm_names.items() >= other.cm_names.items()
            and self.im_names.items() >= other.im_names.items()
        )


class VarSym(NamedTuple):
    ty: str
    code: str


class VarCode:
    def __init__(self, segment: str):
        self.segment: str = segment
        self.count = 0

    def next(self) -> str:
        code = f"{self.segment} {self.count}"
        self.count = self.count + 1
        return code


class SymTable:
    OS: dict[str, SubSym] = {
        "Math": SubSym(
            cm_names={
                "multiply": 2,
                "divide": 2,
                "min": 2,
                "max": 2,
                "sqrt": 2,
            },
            im_names={},
        ),
        "String": SubSym(
            cm_names={"new": 1, "backSpace": 0, "doubleQuote": 0, "newLine": 0},
            im_names={
                "dispose": 0,
                "length": 0,
                "charAt": 1,
                "setCharAt": 2,
                "appendChar": 1,
                "eraseLastChar": 0,
                "intValue": 0,
                "setInt": 1,
            },
        ),
        "Array": SubSym(cm_names={"new": 1}, im_names={"dispose": 0}),
        "Output": SubSym(
            cm_names={
                "moveCursor": 2,
                "printChar": 1,
                "printString": 1,
                "printInt": 1,
                "println": 0,
                "backSpace": 0,
            },
            im_names={},
        ),
        "Screen": SubSym(
            cm_names={
                "clearScreen": 0,
                "setColor": 1,
                "drawPixel": 2,
                "drawLine": 4,
                "drawRectangle": 4,
                "drawCircle": 3,
            },
            im_names={},
        ),
        "Keyboard": SubSym(
            cm_names={
                "keyPressed": 0,
                "readChar": 0,
                "readLine": 1,
                "readInt": 1,
            },
            im_names={},
        ),
        "Memory": SubSym(
            cm_names={"peek": 1, "poke": 2, "alloc": 1, "deAlloc": 1},
            im_names={},
        ),
        "Sys": SubSym(cm_names={"halt": 0, "error": 1, "wait": 1}, im_names={}),
    }

    def __init__(self):
        self.subs: dict[str, SubSym] = {}

        self.class_name: str | None = None
        self.cvars: dict[str, VarSym] | None = None
        self.static_code: VarCode = VarCode("static")
        self.field_code: VarCode | None = None

        self.func_name: str | None = None
        self.fvars: dict[str, VarSym] | None = None
        self.arg_code: VarCode | None = None
        self.loc_code: VarCode | None = None
        self.label_id: int | None = None

    def var_code(self, name: Name) -> VarSym:
        if sym := self.fvars.get(name.value, None):
            return sym
        if sym := self.cvars.get(name.value, None):
            return sym
        raise undef_error(name)

    def arr_code(self, name: Name) -> VarSym:
        sym = self.var_code(name)
        if sym.ty == "<builtin>":
            raise array_error(name)
        return sym

    def label(self, suffix: str | None = None) -> str:
        lbl = f"{self.class_name}.{self.func_name}"
        if suffix:
            self.label_id = self.label_id + 1
            return f"{lbl}.{suffix}${self.label_id}"
        else:
            return lbl

    def add_subs(self, c: Class):
        name = c.name
        if name.value in self.subs:
            raise redef_error(name)
        cm_names: dict[str, int] = {}
        im_names: dict[str, int] = {}
        for sub in c.subs:
            sname = sub.decl.names[0]
            if sub.mtype is Tok.METHOD:
                if sname.value in im_names:
                    raise redef_error(name)
                im_names[sname.value] = len(sub.args)
            else:
                if sname.value in cm_names:
                    raise redef_error(sname)
                cm_names[sname.value] = len(sub.args)
        subsym = SubSym(cm_names, im_names)
        if builtin := self.OS.get(name, None):
            if not subsym.conforms(builtin):
                raise ParseError(f"{name.value} does not implement builtin")
        self.subs[name.value] = subsym

    def get_type(self, decl: Decl) -> str:
        if name := decl.builtin_name():
            return "<builtin>"
        name = decl.class_name()
        if name.value in self.OS or name.value in self.subs:
            return name.value
        raise undef_error(name)

    def add_class(self, c: Class) -> None:
        self.class_name = c.name.value
        self.field_code = VarCode("this")
        cvars: dict[str, VarSym] = {}
        for cvar in c.cvars:
            ty = self.get_type(cvar.decl)
            for name in cvar.decl.names:
                if name.value in cvars:
                    raise redef_error(name)
                if cvar.scope is Tok.STATIC:
                    code = self.static_code.next()
                else:
                    code = self.field_code.next()
                cvars[name.value] = VarSym(ty, code)
        self.cvars = cvars

    def field_count(self):
        return self.field_code.count

    def add_sub(self, s: Subroutine) -> None:
        self.func_name = s.decl.names[0]
        self.arg_code = VarCode("argument")
        if s.mtype is Tok.METHOD:
            self.arg_code.next()
        self.loc_code = VarCode("local")
        fvars: dict[str, VarSym] = {}
        for arg in s.args:
            ty = self.get_type(arg)
            name = arg.names[0]
            if name.value in fvars:
                raise redef_error(name)
            fvars[name.value] = VarSym(ty, self.arg_code.next())
        for loc in s.locs:
            ty = self.get_type(loc)
            for name in loc.names:
                if name.value in fvars:
                    raise redef_error(name)
                fvars[name.value] = VarSym(ty, self.loc_code.next())
        self.fvars = fvars

    def check_call(self, call: Call):
        pass


class Generator:
    def __init__(self, f: TextIO = None):
        self.f: TextIO = f or sys.stdout
        self.syms: SymTable = SymTable()

    def generate(self, node: Program) -> None:
        try:
            for c in node.classes:
                self.syms.add_subs(c)
            for c in node.classes:
                self.generate_class(c)
        except ParseError as e:
            raise ParseError(f"module {c.module}: {e}") from e

    def generate_class(self, node: Class) -> None:
        self.syms.add_class(node)
        for sub in node.subs:
            self.generate_sub(sub)

    def generate_sub(self, node: Subroutine) -> None:
        self.syms.add_sub(node)
        # TODO: if ctor, return type must be classname
        self.write(f"function {self.syms.label()} {len(node.locs)}")
        if node.mtype is Tok.METHOD:
            self.write("push argument 0")
            self.write("pop pointer 0")
        elif node.mtype is Tok.CTOR:
            self.write("push constant {self.syms.field_count()}")
            self.write("call Memory.alloc 1")
            self.write("pop pointer 0")
        for stmt in node.stmts:
            self.generate_stmt(stmt)

    @singledispatchmethod
    def generate_stmt(self, stmt) -> None:
        raise NotImplementedError(f"cannot generate statement {type(stmt)}")

    @generate_stmt.register
    def _(self, node: LetStmt) -> None:
        match node.lvalue:
            case Var(name):
                sym = self.syms.var_code(name)
                self.generate_expr(node.expr)
                self.write(f"pop {sym.code}")
            case Subscript(name, idx):
                sym = self.syms.arr_code(name)
                self.generate_expr(node.expr)
                self.write(f"push {sym.code}")
                self.generate_expr(idx)
                self.write("add")
                self.write("pop pointer 1")
                self.write("pop that 0")

    @generate_stmt.register
    def _(self, node: DoStmt) -> None:
        pass

    @generate_stmt.register
    def _(self, node: WhileStmt) -> None:
        lbl = self.syms.label("while")
        self.write(f"label {lbl}_check")
        self.generate_expr(node.expr)
        self.write(f"if-goto {lbl}_do")
        self.write(f"goto {lbl}_done")
        for stmt in node.stmts:
            self.generate_stmt(stmt)
        self.write(f"goto {lbl}_check")
        self.write(f"label {lbl}_done")

    @generate_stmt.register
    def _(self, node: IfStmt) -> None:
        lbl = self.syms.label("if")
        self.generate_expr(node.expr)
        self.write(f"if-goto {lbl}_true")
        if node.false:
            for stmt in node.false:
                self.generate_stmt(stmt)
        self.write(f"goto {lbl}_done")
        self.write(f"label {lbl}_true")
        for stmt in node.true:
            self.generate_stmt(stmt)
        self.write(f"label {lbl}_done")

    @generate_stmt.register
    def _(self, node: RetStmt) -> None:
        # TODO: void must have None expr
        # TODO: constructor must return this or obj of right type
        if not node.expr:
            self.write("push constant 0")
        else:
            self.generate_expr(node.expr)

    def generate_expr(self, expr: Expr) -> None:
        self.generate_term(expr.terms[0])
        for (term, op) in zip(expr.terms[1:], expr.ops):
            pass

    def write(self, cmd: str) -> None:
        # self.f.write(f"{cmd}\n")
        pass


def test(dirname):
    from pathlib import Path

    p = Path(dirname)
    prog = Program()
    files = p.glob("*.jack")
    for file in files:
        with open(file) as f:
            lines = f.readlines()
        module = file.stem
        prog.parse_module(module, lines)
    g = Generator()
    g.generate(prog)
    return (prog, g)
