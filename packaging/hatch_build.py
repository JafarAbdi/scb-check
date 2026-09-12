"""Build the scb-check binary wheel (run from the ``packaging/`` subproject).

Cross-builds a fully-static musl binary with cargo at the workspace root and
packages it as the wheel's ``scb-check`` script. The binary is statically linked
against musl, so it runs on any Linux distribution; the ``manylinux2014`` tag is
only the broadest tag pip accepts. A previously built binary is reused if present.
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
    """Cross-build the static musl binary and include it in the wheel."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Build (or reuse) the static binary before wheel assembly."""
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

        workspace = Path(self.root).parent
        binary = workspace / "target" / triple / "release" / "scb-check"
        if not binary.is_file():
            cargo = shutil.which("cargo")
            if cargo is None:
                msg = "cargo is required to build the scb-check binary"
                raise RuntimeError(msg)
            env = dict(os.environ)
            # tree-sitter's C sources need a musl C compiler for the musl target.
            env.setdefault(
                f"CC_{triple.replace('-', '_')}",
                "musl-gcc" if arch == "x86_64" else f"{arch}-linux-musl-gcc",
            )
            subprocess.run(  # noqa: S603
                [cargo, "build", "--release", "--target", triple, "-p", "scb-check"],
                cwd=workspace,
                check=True,
                env=env,
            )
        if not binary.is_file():
            msg = f"expected built binary at {binary}"
            raise RuntimeError(msg)
        build_data.setdefault("shared_scripts", {})[str(binary)] = "scb-check"
