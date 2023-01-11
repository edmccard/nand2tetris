class Class:
    def __init__(self):
        self.name = None
        self.vars = []
        self.subs = []

class ClassVar:
    def __init__(self):
        self.scope = None
        self.ty = None
        self.names = []

class Subroutine:
    def __init__(self):
        self.category = None
        self.ty = None
        self.name = None
        self.params = []
        self.vars = []
        self.stmts = []