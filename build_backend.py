"""Custom PEP 517 build backend for tensorbored.

Wraps setuptools' build backend and generates the ``*_pb2.py`` /
``*_pb2_grpc.py`` modules from the vendored ``.proto`` files before each
build.  The generated files are transient build artifacts (gitignored),
never committed to the repository.
"""

import os
from pathlib import Path

from setuptools import build_meta as _setuptools_build_meta

_REPO_ROOT = Path(__file__).resolve().parent
_PROTO_SUBDIR = _REPO_ROOT / "tensorbored"


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


def _with_protos(func):
    def _wrapper(*args, **kwargs):
        _generate_protos()
        return func(*args, **kwargs)

    return _wrapper


build_wheel = _with_protos(_setuptools_build_meta.build_wheel)
build_sdist = _with_protos(_setuptools_build_meta.build_sdist)
build_editable = _with_protos(_setuptools_build_meta.build_editable)

get_requires_for_build_wheel = _setuptools_build_meta.get_requires_for_build_wheel
get_requires_for_build_sdist = _setuptools_build_meta.get_requires_for_build_sdist
get_requires_for_build_editable = _setuptools_build_meta.get_requires_for_build_editable
prepare_metadata_for_build_wheel = _setuptools_build_meta.prepare_metadata_for_build_wheel
prepare_metadata_for_build_editable = _setuptools_build_meta.prepare_metadata_for_build_editable
