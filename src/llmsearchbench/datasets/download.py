"""Fetching source data, and checking what is already on disk.

Downloads go to a temporary file, get verified against the pinned checksum, and
only then move into place - so an interrupted or corrupted fetch never leaves
something at the real path that a later run treats as valid.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import urllib.request
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import BinaryIO, Literal

from llmsearchbench.datasets.registry import DATASETS
from llmsearchbench.datasets.spec import DatasetFile, DatasetSpec
from llmsearchbench.paths import dataset_dir
from llmsearchbench.types import BenchModel


class ChecksumMismatchError(RuntimeError):
    """Raised when a downloaded file does not match its pinned SHA-256."""


#: Opens a URL and returns a readable binary stream. Injected so tests never
#: touch a network.
Fetcher = Callable[[str], BinaryIO]

#: Called with the byte count of each chunk written, for progress reporting.
ProgressHook = Callable[[int], None]

CHUNK_SIZE = 1 << 20

#: `tempfile` creates at 0600. Data files are not secrets, and a mode nobody
#: else can read breaks the moment the repo is shared or a container reads it.
DATA_FILE_MODE = 0o644


def _default_fetcher(url: str) -> BinaryIO:  # pragma: no cover - exercised by `make data`
    # Registry URLs are https literals reviewed in this file.
    response: BinaryIO = urllib.request.urlopen(url)
    return response


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def is_present(spec: DatasetSpec, file: DatasetFile, root: Path | None = None) -> bool:
    """True when the file is on disk and matches its pinned checksum."""
    path = (root or dataset_dir(spec.key)) / file.name
    return path.exists() and sha256_of(path) == file.sha256


def download_file(
    file: DatasetFile,
    target: Path,
    *,
    fetcher: Fetcher = _default_fetcher,
    on_bytes: ProgressHook | None = None,
) -> Path:
    """Fetch one file, verify it, and only then move it into place.

    Downloading to a temporary file first means an interrupted or corrupted
    fetch never leaves something at the real path that later looks valid.

    `on_bytes` is called with the size of each chunk written. It exists so the
    command line can draw a progress bar without this module knowing anything
    about a terminal.
    """
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            with fetcher(file.url) as stream:
                if on_bytes is None:
                    shutil.copyfileobj(stream, handle, CHUNK_SIZE)
                else:
                    while chunk := stream.read(CHUNK_SIZE):
                        handle.write(chunk)
                        on_bytes(len(chunk))
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    actual = sha256_of(temporary)
    if actual != file.sha256:
        temporary.unlink(missing_ok=True)
        raise ChecksumMismatchError(
            f"{file.url}\n  expected sha256 {file.sha256}\n  got      sha256 {actual}\n"
            "The pin in src/llmsearchbench/datasets/registry.py and the file upstream "
            "disagree. "
            "Do not update the pin without deciding whether published numbers still hold."
        )

    temporary.chmod(DATA_FILE_MODE)
    temporary.replace(target)
    return target


class DownloadResult(BenchModel):
    dataset: str
    file: str
    path: Path
    #: True when the file was already present and verified, so nothing was fetched.
    skipped: bool


def download_dataset(
    spec: DatasetSpec,
    *,
    root: Path | None = None,
    force: bool = False,
    fetcher: Fetcher = _default_fetcher,
    on_bytes: ProgressHook | None = None,
) -> list[DownloadResult]:
    """Fetch every file of one dataset, skipping what is already verified."""
    directory = root or dataset_dir(spec.key)
    results: list[DownloadResult] = []

    for file in spec.files:
        target = directory / file.name
        if not force and is_present(spec, file, directory):
            results.append(
                DownloadResult(dataset=spec.key, file=file.name, path=target, skipped=True)
            )
            continue
        download_file(file, target, fetcher=fetcher, on_bytes=on_bytes)
        results.append(
            DownloadResult(dataset=spec.key, file=file.name, path=target, skipped=False)
        )

    return results


def download_all(
    specs: Iterable[DatasetSpec] | None = None,
    *,
    root: Path | None = None,
    force: bool = False,
    fetcher: Fetcher = _default_fetcher,
    on_bytes: ProgressHook | None = None,
) -> list[DownloadResult]:
    results: list[DownloadResult] = []
    for spec in specs if specs is not None else DATASETS.values():
        target_root = root / spec.key if root is not None else None
        results.extend(
            download_dataset(
                spec, root=target_root, force=force, fetcher=fetcher, on_bytes=on_bytes
            )
        )
    return results


class VerifyResult(BenchModel):
    dataset: str
    file: str
    status: Literal["ok", "missing", "corrupt"]

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def verify_dataset(spec: DatasetSpec, *, root: Path | None = None) -> list[VerifyResult]:
    """Check what is on disk against the pins, without fetching anything."""
    directory = root or dataset_dir(spec.key)
    results: list[VerifyResult] = []

    for file in spec.files:
        path = directory / file.name
        if not path.exists():
            results.append(VerifyResult(dataset=spec.key, file=file.name, status="missing"))
        elif sha256_of(path) != file.sha256:
            results.append(VerifyResult(dataset=spec.key, file=file.name, status="corrupt"))
        else:
            results.append(VerifyResult(dataset=spec.key, file=file.name, status="ok"))

    return results


def verify_all(
    specs: Iterable[DatasetSpec] | None = None, *, root: Path | None = None
) -> list[VerifyResult]:
    results: list[VerifyResult] = []
    for spec in specs if specs is not None else DATASETS.values():
        target_root = root / spec.key if root is not None else None
        results.extend(verify_dataset(spec, root=target_root))
    return results
