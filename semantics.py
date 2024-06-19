from pland_ast import *
from parse import integral_types, float_types, basic_types
from typing import Dict

type_hierarchy = {
    "any number": 0, "char": 1, "short": 2, "int": 3, "long": 4, "float": 5, "double": 6
}

# manages scoping, definitions, and types in scope within a function definition
# also used for checking function definition return type
class BlockContext:
    def __init__(self, expected_return_type) -> None:
        self.block_idx = 0
        self.return_type = expected_return_type
        self.variable_idx = 0

        self.block_idx_to_vardict: List[Dict[str, VarNode]] = [{}]
        self.function_locals = []

    def get_scoped_var_node(self, var_name: str):
        # gets the type of the variable by name in
        # the last definition in the most recent scope
        
        last_defined_idx = self.block_idx
        while last_defined_idx >= 0 and not var_name in self.block_idx_to_vardict[last_defined_idx]:
            last_defined_idx -= 1

        assert last_defined_idx >= 0, f"referenced variable {var_name} not defined"
        return self.block_idx_to_vardict[last_defined_idx][var_name]
    
    def advance_variable_idx(self):
        self.variable_idx += 1

    def define_scope_var(self, var_node: VarNode, expected_type: str):
        assert isinstance(var_node, VarNode), "ast_node is not VarNode"
        var_name = var_node.name

        assert not var_name in self.block_idx_to_vardict[self.block_idx], "redefining variable in same block"
        self.block_idx_to_vardict[self.block_idx][var_name] = var_node

        var_node.set_ir_name(f"{var_name}_{self.variable_idx}")
        var_node.set_inferred_type(expected_type)

        self.function_locals.append(var_node)

        self.advance_variable_idx()

    def advance_block_idx(self):
        self.block_idx_to_vardict.append({})
        self.block_idx += 1
    
    def pop_block_idx(self):
        self.block_idx_to_vardict.pop()
        self.block_idx -= 1

# things to check for: type assignments
class Checker:
    def __init__(self) -> None:
        self.function_to_type = {}
        # for function signature to verify parameter types
        self.function_name_to_ast: Dict[str, FunDefNode] = {}

    @staticmethod
    def cmp_expr_type(expr_type, expected_type):
        if expr_type == "any number" and expected_type in basic_types:
            return True

        return expr_type == expected_type
    
    @staticmethod
    def get_as_promoted(expr: TypeableASTNode, expected_type: str) -> TypeableASTNode:
        # if no type promotion is applicable, the argument is returned
        if expr.get_inferred_type() == expected_type:
            return expr

        if not expected_type in type_hierarchy or not expr.get_inferred_type() in type_hierarchy:
            return expr
        
        expr_type_level = type_hierarchy[expr.get_inferred_type()]
        expected_type_level = type_hierarchy[expected_type]

        if expected_type_level > expr_type_level:
            result = TypeCastNode(expected_type, expr)
            result.set_inferred_type(expected_type)
            return result
        
        return expr

    def _get_expr_type_from_cases(self, expr: TypeableASTNode, block_ctx: BlockContext) -> str:
        if isinstance(expr, LiteralNode):
            # TODO string literals yet
            return "any number"
        
        elif isinstance(expr, VarNode):
            block_scoped_var = block_ctx.get_scoped_var_node(expr.name)
            defined_var_type = block_scoped_var.get_inferred_type()
            expr.set_ir_name(block_scoped_var.get_ir_name())

            return defined_var_type
        
        elif isinstance(expr, FunCallNode):
            assert expr.fun_name in self.function_to_type, "function not defined"
            for arg, fun_param_node in zip(expr.args, self.function_name_to_ast[expr.fun_name].params):
                arg_type = self.get_expr_type(arg, block_ctx)
                assert Checker.cmp_expr_type(arg_type, fun_param_node.param_type), "function argument mismatched type"

            return self.function_to_type[expr.fun_name]
        
        elif isinstance(expr, OpBinaryNode):
            # constant folding can also be done here
            expr_left_type = self.get_expr_type(expr.val1, block_ctx)
            expr_right_type = self.get_expr_type(expr.val2, block_ctx)

            # promote nodes
            expr.val1 = self.get_as_promoted(expr.val1, expr_right_type)
            expr.val2 = self.get_as_promoted(expr.val2, expr_left_type)

            assert expr.val1.get_inferred_type() == expr.val2.get_inferred_type(), \
                f"cannot apply {expr.op} {expr.val1} {expr.val2}, types: {expr.val1.get_inferred_type()}, {expr.val2.get_inferred_type()}"
            
            return expr.val1.get_inferred_type()

        elif isinstance(expr, OpUnaryNode):
            operand_type = self.get_expr_type(expr.val, block_ctx)
            if expr.op == "neg":
                assert operand_type in basic_types or operand_type == "any number", "cannot apply arithmetic negation on non basic type"
            elif expr.op == "ref":
                # assert operand_type == "variable", "lvalue required for & ref"
                assert isinstance(expr.val, TypeableASTNode), "lvalue required for & ref"
                return operand_type + "*"
            elif expr.op == "deref":
                assert operand_type[-1] == '*', "pointer required for * deref"
                return operand_type[:-1]

            return operand_type
        
        elif isinstance(expr, TypeCastNode):
            # just check the operand. optionally provide sketchy cast warnings here
            _ = self.get_expr_type(expr.val, block_ctx)
            return expr.cast_to_type

        else:
            assert False, f"case not defined for {expr}"

    def get_expr_type(self, expr: TypeableASTNode, block_ctx: BlockContext):
        assert isinstance(expr, TypeableASTNode), "expr is not type-able"
        expr_type = self._get_expr_type_from_cases(expr, block_ctx)
        expr.set_inferred_type(expr_type)

        return expr_type

    def check_stmt_return(self, stmt: StmtReturnNode, block_ctx: BlockContext):
        assert isinstance(stmt, StmtReturnNode), "not a return stmt"
        _ = self.get_expr_type(stmt.return_val, block_ctx)
        promoted_node = self.get_as_promoted(stmt.return_val, block_ctx.return_type)

        assert Checker.cmp_expr_type(block_ctx.return_type, promoted_node.get_inferred_type()), "return type mismatch"

    def check_stmt_assign(self, stmt: StmtAssignNode, block_ctx: BlockContext):
        assert isinstance(stmt, StmtAssignNode), "not an assignment stmt"

        if stmt.is_define:
            _ = self.get_expr_type(stmt.right, block_ctx) # need to get inferred type
            stmt.right = self.get_as_promoted(stmt.right, stmt.type)

            assert stmt.right.get_inferred_type() == stmt.type, f"def+assign mismatched types {stmt.left} vs {stmt.right}"
            
            block_ctx.define_scope_var(stmt.left, stmt.type) 

            # _ = self.get_expr_type(stmt.left, block_ctx) # just to mark this node as type checked
        else:
            expr_left_type = self.get_expr_type(stmt.left, block_ctx)
            _ = self.get_expr_type(stmt.right, block_ctx)

            stmt.right = self.get_as_promoted(stmt.right, expr_left_type)
            
            assert stmt.right.get_inferred_type() == expr_left_type, f"assign mismatched types {stmt.left} vs {stmt.right}"
    
    def check_stmt_while(self, stmt: StmtWhileNode, block_ctx: BlockContext):
        assert isinstance(stmt, StmtWhileNode), "not while stmt"

        condition_type = self.get_expr_type(stmt.condition, block_ctx)
        assert condition_type in integral_types or condition_type == "any number", "cannot evaluate nonintegral type in condition"

        self.check_stmt_block(stmt.body, block_ctx)

    def check_stmt_ifelse(self, stmt: StmtIfElseNode, block_ctx: BlockContext):
        assert isinstance(stmt, StmtIfElseNode), "not if else stmt"

        condition_type = self.get_expr_type(stmt.condition, block_ctx)
        assert condition_type in integral_types or condition_type == "any number", "cannot evaluate nonintegral type in condition"
        
        self.check_stmt_block(stmt.if_body, block_ctx)

        if stmt.else_body:
            self.check_stmt_block(stmt.else_body, block_ctx)
    
    def check_stmt_expr(self, stmt: StmtExprNode, block_ctx: BlockContext):
        assert isinstance(stmt, StmtExprNode), "not expr stmt"

        self.get_expr_type(stmt.expr, block_ctx)

    def check_stmt(self, stmt: ASTNode, block_ctx: BlockContext):
        if isinstance(stmt, StmtAssignNode):
            self.check_stmt_assign(stmt, block_ctx)
        elif isinstance(stmt, StmtReturnNode):
            self.check_stmt_return(stmt, block_ctx)
        elif isinstance(stmt, StmtWhileNode):
            self.check_stmt_while(stmt, block_ctx)
        elif isinstance(stmt, StmtBlockNode):
            self.check_stmt_block(stmt, block_ctx)
        elif isinstance(stmt, StmtIfElseNode):
            self.check_stmt_ifelse(stmt, block_ctx)
        elif isinstance(stmt, StmtExprNode):
            self.check_stmt_expr(stmt, block_ctx)

    def check_stmt_block(self, stmt_block: StmtBlockNode, block_ctx: BlockContext, new_block = True):
        if new_block:
            block_ctx.advance_block_idx()

        for stmt in stmt_block.statements:
            self.check_stmt(stmt, block_ctx)

        block_ctx.pop_block_idx()

    def check_fun_def(self, fun_def: FunDefNode):
        block_ctx = BlockContext(fun_def.fun_type)

        self.function_to_type[fun_def.fun_name] = fun_def.fun_type
        self.function_name_to_ast[fun_def.fun_name] = fun_def

        # function parameters are defined in the same scope as the body
        for param_node in fun_def.params:
            block_ctx.define_scope_var(param_node.param_var, param_node.param_type)

        self.check_stmt_block(fun_def.body, block_ctx, new_block=False)

        fun_def.set_locals(block_ctx.function_locals)
        
    def check_source_file(self, src_file: SourceFileNode):
        for fun_def in src_file.fun_defs:
            self.check_fun_def(fun_def)