"""Custom PEP 517 build backend for tensorbored.

Wraps setuptools' build backend and, before each build:

* generates the ``*_pb2.py`` / ``*_pb2_grpc.py`` modules from the
  vendored ``.proto`` files, and
* for wheel and editable builds, builds the frontend via Bazel into
  ``tensorbored/webfiles.zip``.

Bazel is a hard dependency for producing installable artifacts: the
frontend assets are built fresh on every wheel/editable build and are
never committed to the repository.  A source distribution (sdist) is
built without Bazel and therefore does not contain the frontend assets;
see ``_warn_missing_webfiles``.  All generated files are transient
build artifacts (gitignored).
"""

import os
import shutil
import subprocess
import warnings
from pathlib import Path

from setuptools import build_meta as _setuptools_build_meta

_REPO_ROOT = Path(__file__).resolve().parent
_PROTO_SUBDIR = _REPO_ROOT / "tensorbored"

_WEBFILES_TARGET = "//tensorbored:webfiles"
_WEBFILES_OUTPUT = _REPO_ROOT / "tensorbored" / "webfiles.zip"


def _build_webfiles():
    """Run Bazel to build the frontend and stage ``webfiles.zip``.

    The built archive is copied into the source tree so that the
    setuptools ``package_data`` picks it up for both wheel and editable
    builds.  The copy is a transient build artifact, never committed.
    """
    bazel = shutil.which("bazel") or shutil.which("bazelisk")
    if bazel is None:
        raise RuntimeError(
            "Bazel is required to build tensorbored frontend assets; "
            "install it (e.g. `npm i -g @bazel/bazelisk`) and retry."
        )
    try:
        subprocess.run(
            [bazel, "build", _WEBFILES_TARGET],
            cwd=str(_REPO_ROOT),
            check=True,
        )
        bazel_bin = subprocess.run(
            [bazel, "info", "bazel-bin"],
            cwd=str(_REPO_ROOT),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Bazel failed to build frontend assets (%s)" % _WEBFILES_TARGET
        ) from exc

    built_zip = Path(bazel_bin) / "tensorbored" / "webfiles.zip"
    if not built_zip.exists():
        raise RuntimeError(
            "Bazel completed but did not produce %s" % built_zip
        )
    _WEBFILES_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(built_zip, _WEBFILES_OUTPUT)


def _warn_missing_webfiles():
    """Warn that a source distribution will lack the frontend assets."""
    warnings.warn(
        "Building a source distribution does not include the frontend "
        "assets: `tensorbored/webfiles.zip` is produced by Bazel during "
        "wheel/editable builds and is not committed.  To obtain an "
        "installable package, build a wheel (`pip wheel .`) instead.",
        UserWarning,
        stacklevel=2,
    )


def _generate_protos():
    proto_files = sorted(_PROTO_SUBDIR.rglob("*.proto"))
    if not proto_files:
        raise RuntimeError(
            "No .proto files found under %s" % _PROTO_SUBDIR
        )

    from grpc_tools import protoc

    proto_include = os.path.join(os.path.dirname(protoc.__file__), "_proto")
    argv = [
        "grpc_tools.protoc",
        "-I%s" % _REPO_ROOT,
        "-I%s" % proto_include,
        "--python_out=%s" % _REPO_ROOT,
        "--grpc_python_out=%s" % _REPO_ROOT,
    ]
    argv.extend(str(f) for f in proto_files)
    try:
        protoc.main(argv)
    except SystemExit as exc:
        if exc.code:
            raise RuntimeError(
                "protoc failed with exit code %s" % exc.code
            ) from exc


def _with_webfiles(func):
    """Build protos and the frontend assets before a wheel/editable build."""

    def _wrapper(*args, **kwargs):
        _generate_protos()
        _build_webfiles()
        return func(*args, **kwargs)

    return _wrapper


def _with_sdist_warning(func):
    """Generate protos and warn about missing assets for an sdist build."""

    def _wrapper(*args, **kwargs):
        _generate_protos()
        _warn_missing_webfiles()
        return func(*args, **kwargs)

    return _wrapper


build_wheel = _with_webfiles(_setuptools_build_meta.build_wheel)
build_sdist = _with_sdist_warning(_setuptools_build_meta.build_sdist)
build_editable = _with_webfiles(_setuptools_build_meta.build_editable)

get_requires_for_build_wheel = _setuptools_build_meta.get_requires_for_build_wheel
get_requires_for_build_sdist = _setuptools_build_meta.get_requires_for_build_sdist
get_requires_for_build_editable = _setuptools_build_meta.get_requires_for_build_editable
prepare_metadata_for_build_wheel = _setuptools_build_meta.prepare_metadata_for_build_wheel
prepare_metadata_for_build_editable = _setuptools_build_meta.prepare_metadata_for_build_editable
