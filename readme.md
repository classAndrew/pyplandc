Pland Compiler for the C Programming Language*

Compiler Pipeline

1. Lexical Analysis 
    - Generates necessary tokens based on lexical rules
2. Parsing
    - Generates AST from tokens
3. Semantic Analysis 
    - Checks program types and creates typed-AST
    - Automatically type casts between different types by inserting TypeCast Nodes
4. IR Generation
    - 3AC-based IR 
    - Unlimited Virtual Registers
    - Function call abstractions
5. Optional IR VM
    - Helps for debugging generated IR
6. Targetted low-level IR 
    - Register allocation for specific architectures
    - Respecting calling conventions at IR level
7. IR to Target Translation
    - Emits assembly instructions for target arch


There are a few major differences / features missing in this implementation that may be added in the future
1. No preprocessor macros
2. Stricter type checking (signed integers are not automatically cast to unsigned or vice versa), though type promotion is implemented.
3. No for-loop semantics
4. No string literals
5. No user-defined types (structs, unions, enums, typedefs)

*= most of the C programming features

