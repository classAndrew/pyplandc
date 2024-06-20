int f(int n) {
    if (n == 0) {
        return 1;
    }

    return n*f(n-1);
}

int main() {
    int a = f(5);
    return 0;
}