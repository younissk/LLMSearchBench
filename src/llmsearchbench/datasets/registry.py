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


HOTPOTQA = DatasetSpec(
    key="hotpotqa",
    title="HotpotQA (distractor setting)",
    homepage="https://hotpotqa.github.io/",
    paper_url="https://arxiv.org/abs/1809.09600",
    license="CC-BY-SA-4.0",
    license_file="hotpotqa-LICENSE.txt",
    pinned_commit="",
    tags=("wikipedia", "multi-hop", "distractor"),
    description=(
        "7,405 multi-hop questions in the distractor setting: each question comes with "
        "ten Wikipedia paragraphs, two of which contain the supporting sentences and "
        "eight of which were retrieved as near neighbours of the question. The "
        "supporting-fact annotations say which paragraphs carry the answer."
    ),
    notes=(
        "Used for the wikipedia category of search-result discrimination. The relevance "
        "grades are derived from the supporting facts rather than judged directly, and "
        "the task set records that: a derived label is weaker evidence than a human "
        "relevance judgement and is never averaged with one."
    ),
    citation="""@inproceedings{yang2018hotpotqa,
  title={{HotpotQA}: A Dataset for Diverse, Explainable Multi-hop Question Answering},
  author={Yang, Zhilin and Qi, Peng and Zhang, Saizheng and Bengio, Yoshua and Cohen, William W. and Salakhutdinov, Ruslan and Manning, Christopher D.},
  booktitle={Conference on Empirical Methods in Natural Language Processing ({EMNLP})},
  year={2018}
}""",
    files=(
        DatasetFile(
            name="hotpot-distractor-validation.parquet",
            url=(
                "https://huggingface.co/datasets/hotpotqa/hotpot_qa/resolve/"
                "1908d6afbbead072334abe2965f91bd2709910ab/distractor/"
                "validation-00000-of-00001.parquet"
            ),
            sha256="c20b638ca82b21d04fe12e14ff417ad05153d4d215a65de54497fca4e972f7c6",
            size_bytes=27_452_575,
            description="The distractor validation split: question, answer, supporting facts, ten paragraphs.",
        ),
    ),
)


TREC_DL = DatasetSpec(
    key="trec-dl",
    title="TREC Deep Learning Track 2019 and 2020, passage judgements",
    homepage="https://trec.nist.gov/data/deep2020.html",
    paper_url="https://arxiv.org/abs/2003.07820",
    license="US Government work (NIST); no licence asserted",
    license_file="trec-dl-TERMS.txt",
    pinned_commit="",
    tags=("web", "graded-relevance", "human-judged"),
    description=(
        "20,646 human relevance judgements over 97 queries, on a four-point scale: "
        "0 not relevant, 1 related but not answering, 2 highly relevant, 3 perfect. "
        "The judged passages were retrieved for their own query, so the non-relevant "
        "ones are on topic without answering — hard negatives by construction."
    ),
    notes=(
        "The grade-1 level is the reason this source was chosen. NIST states plainly "
        "that 'Related' is actually NOT relevant: the passage is on the same general "
        "topic but does not answer the question. That is exactly the distinction this "
        "task measures, already drawn by a person."
    ),
    citation="""@article{craswell2020trecdl,
  title={Overview of the {TREC} 2019 deep learning track},
  author={Craswell, Nick and Mitra, Bhaskar and Yilmaz, Emine and Campos, Daniel and Voorhees, Ellen M.},
  journal={Text REtrieval Conference (TREC)},
  year={2020}
}""",
    files=(
        DatasetFile(
            name="2019qrels-pass.txt",
            url="https://trec.nist.gov/data/deep/2019qrels-pass.txt",
            sha256="8a1f10d550732e4cd91d7fc49846a3784de4040972f583e69285a88f3c5fee92",
            size_bytes=187_092,
            description="NIST passage judgements for the 2019 track.",
        ),
        DatasetFile(
            name="2020qrels-pass.txt",
            url="https://trec.nist.gov/data/deep/2020qrels-pass.txt",
            sha256="60d4c34561f9687f8f73e0a752ba80ab80159b3e9c1bedd0a351f747ed6f5684",
            size_bytes=218_617,
            description="NIST passage judgements for the 2020 track.",
        ),
        DatasetFile(
            name="msmarco-test2019-queries.tsv.gz",
            url=(
                "https://msmarco.z22.web.core.windows.net/msmarcoranking/"
                "msmarco-test2019-queries.tsv.gz"
            ),
            sha256="d66f01dfa8a3e60fe375ba645efc004f97ff4dd2a424536b8d5810c16182a3b5",
            size_bytes=4_276,
            description="The 2019 test queries.",
        ),
        DatasetFile(
            name="msmarco-test2020-queries.tsv.gz",
            url=(
                "https://msmarco.z22.web.core.windows.net/msmarcoranking/"
                "msmarco-test2020-queries.tsv.gz"
            ),
            sha256="0c749b29fd8ca0ccbf129a1bdd283e4081d6c49e96d6bf6290ba554d5d71f7f1",
            size_bytes=4_131,
            description="The 2020 test queries.",
        ),
    ),
)


MSMARCO = DatasetSpec(
    key="msmarco",
    title="MS MARCO passage collection",
    homepage="https://microsoft.github.io/msmarco/",
    paper_url="https://arxiv.org/abs/1611.09268",
    license="MS MARCO terms: non-commercial research use only",
    license_file="msmarco-TERMS.txt",
    pinned_commit="",
    tags=("web", "passages", "non-commercial"),
    description=(
        "8.8 million web passages. Only the text of the 20,349 passages TREC judged is "
        "ever used: `scripts/extract_judged_passages.py` streams the archive once and "
        "keeps those, which is 2.5 MB rather than 3 GB."
    ),
    notes=(
        "Microsoft grants non-commercial research use and explicitly does not extend a "
        "licence. This benchmark therefore does not redistribute MS MARCO text: the web "
        "and no_answer categories are built locally from your own download, and only "
        "their ids and checksums are committed. Everything needed to reproduce them "
        "byte for byte is in the repository; the passages themselves are not."
    ),
    citation="""@article{bajaj2016msmarco,
  title={{MS MARCO}: A Human Generated MAchine Reading COmprehension Dataset},
  author={Bajaj, Payal and Campos, Daniel and Craswell, Nick and Deng, Li and Gao, Jianfeng and Liu, Xiaodong and Majumder, Rangan and McNamara, Andrew and Mitra, Bhaskar and Nguyen, Tri and Rosenberg, Mir and Song, Xia and Stoica, Alina and Tiwary, Saurabh and Wang, Tong},
  journal={arXiv preprint arXiv:1611.09268},
  year={2016}
}""",
    files=(
        DatasetFile(
            name="collection.tar.gz",
            url="https://msmarco.z22.web.core.windows.net/msmarcoranking/collection.tar.gz",
            sha256="70667529e474322327d6441c8f7b621f2a805a7f6220897d9f80e5a8294bd62e",
            size_bytes=1_035_009_698,
            description="The full passage collection, 8.8M passages. Streamed once, never kept.",
        ),
    ),
)


DATASETS: dict[str, DatasetSpec] = {
    spec.key: spec for spec in (RETRIEVALQA, HOTPOTQA, TREC_DL, MSMARCO)
}


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
