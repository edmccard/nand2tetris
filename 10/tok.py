import re
from enum import Enum

Tok = Enum('Tok',
           [('ERR', 1), ('STR', 2), ('ID', 3), ('NUM', 4),
            ('LC', '{'), ('RC', '}'),
            ('LB', '['), ('RB', ']'),
            ('LP', '('), ('RP', ')'),
            ('DOT', '.'), ('COMMA', ','), ('SEMI', ';'),
            ('PLUS', '+'), ('MINUS', '-'), ('MUL', '*'), ('DIV', '/'),
            ('AND', '&'), ('OR', '|'), ('NOT', '~'),
            ('LT', '<'), ('GT', '>'), ('EQ', '='),
            ('CLS', 'class'), ('CTOR', 'constructor'), ('FN', 'function'),
            ('METHOD', 'method'), ('FIELD', 'field'), ('STATIC', 'static'),
            ('VAR', 'var'), ('INT', 'int'), ('CHAR', 'char'),
            ('BOOL', 'boolean'), ('VOID', 'void'), ('TRUE', 'true'),
            ('FALSE', 'false'), ('NULL', 'null'), ('THIS', 'this'),
            ('LET', 'let'), ('DO', 'do'), ('IF', 'if'),
            ('ELSE', 'else'), ('WHILE', 'while'), ('RETURN', 'return')])

TokTy = Enum('TokTy',
             [('KWD', 'keyword'), ('STR', 'stringConstant'),
              ('NUM', 'integerConstant'), ('SYM', 'symbol'),
              ('ID', 'identifier'), ('ERR', 'error')])

class LineTokenizer:
    IDENT = re.compile(r'[A-Za-z]\w*', re.ASCII)
    WS = re.compile(r'\s+', re.ASCII)
    NUM = re.compile(r'\d+', re.ASCII)

    TOKENS = {t.value: t for t in Tok}

    def __init__(self, line, in_cc):
        self.line = line
        self.p = 0
        self.in_cc = in_cc
        
    def tokenize(self):
        in_cc = self.in_cc
        length = len(self.line)
        while self.p < length:
            if in_cc:
                if self.search('*/') is not None:
                    in_cc = False
                else:
                    break
            elif self.rmatch(self.WS):
                pass
            elif self.match('/*'):
                in_cc = True
            elif self.match('//'):
                break
            elif self.match('"'):
                if (txt := self.search('"')) is not None:
                    yield (TokTy.STR, Tok.STR, txt)
                else:
                    yield (TokTy.ERR, Tok.ERR, 'unterminated string')
                    break
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
                yield (TokTy.ERR, Tok.ERR, 'invalid character')
        self.in_cc = in_cc
        
    def match(self, s):
        slen = len(s)
        if self.line[self.p:self.p+slen] == s:
            self.p = self.p + slen
            return True

    def search(self, s):
        idx = self.line.find(s, self.p)
        if idx != -1:
            txt = self.line[self.p:idx]
            self.p = idx + len(s)
            return txt

    def rmatch(self, pat):
        if mo := pat.match(self.line, self.p):            
            self.p = mo.end()
            return mo.group()
        return None

def tokenize(lines):
    in_cc = False
    for lno, line in enumerate(lines, 1):
        tokenizer = LineTokenizer(line, in_cc)
        yield from map(lambda t: (t +(lno,)),
                       tokenizer.tokenize())
        in_cc = tokenizer.in_cc
    if in_cc:
        yield (TokTy.ERR, Tok.ERR, 'unterminated comment', lno)

def test_xml(tokens):
    with open('test.xml', 'w') as f:
        f.write('<tokens>\n')
        for token in tokens:
            ty = token[0].value
            if token[2] == '>':
                txt = '&gt;'
            elif token[2] == '<':
                txt = '&lt;'
            elif token[2] == '&':
                txt = '&amp;'
            else:
                txt = token[2]
            f.write(f'<{ty}> {txt} </{ty}>\n')
        f.write('</tokens>\n')
