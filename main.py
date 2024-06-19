from lex import Lexer
from parse import Parser, LiteralNode
from semantics import Checker
from ir_tac import TAC
from ir_tacvm import TACVM
from x86_cgen import X86VirtCodeGen

lex_testcase_1 = """
float my_function(int arg0, int arg1) {
    int a = 1;
    int b = 2;
    if (a + 1 == b) {
        return 1.05;
    } else {
        return .95;
    }

    return -1.0;
}
"""

# assert Lexer(lex_testcase_1).tokenize() == [('identifier', 'float'), ('identifier', 'my_function'), ('left_paren', '('), ('identifier', 'int'), ('identifier', 'arg0'), ('comma', ','), ('identifier', 'int'), ('identifier', 'arg1'), ('right_paren', ')'), ('left_brace', '{'), ('identifier', 'int'), ('identifier', 'a'), ('assign', '='), ('literal_integer', 1), ('semicolon', ';'), ('identifier', 'int'), ('identifier', 'b'), ('assign', '='), ('literal_integer', 2), ('semicolon', ';'), ('if', 'if'), ('left_paren', '('), ('identifier', 'a'), ('plus', '+'), ('literal_integer', 1), ('equality', '=='), ('identifier', 'b'), ('right_paren', ')'), ('left_brace', '{'), ('return', 'return'), ('literal_decimal', 1.05), ('semicolon', ';'), ('right_brace', '}'), ('else', 'else'), ('left_brace', '{'), ('return', 'return'), ('literal_decimal', 0.95), ('semicolon', ';'), ('right_brace', '}'), ('return', 'return'), ('literal_decimal', -1.0), ('semicolon', ';'), ('right_brace', '}')]

parse_testcase_1 = """
float my_function(int arg0, int arg1) { int a = 0; a = 1; while (a == 0) {a = a + 1;} return 2 + ((1+2) * 3) - 1 + b + fun1(2,3.5); }
"""

parse_testcase_2 = """
float my_function(int arg0, int arg1) { int a = 0; int b = 1; while (a < b | (b < 100 & a > 0)) { a = a + 1; } }
"""

parse_testcase_3 = """
unsigned char *ab(int a0, float *a1) { int t0 = *(int *)(unsigned int *)a0*(*a1)*4; return (unsigned char *)t0; }
"""

type_testcase_1 = """
int main(int argc, char **argv) {
    int a = 0;
}
"""

type_testcase_2 = """
int f(int n) {
    int r = n*f(n-1);
    {
        int redefined = 0;
        int r = 2;
    }
    return r;
}
"""

type_testcase_3 = """
int f(int n) {
    while (1) {
        int a = 3;
    }
}
"""

type_testcase_4 = """
int f(int n) {
    {
        int n = 3;
    }
}
"""

ir_testcase_1 = """
int main(int n) {
    int a = 0;
    int b = 1;

    while (n < 5) {
        n = n - 1;
        int tmp = b;
        b = a + b;
        a = tmp;
    }
}
"""

vm_testcase_1 = """
int main() {
    int n = 10;
    int a = 0;
    int b = 1;

    while (n > 0) {
        n = n - 1;
        int tmp = b;
        b = a + b;
        a = tmp;
    }
}
"""

vm_testcase_2 = """
int main() {
    int n = 10;
    int s = 0;
    while (n > 0) {
        s = s + n;
        n = n - 1;
    }
}
"""

vm_testcase_3 = """
int main() {
    int n = 10;
    int *b = &n;
    int **c = &b;
    int a = **c;
}
"""

vm_testcase_4 = """
int main() {
    int a = 0;
    int *b = &a;
    int **c = &b;
    *(*c+(int*)1) = 1;
}
"""

vm_testcase_5 = """
int main() {
    int a = 0;
    int *b = &a;
    int **c = &b;
    *&*c = (int*)1;
}
"""

vm_testcase_6 = """
int f(int n) {
    if (n == 0) {
        return 1;
    }

    return n*f(n-1);
}

int main() {
    int a = f(3);
    return 0;
}
"""

vm_testcase_7 = """
int main() {
    int a = 1 + 2 + 3 + 4 + 5 + 6;
}
"""

vm_testcase_8 = """
int spill(int a, int b, int c, int d, int e, int f, int g, int h) {
    int r = g + h;
    return r;
}

int main() {
    return spill(1, 2, 3, 4, 5, 6, 7); 
}
"""

# print(Parser(Lexer(lex_testcase_1).tokenize()).parse())
# print(Parser(Lexer("2 + ((1+2) * 3) - 1 + b + c(2,3.5)").tokenize()).parse_expr())
# print(Lexer("while (a == 0) { a = a + 1; }").tokenize())
# print(Parser(Lexer("float my_function(int arg0, int arg1) { while (a == 0) {a = a + 1;} }").tokenize()).parse())
# print(Parser(Lexer("float my_function(int arg0, int arg1) { if (a) {1+1;} else {2+2;} }").tokenize()).parse())

result = Parser(Lexer(vm_testcase_8).tokenize(), vm_testcase_8).parse()
Checker().check_source_file(result)
# print('\n', result.pretty_ast())
# tac = TAC()
# tac.tac_source_file(result)
# print(tac.pretty_tac_ir())

# tacvm = TACVM(tac)
# tacvm.run()
# print(tacvm.reg_file)
# print(tacvm.memory)
x86 = X86VirtCodeGen()
x86.x86_source_file(result)
print(x86.pretty_x86())