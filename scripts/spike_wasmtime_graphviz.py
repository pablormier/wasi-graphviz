"""Spike script: verify wasmtime can render a DOT graph via graphviz.wasm."""

import wasmtime

WASM_PATH = "build/graphviz.wasm"


def main():
    engine = wasmtime.Engine()
    store = wasmtime.Store(engine)
    module = wasmtime.Module.from_file(engine, WASM_PATH)

    linker = wasmtime.Linker(engine)
    linker.define_wasi()

    wasi_config = wasmtime.WasiConfig()
    wasi_config.inherit_stdout()
    store.set_wasi(wasi_config)

    instance = linker.instantiate(store, module)

    mem = instance.exports(store)["memory"]
    render = instance.exports(store)["graphviz_render"]
    free = instance.exports(store)["graphviz_free"]
    malloc = instance.exports(store)["malloc"]
    last_error = instance.exports(store)["graphviz_last_error"]

    def write_str(s):
        b = (s + "\x00").encode("utf-8")
        addr = malloc(store, len(b))
        mem.write(store, b, addr)
        return addr

    def read_str(addr):
        result = b""
        for i in range(addr, addr + 65536):
            b = mem.read(store, i, i + 1)[0]
            if b == 0:
                break
            result += bytes([b])
        return result.decode("utf-8")

    dot = "digraph G { a -> b; }"
    dot_ptr = write_str(dot)
    fmt_ptr = write_str("svg")
    engine_ptr = write_str("dot")

    result_ptr = render(store, dot_ptr, fmt_ptr, engine_ptr)

    if result_ptr == 0:
        err_ptr = last_error(store)
        error = read_str(err_ptr)
        print(f"Render failed: {error}")
    else:
        svg = read_str(result_ptr)
        print(svg[:500])
        free(store, result_ptr)

    free(store, dot_ptr)
    free(store, fmt_ptr)
    free(store, engine_ptr)


if __name__ == "__main__":
    main()
