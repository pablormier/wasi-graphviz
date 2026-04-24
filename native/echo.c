#include <stdlib.h>
#include <string.h>

// Tiny echo module to prove WASI C ABI compatibility

char *echo(const char *input) {
    size_t len = strlen(input);
    char *out = malloc(len + 1);
    if (!out) return NULL;
    memcpy(out, input, len + 1);
    return out;
}

void graphviz_free(char *ptr) {
    free(ptr);
}

// Dummy main to satisfy zig cc wasm32-wasi libc startup
int main(void) { return 0; }
