"""Share packets: a generated, privacy-graded view over one improvement-queue
item (``docs/building/architecture/OPERATING_ROLES.md`` §"Improvement scan,
queue, sharing", slice 4).

Mirrors :mod:`premura.trace`'s ``disclosure_to_json`` / ``disclosure_to_markdown``
pattern exactly: a packet is a generated VIEW over the stored
``log_improvement_item`` row (:func:`premura.session_log.store.get_improvement_item`).
It is never itself the record — nothing here writes to the session log, the
warehouse, or GitHub. Producing a packet and posting it are two separate acts
(see :data:`NOT_POSTED_NOTICE`); this module only ever does the first.

The three sharing levels are the draft's
(``docs/building/planning/operating-agent-roles.md`` "Supported sharing
levels"); see the structural branch's HONESTY NOTE for the one place the
frozen queue-item shape cannot yet deliver the draft's named fields. Each level's allowed content is documented as a RULE next to the
level's branch in :func:`render_share_packet`, not as an enumerated allowlist
of strings (DOCTRINE rule 2). The one rule that holds across ALL three levels,
because it is the actual PHI boundary: an item's own free-text ``summary`` /
``suggested_action`` is never echoed verbatim into ANY packet, at any level —
those fields are agent-authored prose and are exactly where a real value could
have leaked in despite the authoring convention that they be PHI-safe already.
A regex-based scrub of that prose would be fragile and give a false sense of
safety, so this module does not attempt one; it structurally excludes the
free-text fields instead and only ever surfaces closed-vocabulary bookkeeping
(``kind``, ``status``, counts) plus fabricated illustrative content.

Fabricated content (structural's small illustrations, synthetic_example's one
full record) reuses the harness fixture generator's seams (FR-3): a
seed-driven ``random.Random`` and canonical metric ids read from the committed
``dim_metric.yaml`` registry at call time (:func:`premura.harness.fixture_gen.
registry_metric_ids`) — never a hand-maintained metric list here. The seed
defaults to a hash of the item id, so the same item renders the same synthetic
content on every call (reproducible for review), while an explicit ``seed``
override keeps tests deterministic without depending on item-id hashing.
"""

from __future__ import annotations

import random
import zlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from .harness.fixture_gen import registry_metric_ids
from .ui import improvement_kinds

#: The draft's three sharing levels, adopted unchanged.
SHARE_PACKET_LEVELS: frozenset[str] = frozenset({"minimal", "structural", "synthetic_example"})

#: The FR-4 two-acts-split seam: every packet carries this notice verbatim so
#: it is legible wherever the packet is read that producing it is not posting
#: it. Posting (an actual GitHub write) is a separate, explicitly
#: human-approved act this module contains no code path for.
NOT_POSTED_NOTICE = (
    "This packet is produced only; nothing here posts it anywhere. Publishing "
    "to GitHub is a separate, explicit human-approved act."
)


@dataclass(frozen=True)
class SharePacket:
    """A rendered packet for one improvement item at one sharing level."""

    item_id: str
    level: str
    kind: str
    queue_status: str
    created_at: str
    body: str
    synthetic_fields: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "rendered",
            "item_id": self.item_id,
            "level": self.level,
            "kind": self.kind,
            "queue_status": self.queue_status,
            "created_at": self.created_at,
            "body": self.body,
            "synthetic_fields": [dict(f) for f in self.synthetic_fields],
            "notice": NOT_POSTED_NOTICE,
        }


def _kind_description(kind: str) -> str:
    declared = improvement_kinds.get_kind(kind)
    return declared.description if declared is not None else kind


def _fabricate_fields(item_id: str, count: int, seed: int | None) -> tuple[dict[str, Any], ...]:
    """Deterministically fabricate ``count`` synthetic field/value pairs.

    Field names are canonical metric ids drawn from the committed
    ``dim_metric.yaml`` registry (never derived from the real item); values
    are uniform-random numbers, illustration only. Never touches the real
    queue item's content.
    """
    rng = random.Random(seed if seed is not None else zlib.crc32(item_id.encode()))
    metric_ids = sorted(registry_metric_ids())
    chosen = rng.sample(metric_ids, k=min(count, len(metric_ids)))
    return tuple(
        {"field": metric_id, "value": round(rng.uniform(1, 200), 2)} for metric_id in chosen
    )


def _fabricate_timestamp(item_id: str, seed: int | None) -> str:
    rng = random.Random((seed if seed is not None else zlib.crc32(item_id.encode())) ^ 0x5A5A)
    dt = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(
        days=rng.randint(0, 365), minutes=rng.randint(0, 1439)
    )
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def render_share_packet(
    item: dict[str, Any],
    level: str,
    *,
    seed: int | None = None,
) -> SharePacket:
    """Derive a :class:`SharePacket` from one already-fetched queue item.

    ``item`` is the dict :func:`premura.session_log.store.get_improvement_item`
    returns — this function never opens a connection or reads the store
    itself, keeping the packet a pure view. An unknown ``level`` raises
    :class:`ValueError` (callers at the MCP boundary turn that into a
    structured ``rejected`` response, mirroring
    ``record_improvement_item``'s vocabulary checks).
    """
    if level not in SHARE_PACKET_LEVELS:
        raise ValueError(f"level must be one of {sorted(SHARE_PACKET_LEVELS)!r}, got {level!r}.")

    item_id = str(item["item_id"])
    kind = str(item["kind"])
    kind_desc = _kind_description(kind)
    queue_status = str(item["status"])
    created_at = str(item["created_at"])

    if level == "minimal":
        # RULE (draft level 1): say only that an unsupported source artifact
        # or gap of this general category was encountered. No summary, no
        # suggested_action, no trace_refs, no github_refs, no fabricated data.
        # It DOES deliberately carry the bookkeeping identifiers (item_id,
        # queue_status, created_at) so a reviewer can locate the canonical
        # queue row — queue metadata, never operator data.
        body = (
            f"An improvement candidate was recorded ({kind_desc}). No further "
            "detail is shared at this level."
        )
        return SharePacket(item_id, level, kind, queue_status, created_at, body)

    if level == "structural":
        # RULE (draft level 2): bookkeeping (status, how many local/GitHub
        # references exist as counts, never the reference strings' content)
        # plus a couple of fabricated illustrative field/value examples. The
        # item's own free-text summary/suggested_action is still never echoed.
        # HONESTY NOTE: the draft names "source name, file type, column names,
        # units, error class" for this level, but the frozen 9-field queue
        # item stores none of those, so they are NOT deliverable here —
        # emitting them would require item-shape evolution (out of scope for
        # slice 4). Until then this level ships only what the item actually
        # holds (bookkeeping) plus a clearly-generic fabricated illustration.
        fields = _fabricate_fields(item_id, 2, seed)
        trace_ref_count = len(item.get("trace_refs") or [])
        github_ref_count = len(item.get("github_refs") or [])
        body = (
            f"An improvement candidate was recorded ({kind_desc}), currently "
            f"'{queue_status}'. It references {trace_ref_count} local trace "
            f"note(s) and {github_ref_count} GitHub artifact(s) so far. Below "
            "is a generic synthetic illustration of a field/value shape — "
            "fabricated, not derived from the real artifact or its values."
        )
        return SharePacket(item_id, level, kind, queue_status, created_at, body, fields)

    # level == "synthetic_example"
    # RULE (draft level 3): everything structural has, plus ONE fully
    # fabricated record (a timestamp plus a few canonical-metric fields)
    # shaped like a generic source export — still never derived from the
    # item's own free-text content.
    fields = _fabricate_fields(item_id, 4, seed)
    record = {"timestamp": _fabricate_timestamp(item_id, seed)}
    record.update({str(f["field"]): f["value"] for f in fields})
    body = (
        f"An improvement candidate was recorded ({kind_desc}), currently "
        f"'{queue_status}'. Below is a synthetic record shaped like the kind "
        "of source artifact involved — fabricated for illustration, not the "
        "real data encountered."
    )
    return SharePacket(item_id, level, kind, queue_status, created_at, body, (record,))


def share_packet_to_json(packet: SharePacket) -> str:
    """Serialize a packet to JSON text (an on-demand export, not canonical)."""
    import json

    return json.dumps(packet.to_dict(), indent=2, ensure_ascii=False)


def share_packet_to_markdown(packet: SharePacket) -> str:
    """Render a packet as Markdown (an on-demand export, not canonical).

    Generated from the structured packet so it can never drift from the
    stored item's own fields.
    """
    lines: list[str] = []
    lines.append(f"# Share packet — `{packet.item_id}` ({packet.level})")
    lines.append("")
    lines.append(
        f"kind: `{packet.kind}` | status: `{packet.queue_status}` | created: {packet.created_at}"
    )
    lines.append("")
    lines.append(packet.body)
    lines.append("")
    if packet.synthetic_fields:
        lines.append("## Synthetic illustration (fabricated, not real data)")
        lines.append("")
        for row in packet.synthetic_fields:
            lines.append(f"- {row}")
        lines.append("")
    lines.append(f"> {NOT_POSTED_NOTICE}")
    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "NOT_POSTED_NOTICE",
    "SHARE_PACKET_LEVELS",
    "SharePacket",
    "render_share_packet",
    "share_packet_to_json",
    "share_packet_to_markdown",
]
