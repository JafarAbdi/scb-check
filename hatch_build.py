"""Build hook that packages the fully-static musl `scb-check` binary.

The binary is fetched from this project's GitHub release matching the package
version and host architecture, so installing the pre-commit hook needs no Rust
toolchain. A locally cargo-built binary is used instead when present (dev/CI).
The binary is statically linked against musl, so it runs on any Linux distro;
the `manylinux2014` wheel tag is only the broadest tag pip accepts.
"""

from __future__ import annotations

import hashlib
import platform
import stat
import urllib.request
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_REPO = "JafarAbdi/scb-check"

# Linux-only for now; extend this map to add platforms.
_TARGETS = {
    "x86_64": ("x86_64-unknown-linux-musl", "manylinux2014_x86_64"),
    "aarch64": ("aarch64-unknown-linux-musl", "manylinux2014_aarch64"),
}


class CustomBuildHook(BuildHookInterface):
    """Package the static musl binary into the wheel."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Provide the static binary (local build or release download)."""
        if self.target_name != "wheel":
            return

        arch = platform.machine()
        if arch not in _TARGETS:
            msg = f"unsupported architecture {arch!r}; supported: {sorted(_TARGETS)}"
            raise RuntimeError(msg)
        triple, wheel_platform = _TARGETS[arch]

        build_data["pure_python"] = False
        build_data["infer_tag"] = False
        build_data["tag"] = f"py3-none-{wheel_platform}"

        root = Path(self.root)
        local = root / "target" / triple / "release" / "scb-check"
        staged = root / "build" / "bin" / "scb-check"
        staged.parent.mkdir(parents=True, exist_ok=True)
        if local.is_file():
            staged.write_bytes(local.read_bytes())
        else:
            _download_release_binary(version, triple, staged)
        staged.chmod(
            staged.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
        )
        build_data.setdefault("shared_scripts", {})[str(staged)] = "scb-check"


def _download_release_binary(version: str, triple: str, dest: Path) -> None:
    url = f"https://github.com/{_REPO}/releases/download/v{version}/scb-check-{triple}"
    binary = _fetch(url)
    expected = _fetch(f"{url}.sha256").split()[0].decode()
    actual = hashlib.sha256(binary).hexdigest()
    if actual != expected:
        msg = f"sha256 mismatch for {url}: got {actual}, expected {expected}"
        raise RuntimeError(msg)
    dest.write_bytes(binary)


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url) as response:  # noqa: S310
        return response.read()
