from c_ast.pland_ast import *
from typing import Dict, List

# move, jump, jump_if, jump_not, call, ret, add, sub, mul, div, or, and, gt, gte, lt, lte, eq

# calling functions in TAC IR will look like
# call myfunc out_reg, reg_a0, reg_a1, reg_a2
# this will branch and link if needed (jal is not done on IR side)

@dataclass
class VirtualRegister:
    register_name: str

    def __str__(self) -> str:
        return self.register_name
    
    def as_size(self, size=8) -> str:
        reg64_to_reg = {
            "rax": { 1: "al", 2: "ax", 4: "eax", 8: "rax" },
            "rbx": { 1: "bl", 2: "bx", 4: "ebx", 8: "rbx" },
            "rdi": { 1: "dil", 2: "di", 4: "edi", 8: "rdi" },
            "rsi": { 1: "sil", 2: "si", 4: "esi", 8: "rsi" },
            "rdx": { 1: "dl", 2: "dx", 4: "edx", 8: "rdx" },
            "rcx": { 1: "cl", 2: "cx", 4: "ecx", 8: "rcx" },
            "r8": { 1: "r8b", 2: "r8w", 4: "r8d", 8: "r8" },
            "r9": { 1: "r9b", 2: "r9w", 4: "r9d", 8: "r9" },
        }

        return VirtualRegister(reg64_to_reg[self.register_name][size])

class Immediate: pass # just so vscode gives me the green color
Immediate = int | float

@dataclass
class MemoryLocation:
    location: Immediate | VirtualRegister = None # address specified by register or immediate
    offset: int = 0 # maybe not used

    # stack assigned vars should only be determined at a later stage
    # stack ordering specifics may depend on target arch 
    def set_location(self, location: int, offset: int = 0):
        self.location = location
        self.offset = offset

    def get_address(self):
        return self.location + self.offset

    def __str__(self) -> str:
        bracket_part_str = None
        if self.location == None:
            bracket_part_str = "[?]" 
        if self.offset > 0:
            bracket_part_str = f"[{self.location} + {self.offset}]"
        elif self.offset < 0:
            bracket_part_str = f"[{self.location} - {-self.offset}]"
        else:
            bracket_part_str = f"[{self.location}]"
        
        return f"QWORD PTR {bracket_part_str}"

class Operand: pass
Operand = Immediate | VirtualRegister | MemoryLocation

@dataclass
class X86Instruction: pass

@dataclass
class TypedInstruction(X86Instruction): 
    # ins_type: str
    pass

@dataclass
class Move(TypedInstruction):
    dest: Operand
    src: Operand

    def __str__(self) -> str:
        return f"mov {self.dest}, {self.src}"

@dataclass
class SetCmp(TypedInstruction):
    op: str
    dest: Operand
    
    def __str__(self) -> str:
        return f"set{self.op} {self.dest}"

@dataclass
class Jump(X86Instruction):
    dest: Operand

    def __str__(self) -> str:
        return f"jmp {self.dest}"

@dataclass
class JumpIf(X86Instruction):
    dest: Operand

    def __str__(self) -> str:
        return f"jg {self.dest}"

@dataclass
class JumpIfNot(X86Instruction):
    # tests cmp reg, 0. so jeq be jump if not
    dest: Operand

    def __str__(self) -> str:
        return f"je {self.dest}" 

@dataclass 
class Call(X86Instruction):
    target: Operand

    def __str__(self) -> str:
        return f"call {self.target}"

@dataclass
class Return(X86Instruction):
    def __str__(self) -> str:
        return f"ret"

@dataclass
class Leave(X86Instruction):
    def __str__(self) -> str:
        return "leave"
    
@dataclass
class Push(X86Instruction):
    val: Operand
    
    def __str__(self) -> str:
        return f"push {self.val}"

@dataclass
class Pop(X86Instruction):
    dest: MemoryLocation | VirtualRegister

    def __str__(self) -> str:
        return f"pop {self.dest}"

@dataclass
class Arithmetic(X86Instruction):
    op: str
    dest: Operand
    src: Operand

    def __str__(self) -> str:
        return f"{self.op} {self.dest}, {self.src}"

@dataclass
class LoadEffectiveAddress(X86Instruction):
    dest: Operand
    base_reg: VirtualRegister
    idx_reg: VirtualRegister
    stride: Immediate
    offset: Immediate

    def __init__(self, dest, base_reg, idx_reg=None, stride=0, offset=0):
        self.dest = dest
        self.base_reg = base_reg
        self.idx_reg = idx_reg
        self.stride = stride
        self.offset = offset

        if isinstance(base_reg, MemoryLocation):
            self.base_reg = base_reg.location
            self.offset = self.offset + base_reg.offset

    def __str__(self) -> str:
        offset_sign = '+' if self.offset >= 0 else '-'
        stride_sign = '+' if self.stride >= 0 else '-'
        stride = abs(self.stride)
        offset = abs(self.offset)

        if self.idx_reg:
            return f"lea {self.dest}, [{self.base_reg} {stride_sign} {stride}*{self.idx_reg} {offset_sign} {offset}]"

        return f"lea {self.dest}, [{self.base_reg} {offset_sign} {offset}]"

class X86VirtCodeGen:
    def __init__(self, use_virt_regs=False) -> None:
        self.use_virt_regs = use_virt_regs
        self.is_ebx_in_use = False

        self.current_label_idx = 0

        self.arg_reg_idx = 0
        self.temp_reg_idx = 0

        self.instruction_idx = 0
        self.variable_idx = 0

        self.rsp = VirtualRegister("rsp")
        self.rbp = VirtualRegister("rbp")
        self.rax = VirtualRegister("rax")
        self.rbx = VirtualRegister("rbx")

        self.arg_registers = [
            VirtualRegister("rdi"), VirtualRegister("rsi"), VirtualRegister("rdx"), 
            VirtualRegister("rcx"), VirtualRegister("r8"), VirtualRegister("r9")
        ]

        # for the sake of my sanity, assume all locals are on the stack
        self.var_ir_to_location: Dict[str, MemoryLocation] = {}

        self.label_to_ins_idx: Dict[str, int] = {}
        self.ir_code: List[X86Instruction] = []

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

    def get_next_temp_register(self, word_size=8) -> VirtualRegister:
        if self.use_virt_regs:
            old_id = self.temp_reg_idx
            self.temp_reg_idx += 1

            return VirtualRegister(f"t{old_id}")
        
        # use ebx probably
        return self.rbx

    def reset_arg_reg_index(self):
        self.arg_reg_idx = 0
    
    def add_instruction(self, instruction: X86Instruction):
        # ignore mov to the same register
        if isinstance(instruction, Move) and instruction.dest == instruction.src:
            return
        
        self.ir_code.append(instruction)
        self.instruction_idx += 1

    def assign_variable_to_stack(self, var_node: VarNode, location: MemoryLocation):
        var_ir_name = var_node.get_ir_name()
        self.var_ir_to_location[var_ir_name] = location

    def get_variable_stack_loc(self, var_node: VarNode) -> MemoryLocation:
        var_ir_name = var_node.get_ir_name()
        loc = self.var_ir_to_location[var_ir_name]
        return loc

    def x86_binary(self, node: OpBinaryNode) -> VirtualRegister:
        op = { "add": 'add', "sub": 'sub', "mul": "mul", "div": "div", "equality": "e", 
              "less_than": 'l', "less_than_equal": "le", "greater_than": 'g', "greater_than_equal": "ge",
               "bit_and": 'and', "bit_or": 'or' }[node.op]
        
        comparisons = { "l", "e", "le", "g", "ge" }
        if op == "mul":
            op = "imul"

        left, right = self.x86_expr(node.val1), self.x86_expr(node.val2)
        if op in comparisons:
            result_reg = self.get_next_temp_register()
            self.add_instruction(Arithmetic("cmp", left, right))
            self.add_instruction(SetCmp(op, result_reg.as_size(1)))
        else:
            result_reg = self.get_next_temp_register()
            self.add_instruction(Move(result_reg, left))
            self.add_instruction(Arithmetic(op, result_reg, right))

        return result_reg

    def x86_unary(self, node: OpUnaryNode) -> VirtualRegister | int:
        result_reg = self.get_next_temp_register()

        if node.op == "neg":
            self.add_instruction(Arithmetic("imul", result_reg, -1))

        elif node.op == "ref":
            # assert isinstance(node.val, VarNode), "referencing rvalue"
            expr_reg = self.x86_expr(node.val)
            self.add_instruction(LoadEffectiveAddress(result_reg, expr_reg))

        elif node.op == "deref":
            expr_reg = self.x86_expr(node.val)
            if isinstance(expr_reg, Immediate | VirtualRegister):
                self.add_instruction(Move(result_reg, MemoryLocation(location=expr_reg)))
            elif isinstance(expr_reg, MemoryLocation):
                self.add_instruction(Move(result_reg, expr_reg))
            else:
                assert False, f"unknown deref on {expr_reg}" 
        
        return result_reg

    def x86_funcall(self, node: FunCallNode) -> VirtualRegister:
        self.reset_arg_reg_index()
        i = len(node.args) - 1
        while i >= 0:
            arg = self.x86_expr(node.args[i])
            if i >= len(self.arg_registers):
                # spill it 
                self.add_instruction(Push(arg))
            else:
                self.add_instruction(Move(self.arg_registers[i], arg))

            i -= 1
        self.reset_arg_reg_index()
        
        self.add_instruction(Call(node.fun_name))
        return self.rax

    def x86_expr(self, expr: TypeableASTNode) -> Operand:
        # expressions can either return a value that is stored in a register
        # an immediate from a literal node
        # or a variable (in the form of memory location) from variable nodes or derefs

        if isinstance(expr, OpBinaryNode):
            return self.x86_binary(expr)
        elif isinstance(expr, OpUnaryNode):
            return self.x86_unary(expr)
        elif isinstance(expr, FunCallNode):
            return self.x86_funcall(expr)
        elif isinstance(expr, LiteralNode):
            return expr.val
        elif isinstance(expr, VarNode):
            return self.get_variable_stack_loc(expr)
        elif isinstance(expr, TypeCastNode):
            # TODO type casting operations
            return self.x86_expr(expr.val)
        else:
            assert False, f"unidentified expr: {expr}"
    
    def x86_stmt_if_else(self, stmt: StmtIfElseNode):
        if stmt.else_body:
            else_block_label = self.get_next_label(stmt.else_body)

            self.add_instruction(Arithmetic("cmp", self.x86_expr(stmt.condition), 0))
            self.add_instruction(JumpIfNot(else_block_label))
            self.x86_stmt_block(stmt.if_body)

            after_if_else_label = self.get_next_label(stmt)
            self.add_instruction(Jump(after_if_else_label))

            self.insert_label(else_block_label)
            self.x86_stmt_block(stmt.else_body)

            # this instruction is not necessary if the instructions labels are ordered properly
            # self.add_instruction(Jump(after_if_else_label))

            self.insert_label(after_if_else_label)
        else:
            after_if_label = self.get_next_label(stmt)
            self.add_instruction(Arithmetic("cmp", self.x86_expr(stmt.condition), 0))
            self.add_instruction(JumpIfNot(after_if_label))
            self.x86_stmt_block(stmt.if_body)

            # like before, an extra jump to after_if_label is not necessary if dict insertion order is respected
            # self.add_instruction(Jump(after_if_label))

            self.insert_label(after_if_label)
    
    def x86_stmt_assign(self, stmt: StmtAssignNode):
        right_reg = self.x86_expr(stmt.right)
        left_loc = self.x86_expr(stmt.left)

        # TODO make sure that two memory refs cannot happen
        self.add_instruction(Move(left_loc, right_reg))

    def x86_stmt_return(self, stmt: StmtReturnNode):
        result_reg = self.x86_expr(stmt.return_val)
        # TODO, if it's a floating point register, then need to do movd
        self.add_instruction(Move(self.rax, result_reg))

    def x86_stmt_while(self, stmt: StmtWhileNode):
        while_start_label = self.get_next_label(stmt.condition)
        while_after_label = self.get_next_label(stmt.condition)

        self.add_instruction(Jump(while_after_label))
        self.insert_label(while_start_label)

        self.x86_stmt_block(stmt.body)

        self.insert_label(while_after_label)
        self.add_instruction(Arithmetic("cmp", self.x86_expr(stmt.condition), 0))
        self.add_instruction(JumpIf(while_start_label))

    def x86_stmt(self, stmt: ASTNode):
        if isinstance(stmt, StmtAssignNode):
            self.x86_stmt_assign(stmt)
        elif isinstance(stmt, StmtBlockNode):
            self.x86_stmt_block(stmt)
        elif isinstance(stmt, StmtExprNode):
            self.x86_expr(stmt.expr)
        elif isinstance(stmt, StmtIfElseNode):
            self.x86_stmt_if_else(stmt)
        elif isinstance(stmt, StmtReturnNode):
            self.x86_stmt_return(stmt)
        elif isinstance(stmt, StmtWhileNode):
            self.x86_stmt_while(stmt)
        else:
            assert False, "unknown stmt"

    def x86_stmt_block(self, stmt_body: StmtBlockNode):
        for stmt in stmt_body.statements:
            self.x86_stmt(stmt)
        
    def x86_fun_def(self, fun_def: FunDefNode):
        current_label = self.get_next_label(name=fun_def.fun_name)
        self.current_function_name = current_label
        self.insert_label(current_label)

        self.add_instruction(Push(self.rbp))
        self.add_instruction(Move(self.rbp, self.rsp))

        # rbx is callee saved
        rbx_loc = MemoryLocation(self.rbp, -8)
        self.add_instruction(Move(rbx_loc, self.rbx)) # sometimes not used, but do it anyways for simplicity
        next_alloc_bp = -8 # from rbx 
        
        # allocate enough space for all the locals. TODO properly stack-align this
        self.add_instruction(Arithmetic("sub", self.rsp, 16*len(fun_def.fun_locals)))

        # read in the parameters that are passed in as registers and move to stack
        self.reset_arg_reg_index()
        for idx, param in enumerate(fun_def.params, start=1):
            loc = MemoryLocation(location=self.rbp, offset=-idx*8 + next_alloc_bp)
            if self.arg_reg_idx < len(self.arg_registers):
                self.add_instruction(Move(loc, self.arg_registers[self.arg_reg_idx]))
            else:
                # +8 to skip old rbp; another +8 skips return address then 
                stack_arg_loc = MemoryLocation(location=self.rbp, offset=(self.arg_reg_idx - len(self.arg_registers))*8 + 16)
                # move arg on stack to rbx or rax, then move it to current frame's stack
                # this emulates pass by value and complies with gnu assembler rule of only having one mem ref per mov
                self.add_instruction(Move(self.rbx, stack_arg_loc))  
                self.add_instruction(Move(loc, self.rbx))

            self.assign_variable_to_stack(param.param_var, loc)
            self.arg_reg_idx += 1

        self.reset_arg_reg_index()

        # assign all the locals to the stack
        for idx, local_var in enumerate(fun_def.fun_locals, start=1):
            # skip the params which are already assigned
            if local_var.get_ir_name() in self.var_ir_to_location: 
                continue

            loc = MemoryLocation(location=self.rbp, offset=-idx*8 + next_alloc_bp)
            self.assign_variable_to_stack(local_var, loc)
        
        self.x86_stmt_block(fun_def.body)
    
        # because rbx is callee saved
        self.add_instruction(Move(self.rbx, rbx_loc))
        
        self.add_instruction(Leave())
        self.add_instruction(Return())

    def x86_source_file(self, src_file: SourceFileNode):
        for fun_def in src_file.fun_defs:
            self.x86_fun_def(fun_def)
        
    def pretty_x86(self) -> str:
        labels = [*self.label_to_ins_idx.keys()]
        label_idx = 0

        ins_strs = []

        for i in range(self.instruction_idx):
            if label_idx < len(labels) and i == self.label_to_ins_idx[labels[label_idx]]:
                ins_strs.append(labels[label_idx] + ":")
                label_idx += 1

            ins_strs.append(f"\t{self.ir_code[i]}")
        
        return '\n'.join(ins_strs)