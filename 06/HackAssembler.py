import re
import sys
from dataclasses import dataclass

@dataclass
class Const:
    symbol: str

@dataclass
class Label:
    symbol: str

@dataclass
class AInstruction:
    symbol: Const | Label

@dataclass
class LInstruction:
    symbol: str

@dataclass
class CInstruction:
    dest: str
    comp: str
    jump: str

@dataclass
class Error:
    msg: str

class Parser:
    const = re.compile(r'\d+')
    label = re.compile(r'[a-zA-Z.$:][\w.$:]*')
    dest = re.compile(r'[ADM]+')
    jmp = ['', 'JGT', 'JEQ', 'JGE', 'JLT', 'JNE', 'JLE', 'JMP']
    comp = {'0': '0101010',
            '1': '0111111',
            '-1': '0111010',
            'D': '0001100',
            'A': '0110000', 'M': '1110000',
            '!D': '0001101',
            '!A': '0110001', '!M': '1110001',
            '-D': '0001111',
            '-A': '0110011', '-M': '1110011',
            'D+1': '0011111',
            'A+1': '0110111', 'M+1': '1110111',
            'D-1': '0001110',
            'A-1': '0110010', 'M-1': '1110010',
            'D+A': '0000010', 'D+M': '1000010',
            'D-A': '0010011', 'D-M': '1010011',
            'A-D': '0000111', 'M-D': '1000111',
            'D&A': '0000000', 'D&M': '1000000',
            'D|A': '0010101', 'D|M': '1010101'}
    
    def __init__(self, filename):
        def strip(line):
            # remove comments and ALL whitespace (see reference implementation)
            return ''.join(line.split('//')[0].split())
            
        with open(filename) as f:
            self.lines = [line for l in f.readlines()
                          if (line := strip(l)) != '']
            
    def parse(self):
        lineno = 0
        while self.lines:
            lineno = lineno + 1
            line = self.lines.pop(0)
            inst = None
            match line[0]:
                case '(':
                    inst = self.lInstruction(line)
                case '@':
                    inst = self.aInstruction(line)
                case _:
                    inst = self.cInstruction(line)
            match inst:
                case Error(msg):
                    yield Error(f'Line {lineno}: {msg}')
                case _:
                    yield inst

    @staticmethod
    def symbol(line):
        if re.fullmatch(Parser.const, line):
            if int(line) > 32767:
                return Error('constant too large')
            return Const(line)
        elif re.fullmatch(Parser.label, line):
            return Label(line)
        else:
            return Error('invalid symbol')

    @staticmethod
    def lInstruction(line):
        end = line.find(')')
        if end == len(line) - 1:
            if re.fullmatch(Parser.label, line[1:end]):
                return LInstruction(line[1:end])
            else:
                return Error(f'invalid label "{line[1:end]}"')
        elif end == -1:
            return Error('unexpected end of label')
        else:
            return Error(f'expected end of label, found "{line[end:]}"')

    @staticmethod
    def aInstruction(line):
        match Parser.symbol(line[1:]):
            case Error(_) as e:
                return e
            case _ as s:
                return AInstruction(s)

    @staticmethod
    def cInstruction(line):
        dest = ''
        jmp = ''
        if (d := line.find('=')) != -1:
            dest, line = line[:d], line[d+1:]
        if (d := line.find(';')) != -1:
            line, jmp = line[:d], line[d+1:]
            
        if not line:
            return Error('missing computation')
        if (comp := Parser.comp.get(line)) is None:
            return Error(f'invalid computation "{line}"')
        
        if dest:
            if (not re.fullmatch(Parser.dest, dest)
                or len(set(dest)) != len(list(dest))):
                return Error(f'invalid destination "{dest}"')
        dest = ''.join(map(lambda c: ['0', '1'][c in dest], 'ADM'))

        try:
            j = Parser.jmp.index(jmp)
        except ValueError:
            return Error(f'invalid jump "{jmp}"')
        jmp = format(j, '03b')
        
        return CInstruction(dest, comp, jmp)

def assemble(parser, symbols):
    insts = []
    lineno = 0
    for inst in parser.parse():
        match inst:
            case LInstruction(label):
                symbols[label] = lineno
            case _:
                lineno = lineno + 1
                insts.append(inst)

    nextsym = 16
    for inst in insts:
        match inst:
            case Error(msg):
                raise Exception(msg)
            case AInstruction(symbol):
                match symbol:
                    case Const(s):
                        data = int(s)
                    case Label(s):
                        if s not in symbols:
                            symbols[s] = nextsym
                            nextsym = nextsym + 1                
                        data = symbols[s]
                yield format(data, '016b')
            case CInstruction(dest, comp, jmp):
                yield '111' + comp + dest + jmp                
                        
SYMBOLS = {'R0': 0, 'R1': 1, 'R2': 2, 'R3': 3,
           'R4': 4, 'R5': 5, 'R6': 6, 'R7': 7,
           'R8': 8, 'R9': 9, 'R10': 10, 'R11': 11,
           'R12': 12, 'R13': 13, 'R14': 14, 'R15': 15,
           'SCREEN': 16384, 'KBD': 24576}

def main():
    usage = f'usage: {sys.argv[0]} input_file.asm'
    args = sys.argv[1:]
    if not args or len(args) > 1:
        return usage
    asm = args[0]
    if asm.endswith('.asm'):
        hack = asm[:-4] + '.hack'
    else:
        return usage

    symbols = {'SP': 0, 'LCL': 1, 'ARG': 2, 'THIS': 3, 'THAT': 4,
               **SYMBOLS}

    try:
        with open(hack, 'w') as f:
            f.writelines('\n'.join(assemble(Parser(asm), symbols)))
    except Exception as e:
        return str(e)
        
if __name__ == '__main__':
    sys.exit(main())
