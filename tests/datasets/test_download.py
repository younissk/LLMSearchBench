"""Dataset fetching. No test here touches a network: the fetcher is injected."""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

import pytest

from llmsearchbench.datasets import (
    DATASETS,
    ChecksumMismatchError,
    DatasetFile,
    DatasetSpec,
    UnknownDatasetError,
    download_dataset,
    download_file,
    get_dataset,
    is_present,
    lockfile_contents,
    sha256_of,
    verify_all,
    verify_dataset,
)
from llmsearchbench.paths import DATASETS_LOCK

PAYLOAD = b'{"question": "who?", "ground_truth": ["someone"]}\n'
PAYLOAD_SHA = "d2e0a5b2e4c8dd0b7b0e6b5d3d4e3c2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d"


def sha_of_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def make_file(name: str = "data.jsonl", payload: bytes = PAYLOAD) -> DatasetFile:
    return DatasetFile(
        name=name,
        url=f"https://example.invalid/{name}",
        sha256=sha_of_bytes(payload),
        size_bytes=len(payload),
    )


def make_spec(*files: DatasetFile, key: str = "fake") -> DatasetSpec:
    return DatasetSpec(
        key=key,
        title="Fake",
        homepage="https://example.invalid",
        license="MIT",
        license_file="fake-LICENSE.txt",
        citation="@misc{fake}",
        description="A fake dataset.",
        files=files or (make_file(),),
    )


def fetcher_for(payloads: dict[str, bytes]) -> Callable[[str], BinaryIO]:
    """A fetcher that serves fixed bytes and records nothing else."""

    def fetch(url: str) -> BinaryIO:
        return io.BytesIO(payloads[url])

    return fetch


class TestDownloadFile:
    def test_writes_the_payload(self, tmp_path: Path) -> None:
        file = make_file()
        target = tmp_path / file.name
        download_file(file, target, fetcher=fetcher_for({file.url: PAYLOAD}))
        assert target.read_bytes() == PAYLOAD

    def test_creates_missing_directories(self, tmp_path: Path) -> None:
        file = make_file()
        target = tmp_path / "a" / "b" / file.name
        download_file(file, target, fetcher=fetcher_for({file.url: PAYLOAD}))
        assert target.exists()

    def test_a_checksum_mismatch_raises(self, tmp_path: Path) -> None:
        file = make_file()
        target = tmp_path / file.name
        with pytest.raises(ChecksumMismatchError, match="expected sha256"):
            download_file(file, target, fetcher=fetcher_for({file.url: b"tampered"}))

    def test_a_checksum_mismatch_leaves_nothing_behind(self, tmp_path: Path) -> None:
        """A corrupt fetch must not leave a file that a later run treats as real."""
        file = make_file()
        target = tmp_path / file.name
        with pytest.raises(ChecksumMismatchError):
            download_file(file, target, fetcher=fetcher_for({file.url: b"tampered"}))
        assert not target.exists()
        assert list(tmp_path.iterdir()) == []

    def test_a_failed_fetch_leaves_nothing_behind(self, tmp_path: Path) -> None:
        file = make_file()
        target = tmp_path / file.name

        def explode(url: str) -> BinaryIO:
            raise ConnectionError("the network went away")

        with pytest.raises(ConnectionError):
            download_file(file, target, fetcher=explode)
        assert list(tmp_path.iterdir()) == []

    def test_the_written_file_is_readable(self, tmp_path: Path) -> None:
        """tempfile creates at 0600; data files are not secrets."""
        file = make_file()
        target = tmp_path / file.name
        download_file(file, target, fetcher=fetcher_for({file.url: PAYLOAD}))
        assert target.stat().st_mode & 0o777 == 0o644

    def test_an_existing_good_file_is_replaced_not_appended(self, tmp_path: Path) -> None:
        file = make_file()
        target = tmp_path / file.name
        target.write_bytes(b"stale content")
        download_file(file, target, fetcher=fetcher_for({file.url: PAYLOAD}))
        assert target.read_bytes() == PAYLOAD


class TestDownloadDataset:
    def test_fetches_every_file(self, tmp_path: Path) -> None:
        first = make_file("one.jsonl", b"one\n")
        second = make_file("two.jsonl", b"two\n")
        spec = make_spec(first, second)
        results = download_dataset(
            spec,
            root=tmp_path,
            fetcher=fetcher_for({first.url: b"one\n", second.url: b"two\n"}),
        )
        assert [r.file for r in results] == ["one.jsonl", "two.jsonl"]
        assert all(not r.skipped for r in results)

    def test_a_verified_file_is_not_fetched_again(self, tmp_path: Path) -> None:
        """35 MB re-downloaded on every `make data` would make the target useless."""
        file = make_file()
        spec = make_spec(file)
        (tmp_path / file.name).write_bytes(PAYLOAD)

        def explode(url: str) -> BinaryIO:
            raise AssertionError("should not have fetched anything")

        results = download_dataset(spec, root=tmp_path, fetcher=explode)
        assert [r.skipped for r in results] == [True]

    def test_force_refetches_even_when_the_checksum_matches(self, tmp_path: Path) -> None:
        file = make_file()
        spec = make_spec(file)
        (tmp_path / file.name).write_bytes(PAYLOAD)
        results = download_dataset(
            spec, root=tmp_path, force=True, fetcher=fetcher_for({file.url: PAYLOAD})
        )
        assert [r.skipped for r in results] == [False]

    def test_a_corrupt_file_on_disk_is_refetched(self, tmp_path: Path) -> None:
        file = make_file()
        spec = make_spec(file)
        (tmp_path / file.name).write_bytes(b"half a fi")
        results = download_dataset(
            spec, root=tmp_path, fetcher=fetcher_for({file.url: PAYLOAD})
        )
        assert [r.skipped for r in results] == [False]
        assert (tmp_path / file.name).read_bytes() == PAYLOAD


class TestVerify:
    def test_reports_ok_for_a_matching_file(self, tmp_path: Path) -> None:
        file = make_file()
        (tmp_path / file.name).write_bytes(PAYLOAD)
        assert [r.status for r in verify_dataset(make_spec(file), root=tmp_path)] == ["ok"]

    def test_reports_missing(self, tmp_path: Path) -> None:
        assert [r.status for r in verify_dataset(make_spec(), root=tmp_path)] == ["missing"]

    def test_reports_corrupt_rather_than_missing(self, tmp_path: Path) -> None:
        """Truncated and absent are different problems, and the message should say which."""
        file = make_file()
        (tmp_path / file.name).write_bytes(b"truncated")
        assert [r.status for r in verify_dataset(make_spec(file), root=tmp_path)] == ["corrupt"]

    def test_verify_all_walks_every_registered_dataset(self, tmp_path: Path) -> None:
        results = verify_all(root=tmp_path)
        assert {r.dataset for r in results} == set(DATASETS)


class TestRegistry:
    def test_unknown_key_names_what_is_known(self) -> None:
        with pytest.raises(UnknownDatasetError, match="retrievalqa"):
            get_dataset("not-a-dataset")

    def test_every_dataset_declares_a_licence_and_a_citation(self) -> None:
        """Data without attribution is not usable, whatever the code says."""
        for spec in DATASETS.values():
            assert spec.license, f"{spec.key} has no licence"
            assert spec.citation.strip().startswith("@"), f"{spec.key} has no BibTeX"
            assert spec.homepage.startswith("https://")

    def test_every_file_is_pinned_to_a_commit_not_a_branch(self) -> None:
        """`main` moves; a benchmark pinned to it is not reproducible."""
        for spec in DATASETS.values():
            for file in spec.files:
                assert "/main/" not in file.url, f"{spec.key}/{file.name} is pinned to a branch"
                assert len(file.sha256) == 64, f"{spec.key}/{file.name} has no usable checksum"

    def test_licence_text_is_saved_for_every_dataset(self) -> None:
        from llmsearchbench.datasets.attribution import missing_license_files

        assert missing_license_files() == []


class TestLockfile:
    def test_the_committed_lockfile_matches_the_registry(self) -> None:
        """The lockfile travels with the repo; a stale one pins nothing."""
        committed = json.loads(DATASETS_LOCK.read_text(encoding="utf-8"))
        assert committed == json.loads(json.dumps(lockfile_contents()))


class TestHelpers:
    def test_sha256_of_matches_the_registry(self, tmp_path: Path) -> None:
        path = tmp_path / "f"
        path.write_bytes(PAYLOAD)
        assert sha256_of(path) == sha_of_bytes(PAYLOAD)

    def test_is_present_is_false_for_a_wrong_checksum(self, tmp_path: Path) -> None:
        file = make_file()
        (tmp_path / file.name).write_bytes(b"different")
        assert not is_present(make_spec(file), file, tmp_path)


class TestDownloadAll:
    def test_walks_every_dataset_into_its_own_directory(self, tmp_path: Path) -> None:
        from llmsearchbench.datasets import download_all

        payloads = {file.url: b"x" for spec in DATASETS.values() for file in spec.files}

        def fetch(url: str) -> BinaryIO:
            return io.BytesIO(payloads[url])

        # Real checksums will not match a stub payload; the point here is that
        # each dataset lands under its own key.
        with pytest.raises(ChecksumMismatchError):
            download_all(root=tmp_path, fetcher=fetch)
        assert (tmp_path / "retrievalqa").is_dir()

    def test_verify_all_scopes_each_dataset_to_its_own_directory(self, tmp_path: Path) -> None:
        spec = get_dataset("retrievalqa")
        directory = tmp_path / spec.key
        directory.mkdir(parents=True)
        for file in spec.files:
            (directory / file.name).write_bytes(b"not the real bytes")

        results = verify_all(root=tmp_path)
        ours = {r.status for r in results if r.dataset == spec.key}
        others = {r.status for r in results if r.dataset != spec.key}
        # Wrong bytes under this key are corrupt; another dataset's files are
        # not there at all, and must not be reported against this one.
        assert ours == {"corrupt"}
        assert others <= {"missing"}
