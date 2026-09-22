"""The source datasets this benchmark builds on.

This registry is the single source of truth. The attribution files under
`attribution/` and the site\'s data-sources page are generated from it, so a
dataset can never be used without its licence and citation travelling with it.
"""

from __future__ import annotations

from llmsearchbench.datasets.spec import DatasetFile, DatasetSpec

RETRIEVALQA = DatasetSpec(
    key="retrievalqa",
    title="RetrievalQA",
    homepage="https://github.com/hyintell/RetrievalQA",
    paper_url="https://arxiv.org/abs/2402.16457",
    license="MIT",
    license_file="retrievalqa-LICENSE.txt",
    pinned_commit="f26134cb167f420a657684665f597964aadabd3c",
    tags=("short-form", "open-domain", "adaptive-retrieval"),
    description=(
        "2,785 short-form open-domain questions, each with a retrieved context and a "
        "`param_knowledge_answerable` flag marking whether an LLM can answer it from "
        "parametric memory alone. The questions come from five sources: PopQA, "
        "TriviaQA, RealtimeQA, ToolQA and FreshQA."
    ),
    notes=(
        "The `param_knowledge_answerable` flag is the reason this dataset is first in "
        "the queue: it is a ready-made version of our admission rule that a task must "
        "not be answerable from memory. It is the authors' judgement, not ours, so it "
        "seeds the candidate pool rather than replacing our own memory check."
    ),
    citation="""@misc{zhang2024retrievalqa,
      title={RetrievalQA: Assessing Adaptive Retrieval-Augmented Generation for Short-form Open-Domain Question Answering},
      author={Zihan Zhang and Meng Fang and Ling Chen},
      year={2024},
      eprint={2402.16457},
      archivePrefix={arXiv},
      primaryClass={cs.CL}
}""",
    files=(
        DatasetFile(
            name="retrievalqa.jsonl",
            url=(
                "https://raw.githubusercontent.com/hyintell/RetrievalQA/"
                "f26134cb167f420a657684665f597964aadabd3c/data/retrievalqa.jsonl"
            ),
            sha256="cf86765748a8f54e8f6bbaec8a59de43d3fb2e01e4c69bc35bef559253c76aed",
            size_bytes=35_833_609,
            description="The dataset: question, ground truth answers, and retrieved context.",
        ),
        DatasetFile(
            name="retrievalqa_gpt4.jsonl",
            url=(
                "https://raw.githubusercontent.com/hyintell/RetrievalQA/"
                "f26134cb167f420a657684665f597964aadabd3c/data/retrievalqa_gpt4.jsonl"
            ),
            sha256="96b0811e12df9baba02384f53dd77851cb154bcfd7d726db2fd36ca0820c18b1",
            size_bytes=1_959_546,
            description="The authors' GPT-4 baseline outputs.",
        ),
        DatasetFile(
            name="data_statistics.jsonl",
            url=(
                "https://raw.githubusercontent.com/hyintell/RetrievalQA/"
                "f26134cb167f420a657684665f597964aadabd3c/data/data_statistics.jsonl"
            ),
            sha256="b326636ba7a6403cc9e428dd3aa0836b6fcefac4a032d243d3f32623a9ac978b",
            size_bytes=1_372,
            description="Per-source counts and token statistics.",
        ),
    ),
)


DATASETS: dict[str, DatasetSpec] = {spec.key: spec for spec in (RETRIEVALQA,)}


class UnknownDatasetError(KeyError):
    """Raised for a dataset key that is not in the registry."""


def get_dataset(key: str) -> DatasetSpec:
    try:
        return DATASETS[key]
    except KeyError:
        known = ", ".join(sorted(DATASETS))
        raise UnknownDatasetError(
            f"unknown dataset {key!r}. Known: {known}. "
            "Add it to DATASETS in src/llmsearchbench/datasets/registry.py."
        ) from None


def lockfile_contents() -> dict[str, object]:
    """The committed record of what every dataset is pinned to."""
    return {
        "datasets": {
            spec.key: {
                "title": spec.title,
                "homepage": spec.homepage,
                "license": spec.license,
                "pinned_commit": spec.pinned_commit,
                "files": [
                    {
                        "name": file.name,
                        "url": file.url,
                        "sha256": file.sha256,
                        "size_bytes": file.size_bytes,
                    }
                    for file in spec.files
                ],
            }
            for spec in DATASETS.values()
        }
    }
