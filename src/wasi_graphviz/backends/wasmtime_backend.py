"""Wasmtime backend for wasi-graphviz."""

import struct
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import wasmtime

from wasi_graphviz._constants import PACKAGE_WASM_PATH
from wasi_graphviz._assets import embed_svg_assets, is_svg_output_format, staged_assets
from wasi_graphviz._exceptions import RenderError


@dataclass
class _Session:
    store: wasmtime.Store
    memory: wasmtime.Memory
    render_fn: object
    free_fn: object
    malloc_fn: object
    last_error_fn: object


class WasmtimeBackend:
    """Fast Graphviz backend using wasmtime."""

    def __init__(self, wasm_path: Union[str, Path] = PACKAGE_WASM_PATH) -> None:
        self.wasm_path = Path(wasm_path)
        if not self.wasm_path.exists():
            raise FileNotFoundError(f"WASM file not found: {self.wasm_path}")

        self._engine = wasmtime.Engine()
        self._module = wasmtime.Module.from_file(self._engine, str(self.wasm_path))
        self._session = self._create_session()

    def _create_session(self, asset_dir: Path | None = None) -> _Session:
        store = wasmtime.Store(self._engine)
        linker = wasmtime.Linker(self._engine)
        linker.define_wasi()

        wasi_config = wasmtime.WasiConfig()
        wasi_config.inherit_stdout()
        if asset_dir is not None:
            wasi_config.preopen_dir(
                str(asset_dir),
                "/assets",
                dir_perms=wasmtime.DirPerms.READ_ONLY,
                file_perms=wasmtime.FilePerms.READ_ONLY,
            )
        store.set_wasi(wasi_config)

        instance = linker.instantiate(store, self._module)
        exports = instance.exports(store)
        return _Session(
            store=store,
            memory=exports["memory"],
            render_fn=exports["graphviz_render"],
            free_fn=exports["graphviz_free"],
            malloc_fn=exports["malloc"],
            last_error_fn=exports["graphviz_last_error"],
        )

    @staticmethod
    def _malloc(session: _Session, size: int) -> int:
        return session.malloc_fn(session.store, size)

    @staticmethod
    def _free(session: _Session, addr: int) -> None:
        session.free_fn(session.store, addr)

    def _write_string(self, session: _Session, text: str) -> int:
        data = (text + "\x00").encode("utf-8")
        addr = self._malloc(session, len(data))
        session.memory.write(session.store, data, addr)
        return addr

    @staticmethod
    def _read_bytes(session: _Session, addr: int, length: int) -> bytes:
        return bytes(session.memory.read(session.store, addr, addr + length))

    @staticmethod
    def _read_cstring(session: _Session, addr: int, max_len: int = 4096) -> str:
        buf = session.memory.read(session.store, addr, addr + max_len)
        nul = buf.find(0)
        if nul >= 0:
            buf = buf[:nul]
        return bytes(buf).decode("utf-8", errors="replace")

    @staticmethod
    def _read_u32(session: _Session, addr: int) -> int:
        return struct.unpack("<I", session.memory.read(session.store, addr, addr + 4))[
            0
        ]

    def render(
        self,
        dot_source: str,
        *,
        format: str = "svg",
        engine: str = "dot",
        assets: Mapping[str, bytes | bytearray | memoryview] | None = None,
    ) -> bytes:
        """Render a DOT string to the requested format."""
        with staged_assets(assets) as staged:
            session = (
                self._session
                if staged.directory is None
                else self._create_session(staged.directory)
            )
            output = self._render_in_session(session, dot_source, format, engine)
            if is_svg_output_format(format) and staged.files:
                return embed_svg_assets(output, staged.files)
            return output

    def _render_in_session(
        self, session: _Session, dot_source: str, format: str, engine: str
    ) -> bytes:
        dot_ptr = self._write_string(session, dot_source)
        fmt_ptr = self._write_string(session, format)
        engine_ptr = self._write_string(session, engine)
        out_len_ptr = self._malloc(session, 4)

        try:
            result_ptr = session.render_fn(
                session.store, dot_ptr, fmt_ptr, engine_ptr, out_len_ptr
            )

            if result_ptr == 0:
                err_ptr = session.last_error_fn(session.store)
                error = self._read_cstring(session, err_ptr)
                raise RenderError(error or "Graphviz rendering failed")

            out_len = self._read_u32(session, out_len_ptr)
            try:
                return self._read_bytes(session, result_ptr, out_len)
            finally:
                self._free(session, result_ptr)
        finally:
            self._free(session, dot_ptr)
            self._free(session, fmt_ptr)
            self._free(session, engine_ptr)
            self._free(session, out_len_ptr)
