"""Spike script: verify pywasm can load and call a tiny WASI C ABI module."""

import pywasm
from pywasm import wasi

WASM_PATH = "build/echo.wasm"


def main():
    runtime = pywasm.core.Runtime()
    preview = wasi.Preview1(args=[], dirs={}, envs={})
    preview.bind(runtime)
    inst = runtime.instance_from_file(WASM_PATH)

    mem = runtime.exported_memory(inst, "memory")

    # Allocate and write input string
    input_bytes = b"hello\x00"
    input_len = len(input_bytes)
    malloc_addr = runtime.invocate(inst, "malloc", [input_len])[0]
    mem.data[malloc_addr : malloc_addr + input_len] = input_bytes

    # Call echo
    result_addr = runtime.invocate(inst, "echo", [malloc_addr])[0]

    # Read result string
    result = b""
    for i in range(result_addr, result_addr + 1024):
        b = mem.data[i]
        if b == 0:
            break
        result += bytes([b])

    print(result.decode("utf-8"))

    # Free both allocations
    runtime.invocate(inst, "graphviz_free", [result_addr])
    runtime.invocate(inst, "graphviz_free", [malloc_addr])


if __name__ == "__main__":
    main()
