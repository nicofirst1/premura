"""AI-chat supplement/medication recall parser — supplement intake seam.

Reads a ``premura.ai_chat_recall.v1`` JSON document (an AI assistant's
recollection of the supplements and oral medications the user told it about,
produced by a paste-prompt derived from the interchange contract) and emits an
**intake-only** :class:`~premura.parsers.base.ParseOutput`. One entry is one
recalled item, which maps onto one :class:`SupplementIntakeInput` with one
item and at most one dose.

Authoritative format: ``docs/building/architecture/AI_CHAT_RECALL_CONTRACT.md``.
The parser knows the format, never the assistant: each export names its
``assistant``, which becomes a distinct provenance source
``ai_chat_recall:<slug>`` without any registry edit.

Honesty posture (the two contract decisions):

- **Fuzzy time.** ``since`` carries an explicit precision (``day`` / ``month``
  / ``year``) whose ``date`` shape must match (``YYYY-MM-DD`` / ``YYYY-MM`` /
  ``YYYY``); a mismatch is a contradiction and the entry is skipped with a
  reason. The event anchors at the earliest instant of the declared period
  (month -> 1st, year -> Jan 1) at midnight, naive, no timezone invented
  (same posture as other bare-date sources). An entry with no ``since``
  anchors at ``exported_on`` with precision ``"unknown"``. The declared
  precision and the original chat wording persist verbatim in
  ``raw_payload``, so no consumer must trust the anchor as more precise than
  it is.
- **Provenance grade.** Everything lands under
  ``source_kind = "ai_chat_recall"`` — recalled, hallucination-prone, never
  mixed with app-logged intake. ``quote`` (the source chat's own wording) is
  mandatory per entry; an entry without it is skipped, never loaded. This
  source answers the *inventory* question only: one event per recalled item,
  daily events are never synthesized from "I take it every day".

Idempotency: ``dedupe_key = sha256("ai_chat_recall|<assistant_slug>|<labels>|<since>")``
— re-running the export later (new ``exported_on``) is a no-op for
already-loaded items; the store is append-only, first write wins.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import (
    IntakeBatch,
    ParseOutput,
    SkippedRow,
    SourceDescriptor,
    SupplementDoseInput,
    SupplementIntakeInput,
    SupplementItemInput,
)

SOURCE_KIND = "ai_chat_recall"
FORMAT_MARKER = "premura.ai_chat_recall.v1"

# since.precision -> (exact date shape that precision claims, strptime format).
# A pair that disagrees is a contradiction, not data. The shape regex is strict
# (zero-padded) so the dedupe token derived from the date is stable: "2026-3"
# and "2026-03" must not become two different inventory rows.
_PRECISION_SHAPES: dict[str, tuple[re.Pattern[str], str]] = {
    "day": (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "%Y-%m-%d"),
    "month": (re.compile(r"^\d{4}-\d{2}$"), "%Y-%m"),
    "year": (re.compile(r"^\d{4}$"), "%Y"),
}

_ENTRY_KEYS = {
    "product_label",
    "ingredient_label",
    "form_label",
    "dose",
    "since",
    "quote",
    "chat_date",
}
_TOP_KEYS = {"format", "assistant", "exported_on", "entries"}
_DOSE_KEYS = {"amount_num", "unit", "amount_text"}
_SINCE_KEYS = {"date", "precision", "ongoing"}


def _slug(assistant: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", assistant.lower()).strip("_")


def _dedupe_key(assistant_slug: str, labels: str, since: str) -> str:
    payload = f"{SOURCE_KIND}|{assistant_slug}|{labels}|{since}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_day(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%Y-%m-%d")


def _strip_markdown_fence(text: str) -> str:
    """Unwrap one whole-document markdown code fence, if present.

    Assistants routinely wrap the JSON reply in a ``` fence despite the
    paste-prompt's "nothing else" instruction, and the user saves the reply
    verbatim. This is bounded format-level recovery only — a fence around the
    entire document — never extraction of JSON out of surrounding prose.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines[-1].strip() == "```" and len(lines) >= 2:
        return "\n".join(lines[1:-1]).strip()
    return stripped


class AiChatRecallParser:
    """Parses an AI-chat recall export into an intake-only batch."""

    source_kind = SOURCE_KIND
    language_hint: str | None = "en"

    def declares_metrics(self) -> list[str]:
        # Intake-only: emits no observation metric_ids, so no dim_metric rows.
        return []

    def parse(self, path: Path) -> ParseOutput:
        text = _strip_markdown_fence(path.read_text(encoding="utf-8"))
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}: not valid JSON: {exc}") from exc
        if not isinstance(doc, dict) or doc.get("format") != FORMAT_MARKER:
            raise ValueError(
                f"{path.name}: missing format marker {FORMAT_MARKER!r}; "
                "not an AI-chat recall export?"
            )

        assistant = doc.get("assistant")
        if not isinstance(assistant, str) or not _slug(assistant):
            raise ValueError(f"{path.name}: 'assistant' must be a non-empty string")
        assistant_slug = _slug(assistant)

        exported_on_raw = doc.get("exported_on")
        try:
            exported_on = _parse_day(str(exported_on_raw))
        except (ValueError, TypeError):
            raise ValueError(
                f"{path.name}: 'exported_on' must be a YYYY-MM-DD date, got {exported_on_raw!r}"
            ) from None

        entries = doc.get("entries")
        if not isinstance(entries, list):
            raise ValueError(f"{path.name}: 'entries' must be a list")

        source_id = f"{SOURCE_KIND}:{assistant_slug}"
        batch = IntakeBatch()
        batch.source_descriptors[source_id] = SourceDescriptor(
            source_id=source_id,
            source_kind=SOURCE_KIND,
            app_name=assistant,
        )

        unmapped: set[str] = set()
        for key in doc:
            if key not in _TOP_KEYS:
                unmapped.add(f"vendor:{SOURCE_KIND}:{key}")

        for index, entry in enumerate(entries):
            self._parse_entry(
                entry,
                index=index,
                assistant=assistant,
                assistant_slug=assistant_slug,
                source_id=source_id,
                exported_on=exported_on,
                exported_on_raw=str(exported_on_raw),
                batch=batch,
                unmapped=unmapped,
            )

        batch.unmapped_metrics = sorted(unmapped)
        return ParseOutput(intake=batch)

    # ----- entries ---------------------------------------------------------- #
    def _parse_entry(
        self,
        entry: Any,
        *,
        index: int,
        assistant: str,
        assistant_slug: str,
        source_id: str,
        exported_on: datetime,
        exported_on_raw: str,
        batch: IntakeBatch,
        unmapped: set[str],
    ) -> None:
        def skip(reason: str, label: str = "?") -> None:
            batch.skipped_rows.append(
                SkippedRow(raw_field=f"entries[{index}]:{label}", reason=reason)
            )

        if not isinstance(entry, dict):
            skip("entry is not a JSON object")
            return

        product = self._clean_str(entry.get("product_label"))
        ingredient = self._clean_str(entry.get("ingredient_label"))
        label = product or ingredient or "?"
        if not product and not ingredient:
            skip("entry names neither product_label nor ingredient_label")
            return

        quote = self._clean_str(entry.get("quote"))
        if not quote:
            skip(
                "no provenance quote from the source chat; recalled intake "
                "without the chat's own wording is unverifiable",
                label,
            )
            return

        for key in entry:
            if key not in _ENTRY_KEYS:
                unmapped.add(f"vendor:{SOURCE_KIND}:entry.{key}")

        # --- fuzzy time: explicit precision, contradictions are skipped ----- #
        since = entry.get("since")
        ongoing: bool | None = None
        if since is None:
            ts = exported_on
            precision = "unknown"
            since_token = "unknown"
        else:
            if not isinstance(since, dict):
                skip("'since' is not a JSON object", label)
                return
            precision_raw = since.get("precision")
            date_raw = since.get("date")
            if not isinstance(precision_raw, str) or precision_raw not in _PRECISION_SHAPES:
                skip(
                    f"'since.precision' must be one of {sorted(_PRECISION_SHAPES)}, "
                    f"got {precision_raw!r}",
                    label,
                )
                return
            if date_raw is None:
                skip("'since' declares a precision but carries no date", label)
                return
            shape, fmt = _PRECISION_SHAPES[precision_raw]
            date_str = str(date_raw).strip()
            if not shape.match(date_str):
                skip(
                    f"'since.date' {date_raw!r} does not match declared "
                    f"precision {precision_raw!r} (a fabricated-precision contradiction)",
                    label,
                )
                return
            try:
                ts = datetime.strptime(date_str, fmt)
            except ValueError:
                skip(f"'since.date' {date_raw!r} is not a real calendar date", label)
                return
            ongoing_raw = since.get("ongoing")
            if ongoing_raw is not None and not isinstance(ongoing_raw, bool):
                skip(f"'since.ongoing' must be a boolean, got {ongoing_raw!r}", label)
                return
            ongoing = ongoing_raw
            precision = precision_raw
            # The dedupe token is the canonical re-rendering of the parsed
            # date, not the raw string, so equal facts hash equally.
            since_token = ts.strftime(fmt)
            for key in since:
                if key not in _SINCE_KEYS:
                    unmapped.add(f"vendor:{SOURCE_KIND}:entry.since.{key}")

        # --- dose: numeric and/or free text, never coerced ------------------ #
        doses: list[SupplementDoseInput] = []
        dose = entry.get("dose")
        if dose is not None:
            if not isinstance(dose, dict):
                skip("'dose' is not a JSON object", label)
                return
            amount_num = dose.get("amount_num")
            amount_text = self._clean_str(dose.get("amount_text"))
            if amount_num is not None and not isinstance(amount_num, (int, float)):
                skip(f"'dose.amount_num' must be a number, got {amount_num!r}", label)
                return
            if amount_num is None and not amount_text:
                skip("'dose' carries neither amount_num nor amount_text", label)
                return
            for key in dose:
                if key not in _DOSE_KEYS:
                    unmapped.add(f"vendor:{SOURCE_KIND}:entry.dose.{key}")
            doses.append(
                SupplementDoseInput(
                    ingredient_label=ingredient,
                    amount_num=float(amount_num) if amount_num is not None else None,
                    amount_text=amount_text,
                    unit=self._clean_str(dose.get("unit")),
                )
            )

        raw_payload: dict[str, Any] = {
            "quote": quote,
            "date_precision": precision,
            "assistant": assistant,
            "exported_on": exported_on_raw,
        }
        if ongoing is not None:
            raw_payload["ongoing"] = ongoing
        chat_date = self._clean_str(entry.get("chat_date"))
        if chat_date:
            raw_payload["chat_date"] = chat_date

        labels_token = f"{(product or '').lower()}|{(ingredient or '').lower()}"
        dedupe_key = _dedupe_key(assistant_slug, labels_token, since_token)
        if any(e.dedupe_key == dedupe_key for e in batch.supplement_events):
            # A duplicated item is the source class's own failure mode
            # (assistant recall); skip it honestly rather than letting the
            # within-batch dedupe-uniqueness check fail the whole export.
            skip(
                "duplicate of an earlier entry (same labels and same start); first occurrence wins",
                label,
            )
            return
        batch.supplement_events.append(
            SupplementIntakeInput(
                source_id=source_id,
                source_kind=SOURCE_KIND,
                ts_utc=ts,
                dedupe_key=dedupe_key,
                local_tz=None,
                items=[
                    SupplementItemInput(
                        product_label=product,
                        ingredient_label=ingredient,
                        form_label=self._clean_str(entry.get("form_label")),
                        doses=doses,
                    )
                ],
                raw_payload=raw_payload,
            )
        )

    @staticmethod
    def _clean_str(value: Any) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None
