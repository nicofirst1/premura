# Tests

Grouped by subsystem, not by filename prefix.

| folder          | covers                                                   |
| --------------- | -------------------------------------------------------- |
| `engine/`       | signal engine, policy model, stats                       |
| `mcp/`          | MCP tool surfaces                                        |
| `intake/`       | ingest: parsers, profile, scenarios, reconcile, store    |
| `live_trial/`   | model-driven trials (needs Ollama; `live_trial` marker)  |
| `operating/`    | agent roles, interview, session log, trace, routing      |
| `eval/`         | judge, grader, adversarial, answer, refusal, check-loops |
| `ops/`          | bootstrap, cli, launchd, encrypt, sandbox, install, docs |
| `test_parsers/` | one file per federated parser                            |

`fixtures/`, `contracts/`, and `conftest.py` stay at this root and serve every folder.

## Paths

Anchor filesystem lookups on the constants in `__init__.py` (`TESTS_DIR`, `REPO_ROOT`, `FIXTURES_DIR`, `CONTRACTS_DIR`), never on a test's own `__file__` - the latter breaks when a file moves between folders.

## Parallelism (`-n auto`)

The suite runs under `pytest-xdist` (`-n auto`), so tests execute concurrently across workers. A test that inspects a shared global resource (the OS tempdir, a well-known path, an env-wide singleton) must isolate that resource per-test - e.g. redirect `tempfile.tempdir` to `tmp_path` before scanning for `premura-sandbox-*`. A before/after diff of shared state is otherwise racy: another worker mutates it mid-test. Do not paper over this with `xdist_group` serialization; isolate the state instead.

## Placement

A new test joins the folder matching the subsystem it exercises. New subsystem, no fit? Add a folder (with `__init__.py`) rather than dropping the file at root.
