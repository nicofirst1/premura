"""Deterministic contract surface of the tool-loop live-trial tier (WP03).

This module is the model-server-free half of the tool-loop tier: a chat client,
a bounded tool registry, and a single-source brief assembler. It is fully
testable without an Ollama process (the chat client takes an injectable
transport seam, DIRECTIVE_036); WP04's loop and WP05's end-to-end path build on
top of it. The binding behavior is ``contracts/tool-loop-tier.md`` §§1–2 and §6.

Boundaries this module establishes (and why):

* **What a tool is (the rule, not a list — FR-003/FR-004, NFR-005).** A tool is
  a :class:`ToolRegistration` ``{name, description, parameters-schema, handler}``
  whose handler's reach is *physically bounded* to the capability its
  registration states, resolved inside the trial's :class:`TrialContext`.
  Registering a new tool is **adding one entry** to
  :func:`default_tool_registry`; there is deliberately no ``if name == ...``
  ladder anywhere a handler is dispatched. The three first instances
  (``read_context``, ``write_parser``, ``run_ingest``) are *instances* of that
  rule, not its bounds.

* **Why the fixture manifest is physically unreachable (C-005 by
  construction).** ``read_context`` resolves a requested path against an
  explicit allowlist (the scenario source + ``CONTRACT.md`` + ``base.py``,
  resolved INSIDE the sandbox tree) and refuses anything else — including
  ``../`` traversals and absolute escapes — by comparing *resolved real paths*.
  ``tests/fixtures/session_log/fixture_fields.yaml`` is not in the allowlist and
  no other handler can reach it, so no sequence of tool calls at any turn can
  observe the answer key. A refused read returns a refusal STRING (fed back as
  the tool result so the model can self-correct), never file content and never
  an exception.

* **One canonical source per brief part (FR-001).** :func:`assemble_brief`
  builds the brief from exactly one source per part: the loop preamble (here),
  the drawer probe's contract surface (imported from ``live_trial_ollama``, with
  its one-shot-only output directive stripped *structurally* so the brief cannot
  simultaneously demand "output only a module" and "use tools" — the spike's
  self-contradiction class), the driver goal, and the data sample in the same
  8-line form the one-shot operator serves.

* **Loud budget failure, never truncation.** The brief is sized against the
  pinned ``num_ctx`` (minus a documented response/history reserve) using a
  conservative ``len(brief) // 3`` token overestimate. On overflow it raises
  :class:`BriefBudgetError` naming the sizes. It NEVER truncates: silent
  truncation that can drop required API surface is exactly the defect class the
  2026-06-04 tool-loop follow-up audit identified, and the thing this tier
  exists to prevent.

Reuse, not fork (NFR-004): the chat client mirrors the ``urllib`` discipline of
``live_trial_ollama._ollama`` and imports — never copies — the URL guard,
exception, drawer probes, parser destination, and ingest runner from the sibling
harness modules.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from premura.harness import live_trial
from premura.harness.live_trial_ollama import (
    _PARSER_DEST_RELPATH,
    OLLAMA_URL,
    OllamaUnavailableError,
    _DrawerProbe,
    _resolve_drawer_probe,
    _validated_ollama_url,
)
from premura.harness.sandbox import Sandbox

# Re-exported so callers (WP04's loop, the WP03 brief tests) resolve a scenario to
# its drawer probe through this contract module without re-spelling the sibling
# harness path. The probe rubric stays owned by ``live_trial_ollama`` (NFR-004).
resolve_drawer_probe = _resolve_drawer_probe

# The runner resolves the operator-authored parser by this module:attr spec; it
# mirrors live_trial's _PARSER_MODULE / _PARSER_ATTR (kept in one place there).
_PARSER_MODULE = "premura.parsers._live_trial_parser"
_PARSER_ATTR = "LiveTrialParser"
_PARSER_SPEC = f"{_PARSER_MODULE}:{_PARSER_ATTR}"

#: Pinned model context window (contract §6). Single home; WP04 imports it.
_NUM_CTX_DEFAULT = 16384

#: The one-shot-only output directive both contract prompts END with. The brief
#: strips it STRUCTURALLY (partition on this sentence) so the loop brief cannot
#: contradict the tool protocol (FR-001 crux).
_ONE_SHOT_DIRECTIVE = "Output ONLY the python module"

# The two allowlisted contract files, relative to the sandbox tree. The scenario
# source is added per-context. The fixture manifest is deliberately absent.
_ALLOWLIST_CONTRACT_RELPATHS = (
    "src/premura/parsers/CONTRACT.md",
    "src/premura/parsers/base.py",
)


def resolve_num_ctx() -> int:
    """Resolve the pinned context window from ``LIVE_TRIAL_NUM_CTX`` (default 16384).

    Single home for the env knob (contract §6); WP04's loop imports this rather
    than re-reading the environment, so the pinned size is set in exactly one
    place.
    """
    raw = os.environ.get("LIVE_TRIAL_NUM_CTX")
    if raw is None:
        return _NUM_CTX_DEFAULT
    try:
        value = int(raw)
    except ValueError:
        return _NUM_CTX_DEFAULT
    return value if value > 0 else _NUM_CTX_DEFAULT


# --------------------------------------------------------------------------- #
# 1. Chat client (stdlib urllib only; injectable transport seam). [T009]
# --------------------------------------------------------------------------- #


class ToolCallsUnsupportedError(RuntimeError):
    """Raised when the model's template lacks native tool-calling support.

    An explicit, returnable failure mode distinct from
    :class:`OllamaUnavailableError`: the endpoint is reachable but the loaded
    model cannot accept the ``tools`` parameter (Ollama answers with an HTTP
    error whose body mentions tool support). WP04 turns this into the
    ``tool_calls_unsupported`` outcome rather than a crash (NFR-006).
    """


#: A transport is the OUTSIDE boundary (DIRECTIVE_036): it takes the derived chat
#: URL + the encoded body and returns the raw response bytes (or raises a urllib
#: error). The default goes through the real localhost urlopen; tests and WP04's
#: fake backend substitute their own.
Transport = Callable[..., bytes]


def _chat_url() -> str:
    """Derive the ``/api/chat`` URL from the validated ``OLLAMA_URL`` host (NFR-001).

    The existing env knob keeps working (host/port honored) and the same
    local-only guard applies to the derived URL — prompt data cannot be sent
    off-machine by configuration drift.
    """
    validated = _validated_ollama_url(OLLAMA_URL)
    parsed = urlparse(validated)
    return urlunparse(parsed._replace(path="/api/chat"))


def _default_transport(url: str, body: bytes, *, timeout: int) -> bytes:
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - validated localhost URL
        raw: bytes = resp.read()
    return raw


def ollama_chat(
    messages: list[dict],
    *,
    model: str,
    tools: list[dict],
    num_ctx: int | None = None,
    timeout: int = 300,
    transport: Transport | None = None,
) -> dict:
    """Call local Ollama ``/api/chat`` with native tool-calling; return the message.

    POSTs ``{model, messages, tools, stream: False, options: {temperature: 0.1,
    num_ctx}}`` and returns the response ``message`` dict (``content`` + optional
    ``tool_calls``). Stdlib ``urllib`` only — no new dependency.

    Error mapping mirrors the one-shot posture: connection/timeout/garbled-JSON
    surface as :class:`OllamaUnavailableError` (a returnable sentinel, not a
    crash); an HTTP error whose body mentions tool support raises
    :class:`ToolCallsUnsupportedError`; any other HTTP error is "unavailable"
    too (a reachable-but-broken endpoint is unavailable to callers).

    ``transport`` is the injectable outside boundary (DIRECTIVE_036): the default
    goes through the real urlopen; tests pass a fake.
    """
    url = _chat_url()
    effective_num_ctx = num_ctx if num_ctx is not None else resolve_num_ctx()
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "options": {"temperature": 0.1, "num_ctx": effective_num_ctx},
        }
    ).encode("utf-8")

    send = transport if transport is not None else _default_transport
    try:
        raw = send(url, body, timeout=timeout)
    except urllib.error.HTTPError as exc:
        detail = _http_error_body(exc)
        if "tool" in detail.lower():
            raise ToolCallsUnsupportedError(
                f"Ollama model {model!r} does not support tools: {detail}"
            ) from exc
        raise OllamaUnavailableError(f"Ollama HTTP error {exc.code} at {url}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise OllamaUnavailableError(f"Ollama not reachable at {url}: {exc}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OllamaUnavailableError(
            f"Ollama returned a non-JSON response at {url}: {exc}"
        ) from exc
    message = payload.get("message")
    if not isinstance(message, dict):
        raise OllamaUnavailableError(f"Ollama returned no 'message' field: {payload!r}")
    return message


def _http_error_body(exc: urllib.error.HTTPError) -> str:
    """Best-effort read of an HTTPError body for tool-support classification."""
    try:
        raw = exc.read()
    except Exception:  # noqa: BLE001 - body read is best-effort only
        return str(exc.reason)
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw)


# --------------------------------------------------------------------------- #
# 2. Bounded tool registry + the three first handlers. [T010]
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TrialContext:
    """The bounded capability surface every tool handler resolves against.

    ``read_allowlist`` is the *only* read surface: the scenario source plus the
    contract files, all resolved INSIDE the sandbox tree. The fixture manifest is
    deliberately absent, so C-005 holds by construction. ``parser_spec`` is the
    ``module:attr`` the ingest runner resolves the operator-authored parser by.
    """

    sandbox: Sandbox
    sandbox_root: Path
    source: Path
    read_allowlist: tuple[Path, ...]
    parser_spec: str = _PARSER_SPEC


def build_trial_context(sandbox: Sandbox, *, source: Path) -> TrialContext:
    """Build a :class:`TrialContext` from a sandbox + scenario source (one factory).

    The allowlist is ``source`` + ``CONTRACT.md`` + ``base.py``, resolved against
    the sandbox tree. Anything not on it (the manifest, an arbitrary repo file,
    a traversal, an absolute escape) is unreachable by every handler.
    """
    root = sandbox.root.resolve()
    allowlist = [source.resolve()]
    for rel in _ALLOWLIST_CONTRACT_RELPATHS:
        allowlist.append((root / rel).resolve())
    return TrialContext(
        sandbox=sandbox,
        sandbox_root=root,
        source=source.resolve(),
        read_allowlist=tuple(allowlist),
    )


@dataclass(frozen=True, slots=True)
class ToolRegistration:
    """One bounded tool: ``{name, description, parameters-schema, handler}`` (FR-003).

    ``handler`` takes the validated args dict + the :class:`TrialContext` and
    returns a STRING (the tool-result message). The handler's reach is whatever
    its capability states and nothing more — the registration IS the bound.
    """

    name: str
    description: str
    parameters: dict
    handler: Callable[[dict, TrialContext], str]


def _handle_read_context(args: dict, ctx: TrialContext) -> str:
    """Return the WHOLE content of an allowlisted file; refuse anything else.

    Resolves the requested path (collapsing ``..`` and symlinks via
    ``Path.resolve()``) and compares it against the allowlist's resolved real
    paths. A non-allowlisted path — the manifest, an absolute escape, a
    traversal, any other repo file — returns a refusal STRING naming the
    allowlist so the model can self-correct. Never the content, never an
    exception. Allowlisted files are served whole (no truncation, FR-002).
    """
    requested = str(args.get("path", ""))
    try:
        resolved = Path(requested).resolve()
    except (OSError, RuntimeError):
        resolved = None
    if resolved is None or resolved not in set(ctx.read_allowlist):
        allowed = ", ".join(p.name for p in ctx.read_allowlist)
        return (
            f"REFUSED: {requested!r} is not a readable context file. "
            f"You may only read these allowlisted files: {allowed}."
        )
    try:
        return resolved.read_text(encoding="utf-8")
    except OSError as exc:
        return f"REFUSED: could not read {resolved.name!r}: {exc}"


def _handle_write_parser(args: dict, ctx: TrialContext) -> str:
    """Write ``code`` to the sandbox parser destination; return a confirmation.

    Stateless: a second call overwrites. (The first-call snapshot is WP04's loop
    concern, not this handler's.) The destination is exactly
    ``<sandbox>/src/premura/parsers/_live_trial_parser.py``.
    """
    code = str(args.get("code", ""))
    dest = ctx.sandbox_root / _PARSER_DEST_RELPATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(code, encoding="utf-8")
    return f"Wrote {len(code.encode('utf-8'))} bytes to {_PARSER_DEST_RELPATH}."


def _handle_run_ingest(args: dict, ctx: TrialContext) -> str:  # noqa: ARG001 - no args
    """Run the real WP03 ingest subprocess; return the JSON envelope verbatim.

    Delegates to ``live_trial._run_ingest_subprocess`` (reuse, never fork —
    NFR-004) over the context's sandbox/source/parser-spec and returns the
    runner's JSON envelope as a compact string, exactly as the runner emitted it
    (stage-tagged errors included). It NEVER returns grader output (contract §1).
    """
    envelope = live_trial._run_ingest_subprocess(
        ctx.sandbox, source=ctx.source, parser_spec=ctx.parser_spec
    )
    return json.dumps(envelope, separators=(",", ":"))


def default_tool_registry() -> dict[str, ToolRegistration]:
    """The three first registered tools (FR-003/FR-004).

    Registering a NEW tool is adding one entry to this dict — never editing a
    handler dispatcher or adding an ``if name == ...`` branch (NFR-005). Each
    handler's reach is bounded by :class:`TrialContext`; none can reach the
    fixture manifest, so C-005 holds at every turn by construction.
    """
    return {
        "read_context": ToolRegistration(
            name="read_context",
            description=(
                "Read the whole content of an allowlisted context file (the data "
                "source, the parser CONTRACT.md, or parsers/base.py). Returns a "
                "refusal string for any other path."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to an allowlisted context file.",
                    }
                },
                "required": ["path"],
            },
            handler=_handle_read_context,
        ),
        "write_parser": ToolRegistration(
            name="write_parser",
            description=(
                "Write the complete Python parser module to the sandbox parser "
                "destination. A later call overwrites it."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The full Python module source for the parser.",
                    }
                },
                "required": ["code"],
            },
            handler=_handle_write_parser,
        ),
        "run_ingest": ToolRegistration(
            name="run_ingest",
            description=(
                "Run the real sandbox ingest over the source using the currently "
                "written parser. Returns the runner's JSON envelope (errors are "
                "stage-tagged). Use it to verify your parser."
            ),
            parameters={"type": "object", "properties": {}, "required": []},
            handler=_handle_run_ingest,
        ),
    }


def registry_as_chat_tools(registry: dict[str, ToolRegistration]) -> list[dict]:
    """Project a registry into the ``tools`` list for the chat ``/api/chat`` call.

    Pure transformation over the registry: a tool added to the registry appears
    here automatically (no enumeration here either, NFR-005).
    """
    return [
        {
            "type": "function",
            "function": {
                "name": reg.name,
                "description": reg.description,
                "parameters": reg.parameters,
            },
        }
        for reg in registry.values()
    ]


# --------------------------------------------------------------------------- #
# 3. Single-source brief assembler with loud budget check. [T011]
# --------------------------------------------------------------------------- #


class BriefBudgetError(RuntimeError):
    """Raised when the assembled brief overflows the pinned context budget.

    The tier exists to PREVENT silent truncation (the 2026-06-04 audit's defect
    class): rather than drop required API surface, the assembler fails loudly
    and names the sizes so the caller pins a larger ``num_ctx`` or shrinks the
    brief deliberately.
    """


# The loop protocol preamble REPLACES the one-shot output directive (FR-001): it
# tells the operator it has tools and one response per turn, instead of demanding
# a bare module. It is the single canonical source for this brief part.
_LOOP_PREAMBLE = (
    "You are authoring a Premura parser over MULTIPLE TURNS using tools.\n"
    "Each of your responses is ONE turn. You have these tools:\n"
    "  - read_context(path): read the data source or an allowlisted contract file, whole.\n"
    "  - write_parser(code): write your complete parser module to the sandbox.\n"
    "  - run_ingest(): run the real sandbox ingest with your current parser and\n"
    "    read the JSON result envelope to see what passed or failed.\n"
    "Read what you need, write the parser with write_parser, verify it with\n"
    "run_ingest, and iterate. When the parser is correct, reply with NO tool\n"
    "calls (a short plain-text confirmation) to end the working phase.\n"
)

#: Conservative chars-per-token overestimate (documented crude rule). 3 over-counts
#: tokens for English/code, so the budget check errs toward failing LOUD rather
#: than shipping an over-budget brief.
_CHARS_PER_TOKEN = 3

#: Fraction of num_ctx reserved for the model's responses + accumulated turn
#: history. The brief itself must fit in the remaining budget.
_RESPONSE_RESERVE_FRACTION = 0.5


def _strip_one_shot_directive(contract_prompt: str) -> str:
    """Remove the trailing one-shot "Output ONLY the python module" directive.

    Structural strip (partition on the known sentence), so if the upstream prompt
    wording drifts the brief test catches the contradiction rather than shipping
    it (FR-001). Everything before the directive is kept verbatim; the directive
    and anything after it is dropped (it is the final line of both prompts).
    """
    head, sep, _tail = contract_prompt.partition(_ONE_SHOT_DIRECTIVE)
    if not sep:
        return contract_prompt.rstrip()
    return head.rstrip()


def assemble_brief(
    probe: _DrawerProbe,
    goal: str,
    source: Path,
    *,
    num_ctx: int | None = None,
) -> str:
    """Assemble the one coherent brief from one canonical source per part (FR-001).

    Parts, in contract §2 order:

    1. the tool-loop preamble (loop protocol + tool usage — REPLACES the one-shot
       output directive);
    2. the drawer probe's contract surface MINUS its one-shot-only output
       directive (stripped structurally);
    3. the ``GOAL:`` line (the driver's PHI-safe goal);
    4. the ``DATA SAMPLE (<name>):`` block — the same 8-line head the one-shot
       operator serves (mirrors ``OllamaOperator.operate``).

    The assembled size is checked against the effective ``num_ctx`` (default
    :func:`resolve_num_ctx`) minus a documented response/history reserve using a
    conservative ``len(brief) // _CHARS_PER_TOKEN`` token overestimate. On
    overflow it raises :class:`BriefBudgetError` naming the sizes — it NEVER
    truncates.
    """
    contract_surface = _strip_one_shot_directive(probe.contract_prompt)
    sample = "\n".join(source.read_text(encoding="utf-8").splitlines()[:8])
    brief = (
        f"{_LOOP_PREAMBLE}\n"
        f"{contract_surface}\n\n"
        f"GOAL: {goal}\n\n"
        f"DATA SAMPLE ({source.name}):\n{sample}\n"
    )

    effective_num_ctx = num_ctx if num_ctx is not None else resolve_num_ctx()
    budget_tokens = int(effective_num_ctx * (1.0 - _RESPONSE_RESERVE_FRACTION))
    estimated_tokens = len(brief) // _CHARS_PER_TOKEN
    if estimated_tokens > budget_tokens:
        raise BriefBudgetError(
            f"Brief overflows the pinned context budget: estimated "
            f"{estimated_tokens} tokens (len {len(brief)} / {_CHARS_PER_TOKEN}) "
            f"exceeds the {budget_tokens}-token budget "
            f"(num_ctx={effective_num_ctx} minus a "
            f"{int(_RESPONSE_RESERVE_FRACTION * 100)}% response/history reserve). "
            f"This tier NEVER truncates the brief — pin a larger LIVE_TRIAL_NUM_CTX "
            f"or shrink the served contract deliberately."
        )
    return brief


__all__ = [
    "OLLAMA_URL",
    "BriefBudgetError",
    "OllamaUnavailableError",
    "ToolCallsUnsupportedError",
    "ToolRegistration",
    "TrialContext",
    "assemble_brief",
    "build_trial_context",
    "default_tool_registry",
    "ollama_chat",
    "registry_as_chat_tools",
    "resolve_drawer_probe",
    "resolve_num_ctx",
]
