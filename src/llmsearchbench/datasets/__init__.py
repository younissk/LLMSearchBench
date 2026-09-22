"""Source datasets: what they are, how to fetch them, and who to credit.

* `spec` - the shapes, with their pins
* `registry` - the datasets themselves
* `download` - fetching and verifying
* `attribution` - the generated licence and citation files
"""

from llmsearchbench.datasets.download import (
    ChecksumMismatchError,
    DownloadResult,
    VerifyResult,
    download_all,
    download_dataset,
    download_file,
    is_present,
    sha256_of,
    verify_all,
    verify_dataset,
)
from llmsearchbench.datasets.registry import (
    DATASETS,
    RETRIEVALQA,
    UnknownDatasetError,
    get_dataset,
    lockfile_contents,
)
from llmsearchbench.datasets.spec import DatasetFile, DatasetSpec

__all__ = [
    "DATASETS",
    "RETRIEVALQA",
    "ChecksumMismatchError",
    "DatasetFile",
    "DatasetSpec",
    "DownloadResult",
    "UnknownDatasetError",
    "VerifyResult",
    "download_all",
    "download_dataset",
    "download_file",
    "get_dataset",
    "is_present",
    "lockfile_contents",
    "sha256_of",
    "verify_all",
    "verify_dataset",
]
