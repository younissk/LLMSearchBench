"""What a source dataset is, and what it takes to credit it.

Every file is pinned to a commit and a SHA-256. A benchmark whose inputs can
change underneath it is not reproducible, and "main" is not a pin.
"""

from __future__ import annotations

from pydantic import Field

from llmsearchbench.types import BenchModel


class DatasetFile(BenchModel):
    """One downloadable file, pinned by checksum."""

    #: Path relative to the dataset's directory under `data/raw/`.
    name: str = Field(min_length=1)
    #: Pinned to an immutable ref. A URL containing `/main/` is not a pin.
    url: str = Field(pattern=r"^https://")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    description: str = ""


class DatasetSpec(BenchModel):
    """A source dataset, with everything needed to fetch and credit it."""

    key: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    title: str = Field(min_length=1)
    homepage: str = Field(pattern=r"^https://")
    #: SPDX identifier of the licence the data is released under. Required:
    #: data without a licence is not usable, whatever the code says.
    license: str = Field(min_length=1)
    #: Path under `attribution/licenses/` holding the licence text we received.
    license_file: str = Field(min_length=1)
    #: BibTeX entry, copied verbatim from the authors where they publish one.
    citation: str = Field(pattern=r"(?s)^\s*@")
    #: Free text: what it is and why this benchmark uses it.
    description: str = Field(min_length=1)
    files: tuple[DatasetFile, ...] = Field(min_length=1)
    #: Upstream commit the files were pinned at, when the source is a git host.
    pinned_commit: str = Field(default="", pattern=r"^([0-9a-f]{40})?$")
    paper_url: str = ""
    notes: str = ""
    tags: tuple[str, ...] = ()

    @property
    def total_bytes(self) -> int:
        return sum(file.size_bytes for file in self.files)
