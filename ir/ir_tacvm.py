from ir.ir_tac import *

class TACVM:
    def __init__(self, tac: TAC) -> None:
        self.tac = tac
        self.pc = 0
        self.memory: Dict[int, object] = {}
        self.reg_file: Dict[str, object] = {}
        self.reg_file["sp"] = 0xFFFF
        self.reg_file["bp"] = 0xFFFF
        self.reg_file["ra"] = 0
        self.reg_file["rt"] = 0

        # used to get which local vars should be stack saved
        self.current_function: str = None
        self.caller_name_stack: List[str] = []

        # call args go here. no threads allowed
        self.call_arg_vals = []

        # needs to be a stack because of recursive calls
        self.ret_registers = []

        # local_variable
        self.fun_block_regs: Dict[str, List[VirtualRegister]] = {}

    def get_src_val(self, source: VirtualRegister | MemoryLocation) -> object:
        if not isinstance(source, VirtualRegister | MemoryLocation | UDVal):
            return source
        
        if isinstance(source, VirtualRegister):
            return self.reg_file[source.register_name]
        elif isinstance(source, UDVal):
            return self.get_src_val(source.val)
        elif isinstance(source, MemoryLocation) and isinstance(source.location, UDVal):
            return self.get_src_val(source.location)
        else:
            return self.memory[self.get_src_val(source.location) + source.offset]
    
    def store_val(self, dest: VirtualRegister | MemoryLocation | object, source: VirtualRegister | MemoryLocation):
        val = source if not isinstance(source, VirtualRegister | MemoryLocation) else self.get_src_val(source)
        
        if isinstance(dest, VirtualRegister):
            self.reg_file[dest.register_name] = val
        
        elif isinstance(dest, MemoryLocation):
            self.memory[self.get_src_val(dest.location) + dest.offset] = val
        
    def set_pc_before(self, dest: VirtualRegister | MemoryLocation):
        # minus 1 bc of pc inc after
        self.pc = self.tac.label_to_ins_idx[self.get_src_val(dest)] - 1

    def set_current_function(self, curr_fun_name: str):
        self.current_function = curr_fun_name
    
    def run_alu(self, op: str, left: object, right: object) -> object:
        if op == "add":
            return left + right
        elif op == "sub":
            return left - right
        elif op == "mul":
            return left * right
        elif op == "div":
            return left / right
        elif op == "eq":
            return left == right
        elif op == "lt":
            return left < right
        elif op == "lte":
            return left <= right
        elif op == "gt":
            return left > right
        elif op == "gte":
            return left >= right
        elif op == "and":
            return left & right
        elif op == "or":
            return left | right
        else:
            assert False, "unknown operation"

    def push_stack_frame(self):
        self.caller_name_stack.append(self.current_function)
        old_bp = self.reg_file["bp"]
        self.reg_file["bp"] = self.reg_file["sp"]
        # push the previous base pointer onto the stack
        self.store_val(MemoryLocation(location=self.reg_file["bp"]), old_bp)
        self.reg_file["sp"] -= 1

        # push ra on to the stack and set ra to the next instruction
        self.store_val(MemoryLocation(location=self.reg_file["bp"] - 1), self.reg_file["ra"])
        self.reg_file["sp"] -= 1
        self.reg_file["ra"] = self.pc  # no need for + 1 since will automatically inc to next ins
        
        # push locals onto stack. intermediate temporaries shouldn't matter
        for i, var_ir_name in enumerate(self.tac.fun_name_to_locals[self.current_function]):
            var_reg = self.tac.variable_to_location[var_ir_name]
            # ignore locals that have escaped to stack (via. &)
            if not isinstance(var_reg, VirtualRegister): 
                continue

            # some locals might not be defined yet
            if not var_reg.register_name in self.reg_file:
                continue
            
            self.store_val(MemoryLocation(self.reg_file["bp"] - i - 2), self.get_src_val(self.tac.variable_to_location[var_ir_name]))
            self.reg_file["sp"] -= 1
        
    def pop_stack_frame(self):
        self.set_current_function(self.caller_name_stack.pop())
        # restore locals
        local_vars = self.tac.fun_name_to_locals[self.current_function]
        for i, local_var in enumerate(local_vars):
            var_reg = self.tac.variable_to_location[local_var]
            # ignore locals that have escaped to stack (via. &)
            if not isinstance(var_reg, VirtualRegister): 
                continue

            # some locals might not be defined yet
            if not var_reg.register_name in self.reg_file:
                continue

            restore_to_reg = self.tac.get_virt_register(local_var)
            self.store_val(restore_to_reg, MemoryLocation(self.reg_file["bp"] - i - 2))

        # restore return addr
        return_to = self.reg_file["ra"]
        self.reg_file["ra"] = self.get_src_val(MemoryLocation(self.reg_file["bp"] - 1))
        # restore the base pointer
        self.reg_file["bp"] = self.get_src_val(MemoryLocation(self.reg_file["bp"]))

        # restore the stack pointer
        self.reg_file["sp"] = self.reg_file["bp"]

        return return_to
        
    def run_instruction(self):
        curr_ins = self.tac.ir_code[self.pc]

        if isinstance(curr_ins, Move):
            if isinstance(curr_ins.src, UDVal) and isinstance(curr_ins.src.val, MemoryLocation):
                    self.store_val(curr_ins.dest, curr_ins.src.val.get_address())
            else:
                self.store_val(curr_ins.dest, curr_ins.src)

        elif isinstance(curr_ins, Jump):
            self.set_pc_before(curr_ins.dest)

        elif isinstance(curr_ins, JumpIf):
            if self.get_src_val(curr_ins.cond) != 0:
                self.set_pc_before(curr_ins.dest)

        elif isinstance(curr_ins, JumpIfNot):
            if self.get_src_val(curr_ins.cond) == 0:
                self.set_pc_before(curr_ins.dest)

        elif isinstance(curr_ins, Call):
            self.push_stack_frame()

            self.set_current_function(curr_ins.target)
            self.ret_registers.append(curr_ins.out_register)

            for arg in curr_ins.args:
                self.call_arg_vals.append(self.get_src_val(arg))

            self.set_pc_before(curr_ins.target)

        elif isinstance(curr_ins, Params):
            for i in range(len(curr_ins.params_regs)-1, -1, -1):
                self.store_val(curr_ins.params_regs[i], self.call_arg_vals.pop())
        
        elif isinstance(curr_ins, Return):
            if self.ret_registers:
                self.store_val(self.ret_registers.pop(), curr_ins.src)
            
            return_to = self.pop_stack_frame()
            self.pc = return_to

        elif isinstance(curr_ins, Push):
            mem_loc = self.tac.variable_to_location[f"ref_{curr_ins.val.register_name}"]
            mem_loc.set_location(self.reg_file["sp"])
            self.store_val(mem_loc, curr_ins.val)
            self.reg_file["sp"] -= 1

            # this is to update "post arch selection addrs" like sp offsets to ref vars
            curr_ins.pushed_to = mem_loc
        
        elif isinstance(curr_ins, Pop):
            mem_loc = MemoryLocation(self.reg_file["sp"])
            self.store_val(curr_ins.dest, self.get_src_val(mem_loc))
            self.reg_file["sp"] += 1
        
        elif isinstance(curr_ins, Arithmetic):
            left, right = self.get_src_val(curr_ins.left), self.get_src_val(curr_ins.right)
            result = self.run_alu(curr_ins.op, left, right)
            self.store_val(curr_ins.dest, result)
        
        self.pc += 1

    def run(self):
        self.set_current_function("main")
        self.pc = self.tac.label_to_ins_idx["main"]
        
        while self.pc < len(self.tac.ir_code):
            # print("running: ", self.tac.ir_code[self.pc]); input()
            self.run_instruction()