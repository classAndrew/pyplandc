from typing import Tuple, List
from collections import namedtuple

LexicalToken = namedtuple("LexicalToken", ["token_type", "token_val", "line_num", "char_num"])

# lexer
class Lexer:
    def __init__(self, code) -> None:
        self.line_num = 0
        self.p = 0
        self.code = code

    def advance(self):
        self.p += 1

    def has_next(self) -> bool:
        return self.p < len(self.code)

    def at(self) -> str:
        return self.code[self.p]
    
    def peek_char(self) -> str:
        if self.p + 1 >= len(self.code):
            return ''
        
        return self.code[self.p + 1]
    
    def skip_whitespace(self):
        while self.has_next() and self.at() in [' ', '\t', '\n']:
            self.line_num += self.at() == '\n'
            self.advance()

    def cmp_literal_and_advance(self, literal):
        beginning = self.code[self.p:self.p+len(literal)]
        result = len(beginning) == len(literal) and beginning == literal
        if result: 
            self.p += len(literal)

        return result
    
    def create_token(self, token_type: str, token_val: object):
        return LexicalToken(token_type, token_val, self.line_num, self.p)
    
    def next_keyword(self) -> Tuple[str, object]:
        if self.cmp_literal_and_advance("return"):
            return self.create_token("return", "return")
        elif self.cmp_literal_and_advance("if"):
            return self.create_token("if", "if")
        elif self.cmp_literal_and_advance("else"):
            return self.create_token("else", "else")
        elif self.cmp_literal_and_advance("while"):
            return self.create_token("while", "while")
        elif self.cmp_literal_and_advance("struct"):
            return self.create_token("struct", "struct")
        elif self.cmp_literal_and_advance("unsigned"):
            return self.create_token("unsigned", "unsigned")
        # elif self.cmp_literal_and_advance("const"):
        #     return self.create_token("const", "const")
        
        return False
    
    def next_identifier(self) -> Tuple[str, object]:
        char_buffer = []
        while self.has_next() and (self.at().isalnum() or self.at() == '_'):
            char_buffer.append(self.at())
            self.advance()
        
        return self.create_token("identifier", ''.join(char_buffer))
    
    def next_decimal(self) -> Tuple[str, object]:
        # decimals may return literal ints or literal floats
        digits = []
        seen_dot = False
        while self.has_next() and (self.at().isdigit() or self.at() == '.'):
            if seen_dot and self.at() == '.':
                break

            seen_dot = seen_dot or self.at() == '.'
            
            digits.append(self.at())

            self.advance()
        
        if '.' in digits:
            return self.create_token("literal_decimal", float(''.join(digits)))
        
        return self.create_token("literal_integer", int(''.join(digits)))


    def next_token(self) -> Tuple[str, object]:
        self.skip_whitespace()

        if not self.has_next():
            return False
        
        curr_char = self.code[self.p]

        if curr_char.isalpha():
            keyword = self.next_keyword()
            if keyword:
                return keyword
            return self.next_identifier()
            
        elif curr_char == '(':
            self.advance()
            return self.create_token("left_paren", curr_char)
            
        elif curr_char == ')':
            self.advance()
            return self.create_token("right_paren", curr_char)

        elif curr_char == "{":
            self.advance()
            return self.create_token("left_brace", curr_char)

        elif curr_char == "}":
            self.advance()
            return self.create_token("right_brace", curr_char)
    
        elif curr_char == ';':
            self.advance()
            return self.create_token("semicolon", curr_char)
        
        elif curr_char == ',':
            self.advance()
            return self.create_token("comma", curr_char)
        
        elif curr_char == '=':
            if self.peek_char() == '=':
                self.advance(); self.advance()
                return self.create_token("equality", '==')
            else:
                self.advance()
                return self.create_token("assign", '=')
            
        elif curr_char == ">":
            if self.peek_char() == '=':
                self.advance(); self.advance()
                return self.create_token("greater_than_equal", ">=")
            else:
                self.advance()
                return self.create_token("greater_than", ">")
        
        elif curr_char == "<":
            if self.peek_char() == "=":
                self.advance(); self.advance()
                return self.create_token("less_than_equal", "<=")
            else:
                self.advance()
                return self.create_token("less_than", "<")
        
        elif curr_char == "&":
            # add short circuiting bit ops later
            self.advance()
            return self.create_token("ampersand", curr_char)

        elif curr_char == "|":
            self.advance()
            return self.create_token("pipe", curr_char)
            
        elif curr_char == '*':
            self.advance()
            return self.create_token("star", curr_char)
        
        elif curr_char == '/':
            self.advance()
            return self.create_token("slash", curr_char)

        elif curr_char == '+':
            self.advance()
            return self.create_token("plus", curr_char)

        elif curr_char == '-': 
            # negative decimal literals unfortunately need to be handled in parsing
            self.advance()
            return self.create_token("minus", curr_char)

            # if self.at().isdigit():
            #     tok_type, tok_value = self.next_decimal()
            #     return tok_type, -tok_value
        
        elif curr_char == ".":
            next_char = self.peek_char()
            if not next_char or next_char.isalpha():
                self.advance()
                return "dot",

            if next_char.isdigit():
                return self.next_decimal()
        
        elif curr_char.isdigit():
            return self.next_decimal()
        
    def tokenize(self) -> List[Tuple[str, object]]:
        tokens = []
        while self.has_next():
            result = self.next_token()
            if not result: 
                break

            tokens.append(result)

        return tokens
