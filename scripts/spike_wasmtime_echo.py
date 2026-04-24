"""Spike script: verify wasmtime can load and call a tiny WASI C ABI module."""

import wasmtime

WASM_PATH = "build/echo.wasm"


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
    echo = instance.exports(store)["echo"]
    free = instance.exports(store)["graphviz_free"]
    malloc = instance.exports(store)["malloc"]

    # Allocate and write input string
    input_bytes = b"hello\x00"
    input_len = len(input_bytes)
    malloc_addr = malloc(store, input_len)
    mem.write(store, input_bytes, malloc_addr)

    # Call echo
    result_addr = echo(store, malloc_addr)

    # Read result string
    result = b""
    for i in range(result_addr, result_addr + 1024):
        b = mem.read(store, i, i + 1)[0]
        if b == 0:
            break
        result += bytes([b])

    print(result.decode("utf-8"))

    # Free both allocations
    free(store, result_addr)
    free(store, malloc_addr)


if __name__ == "__main__":
    main()
