"""Building task sets from source data.

* `filters` — the admission rules, each named so a build report can say why
  the candidate pool shrank
* `tooluse` — the tool-use-correctness task set
"""

from llmsearchbench.taskgen.tooluse import BuildReport, build, save

__all__ = ["BuildReport", "build", "save"]
