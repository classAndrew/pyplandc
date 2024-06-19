from typing import List, Set
from dataclasses import dataclass
from collections import namedtuple

VarScopedName = namedtuple("VarScopedName", ["block_idx", "idx_in_block", "name"])

def indent_newlines(s: str) -> str:
    return s.replace('\n', '\n  ')

@dataclass(kw_only=True)
class ASTNode: 
    line_number: int = None
    char_number: int = None

@dataclass(kw_only=True)
class TypeableASTNode(ASTNode):
    is_type_checked: bool = False
    _inferred_type: str = None

    def set_inferred_type(self, inferred_type):
        assert not self.is_type_checked
        self.is_type_checked = True
        self._inferred_type = inferred_type
    
    def get_inferred_type(self):
        assert self.is_type_checked
        return self._inferred_type

@dataclass
class LiteralNode(TypeableASTNode):
    val: object
    
    def __str__(self) -> str:
        return str(self.val)
    
    def pretty_ast(self) -> str:
        return f"{self.get_inferred_type() if self.is_type_checked else 'untyped'} Literal: {self.val}"

@dataclass
class VarNode(TypeableASTNode):
    name: str
    _ir_name: str = None # this includes an id for ir gen

    def __str__(self) -> str:
        return str(self.name)
    
    def pretty_ast(self) -> str:
        return f"{self.get_inferred_type() if self.is_type_checked else 'untyped'} Var: {self.name}"
    
    def get_ir_name(self) -> str:
        assert self.is_type_checked
        return self._ir_name
    
    def set_ir_name(self, ir_name):
        self._ir_name = ir_name

@dataclass
class FunCallNode(TypeableASTNode):
    fun_name: str
    args: List[TypeableASTNode]

    def __str__(self) -> str:
        return f"{self.fun_name}({', '.join(str(x) for x in self.args)})"
    
    def pretty_ast(self) -> str:
        return f"{self.get_inferred_type() if self.is_type_checked else 'untyped'} FunCall: {self.fun_name}" +\
            '\n'.join(f'  arg{i}: {indent_newlines(self.args[i].pretty_ast())}' for i in range(len(self.args))) 
    
def paren_exprs(val, is_mul=False):
    # makes order of operations explicit with parenthesis when it's not obvious
    surrounded = f"({val})" if not type(val) in [LiteralNode, VarNode, FunCallNode] else str(val)
    return surrounded


@dataclass
class OpBinaryNode(TypeableASTNode):
    op: str
    val1: object
    val2: object

    def __str__(self) -> str:
        op = { "add": '+', "sub": '-', "mul": "*", "div": "/", "equality": "==", 
              "less_than": '<', "less_than_equal": "<=", "greater_than": '>', "greater_than_equal": ">=",
               "bit_and": '&', "bit_or": '|' }[self.op]
        return f"{paren_exprs(self.val1)} {op} {paren_exprs(self.val2)}"
    
    def pretty_ast(self) -> str:
        return f"{self.get_inferred_type() if self.is_type_checked else 'untyped'} OpBinary: {self.op}\n" + \
            f"  left: {indent_newlines(self.val1.pretty_ast())}" + '\n' + \
            f"  right: {indent_newlines(self.val2.pretty_ast())}"
            
    
@dataclass
class OpUnaryNode(TypeableASTNode):
    op: str
    val: object

    def __str__(self) -> str:
        op = { "neg": '-', "deref": "*", "ref": "&" }[self.op]
        return f"{op}{paren_exprs(self.val)}"
    
    def pretty_ast(self) -> str:
        return f"{self.get_inferred_type() if self.is_type_checked else 'untyped'} OpUnary: {self.op}\n" + \
                f"  val: {indent_newlines(self.val.pretty_ast())}" + '\n' 
    
@dataclass
class TypeCastNode(TypeableASTNode):
    cast_to_type: str 
    val: TypeableASTNode

    def __str__(self) -> str:
        return f"({self.cast_to_type}){paren_exprs(self.val)}"

    def pretty_ast(self) -> str:
        return f"{self.get_inferred_type() if self.is_type_checked else 'untyped'} TypeCast \n" + \
                f"  val: {indent_newlines(self.val.pretty_ast())}" + '\n'

@dataclass
class StmtReturnNode(ASTNode):
    return_val: object

    def __str__(self) -> str:
        return f"return {self.return_val};"
    
    def pretty_ast(self) -> str:
        return f"Return \n" + \
                f"  val: {indent_newlines(self.return_val.pretty_ast())}" + '\n'

@dataclass
class StmtAssignNode(ASTNode):
    left: VarNode | TypeableASTNode
    right: TypeableASTNode
    is_define: bool = False
    type: str = None

    def __str__(self) -> str:
        return (f"{self.type} " if self.is_define else "") + f"{self.left} = {self.right};"
    
    def pretty_ast(self) -> str:
        return f"StmtAssign \n" + \
                (f"  DefineType: {self.type}\n" if self.is_define else "") + \
            f"  left: {indent_newlines(self.left.pretty_ast())}\n" + \
            f"  right: {indent_newlines(self.right.pretty_ast())}\n"

@dataclass
class StmtExprNode(ASTNode):
    expr: TypeableASTNode

    def __str__(self) -> str:
        return f"{self.expr};"
    
    def pretty_ast(self) -> str:
        return f"StmtExpr \n" + \
                f"  expr: {indent_newlines(self.expr.pretty_ast())}" + '\n'

@dataclass
class StmtBlockNode(ASTNode):
    statements: list

    def __str__(self) -> str:
        return "{\n" + '\n'.join('  '+str(x).replace('\n', '\n  ') for x in self.statements) + '\n' + '}'
    
    def pretty_ast(self) -> str:
        return f"StmtBlock \n" +\
            ''.join(f'  stmt{i}: {indent_newlines(self.statements[i].pretty_ast())}' for i in range(len(self.statements)))

@dataclass
class StmtWhileNode(ASTNode):
    condition: TypeableASTNode
    body: StmtBlockNode

    def __str__(self) -> str:
        # hacky way to get indentation to carry down
        return f"while ({self.condition}) " + str(self.body)
    
    def pretty_ast(self) -> str:
        return "StmtWhile \n" +\
            f"  Condition: {self.condition.pretty_ast()}\n" +\
            f"  Body: \n" +\
            f"    {indent_newlines(self.body.pretty_ast())}\n" 

@dataclass
class StmtIfElseNode(ASTNode):
    condition: TypeableASTNode
    if_body: StmtBlockNode
    else_body: StmtBlockNode

    def __str__(self) -> str:
        return f"if ({self.condition}) " + str(self.if_body) + \
            ("\nelse " + str(self.else_body) if self.else_body else "")
    
    def pretty_ast(self) -> str:
        return "StmtIfElse \n" +\
            f"  Condition: {self.condition.pretty_ast()}\n" +\
            f"  IfBody: \n" +\
            f"    {indent_newlines(self.if_body.pretty_ast())}" + \
            (f"  ElseBody: \n    {indent_newlines(self.else_body.pretty_ast())}\n" if self.else_body else "")

@dataclass
class FunParamNode(ASTNode):
    param_type: str
    param_var: VarNode

    def __str__(self) -> str:
        return f"{self.param_type} {self.param_var}"

@dataclass
class FunDefNode(ASTNode):
    fun_type: str
    fun_name: str 
    params: List[FunParamNode]
    body: StmtBlockNode 
    fun_locals: List[VarNode]

    def set_locals(self, fun_locals: List[VarNode]):
        self.fun_locals = fun_locals

    def __str__(self) -> str:
        return f"{self.fun_type} {self.fun_name}(" + ', '.join(map(str, self.params)) + ') ' + str(self.body)
    
    def pretty_ast(self) -> str:
        return f"FunDef: {indent_newlines(str(self.params))}\n" + f"  Body\n    {indent_newlines(self.body.pretty_ast())}"

@dataclass
class SourceFileNode(ASTNode):
    fun_defs: List[FunDefNode]

    def __str__(self) -> str:
        return '\n\n'.join(map(str, self.fun_defs))
    
    def pretty_ast(self) -> str:
        return '\n'.join(map(indent_newlines, map(str, self.fun_defs)))
