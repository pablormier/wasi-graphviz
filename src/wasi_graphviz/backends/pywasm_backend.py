"""Pywasm backend for wasi-graphviz."""

import io
import os
import struct
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import pywasm
from pywasm import wasi

from wasi_graphviz._assets import embed_svg_assets, is_svg_output_format, staged_assets
from wasi_graphviz._constants import PACKAGE_WASM_PATH
from wasi_graphviz._exceptions import RenderError


@dataclass
class _Session:
    runtime: pywasm.core.Runtime
    wasi: wasi.Preview1
    instance: object
    memory: object


class PywasmBackend:
    """Pure-Python Graphviz backend using pywasm."""

    def __init__(self, wasm_path: Union[str, Path] = PACKAGE_WASM_PATH) -> None:
        self.wasm_path = Path(wasm_path)
        if not self.wasm_path.exists():
            raise FileNotFoundError(f"WASM file not found: {self.wasm_path}")

        self._session = self._create_session()

    def _create_session(self, asset_dir: Path | None = None) -> _Session:
        runtime = pywasm.core.Runtime()
        # pywasm Preview1 accesses sys.stdin.fileno() on construction.
        # When pytest captures stdin this is a pseudofile whose fileno()
        # raises UnsupportedOperation, so we temporarily substitute the
        # real stdin.
        _orig_stdin = sys.stdin
        try:
            try:
                sys.stdin.fileno()
            except (OSError, io.UnsupportedOperation):
                sys.stdin = sys.__stdin__
            dirs = {} if asset_dir is None else {"/assets": str(asset_dir)}
            wasi_context = wasi.Preview1(args=[], dirs=dirs, envs={})
        finally:
            sys.stdin = _orig_stdin
        try:
            wasi_context.bind(runtime)
            instance = runtime.instance_from_file(str(self.wasm_path))
            memory = runtime.exported_memory(instance, "memory")
        except BaseException:
            self._close_wasi_descriptors(wasi_context)
            raise
        return _Session(runtime, wasi_context, instance, memory)

    @staticmethod
    def _close_wasi_descriptors(wasi_context: wasi.Preview1) -> None:
        # Preview1 keeps the host descriptors for preopened directories in its
        # table. Close those along with any descriptor Graphviz left open.
        for file in wasi_context.fd:
            if (
                file.wasm_type != wasi.Preview1.FILETYPE_CHARACTER_DEVICE
                and file.host_status == wasi.Preview1.FILE_STATUS_OPENED
            ):
                try:
                    os.close(file.host_fd)
                except OSError:
                    pass
                file.host_status = wasi.Preview1.FILE_STATUS_CLOSED

    @classmethod
    def _dispose_session(cls, session: _Session) -> None:
        cls._close_wasi_descriptors(session.wasi)

    @staticmethod
    def _malloc(session: _Session, size: int) -> int:
        return session.runtime.invocate(session.instance, "malloc", [size])[0]

    @staticmethod
    def _free(session: _Session, addr: int) -> None:
        session.runtime.invocate(session.instance, "graphviz_free", [addr])

    def _write_string(self, session: _Session, text: str) -> int:
        data = (text + "\x00").encode("utf-8")
        addr = self._malloc(session, len(data))
        session.memory.data[addr : addr + len(data)] = data
        return addr

    @staticmethod
    def _read_bytes(session: _Session, addr: int, length: int) -> bytes:
        return bytes(session.memory.data[addr : addr + length])

    @staticmethod
    def _read_cstring(session: _Session, addr: int, max_len: int = 4096) -> str:
        buf = bytes(session.memory.data[addr : addr + max_len])
        nul = buf.find(0)
        if nul >= 0:
            buf = buf[:nul]
        return buf.decode("utf-8", errors="replace")

    @staticmethod
    def _read_u32(session: _Session, addr: int) -> int:
        return struct.unpack("<I", bytes(session.memory.data[addr : addr + 4]))[0]

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
            if staged.directory is None:
                return self._render_in_session(
                    self._session, dot_source, format, engine
                )

            session = self._create_session(staged.directory)
            try:
                output = self._render_in_session(session, dot_source, format, engine)
            finally:
                self._dispose_session(session)
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
            result_ptr = session.runtime.invocate(
                session.instance,
                "graphviz_render",
                [dot_ptr, fmt_ptr, engine_ptr, out_len_ptr],
            )[0]

            if result_ptr == 0:
                err_ptr = session.runtime.invocate(
                    session.instance, "graphviz_last_error", []
                )[0]
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
