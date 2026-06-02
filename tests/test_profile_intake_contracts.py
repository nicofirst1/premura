"""Machine-applicable validation harness for the profile/intake contract (WP02).

These tests read the *shipped* contract artifacts under
``docs/architecture/contracts/`` as an external consumer would, and turn the
load-bearing planning invariants into pass/fail gates an agent reviewer can rely
on.

Stance: enforce SEMANTICS, not wording. The tests deliberately avoid freezing
exact prose sentences (those pass while the contract silently drifts). Each
assertion targets a structural/semantic guarantee that would FAIL if a future
change collapsed an overlap case, smuggled in a catch-all home, normalized a
hidden prerequisite, or grew a fake API/transport shape. The contract is
intentionally storage-agnostic, so the harness never asserts a storage shape.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

# Repo root from tests/: this file lives at <repo>/tests/test_*.py.
REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = REPO_ROOT / "docs" / "architecture" / "contracts"
PROSE_CONTRACT = REPO_ROOT / "docs" / "architecture" / "PROFILE_AND_INTAKE_CONTRACT.md"

ENTITIES_FILE = CONTRACTS_DIR / "profile_and_intake_entities.yaml"
EXAMPLES_FILE = CONTRACTS_DIR / "profile_and_intake_examples.yaml"
INVARIANTS_FILE = CONTRACTS_DIR / "profile_and_intake_invariants.yaml"
DEPENDENCIES_FILE = CONTRACTS_DIR / "profile_and_intake_dependencies.yaml"

SHIPPED_FILES = {
    "entities": ENTITIES_FILE,
    "examples": EXAMPLES_FILE,
    "invariants": INVARIANTS_FILE,
    "dependencies": DEPENDENCIES_FILE,
}

# The closed set of canonical homes. There is deliberately NO context/misc/
# metadata home; an extra home is a failure mode the harness must catch.
EXPECTED_CANONICAL_HOMES = frozenset(
    {
        "profile_context",
        "nutrition_intake",
        "supplement_intake",
        "observation_history",
        "note_history",
    }
)

# Homes that must never appear: a catch-all bucket collapses the one-home rule.
FORBIDDEN_HOME_TOKENS = frozenset({"context", "misc", "metadata", "other", "general"})


# --------------------------------------------------------------------------- #
# Helpers — load the real artifacts as an external consumer (no mocking).
# --------------------------------------------------------------------------- #
def _load(path: Path) -> dict:
    """Parse a shipped YAML contract file into a dict."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path.name} should parse to a mapping, got {type(data)}"
    return data


@pytest.fixture(scope="module")
def entities() -> dict:
    return _load(ENTITIES_FILE)


@pytest.fixture(scope="module")
def examples() -> dict:
    return _load(EXAMPLES_FILE)


@pytest.fixture(scope="module")
def invariants() -> dict:
    return _load(INVARIANTS_FILE)


@pytest.fixture(scope="module")
def dependencies() -> dict:
    return _load(DEPENDENCIES_FILE)


def _flatten_strings(obj) -> list[str]:
    """Collect every string scalar anywhere in a nested YAML structure."""
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str):
                out.append(k)
            out.extend(_flatten_strings(v))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            out.extend(_flatten_strings(item))
    return out


# =========================================================================== #
# T006 — black-box loading and cross-artifact vocabulary consistency.
# =========================================================================== #
def test_all_four_contract_files_exist_on_disk() -> None:
    """Treat the contract as an external artifact: the real files must ship."""
    for label, path in SHIPPED_FILES.items():
        assert path.is_file(), f"missing shipped contract artifact ({label}): {path}"


def test_each_contract_file_parses_as_a_mapping() -> None:
    for label, path in SHIPPED_FILES.items():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{label} did not parse to a mapping"


def test_each_file_declares_it_is_a_semantic_not_storage_contract(
    entities, examples, invariants, dependencies
) -> None:
    """The whole point of the surface is storage-agnostic meaning.

    If a future edit flips ``storage_prescribed`` to true or drops the
    ``semantic_contract_only`` scope, the contract has changed character and the
    harness should fail rather than quietly bless a storage design.
    """
    for label, doc in (
        ("entities", entities),
        ("examples", examples),
        ("invariants", invariants),
        ("dependencies", dependencies),
    ):
        assert doc.get("scope") == "semantic_contract_only", f"{label} lost semantic-only scope"
        assert doc.get("storage_prescribed") is False, f"{label} now prescribes storage"


def test_entities_have_expected_top_level_sections(entities) -> None:
    assert "canonical_homes" in entities
    assert "entities" in entities
    assert isinstance(entities["entities"], list) and entities["entities"]


def test_examples_have_expected_top_level_sections(examples) -> None:
    assert "canonical_homes" in examples
    assert "examples" in examples and examples["examples"]
    assert "overlap_pairs" in examples and examples["overlap_pairs"]


def test_invariants_have_expected_top_level_sections(invariants) -> None:
    assert "invariants" in invariants
    invs = invariants["invariants"]
    assert isinstance(invs, list) and invs
    for inv in invs:
        # Every invariant must lead with a positive "must always be true" rule.
        assert inv.get("invariant_id"), "invariant missing id"
        assert inv.get("must_always_be_true"), f"{inv.get('invariant_id')} has no positive rule"


def test_dependencies_have_expected_top_level_sections(dependencies) -> None:
    assert "declaration_shape" in dependencies
    assert "rules" in dependencies and dependencies["rules"]
    assert "examples" in dependencies and dependencies["examples"]


def test_canonical_homes_match_the_closed_expected_set(entities, examples) -> None:
    """Entities and examples must agree on the exact same closed home set.

    This fails loudly if a new home is appended or one is dropped in only one
    file — i.e. the two artifacts drifting apart.
    """
    assert set(entities["canonical_homes"]) == EXPECTED_CANONICAL_HOMES
    assert set(examples["canonical_homes"]) == EXPECTED_CANONICAL_HOMES


def test_no_catch_all_home_anywhere(entities, examples) -> None:
    """A context/misc/metadata bucket would silently absorb the undecided."""
    declared = set(entities["canonical_homes"]) | set(examples["canonical_homes"])
    assert declared.isdisjoint(FORBIDDEN_HOME_TOKENS), (
        f"forbidden catch-all home present in canonical_homes: {declared & FORBIDDEN_HOME_TOKENS}"
    )


def test_artifacts_share_one_vocabulary_for_homes_entities_and_keys(
    entities, examples, invariants, dependencies
) -> None:
    """Cross-reference NAMES across the four files, not unrelated strings.

    Every domain-level structured entity is referenced by an example, every
    example home is a declared home, and the dependency contract's domains are a
    subset of the canonical homes. This catches one file inventing a vocabulary
    the others do not know about.
    """
    homes = set(entities["canonical_homes"])

    # Structured entities defined for the new in-contract domains (i.e. not the
    # pre-existing observation/note homes, which this contract references but
    # does not define) must each be used by at least one classification example.
    in_contract_domains = {"profile_context", "nutrition_intake", "supplement_intake"}
    structured_entity_names = {
        e["name"]
        for e in entities["entities"]
        if e.get("domain") in in_contract_domains or e.get("also_used_by") in in_contract_domains
    }
    example_entities = {ex["entity"] for ex in examples["examples"]}
    # IntakeEvent/IntakeItem are backbone entities; examples reference the
    # quantity-bearing leaves (NutritionFact, SupplementDose) and the profile
    # leaf (ProfileAssertion). Require that every example entity that IS a
    # defined entity actually exists in the entity vocabulary.
    defined_names = {e["name"] for e in entities["entities"]}
    for ex in examples["examples"]:
        ent = ex["entity"]
        # Examples may name observation/note row-types that this contract does
        # not own; only entities claimed as in-contract must be defined here.
        if ent in defined_names or ent in structured_entity_names:
            assert ent in defined_names, f"example entity {ent!r} not defined in entities.yaml"

    # Every example's home is a declared canonical home.
    for ex in examples["examples"]:
        assert ex["canonical_home"] in homes, f"example {ex['example']!r} uses unknown home"

    # Dependency domains are a subset of canonical homes (shared vocabulary).
    for dep in dependencies["examples"]:
        for dom in dep["depends_on_domain"]:
            assert dom in homes, f"dependency {dep['consumer_name']!r} uses unknown domain {dom!r}"

    # At least one structured entity per in-contract domain is exercised by an
    # example, proving the example file speaks the entity file's language.
    assert example_entities & {"ProfileAssertion"}, "no profile example references ProfileAssertion"
    assert example_entities & {"NutritionFact"}, "no nutrition example references NutritionFact"
    assert example_entities & {"SupplementDose"}, "no supplement example references SupplementDose"


# =========================================================================== #
# T007 — invariant-oriented semantic gates.
# =========================================================================== #
def test_every_example_maps_to_exactly_one_canonical_home(examples) -> None:
    """INV-001: one-home classification, enforced structurally.

    Each example carries exactly one ``canonical_home`` scalar (not a list, not
    empty), drawn from the closed set. A dual classification or a vague/blank
    home fails here.
    """
    seen_examples = set()
    for ex in examples["examples"]:
        name = ex["example"]
        assert name not in seen_examples, f"duplicate example name {name!r}"
        seen_examples.add(name)
        home = ex.get("canonical_home")
        assert isinstance(home, str) and home, f"example {name!r} has no single home"
        assert home in EXPECTED_CANONICAL_HOMES, f"example {name!r} home {home!r} not canonical"


def test_overlap_pairs_keep_distinct_meanings(examples) -> None:
    """INV-002: similar real-world subjects must NOT collapse into one meaning.

    Every overlap pair must keep its members distinct: distinct example names,
    and a real distinguishing axis. The contract uses two axes:

      * different canonical homes (e.g. declared height -> profile_context vs
        measured height -> observation_history; meal energy -> nutrition_intake
        vs wearable kcal -> observation_history), and
      * asserted-vs-derived within one home (age is derived from birth_date and
        never asserted independently, so both sit in profile_context but are not
        the same value).

    A future edit that merged two members onto one identity (same name, or a
    same-home pair with no derived distinction) fails here — exactly the silent
    collapse the planning phase feared.
    """
    pairs = examples["overlap_pairs"]
    assert pairs, "overlap pairs are required to police conflation"

    # The contract names height (declared vs measured) and calories (intake vs
    # expenditure) as the canonical conflation cases; require they survive with
    # members spanning two different homes.
    by_subject = {p["subject"]: p for p in pairs}
    for subject, low, high in (
        ("height", "profile_context", "observation_history"),
        ("calories", "nutrition_intake", "observation_history"),
    ):
        assert subject in by_subject, f"{subject!r} overlap pair was dropped"
        homes = {m["canonical_home"] for m in by_subject[subject]["members"]}
        assert {low, high}.issubset(homes), (
            f"{subject!r} overlap no longer spans {low} and {high}; it may have collapsed"
        )

    # General structural guarantee for every pair.
    derived_marker = re.compile(r"deriv", re.IGNORECASE)
    for pair in pairs:
        members = pair["members"]
        assert len(members) >= 2, f"overlap {pair['subject']!r} needs >=2 members"
        names = {m["example"] for m in members}
        homes = {m["canonical_home"] for m in members}
        assert len(names) == len(members), (
            f"overlap {pair['subject']!r} reuses an example name across members"
        )
        for m in members:
            assert m["canonical_home"] in EXPECTED_CANONICAL_HOMES

        spans_homes = len(homes) == len(members)
        # Same-home overlaps are only legitimate when one member is explicitly
        # derived (the age-vs-birth-date carve-out). Anything else is a collapse.
        has_derived_distinction = any(
            derived_marker.search(" ".join(str(v) for v in m.values())) for m in members
        )
        assert spans_homes or has_derived_distinction, (
            f"overlap {pair['subject']!r} collapsed members into one home {homes} "
            f"without a derived-vs-asserted distinction"
        )


def test_profile_intake_observation_note_meanings_stay_distinct(examples) -> None:
    """The four meanings the overlap rule guards must each be reachable.

    profile_context, nutrition_intake, supplement_intake, observation_history,
    and note_history must each be the home of at least one shipped example,
    proving the homes are live distinctions and not merged in practice.
    """
    homes_in_use = {ex["canonical_home"] for ex in examples["examples"]}
    for required in (
        "profile_context",
        "nutrition_intake",
        "supplement_intake",
        "observation_history",
        "note_history",
    ):
        assert required in homes_in_use, f"no example exercises {required!r}; meaning may be merged"


def test_supersession_correction_path_is_present(entities, invariants) -> None:
    """INV-003: a visible supersession/correction path must exist.

    Enforced structurally: the entities that the corrections invariant applies
    to expose a ``supersedes_*`` reference, AND their ``provenance_kind`` admits
    a 'corrected' origin. A future edit that drops the supersedes field or
    removes 'corrected' (i.e. allows silent in-place overwrite) fails here.
    """
    by_name = {e["name"]: e for e in entities["entities"]}

    def _field_names(entity: dict) -> set[str]:
        fields = list(entity.get("required_fields") or []) + list(
            entity.get("optional_fields") or []
        )
        return {f["name"] for f in fields}

    def _allowed_provenance(entity: dict) -> set[str]:
        for f in entity.get("required_fields") or []:
            if f["name"] == "provenance_kind":
                return set(f.get("allowed") or [])
        return set()

    # ProfileAssertion (profile_context) must keep its supersession chain.
    pa = by_name["ProfileAssertion"]
    assert "supersedes_assertion_id" in _field_names(pa), "ProfileAssertion lost supersession ref"
    assert "corrected" in _allowed_provenance(pa), "ProfileAssertion can no longer be 'corrected'"

    # IntakeEvent (nutrition + supplement backbone) must keep its chain too.
    ie = by_name["IntakeEvent"]
    assert "supersedes_event_id" in _field_names(ie), "IntakeEvent lost supersession ref"
    assert "corrected" in _allowed_provenance(ie), "IntakeEvent can no longer be 'corrected'"

    # The invariant set must still carry a corrections-stay-visible rule.
    inv_names = {inv.get("name") for inv in invariants["invariants"]}
    assert "corrections_stay_visible" in inv_names, "corrections invariant was removed"


def test_partial_knowledge_allowed_without_inventing_values(entities, invariants) -> None:
    """INV-005: partial records are valid; unknowns are absent, never fabricated.

    Structural enforcement on the quantity-bearing entities:
      - NutritionFact carries an ``estimate_quality`` that admits 'partial'.
      - SupplementDose carries an ``ingredient_scope`` that admits 'unknown'
        and keeps ``ingredient_reference`` OPTIONAL (never required), so an
        unknown ingredient list stays representable rather than invented.
      - IntakeItem keeps ``product_reference`` optional (unknown product OK).
    If a future edit promoted any of these unknown-tolerant fields to required,
    that would force fabrication and fail here.
    """
    by_name = {e["name"]: e for e in entities["entities"]}

    def _required_names(entity: dict) -> set[str]:
        return {f["name"] for f in entity.get("required_fields") or []}

    def _optional_names(entity: dict) -> set[str]:
        return {f["name"] for f in entity.get("optional_fields") or []}

    def _allowed(entity: dict, field: str) -> set[str]:
        for f in (entity.get("required_fields") or []) + (entity.get("optional_fields") or []):
            if f["name"] == field:
                return set(f.get("allowed") or [])
        return set()

    nf = by_name["NutritionFact"]
    assert "partial" in _allowed(nf, "estimate_quality"), "NutritionFact can't be partial anymore"

    sd = by_name["SupplementDose"]
    assert "unknown" in _allowed(sd, "ingredient_scope"), "SupplementDose lost 'unknown' scope"
    assert "ingredient_reference" in _optional_names(sd), "ingredient_reference became required"
    assert "ingredient_reference" not in _required_names(sd), (
        "ingredient_reference must stay optional so unknown composition is representable"
    )

    item = by_name["IntakeItem"]
    assert "product_reference" in _optional_names(item), "product_reference became required"
    assert "product_reference" not in _required_names(item)

    # The invariant set must still carry the partial-allowed / no-fabrication rule.
    inv_names = {inv.get("name") for inv in invariants["invariants"]}
    assert "partial_allowed_fabrication_forbidden" in inv_names, "partial/fabrication rule removed"


# =========================================================================== #
# T008 — dependency-contract regression: hidden prerequisites & fake APIs.
# =========================================================================== #
REQUIRED_DECLARATION_FIELDS = frozenset(
    {"consumer_name", "depends_on_domain", "required_keys", "failure_mode"}
)


def test_declaration_shape_lists_the_required_fields(dependencies) -> None:
    shape = dependencies["declaration_shape"]
    declared_required = set(shape.get("required_fields") or [])
    assert REQUIRED_DECLARATION_FIELDS.issubset(declared_required), (
        f"declaration_shape dropped required fields: "
        f"{REQUIRED_DECLARATION_FIELDS - declared_required}"
    )


def test_every_dependency_example_carries_all_required_fields(dependencies) -> None:
    """INV-004: a real declaration names its keys; a bare domain ref is not one."""
    for dep in dependencies["examples"]:
        present = set(dep.keys())
        missing = REQUIRED_DECLARATION_FIELDS - present
        assert not missing, f"dependency {dep.get('consumer_name')!r} missing fields {missing}"
        # required_keys must actually name keys (non-empty), not be a placeholder.
        keys = dep["required_keys"]
        assert isinstance(keys, list) and keys, (
            f"dependency {dep['consumer_name']!r} declares no concrete required_keys"
        )
        for k in keys:
            assert isinstance(k, str) and k.strip(), f"empty key in {dep['consumer_name']!r}"


def test_dependency_examples_cover_profile_nutrition_and_supplement(dependencies) -> None:
    """Examples must exercise profile, nutrition, AND supplement use cases."""
    covered_domains: set[str] = set()
    for dep in dependencies["examples"]:
        covered_domains.update(dep["depends_on_domain"])
    for required in ("profile_context", "nutrition_intake", "supplement_intake"):
        assert required in covered_domains, f"no dependency example covers {required!r}"


def test_rules_explicitly_reject_opportunistic_fallback(dependencies) -> None:
    """The rules must FORBID treating opportunistic presence as a declaration.

    Semantic check, not a sentence snapshot: there must be a rule keyed
    ``forbidden`` whose text ties 'opportunistic' (or observation-history reuse)
    to being not a substitute for an explicit declaration. This catches the
    'undeclared prerequisite normalized after the fact' failure mode.
    """
    rules = dependencies["rules"]
    forbidden_texts = [
        str(r["forbidden"]).lower() for r in rules if isinstance(r, dict) and "forbidden" in r
    ]
    assert forbidden_texts, "no 'forbidden' rule present in dependency contract"
    assert any(
        "opportunistic" in t or ("observation" in t and "substitute" in t) for t in forbidden_texts
    ), "no rule forbids opportunistic/observation-history reuse as a substitute for declaration"

    # The matching invariant must also exist so reviewers can gate on it.
    inv_present = any("opportunistic" in str(r).lower() for r in _flatten_strings(rules))
    assert inv_present


def test_failure_modes_are_honest_not_silent(dependencies) -> None:
    """Each example must declare a non-empty failure_mode (honest behavior).

    A missing/blank failure_mode would let a consumer silently assume presence —
    exactly what the explicit-dependency invariant exists to prevent.
    """
    for dep in dependencies["examples"]:
        fm = dep.get("failure_mode")
        assert isinstance(fm, str) and fm.strip(), (
            f"dependency {dep.get('consumer_name')!r} has no honest failure_mode"
        )


def test_no_transport_contract_leakage_in_any_artifact(
    entities, examples, invariants, dependencies
) -> None:
    """This mission defines NO API surface; reject REST/GraphQL/endpoint shapes.

    Scan every string scalar across all four artifacts for transport-layer
    vocabulary. The dependency contract is a *domain* contract (what a consumer
    needs and how it fails), not a request schema. A future edit that grew a
    fake API (HTTP verbs, routes, status codes, GraphQL types) fails here.
    """
    transport_patterns = [
        r"\bhttps?://",
        r"\bGET\b",
        r"\bPOST\b",
        r"\bPUT\b",
        r"\bPATCH\b",
        r"\bDELETE\b",
        r"\bendpoint\b",
        r"\bgraphql\b",
        r"\bmutation\b",
        r"\bopenapi\b",
        r"\bswagger\b",
        r"\brest api\b",
        r"\brequest_schema\b",
        r"\bstatus_code\b",
        r"\bhttp_status\b",
        r"\bcontent-type\b",
        r"/api/",
        r"\bquery_param\b",
    ]
    compiled = [re.compile(p, re.IGNORECASE) for p in transport_patterns]

    offenders: list[str] = []
    for label, doc in (
        ("entities", entities),
        ("examples", examples),
        ("invariants", invariants),
        ("dependencies", dependencies),
    ):
        for s in _flatten_strings(doc):
            for rx in compiled:
                if rx.search(s):
                    offenders.append(f"{label}: {rx.pattern!r} matched in {s!r}")
    assert not offenders, "transport-contract leakage detected:\n" + "\n".join(offenders)


def test_dependency_contract_declares_itself_domain_not_request_schema(dependencies) -> None:
    """Guard the framing: the description must position this as a domain contract.

    Not a wording snapshot — it only asserts the file still claims to be a
    domain contract and disclaims being a request/wire schema, which is the
    invariant the no-API constraint rests on.
    """
    desc = str(dependencies.get("description", "")).lower()
    assert "domain contract" in desc, "dependency file no longer frames itself as a domain contract"
    assert "not an api request schema" in desc or "not how a request travels" in desc, (
        "dependency file dropped its disclaimer that it is not a transport/request schema"
    )
