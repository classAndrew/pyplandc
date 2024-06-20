from c_ast.lex import Lexer
from c_ast.parse import Parser, LiteralNode
from c_ast.semantics import Checker
from ir.ir_tac import TAC
from ir.ir_tacvm import TACVM
from cgen.x86_cgen import X86VirtCodeGen

if __name__ == "__main__":
    import argparse
    argp = argparse.ArgumentParser(prog="pyplandc", description="A C compiler written in Python")
    argp.add_argument("-i", "--input_file", type=str, default="/dev/stdin")
    argp.add_argument("-o", "--output_file", type=str, default="/dev/stdout")

    opt = argp.parse_args()
    with open(opt.input_file, 'r') as f:
        source_file = f.read()

    result = Parser(Lexer(source_file).tokenize(), source_file).parse()
    Checker().check_source_file(result)
    x86 = X86VirtCodeGen()
    x86.x86_source_file(result)

    with open(opt.output_file, 'w') as f:
        f.write(x86.pretty_x86() + '\n')