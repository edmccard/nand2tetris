import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Error:
    msg: str

@dataclass
class Fixed: pass

@dataclass
class Floating:
    base: str

@dataclass
class Const: pass

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

class Parser:
    label = re.compile(r'[a-zA-Z.$:][\w.$:]*')

    def __init__(self, module, lines):
        self.module = module
        self.lines = lines

    def parse(self):
        filename = self.module + ".vm"
        lines = [line for l in self.lines
                 if (line := l.split('//')[0].strip()) != '']
        for lineno, line in enumerate(lines):
            line = line.split()
            inst = Error('unknown instruction')
            op, args = line[0], line[1:]
            match op:
                case 'push' | 'pop':
                    if len(args) != 2:
                        inst = Error(f'{op} takes 2 arguments')
                    else:   
                        inst = self.stack(op, args)
                case 'neg' | 'not':
                    if args:
                        inst = Error(f'{op} takes no arguments')
                    else:
                        inst = UnaryOp(op)
                case 'add' | 'sub' | 'and' | 'or':
                    if args:
                        inst = Error(f'{op} takes no arguments')
                    else:
                        inst = BinaryOp(op)
                case 'eq' | 'lt' | 'gt':
                    if args:
                        inst = Error(f'{op} takes no arguments')
                    else:
                        inst = CompOp(op)
                case 'label' | 'goto' | 'if-goto':
                    if len(args) != 1:
                        inst = Error(f'{op} takes 1 argument')
                    elif not re.fullmatch(Parser.label, args[0]):
                        inst = Error('invalid label')
                    else:
                        inst = Branch(op, args[0])
            match inst:
                case Error(msg):
                    yield Error(f'{filename} line {lineno+1}: {msg}')
                case _:
                    yield inst                                    

    def stack(self, op, args):
        try:
            idx = int(args[1])
        except ValueError:
            idx = -1
        if idx < 0:
            return Error('index must be a non-negative integer')

        match args[0]:
            case 'argument':
                seg = Floating('ARG')
            case 'local':
                seg = Floating('LCL')
            case 'static':
                seg = Fixed()
                idx = f'{self.module}.{idx}'
            case 'constant':
                if op == 'pop':
                    return Error('you cannot pop to a constant')
                seg = Const()
            case 'this':
                seg = Floating('THIS')
            case 'that':
                seg = Floating('THAT')
            case 'pointer':
                seg = Fixed()
                idx = idx + 3
            case 'temp':
                seg = Fixed()
                idx = idx + 5
            case '_':
                return Error(f'unknown segment "{seg}"')
        if op == 'push':
            return Push(seg, str(idx))
        else:
            return Pop(seg, str(idx))

class Translator:
    ops = {'add': '+', 'sub': '-', 'and': '&', 'or': '|',
           'neg': '-', 'not': '!',
           'eq': 'JEQ', 'lt': 'JLT', 'gt': 'JGT'}

    def __init__(self, parser):
        self.cmds = parser.parse()
        self.module = parser.module
        self.next_cmp = 0
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
                case Branch('label', symbol):
                    yield self.label(symbol)
                case Branch('goto', symbol):
                    yield self.goto(symbol)
                case Branch('if-goto', symbol):
                    yield self.ifGoto(symbol)

    def push(self, seg, idx):
        match seg:
            case Floating(base):
                load = (f'@{base} \n'
                         'D=M     \n'
                        f'@{idx}  \n'
                         'A=D+A   \n'
                         'D=M     \n')
            case Fixed():
                load = (f'@{idx}  \n'
                         'D=M     \n')
            case Const():
                load = (f'@{idx}  \n'
                         'D=A     \n')
        return load + ('@SP   \n'
                       'M=M+1 \n'
                       'A=M-1 \n'
                       'M=D   \n')

    def pop(self, seg, idx):
        match seg:
            case Floating(base):
                return (f'@{base} \n'
                         'D=M     \n'
                        f'@{idx}  \n'
                         'D=D+A   \n'
                         '@SP     \n'
                         'M=M-1   \n'
                         'A=M     \n'
                         'D=D+M   \n'
                         'A=D-M   \n'
                         'M=D-A   \n')
            case Fixed():
                return (f'@SP     \n'
                         'M=M-1   \n'
                         'A=M     \n'
                         'D=M     \n'
                        f'@{idx}  \n'
                         'M=D     \n')

    def unaryOp(self, op):
        op = Translator.ops[op]
        return (f'@SP     \n'
                 'A=M-1   \n'
                f'M={op}M \n')

    def binaryOp(self, op):
        op = Translator.ops[op]
        if op == '-':
            action = 'M=M-D     \n'
        else:
            action = f'M=D{op}M \n'
        return ('@SP     \n'
                'AM=M-1  \n'
                'D=M     \n'
                'A=A-1   \n') + action

    def compOp(self, op):
        self.next_cmp = self.next_cmp + 1
        label = f'{self.module}${op}.{self.next_cmp}'
        op = Translator.ops[op]
        return (f'@SP       \n'
                 'AM=M-1    \n'
                 'D=M       \n'
                 'A=A-1     \n'
                 'D=M-D     \n'
                 'M=-1      \n'
                f'@{label}  \n'
                f'D;{op}    \n'
                 '@SP       \n'
                 'A=M-1     \n'
                 'M=0       \n'
                f'({label}) \n')

    def makeLabel(self, symbol):
        return f'{self.module}.{self.funcname}${symbol}'
    
    def label(self, symbol):
        return f'({self.makeLabel(symbol)}) \n'

    def goto(self, symbol):
        label = self.makeLabel(symbol)
        return (f'@{label} \n'
                 '0;JMP    \n')

    def ifGoto(self, symbol):
        label = self.makeLabel(symbol)
        return (f'@SP      \n'
                 'AM=M-1   \n'
                 'D=M      \n'
                f'@{label} \n'
                 'D;JNE    \n')

def main():
    usage = f'usage: {sys.argv[0]} input_file.vm'
    args = sys.argv[1:]
    if not args or len(args) > 1:
        return usage
    vm = args[0]
    if vm.endswith('.vm'):
        module = Path(vm).stem
        asm = vm[:-3] + '.asm'
    else:
        return usage

    with tempfile.NamedTemporaryFile(mode='wt', dir=os.getcwd(), delete=False) as of:
        with open(vm) as f:
            p = Parser(module, f.readlines())
        t = Translator(p)
        try:
            of.writelines(t.translate())
        except Exception as err:
            os.remove(of.name)
            return str(err)
        of.close()
        os.rename(of.name, asm)

if __name__ == '__main__':
    sys.exit(main())
