from jack_parser import *
from functools import singledispatchmethod
from typing import NamedTuple, TextIO
import sys


def redef_error(name: Name) -> ParseError:
    return ParseError(f"line {name.line}: {name.value} redefined")


class SubSym(NamedTuple):
    cm_names: dict[str, int]
    im_names: dict[str, int]

    def conforms(self, other: "SubSym") -> bool:
        return (
            self.cm_names.items() >= other.cm_names.items()
            and self.im_names.items() >= other.im_names.items()
        )


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

    def check_call(self, call: Call):
        pass


class Generator:
    def __init__(self, f: TextIO = None):
        self.f: TextIO = f or sys.stdout
        self.syms: SymTable = SymTable()

    @singledispatchmethod
    def generate(self, node) -> None:
        raise NotImplementedError(f"Cannot generate {type(node)}")

    @generate.register
    def _(self, node: Program) -> None:
        for c in node.classes:
            try:
                self.syms.add_subs(c)
            except ParseError as e:
                raise ParseError(f"module {c.module}: {e}") from e

        for c in node.classes:
            self.generate(c)

    @generate.register
    def _(self, node: Class) -> None:
        self.syms.class_name = node.name.value


def test(filename):
    from pathlib import Path

    p = Path(filename)
    with open(p) as f:
        lines = f.readlines()
    module = p.stem
    prog = Program()
    prog.parse_module(module, lines)
    g = Generator()
    g.generate(prog)
    return (prog, g)
