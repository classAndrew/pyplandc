from c_ast.pland_ast import *
from typing import Dict, List

# move, jump, jump_if, jump_not, call, ret, add, sub, mul, div, or, and, gt, gte, lt, lte, eq

# calling functions in TAC IR will look like
# call myfunc out_reg, reg_a0, reg_a1, reg_a2
# this will branch and link if needed (jal is not done on IR side)

@dataclass
class VirtualRegister:
    register_name: str
    bound_ir_var: str

    def __str__(self) -> str:
        return self.register_name

@dataclass
class UDVal:
    annotation: str
    val: object = None
    def __str__(self) -> str:
        if self.val:
            return str(self.val)
        
        return f"? ({self.annotation})"

@dataclass
class MemoryLocation:
    location: int | VirtualRegister = None # address specified by register or immediate
    offset: int = 0 # maybe not used

    # stack assigned vars should only be determined at a later stage
    # stack ordering specifics may depend on target arch 
    def set_location(self, location: int, offset: int = 0):
        self.location = location
        self.offset = offset

    def get_address(self):
        return self.location + self.offset

    def __str__(self) -> str:
        if self.location == None:
            return "?(sp)" 
        if self.offset > 0:
            return f"[{self.location} + {self.offset}]"
        elif self.offset < 0:
            return f"[{self.location} - {-self.offset}]"
        else:
            return f"[{self.location}]"
            
@dataclass()
class TACInstruction: pass

@dataclass
class TypedInstruction(TACInstruction): 
    ins_type: str

@dataclass
class Move(TypedInstruction):
    dest: MemoryLocation | VirtualRegister # addr, reg
    src: MemoryLocation | VirtualRegister | int | float # addr, reg, immediate/const 

    def __str__(self) -> str:
        return f"move {self.dest}, {self.src}"

@dataclass
class Jump(TACInstruction):
    dest: str | MemoryLocation | VirtualRegister | int # label, indirection, reg, imm addr

    def __str__(self) -> str:
        return f"jump {self.dest}"

@dataclass
class JumpIf(TACInstruction):
    dest: str | MemoryLocation | VirtualRegister | int
    cond: MemoryLocation | VirtualRegister

    def __str__(self) -> str:
        return f"jump_if {self.dest}, {self.cond}"

@dataclass
class JumpIfNot(TACInstruction):
    dest: str | MemoryLocation | VirtualRegister | int
    cond: MemoryLocation | VirtualRegister

    def __str__(self) -> str:
        return f"jump_ifnot {self.dest}, {self.cond}"

@dataclass
class Params(TACInstruction):
    params_regs: List[VirtualRegister]

    def __str__(self) -> str:
        return f"params {', '.join(str(reg) for reg in self.params_regs)}"

@dataclass 
class Call(TACInstruction):
    target: str | MemoryLocation | VirtualRegister
    out_register: VirtualRegister
    args: List[VirtualRegister]

    def __str__(self) -> str:
        return f"call {self.target}, {self.out_register}, {', '.join(str(arg) for arg in self.args)}"

@dataclass
class Return(TACInstruction):
    src: VirtualRegister

    def __str__(self) -> str:
        return f"ret {self.src}"
    
@dataclass
class Push(TACInstruction):
    val: MemoryLocation | VirtualRegister
    pushed_to: MemoryLocation
    
    def __str__(self) -> str:
        return f"push {self.val}"

@dataclass
class Pop(TACInstruction):
    dest: MemoryLocation | VirtualRegister

    def __str__(self) -> str:
        return f"pop {self.dest}"

@dataclass
class Arithmetic(TACInstruction):
    dest: MemoryLocation | VirtualRegister
    op: str
    left: MemoryLocation | VirtualRegister | int | float
    right: MemoryLocation | VirtualRegister | int | float

    def __str__(self) -> str:
        return f"{self.op} {self.dest}, {self.left}, {self.right}"

class TAC:
    def __init__(self) -> None:
        self.current_label_idx = 0
        self.register_idx = 0
        self.instruction_idx = 0
        self.variable_idx = 0

        self.variable_to_location: Dict[str, VirtualRegister | MemoryLocation] = {}
        self.label_to_ins_idx: Dict[str, int] = {}
        self.ir_code: List[TACInstruction] = []

        self.current_function_name: str = None
        self.fun_name_to_locals: Dict[str, List[str]] = {}

        self.cfg_graph = [] # this comes later

    def get_next_label(self, ast_node: ASTNode=None, name: str = None) -> str:
        if not ast_node and name:
            return name
        
        label_idx = self.current_label_idx
        self.advance_label_idx()
        return f".L{label_idx}_{ast_node.line_number}"

    def insert_label(self, label: str):
        self.label_to_ins_idx[label] = self.instruction_idx
    
    def advance_label_idx(self):
        self.current_label_idx += 1

    def get_next_virt_register(self, var_ir_name: str = None) -> int:
        old_id = self.variable_idx
        self.variable_idx += 1
        return VirtualRegister(f"t{old_id}", var_ir_name)
    
    def get_virt_register(self, var_ir_name: str) -> VirtualRegister:
        return self.variable_to_location[var_ir_name]
    
    def add_instruction(self, instruction: TACInstruction):
        self.ir_code.append(instruction)
        self.instruction_idx += 1

    def assign_variable(self, var_node: VarNode, register: VirtualRegister = None):
        var_ir_name = var_node.get_ir_name()
        self.fun_name_to_locals[self.current_function_name].append(var_ir_name)
        if register:
            register.bound_ir_var = var_ir_name
            self.variable_to_location[var_ir_name] = register
        else:
            self.variable_to_location[var_ir_name] = self.get_next_virt_register(var_ir_name)

    def tac_binary(self, node: OpBinaryNode) -> VirtualRegister:
        result_reg = self.get_next_virt_register()
        op = { "add": 'add', "sub": 'sub', "mul": "mul", "div": "div", "equality": "eq", 
              "less_than": 'lt', "less_than_equal": "lte", "greater_than": 'gt', "greater_than_equal": "gte",
               "bit_and": 'and', "bit_or": 'or' }[node.op]
        
        if op == "mul":
            op = "imul"
            
        self.add_instruction(
            Arithmetic(result_reg, op, self.tac_expr(node.val1), self.tac_expr(node.val2))
        )

        return result_reg

    def tac_unary(self, node: OpUnaryNode) -> VirtualRegister | int:
        result_reg = None

        if node.op == "neg":
            result_reg = self.get_next_virt_register()
            self.add_instruction(Arithmetic(result_reg, "sub", 0, result_reg))

        elif node.op == "ref":
            # assert isinstance(node.val, VarNode), "referencing rvalue"
            expr_reg = self.tac_expr(node.val)
            mem_loc = MemoryLocation()
            self.variable_to_location[f"ref_{expr_reg.register_name}"] = mem_loc
            push_ins = Push(expr_reg, mem_loc)
            self.add_instruction(push_ins)
            return UDVal("some stack mem", push_ins.pushed_to)
        
        elif node.op == "deref":
            result_reg = self.get_next_virt_register()
            mem_loc = MemoryLocation(self.tac_expr(node.val))
            self.add_instruction(Move(None, result_reg, mem_loc))
        
        return result_reg

    def tac_funcall(self, node: FunCallNode) -> VirtualRegister:
        arg_registers = []
        for arg in node.args:
            arg_registers.append(self.tac_expr(arg))
        
        out_register = self.get_next_virt_register()
        self.add_instruction(Call(node.fun_name, out_register, arg_registers))

        return out_register

    def tac_expr(self, expr: TypeableASTNode) -> VirtualRegister | float | int:
        if isinstance(expr, OpBinaryNode):
            return self.tac_binary(expr)
        elif isinstance(expr, OpUnaryNode):
            return self.tac_unary(expr)
        elif isinstance(expr, FunCallNode):
            return self.tac_funcall(expr)
        elif isinstance(expr, LiteralNode):
            return expr.val
        elif isinstance(expr, VarNode):
            assert expr.get_ir_name() in self.variable_to_location, "variable not defined"
            return self.variable_to_location[expr.get_ir_name()]
        elif isinstance(expr, TypeCastNode):
            # TODO type casting operations
            return self.tac_expr(expr.val)
        else:
            assert False, f"unidentified expr: {expr}"
    
    def tac_stmt_if_else(self, stmt: StmtIfElseNode):
        if stmt.else_body:
            else_block_label = self.get_next_label(stmt.else_body)

            self.add_instruction(JumpIfNot(else_block_label, self.tac_expr(stmt.condition)))
            self.tac_stmt_block(stmt.if_body)

            after_if_else_label = self.get_next_label(stmt)
            self.add_instruction(Jump(after_if_else_label))

            self.insert_label(else_block_label)
            self.tac_stmt_block(stmt.else_body)

            # this instruction is not necessary if the instructions labels are ordered properly
            # self.add_instruction(Jump(after_if_else_label))

            self.insert_label(after_if_else_label)
        else:
            after_if_label = self.get_next_label(stmt)
            self.add_instruction(JumpIfNot(after_if_label, self.tac_expr(stmt.condition)))
            self.tac_stmt_block(stmt.if_body)

            # like before, an extra jump to after_if_label is not necessary if dict insertion order is respected
            # self.add_instruction(Jump(after_if_label))

            self.insert_label(after_if_label)
    
    def tac_stmt_assign(self, stmt: StmtAssignNode):
        right_reg = self.tac_expr(stmt.right)
        if stmt.is_define:
            self.assign_variable(stmt.left)

        if isinstance(stmt.left, VarNode):
            left_loc = self.get_virt_register(stmt.left.get_ir_name())
        else:
            # TODO this should be in semantic type checking
            assert isinstance(stmt.left, OpUnaryNode) and stmt.left.op == "deref", "invalid lvalue in deref"
            left_loc = MemoryLocation(self.tac_expr(stmt.left.val))

        self.add_instruction(Move(None, left_loc, right_reg))

    def tac_stmt_return(self, stmt: StmtReturnNode):
        self.add_instruction(Return(self.tac_expr(stmt.return_val)))

    def tac_stmt_while(self, stmt: StmtWhileNode):
        while_start_label = self.get_next_label(stmt.condition)
        self.insert_label(while_start_label)

        self.tac_stmt_block(stmt.body)

        self.add_instruction(JumpIf(while_start_label, self.tac_expr(stmt.condition)))

    def tac_stmt(self, stmt: ASTNode):
        if isinstance(stmt, StmtAssignNode):
            self.tac_stmt_assign(stmt)
        elif isinstance(stmt, StmtBlockNode):
            self.tac_stmt_block(stmt)
        elif isinstance(stmt, StmtExprNode):
            self.tac_expr(stmt.expr)
        elif isinstance(stmt, StmtIfElseNode):
            self.tac_stmt_if_else(stmt)
        elif isinstance(stmt, StmtReturnNode):
            self.tac_stmt_return(stmt)
        elif isinstance(stmt, StmtWhileNode):
            self.tac_stmt_while(stmt)
        else:
            assert False, "unknown stmt"

    def tac_stmt_block(self, stmt_body: StmtBlockNode):
        for stmt in stmt_body.statements:
            self.tac_stmt(stmt)
        
    def tac_fun_def(self, fun_def: FunDefNode):
        current_label = self.get_next_label(name=fun_def.fun_name)
        self.current_function_name = current_label
        self.fun_name_to_locals[current_label] = []
        self.insert_label(current_label)

        param_regs = []
        for param in fun_def.params:
            p_reg = self.get_next_virt_register()
            self.assign_variable(param.param_var, p_reg)
            param_regs.append(p_reg)
        
        self.add_instruction(Params(param_regs))
        
        self.tac_stmt_block(fun_def.body)
    
    def tac_source_file(self, src_file: SourceFileNode):
        for fun_def in src_file.fun_defs:
            self.tac_fun_def(fun_def)
        
    def pretty_tac_ir(self) -> str:
        labels = [*self.label_to_ins_idx.keys()]
        label_idx = 0

        ins_strs = []

        for i in range(self.instruction_idx):
            if label_idx < len(labels) and i == self.label_to_ins_idx[labels[label_idx]]:
                ins_strs.append(labels[label_idx] + ":")
                label_idx += 1

            ins_strs.append(f"\t{self.ir_code[i]}")
        
        return '\n'.join(ins_strs)