# parser
from c_ast.pland_ast import *
from c_ast.lex import LexicalToken

valid_expr_start = ["literal_decimal", "literal_integer", "identifier", "left_paren",
                    "minus", "ampersand", "star"]
valid_stmt_start_tokens = ["left_brace", "right_brace", "return", "while", "if", 
                           "identifier", "struct", "unsigned", "literal_decimal", 
                           "literal_integer", "left_paren", "minus", "ampersand", "star"]
integral_types = ["char", "short", "int", "long"] # must take care of unsigned in ast
float_types = ["float", "double"]
basic_types = integral_types + float_types

class ParserException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class Parser:
    def __init__(self, tokens: List[LexicalToken], code: str) -> None:
        self.p = 0
        self.tokens = tokens
        self.code = code

    def parser_assert(self, condition: bool, msg: str):
        token_line = self.tokens[self.p].line_num
        token_pos = self.tokens[self.p].char_num
        nearby_code = self.code[max(0,token_pos-10):min(token_pos+10, len(self.code))]
        if not condition:
            raise ParserException(f"""at line {token_line}
near 
{nearby_code}
error: {msg}""")
        
    def tag_ast_with_debug(self, node: ASTNode) -> ASTNode:
        token_line = self.tokens[min(self.p, len(self.tokens) - 1)].line_num
        token_pos = self.tokens[min(self.p, len(self.tokens) - 1)].char_num

        node.line_number = token_line
        node.char_number = token_pos

        return node

    def at_tok_val(self, offset=0):
        return self.tokens[self.p + offset].token_val
    
    def at_tok_type(self, offset=0):
        return self.tokens[self.p + offset].token_type
    
    def has_next(self):
        return self.p < len(self.tokens)

    def advance(self, lookahead=1):
        self.p += lookahead
        return self.p < len(self.tokens)
    
    def try_parse_type_name(self, lookahead=0):
        result = ""

        if self.at_tok_type(lookahead) == "struct":
            result += "struct "
            lookahead += 1
        
            if self.at_tok_type(lookahead) != "identifier":
                return False, lookahead
            
            result += self.at_tok_val(lookahead)
            lookahead += 1

        elif self.at_tok_type(lookahead) == "unsigned":
            result += "unsigned "
            lookahead += 1
            
            if not self.at_tok_val(lookahead) in integral_types:
                return False, lookahead
        
        if self.at_tok_val(lookahead) in basic_types:
            result += self.at_tok_val(lookahead)
            lookahead += 1

        if not result:
            return False, lookahead
        
        while self.at_tok_type(lookahead) == "star":
            result += self.at_tok_val(lookahead)
            lookahead += 1
    
        return result, lookahead
    
    def parse_paren(self):
        self.parser_assert(self.at_tok_type() == "left_paren", "paren expr start left")
        self.advance()

        # ok we might be trying to cast something, so check that first
        type_name, lookahead = self.try_parse_type_name()
        # should never be confused with multiplication because it requires a basic type as an identifier or struct to precede user-defined type
        if type_name: 
            self.advance(lookahead)

            self.parser_assert(self.at_tok_type() == "right_paren", "type cast end right paren")
            self.advance() 

            return self.tag_ast_with_debug(TypeCastNode(type_name, self.parse_expr()))
        
        result = self.parse_expr()

        self.parser_assert(self.at_tok_type() == "right_paren", "paren expr end right")
        self.advance()

        return self.tag_ast_with_debug(result)
    
    def parse_fun_call(self):
        self.parser_assert(self.at_tok_type() == "identifier", "function name identifier")
        fun_name = self.at_tok_val()
        self.advance() 

        self.parser_assert(self.at_tok_type() == "left_paren" and self.has_next(), "function left_paren or end")
        self.advance()

        args = []
        while self.has_next() and self.at_tok_type() != "right_paren":
            args.append(self.parse_expr())
            
            self.parser_assert(self.at_tok_type() == "comma" or self.at_tok_type() == "right_paren", "function arg list comma or right_paren")
            if self.at_tok_type() == "right_paren":
                break

            self.advance()
        
        self.advance()

        return self.tag_ast_with_debug(FunCallNode(fun_name, args))

    def parse_var(self):
        self.parser_assert(self.at_tok_type() == "identifier", "variable name identifier")

        result = VarNode(self.at_tok_val())
        self.advance()

        return self.tag_ast_with_debug(result)

    def parse_expr_term(self):
        if self.at_tok_type() in ["literal_decimal", "literal_integer"]:
            val = self.at_tok_val()
            self.advance()

            return self.tag_ast_with_debug(LiteralNode(val))

        elif self.at_tok_type() == "identifier":
            if self.has_next() and self.at_tok_type(1) == "left_paren":
                return self.tag_ast_with_debug(self.parse_fun_call())
            else:
                return self.tag_ast_with_debug(self.parse_var())
            
        elif self.at_tok_type() == "left_paren":
            return self.tag_ast_with_debug(self.parse_paren())

    def parse_dot(self):
        left = self.parse_expr_term()
        
        while self.has_next() and self.at_tok_type() == "dot":
            self.advance()
            self.parser_assert(self.at_tok_type() == "identifier", "identifier following dot access")

            left = OpBinaryNode("dot", left, self.parse_expr_term())
        
        return self.tag_ast_with_debug(left)

    def parse_unary(self):
        while self.at_tok_type() in ["minus", "star", "ampersand"]:
            unary_op = self.at_tok_type()
            self.advance()
            if unary_op == "minus":
                return self.tag_ast_with_debug(OpUnaryNode("neg", self.parse_unary()))
            elif unary_op == "star":
                return self.tag_ast_with_debug(OpUnaryNode("deref", self.parse_unary()))
            elif unary_op == "ampersand":
                return self.tag_ast_with_debug(OpUnaryNode("ref", self.parse_unary()))
        
        return self.tag_ast_with_debug(self.parse_dot())
    
    def parse_mul(self):
        # includes divide
        left = self.parse_unary()

        while self.has_next() and self.at_tok_type() in ["star", "slash"]:
            if self.at_tok_type() == "star":
                self.advance() # for division, we need to check before advancing whether to divide or not
                left = OpBinaryNode("mul", left, self.parse_unary())
            else:
                self.advance()
                left = OpBinaryNode("div", left, self.parse_unary())

        return self.tag_ast_with_debug(left)
        
    def parse_add(self):
        # includes sub
        left = self.parse_mul()

        while self.has_next() and self.at_tok_type() in ["plus", "minus"]:
            if self.at_tok_type() == "plus":
                self.advance()
                left = OpBinaryNode("add", left, self.parse_mul())
            else:
                self.advance()
                left = OpBinaryNode("sub", left, self.parse_mul())
        
        return self.tag_ast_with_debug(left)
        
    def parse_cmp(self):
        left = self.parse_add()

        while self.has_next() and self.at_tok_type() in ["equality", "less_than", "less_than_equal", "greater_than", "greater_than_equal"]:
            comparison_op = self.at_tok_type()
            self.advance() # again, like mul check the other comparison operators
            left = OpBinaryNode(comparison_op, left, self.parse_add())
        
        return self.tag_ast_with_debug(left)
    
    def parse_bitwise(self):
        left = self.parse_cmp()

        while self.has_next() and self.at_tok_type() in ["pipe", "ampersand"]:
            bitwise_op_token = self.at_tok_type()
            self.advance()
            if bitwise_op_token == "pipe":
                left = OpBinaryNode("bit_or", left, self.parse_cmp())
            elif bitwise_op_token == "ampersand":
                left = OpBinaryNode("bit_and", left, self.parse_cmp())
        
        return self.tag_ast_with_debug(left)
    
    def parse_expr(self):
        return self.tag_ast_with_debug(self.parse_bitwise())
    
    def parse_stmt_return(self):
        self.parser_assert(self.at_tok_type() == "return", "return statement start")
        self.advance()

        self.parser_assert(self.at_tok_type() in valid_expr_start, "return expr token start")
        expr_node = self.parse_expr()

        self.parser_assert(self.at_tok_type() == "semicolon", "ending stmt with semicolon")
        self.advance()

        return self.tag_ast_with_debug(StmtReturnNode(expr_node))
    
    def parse_stmt_expr(self):
        self.parser_assert(self.at_tok_type() in valid_expr_start, "stmt expr does not begin with valid token")

        result = self.parse_expr()

        self.parser_assert(self.at_tok_type() == "semicolon", "ending stmt with semicolon")
        self.advance()

        return self.tag_ast_with_debug(StmtExprNode(result))
    
    def parse_stmt_assign(self, assign_name: TypeableASTNode = None):
        # assign_name is really an expression and not a str at this point
        # self.parser_assert(self.at_tok_type() == "identifier" and \)
        #         (self.at_tok_type(1) == "assign" or (self.at_tok_type(1) == "identifier" and self.at_tok_type(2) == "assign"))
        
        # declare and initialize
        assign_type, lookahead = self.try_parse_type_name()
        if assign_type:
            self.advance(lookahead)

            assign_name = self.parse_var()

            self.parser_assert(self.at_tok_type() == "assign", "equal sign in assignment")
            self.advance()

            result = self.parse_expr()

            self.parser_assert(self.at_tok_type() == "semicolon", "ending semicolon in assignment")
            self.advance()

            return self.tag_ast_with_debug(StmtAssignNode(left=assign_name, right=result, is_define=True, type=assign_type))

        # assignment only
        else:
            if not assign_name:
                assign_name = self.parse_expr() # self.parse_var()

            self.parser_assert(self.at_tok_type() == "assign", "equal sign in assignment")
            self.advance()

            result = self.parse_expr()

            self.parser_assert(self.at_tok_type() == "semicolon", "ending semicolon in assignment")
            self.advance()

            return self.tag_ast_with_debug(StmtAssignNode(left=assign_name, right=result, type=None, is_define=False))
        
    def parse_stmt_while(self):
        self.parser_assert(self.at_tok_type() == "while", "stmt while starts with while")
        self.advance()

        self.parser_assert(self.at_tok_type() == "left_paren", "stmt while left paren")
        self.advance()

        condition = self.parse_expr()

        self.parser_assert(self.at_tok_type() == "right_paren", "stmt while end left paren")
        self.advance()

        self.parser_assert(self.at_tok_type() == "left_brace", "stmt while start block")
        body = self.parse_stmt_block()

        return self.tag_ast_with_debug(StmtWhileNode(condition, body))
    
    def parse_stmt_if_else(self):
        self.parser_assert(self.at_tok_type() == "if", "if/else start if")
        self.advance()

        self.parser_assert(self.at_tok_type() == "left_paren", "if cond begin left paren")
        self.advance()

        if_cond = self.parse_expr()
        self.parser_assert(self.at_tok_type() == "right_paren", "if cond end right paren")
        self.advance()

        self.parser_assert(self.at_tok_type() == "left_brace", "if body start brace")
        if_body = self.parse_stmt_block()

        else_body = None
        if self.at_tok_type() == "else":
            self.advance()
            if self.at_tok_type() == "if":
                else_body = self.parse_stmt_if_else()
            elif self.at_tok_type() == "left_brace":
                else_body = self.parse_stmt_block()
        
        return self.tag_ast_with_debug(StmtIfElseNode(if_cond, if_body, else_body))

    def parse_stmt_block(self):
        self.parser_assert(self.at_tok_type() == 'left_brace', "stmt block left brace")
        self.advance()

        self.parser_assert(self.at_tok_type() in valid_stmt_start_tokens, "not valid in stmt block")

        statements = []

        while self.at_tok_type() in valid_stmt_start_tokens and self.at_tok_type() != "right_brace":
            try_type, lookahead = self.try_parse_type_name()
            if try_type and self.at_tok_type(lookahead) == "identifier" and self.at_tok_type(lookahead+1) == "assign":
                statements.append(self.parse_stmt_assign())
            else:
                if self.at_tok_type() == "return":
                    statements.append(self.parse_stmt_return())
                elif self.at_tok_type(0) == "identifier" and self.at_tok_type(1) == "assign":
                    # this is for trivial reassignment
                    statements.append(self.parse_stmt_assign())
                elif self.at_tok_type() == "while":
                    statements.append(self.parse_stmt_while())
                elif self.at_tok_type() == "if":
                    statements.append(self.parse_stmt_if_else())
                elif self.at_tok_type() in valid_expr_start:
                    left_or_expr = self.parse_expr()
                    if self.at_tok_type() == "assign":
                        # pointer deref shenanigans going on
                        statements.append(self.parse_stmt_assign(assign_name=left_or_expr))
                    else:
                        statements.append(self.tag_ast_with_debug(StmtExprNode(left_or_expr)))
                        # TODO work this into parse_stmt_expr or remove the function def
                        self.parser_assert(self.at_tok_type() == 'semicolon', "ending stmt with semicolon")
                        self.advance()
                elif self.at_tok_type() == "left_brace":
                    statements.append(self.parse_stmt_block())

        self.parser_assert(self.at_tok_type() == 'right_brace', "right brace closing stmt block")

        self.advance()
        
        return self.tag_ast_with_debug(StmtBlockNode(statements))
            
    def parse_fun_def(self):
        fun_return_type, lookahead = self.try_parse_type_name()
        self.parser_assert(fun_return_type, "return type of function")
        self.advance(lookahead)

        self.parser_assert(self.at_tok_type() == "identifier", "name of function def")
        fun_name = self.at_tok_val()
        self.advance()

        self.parser_assert(self.at_tok_type() == "left_paren", "function definition left paren")
        self.advance()

        params = []
        while self.at_tok_type() != "right_paren":
            param_type, lookahead = self.try_parse_type_name()
            self.parser_assert(param_type, "func parameter type")
            self.advance(lookahead)

            self.parser_assert(self.at_tok_type() == "identifier", "name of param")
            param_name = self.at_tok_val()
            self.advance()
            
            self.parser_assert(self.at_tok_type() == "comma" or self.at_tok_type() == "right_paren", "comma in param list or end right_paren")
            if self.at_tok_type() == "comma":
                self.advance()

            params.append(self.tag_ast_with_debug(FunParamNode(param_type, self.tag_ast_with_debug(VarNode(param_name)))))

        self.parser_assert(self.at_tok_type() == "right_paren", "ending param list right_paren")
        self.advance()

        stmt_block_node = self.parse_stmt_block()
        return self.tag_ast_with_debug(FunDefNode(fun_return_type, fun_name, params, stmt_block_node, []))

    def parse(self):
        fun_defs = []
        while self.has_next():
            fun_return_type, lookahead = self.try_parse_type_name()
            if not fun_return_type: break

            fun_defs.append(self.tag_ast_with_debug(self.parse_fun_def()))
        
        return self.tag_ast_with_debug(SourceFileNode(fun_defs))
