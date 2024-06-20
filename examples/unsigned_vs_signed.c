int main() {
    int a = 5;
    int b = 4;
    int c = a * b; // should generate an imul

    unsigned int ub = (unsigned int)5;
    unsigned int ua = (unsigned int)4;
    unsigned int uc = ua * ub; // should generate a mul
}