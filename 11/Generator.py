from jack_parser import *
from functools import singledispatchmethod
from typing import Tuple, NamedTuple, TextIO
import sys


def redef_error(name: Name) -> ParseError:
    return ParseError(f"line {name.line}: {name.value} redefined")


def undef_error(name: Name) -> ParseError:
    return ParseError(f"line {name.line}: {name.value} undefined")


def array_error(name: Name) -> ParseError:
    return ParseError(
        f"line {name.line}: cannot subscript builtin {name.value}"
    )


def parse_error(name: Name, msg: str) -> ParseError:
    return ParseError(f"line {name.line}: {name.value} {msg}")


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
                "abs": 1,
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

        self.func_decl: Decl | None = None
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
        lbl = f"{self.class_name}.{self.func_decl.names[0].value}"
        if suffix:
            self.label_id = self.label_id + 1
            return f"{lbl}.{suffix}_{self.label_id}"
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
                raise parse_error(name, "does not implement builtin")
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
        self.func_decl = s.decl
        self.label_id = 0
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

    def check_call(self, call: Call) -> Tuple[str, str]:
        name0 = call.names[0]
        if len(call.names) == 2:
            name1 = call.names[1]
            scope = self.subs.get(name0.value, None) or self.OS.get(
                name0.value, None
            )
            if scope:
                try:
                    nargs = scope.cm_names[name1.value]
                except ValueError:
                    raise parse_error(name1, "is not a class method")
                if nargs != len(call.params):
                    raise parse_error(name1, "takes {len(call.params)} args")
                return ("", f"{name0.value}.{name1.value}")

        if len(call.names) == 2:
            try:
                var = self.var_code(name0)
            except:
                raise parse_error(name0, "is not a variable")
            ty = var.ty
            pcode = var.code
            fname = name1
        else:
            ty = self.class_name
            pcode = "argument 0"
            fname = name0

        # fname must be instance method of type
        scope = self.subs[ty]
        try:
            nargs = scope.im_names[fname.value]
        except ValueError:
            raise parse_error(fname, "is not an instance method")
        if nargs != len(call.params):
            raise parse_error(fname, "takes {len(call.params)} args")
        return (pcode, f"{ty}.{fname.value}")


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
        if not isinstance(node.stmts[-1], RetStmt):
            raise parse_error(node.decl.names[0], "must end with return")
        self.write(f"function {self.syms.label()} {len(node.locs)}")
        if node.mtype is Tok.METHOD:
            self.write("push argument 0")
            self.write("pop pointer 0")
        elif node.mtype is Tok.CTOR:
            cname = node.decl.class_name()
            if cname.value != self.syms.class_name:
                raise parse_error(cname, f" is invalid ctor return type")
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
        self.generate_texpr(node.call)
        self.write("pop temp 0")

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
        void = self.syms.func_decl.ty is Tok.VOID
        fname = self.syms.func_decl.names[0].value
        if not node.expr:
            if not void:
                raise ParseError(f"line {node.lno}: {fname} is not void")
            self.write("push constant 0")
        else:
            if void:
                raise ParseError(f"line {node.lno}: {fname} is void")
            self.generate_expr(node.expr)
        self.write("return")

    def generate_expr(self, expr: Expr) -> None:
        self.generate_term(expr.terms[0])
        for (term, op) in zip(expr.terms[1:], expr.ops):
            self.generate_term(term)
            if op is Tok.PLUS:
                self.write("add")
            elif op is Tok.MINUS:
                self.write("sub")
            elif op is Tok.AND:
                self.write("and")
            elif op is Tok.OR:
                self.write("or")
            elif op is Tok.EQ:
                self.write("eq")
            elif op is Tok.LT:
                self.write("lt")
            elif op is Tok.GT:
                self.write("gt")
            elif op is Tok.DIV:
                self.write("call Math.divide 2")
            elif op is Tok.MUL:
                self.write("call Math.multiply 2")

    def generate_term(self, term: Term):
        self.generate_texpr(term.expr)
        if term.unary == "-":
            self.write("neg")
        elif term.unary == "~":
            self.write("not")

    @singledispatchmethod
    def generate_texpr(self, term) -> None:
        raise NotImplementedError(f"cannot generate {type(term)}")

    @generate_texpr.register
    def _(self, expr: Expr) -> None:
        self.generate_expr(expr)

    @generate_texpr.register
    def _(self, expr: Const) -> None:
        if expr.type == "int":
            self.write(f"push const {expr.val}")
        elif expr.type == "str":
            # TODO: charset
            self.write(f"push const {len(expr.val)}")
            self.write("call String.new 1")
            for char in expr.val:
                self.write(f"push const {ord(char)}")
                self.write("call String.appendChar 1")
            pass
        else:
            match expr.val:
                case "true":
                    self.write("push const 1")
                case "false" | "null":
                    self.write("push const 0")
                case "this":
                    self.write("push pointer 0")

    @generate_texpr.register
    def _(self, expr: Var) -> None:
        sym = self.syms.var_code(expr.name)
        self.write(f"push {sym.code}")

    @generate_texpr.register
    def _(self, expr: Call) -> None:
        (pcode, fname) = self.syms.check_call(expr)
        nargs = len(expr.params)
        if pcode:
            if pcode == "argument 0":
                nargs = nargs + 1
            self.write(f"push {pcode}")
        self.write(f"call {fname} {nargs}")

    @generate_texpr.register
    def _(self, expr: Subscript) -> None:
        sym = self.syms.arr_code(expr.name)
        self.write(f"push {sym.code}")
        self.generate_expr(expr.idx)
        self.write("add")
        self.write("pop pointer 1")
        self.write("push that 0")

    def write(self, cmd: str) -> None:
        self.f.write(f"{cmd}\n")


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
