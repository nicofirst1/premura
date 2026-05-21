# Mission Review Rollback Feedback: WP03

## Verdict

Move `WP03` back to `planned`.

## Blocking finding

1. The shipped parser contract disagrees with the shipped code about `PluginParseResult`.
   - Code: `src/premura/parsers/base.py` implements `PluginParseResult` as a mutable `@dataclass` and documents why `frozen=True` could not ship without changing `ParseResult`.
   - Contract: `src/premura/parsers/CONTRACT.md` says `PluginParseResult` is "A frozen dataclass".
   - Downstream skill copy: `src/premura/skills/parser-generator/SKILL.md` also tells implementers it is a "frozen dataclass".

## Why this blocks acceptance

`WP03` owns the parser contract surface. The authoritative shipped contract and the exported Python surface must agree. Right now they do not, so parser authors and future reviewers are being told to implement against a different API than the one the package actually provides.

## Required correction

- Make the shipped contract text match the shipped code, or
- Change the code and its constraints so the contract can truthfully say `frozen`.
