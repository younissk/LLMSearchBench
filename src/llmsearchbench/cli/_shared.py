"""Pieces every command group shares."""

from __future__ import annotations

from llmsearchbench.paths import RESULTS

#: Exit codes are part of the contract, because CI gates on them.
EXIT_OK = 0
#: A real failure: a mismatch, or data that will not load.
EXIT_FAILED = 1
#: Bad input: a path that is not there, an id that is not in a catalogue.
EXIT_BAD_INPUT = 2
#: The thing asked for is not wired up yet.
EXIT_NOT_WIRED = 3

DEFAULT_OUT = RESULTS / "local"
