"""Synthetic intake fixtures + the reference intake parser.

This package is a **proof/test anchor**, not a shipped vendor parser.
The reference parser deliberately lives here under ``tests/fixtures/intake/``
rather than ``src/premura/parsers/`` so it can never be mistaken for an
officially-supported source; real vendor sources are built at runtime via the
build-and-use path. Every value in the bundled fixtures is made up.
"""
