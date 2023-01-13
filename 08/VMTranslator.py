import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Error:
    msg: str


@dataclass
class Fixed:
    pass


@dataclass
class Floating:
    base: str


@dataclass
class Const:
    pass


@dataclass
class Segment:
    seg: Const | Fixed | Floating


@dataclass
class Push:
    seg: Segment
    idx: str


@dataclass
class Pop:
    seg: Segment
    idx: str


@dataclass
class UnaryOp:
    op: str


@dataclass
class BinaryOp:
    op: str


@dataclass
class CompOp:
    op: str


@dataclass
class Branch:
    op: str
    symbol: str


@dataclass
class Function:
    op: str
    name: str
    nArgs: int


@dataclass
class Return:
    pass


class Parser:
    label = re.compile(r"[a-zA-Z.$:][\w.$:]*")

    def __init__(self, module, lines):
        self.module = module
        self.lines = lines

    def parse(self):
        filename = self.module + ".vm"
        lines = [l.split("//")[0].strip() for l in self.lines]
        for lineno, line in enumerate(lines):
            if not line:
                continue
            line = line.split()
            inst = Error("unknown instruction")
            op, args = line[0], line[1:]
            match op:
                case "push" | "pop":
                    inst = self.stack(op, args)
                case "neg" | "not":
                    inst = self.unaryOp(op, args)
                case "add" | "sub" | "and" | "or":
                    inst = self.binaryOp(op, args)
                case "eq" | "lt" | "gt":
                    inst = self.compOp(op, args)
                case "label" | "goto" | "if-goto":
                    inst = self.branch(op, args)
                case "function" | "call":
                    inst = self.function(op, args)
                case "return":
                    inst = self.ret(args)
            match inst:
                case Error(msg):
                    yield Error(f"{filename} line {lineno+1}: {msg}")
                case _:
                    yield inst

    @staticmethod
    def getInt(s):
        try:
            return int(s)
        except ValueError:
            return -1

    def stack(self, op, args):
        if len(args) != 2:
            return Error(f"{op} takes 2 arguments")
        idx = Parser.getInt(args[1])
        if idx < 0:
            return Error("index must be a non-negative integer")

        match args[0]:
            case "argument":
                seg = Floating("ARG")
            case "local":
                seg = Floating("LCL")
            case "static":
                seg = Fixed()
                idx = f"{self.module}.{idx}"
            case "constant":
                if op == "pop":
                    return Error("you cannot pop to a constant")
                seg = Const()
            case "this":
                seg = Floating("THIS")
            case "that":
                seg = Floating("THAT")
            case "pointer":
                seg = Fixed()
                idx = idx + 3
            case "temp":
                seg = Fixed()
                idx = idx + 5
            case "_":
                return Error(f'unknown segment "{seg}"')
        if op == "push":
            return Push(seg, str(idx))
        else:
            return Pop(seg, str(idx))

    def unaryOp(self, op, args):
        if args:
            return Error(f"{op} takes no arguments")
        return UnaryOp(op)

    def binaryOp(self, op, args):
        if args:
            return Error(f"{op} takes no arguments")
        return BinaryOp(op)

    def compOp(self, op, args):
        if args:
            return Error(f"{op} takes no arguments")
        return CompOp(op)

    def branch(self, op, args):
        if len(args) != 1:
            return Error(f"{op} takes 1 argument")
        if not re.fullmatch(Parser.label, args[0]):
            return Error("invalid label")
        return Branch(op, args[0])

    def function(self, op, args):
        if len(args) != 2:
            return Error(f"{op} takes two arguments")
        if (nArgs := Parser.getInt(args[1])) < 0:
            return Error("nArgs must be a non-negative integer")
        if not re.fullmatch(Parser.label, args[0]):
            return Error("invalid function name")
        return Function(op, args[0], nArgs)

    def ret(self, args):
        if args:
            return Error("return takes no arguments")
        return Return()


class Translator:
    bootstrap = (
        "@261      \n"  # to satisfy test scripts
        "D=A       \n"
        "@SP       \n"
        "M=D       \n"
        "@Sys.init \n"
        "0;JMP     \n"
    )

    ops = {
        "add": "+",
        "sub": "-",
        "and": "&",
        "or": "|",
        "neg": "-",
        "not": "!",
        "eq": "JEQ",
        "lt": "JLT",
        "gt": "JGT",
    }

    def __init__(self, parser):
        self.cmds = parser.parse()
        self.module = parser.module
        self.next_cmp = 0
        self.next_ret = 0
        self.funcname = None

    def translate(self):
        for cmd in self.cmds:
            match cmd:
                case Error(msg):
                    raise Exception(msg)
                case Push(seg, idx):
                    yield self.push(seg, idx)
                case Pop(seg, idx):
                    yield self.pop(seg, idx)
                case UnaryOp(op):
                    yield self.unaryOp(op)
                case BinaryOp(op):
                    yield self.binaryOp(op)
                case CompOp(op):
                    yield self.compOp(op)
                case Branch("label", symbol):
                    yield self.label(symbol)
                case Branch("goto", symbol):
                    yield self.goto(symbol)
                case Branch("if-goto", symbol):
                    yield self.ifGoto(symbol)
                case Function("function", name, nArgs):
                    yield self.function(name, nArgs)
                case Function("call", name, nArgs):
                    yield self.call(name, nArgs)
                case Return():
                    yield self.ret()

    def push(self, seg, idx):
        match seg:
            case Floating(base):
                # microoptimize when idx = 0 or 1
                load = (
                    f"@{base} \n" "D=M     \n" f"@{idx}  \n" "A=D+A   \n" "D=M     \n"
                )
            case Fixed():
                load = f"@{idx}  \n" "D=M     \n"
            case Const():
                load = f"@{idx}  \n" "D=A     \n"
        return load + ("@SP   \n" "M=M+1 \n" "A=M-1 \n" "M=D   \n")

    def pop(self, seg, idx):
        match seg:
            case Floating(base):
                # microoptimize when idx = 0 or 1
                return (
                    f"@{base} \n"
                    "D=M     \n"
                    f"@{idx}  \n"
                    "D=D+A   \n"
                    "@SP     \n"
                    "AM=M-1   \n"
                    "D=D+M   \n"
                    "A=D-M   \n"
                    "M=D-A   \n"
                )
            case Fixed():
                return (
                    f"@SP     \n" "AM=M-1  \n" "D=M     \n" f"@{idx}  \n" "M=D     \n"
                )

    def unaryOp(self, op):
        op = Translator.ops[op]
        return f"@SP     \n" "A=M-1   \n" f"M={op}M \n"

    def binaryOp(self, op):
        op = Translator.ops[op]
        if op == "-":
            action = "M=M-D     \n"
        else:
            action = f"M=D{op}M \n"
        return ("@SP     \n" "AM=M-1  \n" "D=M     \n" "A=A-1   \n") + action

    def compOp(self, op):
        self.next_cmp = self.next_cmp + 1
        label = f"{self.module}${op}.{self.next_cmp}"
        op = Translator.ops[op]
        return (
            f"@SP       \n"
            "AM=M-1    \n"
            "D=M       \n"
            "A=A-1     \n"
            "D=M-D     \n"
            "M=-1      \n"
            f"@{label}  \n"
            f"D;{op}    \n"
            "@SP       \n"
            "A=M-1     \n"
            "M=0       \n"
            f"({label}) \n"
        )

    def makeLabel(self, symbol):
        return f"{self.funcname}${symbol}"

    def label(self, symbol):
        return f"({self.makeLabel(symbol)}) \n"

    def goto(self, symbol):
        label = self.makeLabel(symbol)
        return f"@{label} \n" "0;JMP    \n"

    def ifGoto(self, symbol):
        label = self.makeLabel(symbol)
        return f"@SP      \n" "AM=M-1   \n" "D=M      \n" f"@{label} \n" "D;JNE    \n"

    def function(self, name, nArgs):
        self.funcname = name
        self.next_ret = 0
        insts = (
            f"({self.funcname}) \n"
            + ("@SP   \n" "M=M+1 \n" "A=M-1 \n" "M=0   \n") * nArgs
        )
        # microoptimization: M=0/A=A+1 nArgs times then set SP
        return insts

    def call(self, name, nArgs):
        self.next_ret = self.next_ret + 1
        ret = self.makeLabel(f"ret.{self.next_ret}")
        return (
            f"@{ret}     \n"
            "D=A        \n"
            "@SP        \n"
            "M=M+1      \n"
            "A=M-1      \n"
            "M=D        \n"
            "@LCL       \n"
            "D=M        \n"
            "@SP        \n"
            "M=M+1      \n"
            "A=M-1      \n"
            "M=D        \n"
            "@ARG       \n"
            "D=M        \n"
            "@SP        \n"
            "M=M+1      \n"
            "A=M-1      \n"
            "M=D        \n"
            "@THIS      \n"
            "D=M        \n"
            "@SP        \n"
            "M=M+1      \n"
            "A=M-1      \n"
            "M=D        \n"
            "@THAT      \n"
            "D=M        \n"
            "@SP        \n"
            "M=M+1      \n"
            "A=M-1      \n"
            "M=D        \n"
            "D=A        \n"
            f"@{4+nArgs} \n"
            "D=D-A      \n"
            "@ARG       \n"
            "M=D        \n"
            "@SP        \n"
            "D=M        \n"
            "@LCL       \n"
            "M=D        \n"
            f"@{name}    \n"
            "0;JMP      \n"
            f"({ret})    \n"
        )

    def ret(self):
        return (
            "@LCL   \n"
            "D=M    \n"
            "@R13   \n"
            "M=D    \n"
            "@5     \n"
            "A=D-A  \n"
            "D=M    \n"
            "@R14   \n"
            "M=D    \n"
            "@SP    \n"
            "A=M-1  \n"
            "D=M    \n"
            "@ARG   \n"
            "A=M    \n"
            "M=D    \n"
            "D=A    \n"
            "@SP    \n"
            "M=D+1  \n"
            "@R13   \n"
            "AM=M-1 \n"
            "D=M    \n"
            "@THAT  \n"
            "M=D    \n"
            "@R13   \n"
            "AM=M-1 \n"
            "D=M    \n"
            "@THIS  \n"
            "M=D    \n"
            "@R13   \n"
            "AM=M-1 \n"
            "D=M    \n"
            "@ARG   \n"
            "M=D    \n"
            "@R13   \n"
            "AM=M-1 \n"
            "D=M    \n"
            "@LCL   \n"
            "M=D    \n"
            "@R14   \n"
            "A=M    \n"
            "0;JMP  \n"
        )


def main():
    usage = f"usage: {sys.argv[0]} [input_file.vm | input_dir]"
    args = sys.argv[1:]
    if not args or len(args) > 1:
        return usage

    vm = Path(args[0])
    if vm.is_dir():
        files = vm.glob("*.vm")
        asm = vm.joinpath(vm.name).with_suffix(".asm")
    elif vm.suffix == ".vm":
        files = [vm]
        asm = vm.with_suffix(".asm")
    else:
        return usage

    of = tempfile.NamedTemporaryFile(mode="wt", dir=os.getcwd(), delete=False)
    try:
        of.writelines(Translator.bootstrap)
        for vm in files:
            module = vm.stem
            with open(vm) as f:
                p = Parser(module, f.readlines())
            t = Translator(p)
            of.writelines(t.translate())
    except Exception as err:
        of.close()
        os.remove(of.name)
        return str(err)
    of.close()
    shutil.move(of.name, asm)


if __name__ == "__main__":
    sys.exit(main())
