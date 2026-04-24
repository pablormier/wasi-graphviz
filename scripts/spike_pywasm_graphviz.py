"""Spike script: verify pywasm can render a DOT graph via graphviz.wasm."""

import pywasm
from pywasm import wasi

WASM_PATH = "build/graphviz.wasm"


def main():
    runtime = pywasm.core.Runtime()
    preview = wasi.Preview1(args=[], dirs={}, envs={})
    preview.bind(runtime)
    inst = runtime.instance_from_file(WASM_PATH)

    mem = runtime.exported_memory(inst, "memory")

    def write_str(s):
        b = (s + "\x00").encode("utf-8")
        addr = runtime.invocate(inst, "malloc", [len(b)])[0]
        mem.data[addr : addr + len(b)] = b
        return addr

    def read_str(addr):
        result = b""
        for i in range(addr, addr + 65536):
            b = mem.data[i]
            if b == 0:
                break
            result += bytes([b])
        return result.decode("utf-8")

    dot = "digraph G { a -> b; }"
    dot_ptr = write_str(dot)
    fmt_ptr = write_str("svg")
    engine_ptr = write_str("dot")

    result_ptr = runtime.invocate(
        inst, "graphviz_render", [dot_ptr, fmt_ptr, engine_ptr]
    )[0]

    if result_ptr == 0:
        err_ptr = runtime.invocate(inst, "graphviz_last_error", [])[0]
        error = read_str(err_ptr)
        print(f"Render failed: {error}")
    else:
        svg = read_str(result_ptr)
        print(svg[:500])
        runtime.invocate(inst, "graphviz_free", [result_ptr])

    runtime.invocate(inst, "graphviz_free", [dot_ptr])
    runtime.invocate(inst, "graphviz_free", [fmt_ptr])
    runtime.invocate(inst, "graphviz_free", [engine_ptr])


if __name__ == "__main__":
    main()
