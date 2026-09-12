"""Build hook that packages the fully-static musl `scb-check` binary.

The binary is statically linked against musl (no libc dependency), so it runs
on any Linux distribution regardless of glibc version. The wheel is therefore
tagged `manylinux2014` (glibc 2.17) purely as the broadest tag pip will accept;
the binary itself has no glibc floor.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# Linux-only for now; extend this map to add platforms.
_MUSL_TARGETS = {
    "x86_64": ("x86_64-unknown-linux-musl", "manylinux2014_x86_64"),
    "aarch64": ("aarch64-unknown-linux-musl", "manylinux2014_aarch64"),
}


class CustomBuildHook(BuildHookInterface):
    """Build the static musl Rust CLI and include it in the wheel."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Cross-build the static binary before wheel assembly."""
        _ = version
        if self.target_name != "wheel":
            return

        arch = platform.machine()
        if arch not in _MUSL_TARGETS:
            msg = f"unsupported architecture {arch!r}; supported: {sorted(_MUSL_TARGETS)}"
            raise RuntimeError(msg)
        triple, wheel_platform = _MUSL_TARGETS[arch]

        build_data["pure_python"] = False
        build_data["infer_tag"] = False
        build_data["tag"] = f"py3-none-{wheel_platform}"

        root = Path(self.root)
        cargo = shutil.which("cargo")
        if cargo is None:
            msg = "cargo is required to build the scb-check wheel"
            raise RuntimeError(msg)

        env = dict(os.environ)
        # tree-sitter's C sources need a musl C compiler for the musl target.
        env.setdefault(
            f"CC_{triple.replace('-', '_')}",
            "musl-gcc" if arch == "x86_64" else f"{arch}-linux-musl-gcc",
        )
        subprocess.run(  # noqa: S603
            [cargo, "build", "--release", "--target", triple, "-p", "scb-check"],
            cwd=root,
            check=True,
            env=env,
        )

        binary = root / "target" / triple / "release" / "scb-check"
        if not binary.is_file():
            msg = f"expected built binary at {binary}"
            raise RuntimeError(msg)
        shared_scripts = build_data.setdefault("shared_scripts", {})
        shared_scripts[str(binary)] = "scb-check"
