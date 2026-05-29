# premura — Prior Art for Agent-Operated Software and Evidence Guardrails

> Status: proposal/archive. Literature map to inform planning, not a runtime
> contract.
>
> Generated: 2026-05-29
> Scope: what already exists, in research and in industry, for (a) building a
> codebase to be operated and extended by AI agents rather than humans, and
> (b) striking the balance between giving agents freedom and adding guardrails
> that stop them from stating wrong things — especially about health.

## Why this exists

Premura is built to be operated and extended by AI agents (see
[../../product/DOCTRINE.md](../../product/DOCTRINE.md)). A natural question is
whether anyone has already worked out *how* to design software this way, and how
to hold the line between agent freedom and safety. This note records a
deliberate search of the public record so future planning starts from what is
known instead of re-deriving it.

The search was run as four independent passes, each told to actively look for
work that would prove "there is no established approach yet" wrong: one on
academic papers, one on policy-and-guardrail tooling, one on industry practice,
and one on the specific freedom-versus-guardrail / grounding question.

## What the search found, in one paragraph

The pieces premura relies on mostly exist somewhere, but the specific
combination premura is aiming at does not. The *conventions and plumbing* for
agent-operated repositories have genuinely converged (shared standards, a named
practitioner movement, one academic roadmap). The *guardrail* tooling is real
and shipping — but only for the question "is this agent allowed to take this
action?". Nothing on the market checks "is this statement actually true?" in a
hard, deterministic, auditable way; every shipping truth-check is one model
grading another model and returning a probability. The idea of turning "is it
true?" into a checkable structural test ("is this claim backed by admissible
evidence?") does exist in research, but only as an after-the-fact scorer or a
soft learned behavior, and not for personal health data where staleness and
sparseness are the real danger. That last cell is essentially empty, and it is
where premura's Stage 2 evidence work sits.

## Layer 1 — Designing software to be run by agents

This is more developed than "scattered blog posts," but there is still no
settled, proven discipline (no equivalent of a widely-agreed manifesto).

- **Agent-Computer Interface (ACI)** — the idea that an AI agent is a new kind
  of user and you should design the interface *for it*, not reuse the human one.
  Named and shown to matter in the SWE-agent paper. https://arxiv.org/abs/2405.15793
- **Structured Agentic Software Engineering (SASE / "SE4A")** — an academic
  roadmap that explicitly splits software engineering *for humans* from software
  engineering *for agents* — essentially premura's own "for agents, not humans"
  stance, named independently. It is a position paper, not a validated method.
  https://arxiv.org/abs/2509.06216
- **Agent Experience ("AX")** — a named industry movement (Netlify, Jan 2025):
  treat the agent's experience of your product the way you treat a developer's.
  https://biilmann.blog/articles/introducing-ax/
- **Shared standards now under neutral governance** (Linux Foundation's Agentic
  AI Foundation, Dec 2025):
  - **MCP (Model Context Protocol)** — how an agent reaches tools.
    https://modelcontextprotocol.io/docs/getting-started/intro
  - **AGENTS.md** — a repo-root file of instructions for agents; ~60k repos use
    it (premura does). https://agents.md/
  - **A2A (Agent2Agent)** — how agents talk to each other.
    https://a2a-protocol.org/latest/
- **llms.txt** — an agent-readable index of a site's docs. Real but partial
  adoption. https://www.mintlify.com/blog/what-is-llms-txt
- **Vendor guidance** — Anthropic, "Writing effective tools for agents" (fewer,
  better, well-described tools that return meaningful context).
  https://www.anthropic.com/engineering/writing-tools-for-agents
- **A worked case study** — "Codified Context": a 108k-line codebase made
  agent-operable with a written "constitution" plus specialist agents and a
  knowledge base. One team's account, not a general method.
  https://arxiv.org/abs/2602.20478
- **A false friend to avoid** — the older (2000s) field also called
  "agent-oriented software engineering" (Wooldridge/Jennings, Gaia, Tropos) is
  about building systems that *use* software agents as parts, not systems built
  *for* external AI agents to operate. Different problem.
  https://www.cs.ox.ac.uk/people/michael.wooldridge/pubs/aose2000a.pdf

## Layer 2 — Guardrails that check whether an action is allowed

"Policy as code" means writing the rules an action must satisfy as testable,
versioned files that a checker evaluates automatically — rather than leaving
them as prose. For agents this is real and in production, but it only answers
*"is this action permitted?"* — never *"is the answer correct?"*.

- **Open Policy Agent (OPA) / Rego** — general rule engine, now used to gate
  agent tool calls. https://codilime.com/blog/why-use-open-policy-agent-for-your-ai-agents/
- **AWS Cedar / Bedrock AgentCore** — fine-grained permission checks at the
  tool gateway; can constrain individual arguments.
  https://aws.amazon.com/blogs/security/why-policy-in-amazon-bedrock-agentcore-chose-cedar-for-securing-agentic-workflows/
- **Cerbos** — per-action permission rules in plain files, fast and testable.
  https://www.cerbos.dev/features-benefits-and-use-cases/agentic-authorization
- **HashiCorp Sentinel** — notable for *graduated* enforcement: a rule can be
  advisory (warn), soft (block but a human can override), or hard (never). This
  maps cleanly to premura's human-on-the-loop stance. It also checks the
  *proposed* change before it happens.
  https://developer.hashicorp.com/sentinel/docs/concepts/enforcement-levels
- **NeMo Guardrails** (NVIDIA) — broad rails incl. a "fact-checking" rail — but
  that rail is a model scoring whether the answer matches retrieved text, i.e. a
  probability, not a hard check.
  https://docs.nvidia.com/nemo/guardrails/latest/configure-rails/guardrail-catalog/fact-checking.html
- **Guardrails AI** — schema validation plus a hub of risk validators (mostly
  model-scored). https://guardrailsai.com/
- **Meta LlamaFirewall** — prompt-injection, alignment auditing, code scanning.
  https://arxiv.org/abs/2505.03574
- **OpenAI Agents SDK guardrails** — input/output checks with a "tripwire"; can
  run alongside or block the agent. https://openai.github.io/openai-agents-python/guardrails/
- **Invariant Labs (now Snyk)** — data-flow rules ("don't let data from X reach
  Y") and scanning of MCP servers. https://invariantlabs.ai/blog/guardrails
- **Microsoft Agent Governance Toolkit** — multi-engine, maps to the OWASP
  "Agentic AI Top 10" risk list (Dec 2025).
  https://opensource.microsoft.com/blog/2026/04/02/introducing-the-agent-governance-toolkit-open-source-runtime-security-for-ai-agents/
- **"Policies on Paths"** — a formal argument that prose instructions only
  *nudge* an agent, while real governance must evaluate the proposed next action.
  https://arxiv.org/abs/2603.16586
- **Constrained decoding** (Outlines, Guidance, XGrammar) — forces output to fit
  a schema. Guarantees the *shape* is valid, not that the *values* are true.
  https://mbrenndoerfer.com/writing/constrained-decoding-structured-llm-output

## Layer 3 — Treating "is it true?" as a structural check (the gap premura targets)

The honest result is two-sided. The general *move* — refuse to let a claim
stand unless it is backed by admissible evidence, instead of trying to verify
truth directly — does appear in research. But every instance is either
after-the-fact (it scores or fixes a finished answer) or soft (a learned habit,
not a hard precondition), and none is built for personal health data.

- **RARR** — find supporting evidence for a finished answer and rewrite the
  unsupported parts. After-the-fact. https://arxiv.org/abs/2210.08726
- **FActScore** — break an answer into atomic facts and report the share backed
  by a source. After-the-fact scorer. https://arxiv.org/abs/2305.14251
- **Self-RAG** — the model emits special tokens that decide, mid-answer, whether
  to fetch evidence and whether the draft is supported. In-flight but learned
  and soft. https://arxiv.org/abs/2310.11511
- **GRACE** — a trained gate on whether the evidence is *sufficient*; otherwise
  the model declines to answer. https://arxiv.org/abs/2601.04525
- **GSAR** — sorts each claim into Grounded / Ungrounded / Contradicted /
  Complementary and acts on the mix. The clearest "type system for claims," but
  applied after generation. https://arxiv.org/abs/2604.23366
- **Eidoku** — states the exact reframing as its thesis: replace "is this true?"
  with "does this fit coherently in the evidence graph?".
  https://arxiv.org/abs/2512.20664
- **Tool Receipts (NabaOS)** — tamper-proof receipts of what a tool actually
  returned, with claims tagged by where they came from.
  https://arxiv.org/abs/2603.10060
- **MiniScope** — a formal least-privilege scheme for which *tools* an agent may
  call. Restricts actions, not assertions. https://arxiv.org/abs/2512.11147
- **Abstention research** — declining to answer treated as a first-class
  behavior, but triggered by the model's *uncertainty*, not by an evidence rule.
  https://arxiv.org/abs/2407.18418 · https://arxiv.org/abs/2404.10960
- **The theoretical anchor — "Hallucination is Inevitable" (Xu et al. 2024)** —
  proves that, in general, a computable model cannot be guaranteed to avoid
  stating false things. The unstated corollary: the only dependable escape is to
  restrict the agent to questions it can answer from admissible, grounded
  evidence. This is the formal *reason* premura's evidence-admissibility layer is
  not optional polish but the load-bearing idea. https://arxiv.org/abs/2401.11817
- **Closest in a health setting** — a proposed framework that grades evidence
  quality and only reasons over verified sources for clinical decision support.
  Important caveat: it is a design proposal with no implementation, and it works
  over clinical-guideline literature, not a personal warehouse of wearable and
  lab data. https://pmc.ncbi.nlm.nih.gov/articles/PMC12913532/
- **The problem, demonstrated** — a study showing deployed health AIs
  recommended withdrawn or unapproved treatments, i.e. they had no check on
  whether their evidence was still current.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC12722510/

## Where premura sits

The search could not find existing work occupying this combination, which is
exactly what the Stage 2 evidence admissibility mission is reaching for:

1. **Admissibility as a check the agent must pass _before_ it states something**,
   not a scorer applied to a finished answer or a soft learned habit.
2. **For personal health data**, with *freshness* (is this recent enough for the
   question?), *evidence kind* (is this the right sort of measurement?), and
   *sufficiency* (is there enough of it?) treated as explicit, declared
   admission rules — the dimensions that matter most for sparse, self-tracked
   data. Nobody has built this; the nearest health proposal is unbuilt and aimed
   at published literature.
3. **One shared idea behind both kinds of guardrail** — restricting what an
   agent may *do* (Layer 2) and restricting what it may *assert* (Layer 3) — so
   they are designed as the same pattern rather than two bolt-ons.
4. **The language of evidence admissibility** (admissible, stale, wrong-kind,
   too-sparse) borrowed deliberately, as a clear shared vocabulary, the way the
   law of evidence uses it.

## How to use this note

- When planning the Stage 2 evidence work, prefer adopting an existing piece
  over inventing one: the *graduated enforcement* idea from Sentinel, the
  *declaration-checked-by-a-deterministic-evaluator* shape from policy-as-code,
  and the *claim-typing* idea from GSAR are all directly reusable.
- Treat the truth axis and the permission axis as the same shape, per point 3.
- Cite Xu et al. 2024 as the reason the admissibility layer exists at all.

## Caveat on sources

The recent (2026) paper identifiers above came from live web search during this
pass and have not each been opened and verified line by line. The standards,
vendor pages, and the older landmark papers (RARR, FActScore, Self-RAG, Xu et
al.) are reliable; spot-check any 2026 arXiv identifier before relying on it in
formal work.

## Related research

- [AGENT_POLICY_ABSTRACTION_RESEARCH.md](AGENT_POLICY_ABSTRACTION_RESEARCH.md) —
  names and design guidance for the bounded "fill-in-the-declaration" pattern.
- [STAGE2_EVIDENCE_ADMISSIBILITY_RESEARCH.md](STAGE2_EVIDENCE_ADMISSIBILITY_RESEARCH.md)
  — the evidence-admissibility research this prior-art map supports.
