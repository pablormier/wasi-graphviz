"""Validation and temporary staging for files exposed to Graphviz's WASI guest."""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import base64
import posixpath
import re
import tempfile


AssetContent = bytes | bytearray | memoryview
AssetMapping = Mapping[str, AssetContent] | None

_ASSET_PATH = re.compile(r"[A-Za-z0-9._/-]+", re.ASCII)
_SVG_IMAGE_TYPES = {
    ".gif": "image/gif",
    ".jpe": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}
_SVG_IMAGE_TAG = re.compile(rb"<image\b[^>]*>", re.IGNORECASE)
_IMAGE_HREF = re.compile(
    rb"(?P<prefix>(?<![A-Za-z0-9_.:-])(?:xlink:)?href\s*=\s*)"
    rb"(?P<quote>[\"'])(?P<path>[^\"']+)(?P=quote)"
)


@dataclass(frozen=True)
class AssetBundle:
    """Validated asset files and their temporary WASI host directory."""

    directory: Path | None
    files: Mapping[str, bytes]


def _validate_assets(assets: AssetMapping) -> dict[str, bytes]:
    if assets is None:
        return {}
    if not isinstance(assets, Mapping):
        raise TypeError("assets must be a mapping of relative paths to bytes")

    validated: dict[str, bytes] = {}
    for name, content in assets.items():
        if not isinstance(name, str):
            raise TypeError("asset paths must be strings")
        parts = name.split("/")
        if (
            not _ASSET_PATH.fullmatch(name)
            or name.startswith("/")
            or any(part in ("", ".", "..") for part in parts)
            or any(part.endswith((".", " ")) for part in parts)
            or any(_is_windows_device_name(part) for part in parts)
        ):
            raise ValueError(f"asset path must be a safe relative path: {name!r}")
        if not isinstance(content, (bytes, bytearray, memoryview)):
            raise TypeError(f"asset content for {name!r} must be bytes-like")
        validated[name] = bytes(content)
    return validated


_WINDOWS_DEVICE_NAME = re.compile(
    r"^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9]|LPT[1-9])(?:\..*)?$", re.I
)


def _is_windows_device_name(part: str) -> bool:
    return _WINDOWS_DEVICE_NAME.fullmatch(part) is not None


def is_svg_output_format(format: str) -> bool:
    """Check the SVG base format in Graphviz's colon-separated plugin selector."""
    base_format = format.casefold().split(":", maxsplit=1)[0]
    return base_format in {"svg", "svg_inline"}


@contextmanager
def staged_assets(assets: AssetMapping) -> Iterator[AssetBundle]:
    """Expose validated asset contents from a temporary directory for one render."""
    validated = _validate_assets(assets)
    if not validated:
        yield AssetBundle(directory=None, files=validated)
        return

    with tempfile.TemporaryDirectory(prefix="wasi-graphviz-") as tmp_dir:
        # Keep the mounted directory inside a private parent. This also
        # contains prefix-based path checks in some WASI implementations.
        root = Path(tmp_dir) / "assets"
        root.mkdir()
        for name, content in validated.items():
            destination = root.joinpath(*name.split("/"))
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("xb") as output:
                    output.write(content)
            except FileExistsError as exc:
                raise ValueError(
                    f"asset paths collide on this filesystem: {name!r}"
                ) from exc
        yield AssetBundle(directory=root, files=validated)


def embed_svg_assets(svg: bytes, files: Mapping[str, bytes]) -> bytes:
    """Embed referenced staged image assets as base64 data URIs in SVG output."""
    if not files:
        return svg

    data_uris: dict[str, bytes] = {}
    prefix = "/assets/"
    for image in _SVG_IMAGE_TAG.finditer(svg):
        for href_match in _IMAGE_HREF.finditer(image.group(0)):
            href = href_match.group("path").decode("utf-8")
            name = _resolve_asset_reference(href, files, prefix)
            if name is None:
                continue
            suffix = Path(name).suffix.lower()
            mime = _SVG_IMAGE_TYPES.get(suffix)
            if mime is None:
                supported = ", ".join(sorted(_SVG_IMAGE_TYPES))
                raise ValueError(
                    f"SVG asset {name!r} has an unsupported image extension; "
                    f"supported extensions are {supported}"
                )
            encoded = base64.b64encode(files[name]).decode("ascii")
            data_uris[href] = f"data:{mime};base64,{encoded}".encode("ascii")

    if not data_uris:
        return svg

    def replace_image(match: re.Match[bytes]) -> bytes:
        def replace_href(href_match: re.Match[bytes]) -> bytes:
            path = href_match.group("path").decode("utf-8")
            data_uri = data_uris.get(path)
            if data_uri is None:
                return href_match.group(0)
            return (
                href_match.group("prefix")
                + href_match.group("quote")
                + data_uri
                + href_match.group("quote")
            )

        return _IMAGE_HREF.sub(replace_href, match.group(0))

    embedded = _SVG_IMAGE_TAG.sub(replace_image, svg)
    return embedded


def _resolve_asset_reference(
    href: str, files: Mapping[str, bytes], prefix: str
) -> str | None:
    """Map only normalized guest paths or exact relative asset keys to files."""
    if href.startswith(prefix):
        guest_path = posixpath.normpath(href)
        if guest_path.startswith(prefix):
            name = guest_path[len(prefix) :]
            return name if name in files else None
        return None

    # Graphviz keeps a relative image name in the SVG when imagepath found the
    # file. Resolve it only when exactly one supplied path ends with that name;
    # duplicate basenames could refer to different imagepath directories.
    if href.startswith("/") or ":" in href:
        return None
    relative_path = posixpath.normpath(href)
    if relative_path in ("", ".", "..") or relative_path.startswith("../"):
        return None
    matches = [
        name
        for name in files
        if name == relative_path or name.endswith(f"/{relative_path}")
    ]
    if len(matches) > 1:
        raise ValueError(
            f"SVG image reference {href!r} matches multiple supplied assets; "
            "use an explicit /assets/<path> image reference"
        )
    return matches[0] if matches else None
