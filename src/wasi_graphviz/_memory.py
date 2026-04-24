"""Memory helpers for WASM backends."""

from typing import Protocol


class MemoryLike(Protocol):
    """Protocol for WASM memory objects."""

    def read(self, addr: int, length: int) -> bytearray: ...

    def write(self, addr: int, data: bytes) -> None: ...


def write_string(mem, addr: int, text: str) -> None:
    """Write a null-terminated UTF-8 string into WASM memory."""
    data = (text + "\x00").encode("utf-8")
    mem.data[addr : addr + len(data)] = data


def read_string(mem, addr: int, max_len: int = 65536) -> str:
    """Read a null-terminated UTF-8 string from WASM memory."""
    result = bytearray()
    for i in range(addr, addr + max_len):
        b = mem.data[i]
        if b == 0:
            break
        result.append(b)
    return result.decode("utf-8")
