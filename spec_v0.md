# Spec v0: Three Primitives for Agentic Memory

**Status:** Draft for internal pressure-test. Not for publication.
**Author:** Vipul Sehgal
**Date:** 2026-04-25

## Preamble

This spec defines three primitives that any production-grade agentic memory system needs and that most implementations skip. The primitives are extracted from one production system (TurnoCockpit) and will be pressure-tested in a second domain (AI capability tracking). Public spec ships only after both systems are running and the primitives have caught real failures.

A memory system without these three primitives can be useful but cannot be trusted with consequential decisions over time. The thesis is that these three together form a minimum bar: two for trust within the schema as it exists today, one for trust as the schema itself has to evolve.

The three primitives sit on a shared **Foundational Substrate** (described below) that unifies world-knowledge and self-observation under one typed memory store, plus declares the deployment's available models and how agents select them. The substrate is not itself a primitive; it is what the primitives all stand on. **"It works" is a precursor to "it works cost-effectively"**: the protocol defines what makes the system trustable; cost optimization is a refinement built on top.

Note on history: an earlier draft listed Plan-as-the-assumptions-register and Tier-sticky sub-agent delegation as separate primitives. Both were TurnoCockpit-extracted concerns that didn't generalize. Plan-as-register's substance reduced to a grounding contract on synthesis records (covered as part of Primitive 1). Tier-sticky delegation reduced to model selection as a substrate-level configuration concern, not a primitive. The full plan/edit/rerun mechanic and the tier-sticky cost-economics framing are documented as deployment-specific extensions for analytics-heavy and cost-sensitive use cases respectively.

Each section below: definition, problem, mechanism, schema, worked example, and inline decision points marked **[DECISION N]**.

---

## Foundational Substrate: Activity as typed memory

Before the three primitives can do their work, the system needs a substrate that handles three jobs: store world-knowledge (what claims and observations the system holds), store self-observation (what the system itself did, when, and why), and declare what models the deployment has available and how agents select them. The substrate's first design choice is to **unify world-knowledge and self-observation into a single typed memory store** rather than splitting them into "memory" and "logs." The second design choice is to make models declarative deployment configuration that agents reference by name with priority-ordered preferences.

### Why unify

A separate logs table cannot benefit from conflict-flagging, schema evolution, or the same retrieval contract. The system would observe the world with one set of primitives and observe itself with another, and the two would drift. Unifying them means activity records are typed memory records too: same envelope, same retrieval semantics, same evolution mechanism. The system observes itself with the same primitives it uses to observe the world.

### Universal envelope

Every record in the system, whether a `claim`, a `personal_observation`, a `policy`, or an activity event, carries the standard memory envelope (id, type, subject, body, source, claimant, confidence, effective_at, expires_at, provenance, version, timestamps) plus an extended set for activity tracing:

```
trace_id              // groups all records emitted from one user-facing query
actor_type            // 'user' | 'agent' | 'tool' | 'system'
actor_id              // which agent/tool emitted; for sub-agent spawns, identifies the spawn site
event_kind            // see seed activity types below
duration_ms           // latency, when applicable
cost_usd              // model inference cost, when applicable
agent_relevance       // 'high' | 'low' | 'none' — used by agent context lens (see Decision 0.1)
```

Non-activity records leave the activity-specific fields null.

### Seed activity record types

Themselves subject to Primitive 3 schema evolution, but the v0 universal minimum is:

- `query_event` — user asked something
- `retrieval_event` — records were fetched (with which filters, returning which IDs)
- `synthesis_event` — synthesis produced (links to the `synthesis`-type record carrying the SynthesisBody from Primitive 1)
- `tool_call_event` — tool invoked, with policy lookups and any denials
- `subagent_spawn_event` — main agent spawned a runtime sub-agent (records the spawn-site, the sub-agent's prompt summary, and the model selected for it)
- `capture_event` — record added to memory (with conflict-check result)
- `conflict_flagged_event` — contradiction detected
- `schema_proposal_event` and `schema_decision_event` — Primitive 3 case-law entries
- `policy_denial_event` — a tool denied a call due to policy (Primitive 2)
- `cost_cap_event` — a budget cap was hit
- `model_rejig_event` — a model was added or removed in deployment config and agent preferred_models lists were updated (per substrate model selection)

### Two retrieval contracts: same substrate, two lenses

The substrate serves two consumers with very different needs. They read the same store through different contracts.

**Agent context lens.** Used by the main agent at every prompt construction, and by any runtime sub-agent it spawns (so the sub-agent can inherit the relevant slice of what the main agent has been doing within the current trace). Token-budgeted, recent-biased, structured for prompt injection.

```
get_agent_context(
  trace_id,            // current invocation's trace
  scope,               // 'this_trace' | 'recent_user_actions' | 'related_decisions'
  max_tokens,          // hard cap on returned context
  relevance_filter     // optional: filter to event_kinds relevant to next decision
) -> CompactContext
```

Internally it pulls relevant raw activity records, applies rolling summarization for older events, returns the most recent N events verbatim plus a summary tail, and hard-caps tokens.

**Human debug lens.** Used by the user to debug, audit, replay, analyze cost, and review case law. Complete, browseable, time-comprehensive. No summarization, no token cap.

```
get_trace(trace_id)                          -> full ordered list of activity in the trace
get_activity(filters, time_range, sort)      -> browseable list
get_replay(query_id)                         -> reconstructed view of "what the agent saw at each step"
get_cost_summary(grouping, time_range)       -> aggregate cost view
get_conflict_log(time_range)                 -> all conflicts flagged in window
get_schema_decisions(time_range)             -> case law browser
```

The `trace_id` is the spine that links both lenses: the agent uses it to ask "what did I just do," the human uses it to ask "show me everything from this query."

### Model declaration and selection

The deployment declares all available models in a single config:

```yaml
models:
  local_qwen_28b:
    provider: ollama
    endpoint: http://localhost:11434
    cost_per_1k_input: 0
    cost_per_1k_output: 0
  api_haiku:
    provider: anthropic
    model: claude-haiku-4-5-20251001
    endpoint: cloud
    cost_per_1k_input: 0.0008
    cost_per_1k_output: 0.004
  # ...additional models as needed
```

The deployment runs **a single primary agent** (the knowledge manager). Its spec declares a priority-ordered list of preferred models:

```yaml
name: knowledge_manager
purpose: Capture, retrieve, and synthesize records on the user's behalf
preferred_models:
  - local_qwen_28b      # free, decent (preferred)
  - api_haiku           # fallback if local unavailable
  - api_sonnet          # last resort for hard tasks
system_prompt: ...      # the agent's instructions (capture flow, query flow, grounding contract, schema-proposal handling, etc.)
tools:                  # tools the agent has access to
  - capture
  - retrieve
  - synthesize
  - verify_synthesis
  - propose_schema
  - resolve_conflict
  - spawn_subagent      # delegate work to a runtime sub-agent (see below)
  - ...
```

**Sub-agents are runtime, not declarative.** When the main agent wants to delegate work (e.g., extracting claims from a long YouTube transcript while it continues other work, or running a verification pass with isolated context), it calls `spawn_subagent(prompt, preferred_models)`. The runtime spawns a sub-agent with that prompt and model selection. The sub-agent runs to completion and returns its output. The main agent decides whether to spawn, what prompt to pass, and which model to prefer. There are no pre-declared sub-agent specs in the protocol.

Sub-agents inherit the trace_id of the spawning agent's invocation, so all activity records from a sub-agent are grouped under the same trace as the user's original query. Each spawn emits a `subagent_spawn_event`.

At each invocation (main agent OR sub-agent), the runtime walks the agent's `preferred_models` in order and selects the first model that is both AVAILABLE (online and reachable) and within the active cost cap budget for the current query. If no model survives both checks, the invocation returns a structured error (`no_eligible_model`) for next-action reasoning.

**Rejig on model change.** When a model is ADDED to deployment config, the system runs an optional LLM-assisted review: "should this new model be added to the main agent's preferred_models list?" The user reviews and accepts, edits, or rejects. When a model is REMOVED from config, mandatory rejig review fires if the main agent's preferred_models list includes it. The system suggests replacements; user reviews and approves before the removal commits. Removal is blocked until rejig is approved. Both events emit `model_rejig_event` records.

### Substrate decisions

- **[LOCKED 0.1]** Agent context filter mechanism: hybrid. Default agent retrieval uses the `agent_relevance` tag set at emit time for fast filtering (returns only records tagged `agent_relevance: high`). When the agent's tag-based retrieval seems insufficient, it can explicitly invoke a deeper LLM-mediated retrieval that **broadens the pool to all records (any agent_relevance value, including 'low' and 'none') and uses an LLM to filter for relevance to the current task at retrieval time.** This catches the case where an event tagged 'low' at emit time turns out to matter for a later task. The LLM-mediated path runs on a model from the calling agent's preferred_models list (typically the cheapest available). Decided 2026-04-24, scope clarified 2026-04-25.
- **[LOCKED 0.2]** Model selection and agent shape: deployment runs a single primary agent (the knowledge manager). The agent declares `preferred_models` (priority-ordered list); deployment declares all available models in config. Runtime picks first available + within-budget model from the agent's list. Sub-agents are spawned at runtime via `spawn_subagent(prompt, preferred_models)` when the main agent wants to delegate; ephemeral, no pre-declared specs, inherit trace_id of the spawning invocation. Rejig review fires on model add (optional, LLM-suggested) or model remove (mandatory; blocks removal until approved). Decided 2026-04-25, refined to single-agent + runtime sub-agents 2026-04-25.

---

## Primitive 1: Conflict-flagging typed memory

**Definition.** Memory records are typed. When two records about the same subject and same capability disagree on substance, the system flags the contradiction structurally instead of silently merging or letting one overwrite the other.

**Problem it solves.** Synthesis-first memory systems (compile a wiki, write a summary) smooth contradictions away in the name of readability. The smoothing IS the lie. Engineering says timeline is 12 weeks, sales promised 8, and the system that resolves it to "10 weeks" has destroyed the strategic signal. The same dynamic kills AI capability tracking: Anthropic's launch claims, an LMArena ranking, and a practitioner's actual experience often disagree, and that disagreement is the most useful information in the store.

**Mechanism.** Every memory record has:

```
{
  id,
  type,                    // from declared vocabulary (no subtype; each variant is its own type)
  subject,                 // entity the record is about
  capability,              // optional, for claim-style records
  body,                    // the claim or fact
  source,                  // URL, doc ref, or "user_observation"
  claimant,                // who is making this claim
  confidence,              // 0.0 to 1.0, defaults to source-class default
  effective_at,            // when the claim was made
  expires_at,              // optional
  provenance,              // declared | extracted | observed | synthesized
  tags: {                  // namespaced tags
    subjects: [],          // what the record is about (entities, tools, topics)
    freeform: []           // user-added free-text tags
    // additional namespaces added via Primitive 3 schema evolution
  },
  version,
  created_at, last_modified_at
}
```

When a new record is inserted, the system runs a conflict check against existing records matching `subject + capability` with overlapping `effective_at` windows. If the bodies disagree on substance (per a small LLM-judged comparison), both records are retained and a `conflict_link` is created between them. Neither record is modified.

Retrieval surfaces conflicts explicitly: any query that touches one side of a conflict returns the other side too.

**Worked example.** Anthropic's launch post: `Opus 4.7 is SOTA on SWE-bench at 81%`. Two days later, a Hacker News thread: `Re-ran SWE-bench, got 76% on the same set, suspect contamination in original eval.` Both stored. A query for "best model for SWE-bench" returns: `81% per Anthropic launch (declared) vs 76% per HN practitioner re-run (observed). Unresolved.`

### Synthesis records and the grounding contract

A synthesis answer (the system's response to a user query) is itself a typed memory record with `type: synthesis`. It is stored, queryable, conflict-checkable, and subject to the same envelope rules as any other record. The synthesis-record body MUST follow the **grounding contract**:

**Grounding contract (non-negotiable, applies to every synthesis output):**

1. Every factual claim in the answer must cite at least one source record by ID. No claim, no citation, no inclusion.
2. Citations are inline, not just at the end. The rendering style is Wikipedia/Perplexity-shaped: each claim carries `[r:ID]` references to the records that ground it.
3. When the retrieved records cannot support an answer to the user's question, the synthesis returns "I don't have data on this" explicitly. Speculation is forbidden.
4. A post-synthesis verification pass checks every claim against its citations. The pass can be implemented either as a tool the main agent calls (`verify_synthesis(synthesis_record_id)`) or as a sub-agent the main agent spawns with a verification-specific prompt — deployment chooses. Either way, ungrounded claims are removed before the answer is returned to the user, and the removal is logged.

**Synthesis record body schema:**

```
SynthesisBody {
  query,                   // the user's question
  answer_segments: [
    {
      text,                // a single grounded claim or phrase
      citations: [         // record IDs that ground this segment
        { record_id, weight }   // weight = how much this record influenced the segment
      ]
    }
  ],
  source_weights: {        // how source classes were weighted
    official: 0.3, leaderboard: 0.4, practitioner: 0.3, ...
  },
  exclusions: [            // records considered and dismissed
    { record_id, reason }
  ],
  dissents: [              // records that contradict the synthesis but didn't flip it
    { record_id, why_not_followed }
  ],
  ungrounded_segments: [   // user asked things the records can't support
    { question_part, reason }
  ],
  confidence: 0.0..1.0,
  verification_pass: {
    ran: bool,
    removed_claims: [...],
    verifier_model_tier
  }
}
```

The plan/edit-and-rerun mechanic implemented in TurnoCockpit's sandbox (where users edit assumption parameters and re-run synthesis) is documented as a **deployment-specific extension**, not a protocol-level requirement. KM-style deployments need synthesis trust; analytics-style deployments need synthesis trust plus edit-rerun. The protocol covers the first; the second is built on top.

**Synthesis record envelope mapping.** Because synthesis records share the standard envelope with all other typed records, they participate in conflict-flagging, retrieval, and schema evolution like anything else. The envelope fields fill as follows for a `synthesis` record:

| Field | Value |
|---|---|
| `type` | `'synthesis'` |
| `subject` | Extracted from the user's query (e.g., `'opus-4.7'`) by a small LLM step running on the synthesis agent's preferred_models, typically the cheapest available. Null if the query is too broad to scope. |
| `capability` | Extracted from the user's query (e.g., `'code_refactoring'`) by the same step. Null if not scoped. |
| `body` | The `SynthesisBody` structured object defined above. |
| `source` | `'self_synthesis'` (sentinel value indicating the deployment generated this record itself). |
| `claimant` | The synthesis agent's identifier (e.g., `'synthesis_agent_v0'`). |
| `confidence` | Computed per Decision 1.5-impl: `final_confidence = base_synthesis_confidence × (claims_kept / claims_attempted)`. |
| `effective_at` | Timestamp of synthesis production. |
| `expires_at` | Null. Synthesis doesn't expire structurally; it just becomes outdated as new records arrive on the same subject + capability. |
| `provenance` | `'synthesized'` (the new fourth enum value, as above). |
| `tags.subjects` | Inherits the extracted subject + capability if available; empty array otherwise. |
| `tags.freeform` | Empty by default; populated only if the user explicitly pins the synthesis with custom tags. |
| `temporal_semantics` | `'recency_wins'` (a newer synthesis on the same subject + capability supersedes older syntheses unless they explicitly disagree on substance, in which case the standard conflict-flagging fires). |

This mapping makes synthesis records first-class participants in the conflict-flagging primitive: two syntheses about "best model for code refactoring" produced a week apart get matched by `subject + capability` and the newer one supersedes silently unless they disagree on substance, in which case the conflict surfaces in the backlog (Decision 1.3). It also enables a useful user surface: "show me every synthesis I've made about model X" via tag-based browse.

**Decisions inline:**

- **[LOCKED 1.1]** Seed type vocabulary is NOT pre-defined for domain types. Ship **functional universal minimum** (the types the protocol needs to operate): `tool_policy`, `tool_policy_override`, `subject_alias`, `capability_alias`, `synthesis`, `schema_proposal`, `schema_decision`, `record` placeholder. Domain-specific types are LLM-drafted during interactive onboarding: LLM asks user for sources, use case, and 3-5 example records, then proposes a seed vocabulary (typically 3-7 types) that the user reviews and edits before commit. Onboarding is itself the first schema-decision session and seeds the case law. **No `subtype` field on the envelope; each variant is its own type.** Decided 2026-04-24, refined 2026-04-25 to drop `subtype` and list functional types explicitly.
- **[LOCKED 1.2]** Subject-matching semantics: hybrid (Option D). Exact-match on normalized strings at capture time (fast, predictable, free). In parallel, a background fast-tier LLM suggests up to 3 high-confidence (>=0.7) candidates the user might want to mark as comparable. Browse-time semantic match also surfaces up to 3 related-term candidates on user invocation. Anti-catchall constraints: bounded suggestions (max 3), confidence floor (0.7), aliases are narrow string-to-string mappings (not concept-to-concept), no transitive aliasing, aliases are typed memory records subject to Primitive 1 and 3, negative case law (3 dismissals stop re-suggesting), aliases are listable and reversible. Decided 2026-04-24.
- **[LOCKED 1.3]** Conflict resolution authority: human takes the final call (Option C). When a conflict is flagged, an LLM background process (deployment chooses whether to model this as a tool the main agent runs on a schedule, a spawned sub-agent on flagged events, or a separate scheduled job) produces a recommended resolution with reasoning and adds it to a **conflicts backlog** that accumulates asynchronously. The user reviews backlog items and accepts, edits, or rejects each. To accept any resolution (including verbatim acceptance of the LLM's suggestion), the user must write at least one sentence of their own rationale, which becomes the canonical resolution rationale on the record. The LLM's recommendation is also persisted as case law. Resolved conflicts stay visible with a "resolved" badge and rationale inline, never hidden. The backlog is a first-class surface in the human debug lens: queryable, sortable, with stale-item flagging. Decided 2026-04-25.
- **[LOCKED 1.4]** Time-window semantics: per-type (Option C). Each type definition carries a `temporal_semantics` field with one of three values: `recency_wins` (newer supersedes older; conflicts only fire if newer record explicitly references and disagrees with older), `always_flag` (any substance disagreement fires regardless of time gap), or `window_based` (type requires `effective_at` and `expires_at`; conflicts fire only on records with overlapping windows). The LLM proposes a value during type creation; user reviews and can change. Changing a locked type's temporal semantics goes through the Primitive 3 schema evolution gate. Decided 2026-04-25.
- **[LOCKED 1.5 (grounding contract)]** Synthesis records follow the grounding contract: every factual claim must cite at least one source record by ID; citations are inline (Wikipedia/Perplexity-shaped); "I don't have data on this" is the required answer when records cannot support a claim; a fast-tier post-synthesis verification pass removes ungrounded claims before the answer is returned. The `SynthesisBody` schema (above) is mandatory for all `synthesis`-type records. The TurnoCockpit-style edit-and-rerun mechanic is a deployment-specific extension, not protocol. Decided 2026-04-25. (Implementation details in Decision 1.5-impl below remain open.)
- **[LOCKED 1.5-impl]** Synthesis grounding implementation details: (a) Citation format: canonical synthesis form is structured `answer_segments` (text + citations objects); compact IDs `[r:abc123]` inline for agent-readable render; numbered-with-key (Wikipedia-style) for human-readable render. Both renders read from the same canonical structured object. (b) "I don't know" structure: same `synthesis` type with `answer_segments: []` and populated `ungrounded_segments: [{question_part, reason}]`. No separate `no_answer` type. (c) Verification removal: silent in inline prose for both renders (no inline markers). Verification removals propagate into `confidence` field, computed as `final_confidence = base_synthesis_confidence × (claims_kept / claims_attempted)`. Agent consumes `confidence` directly from structured form. Human render adds a metadata HEADER above the prose with confidence badge + "verification removed N of M attempted claims" message. Full removal data queryable in `verification_pass.removed_claims` for both consumers. Decided 2026-04-25.

---

## Primitive 2: Tool self-governance via memory-resident policies

**Definition.** Tools (fetchers, scrapers, API callers) read their own constraints from memory at runtime and return structured deny on block. There is no central enforcement layer. Policies are editable records, not code.

**Problem it solves.** Hardcoded tool limits mean every constraint change is a deploy. Central enforcement layers become brittle as the tool registry grows. Self-governance via memory mirrors how MCP-wrapped external tools naturally behave (the server is the runtime authority and returns structured errors), and lets the user edit policy without touching code.

**Mechanism.** A policy is a typed memory record (`type: 'tool_policy'`) with `tags.subjects = [tool_name]`. Every tool, on invocation, queries `get_memory(type='tool_policy', tags.subjects=[self.name])` and applies the returned policies. If any policy denies the call, the tool returns:

```
{
  status: 'denied',
  reason: <plain English from the policy>,
  policy_id: <ref>,
  retry_after: <optional>
}
```

The agent receives this as a normal tool response and decides next action (retry with different params, schedule for later, escalate to user, abandon).

**Worked example.** Policy record: `{ type: 'tool_policy', tags.subjects: ['x_com_scraper'], body: 'Do not fetch from X.com between 02:00-04:00 IST due to rate limit profile.' }`. Scraper tool reads this on invocation at 03:15 IST, denies the call, returns the structured response. The agent sees the deny, schedules the fetch for 04:01 IST, and reports back.

**Decisions inline:**

- **[LOCKED 2.1]** Policy conflict resolution: intersection semantics (Option C). Tool computes intersection of all applicable policies at runtime. If non-empty, executes within the intersection (which IS the most-restrictive interpretation, naturally). If empty, denies and emits a `policy_conflict_event` to the user backlog for resolution. Substance-level disagreements between policy records (Primitive 1 conflict_link on policy records) are flagged to the user backlog as informational but do NOT block execution if the runtime intersection is non-empty. Decided 2026-04-25.
- **[LOCKED 2.2]** Default-allow when no per-tool policies apply (Option D, simplified). Two universal policies ship with every deployment as memory records that apply to all tools (`tags.subjects: ['*']`): (1) a cost cap and (2) a rate limit. **Cost cap is set during onboarding** (LLM asks the user their per-query spend tolerance and creates the policy record with that value; no hardcoded default). Rate limit defaults to 60 invocations/min/user (editable as a memory record post-onboarding). Both policies are editable, conflict-flaggable, and schema-evolvable like any other memory record. No `side_effect_category` field on tool specs. Per-tool policies are added by the deployment owner as needed (e.g., TurnoCockpit registering `send_sms` time-of-day constraints during its setup). Decided 2026-04-25.
- **[LOCKED 2.4]** Cost cap enforcement (cumulative trace check, Option A). Before each model-inference call, the runtime computes a worst-case pre-call estimate locally as `(input_tokens × cost_per_input) + (max_output_tokens × cost_per_output)`, using the configured pricing from the deployment's `models:` block (Decision 0.2). The cost-cap policy (universal, set during onboarding per 2.2) compares `sum(cost_usd) for trace_id so far + estimate ≤ cap` and denies the call if it would exceed. The denial returns a structured `cost_cap_event` for next-action reasoning (the agent can retry with smaller `max_output_tokens`, request override per Decision 2.3, or escalate to user). Local models have configured pricing of 0, so the check always passes for fully local deployments. Decided 2026-04-25.
- **[LOCKED 2.3]** User runtime override (Option E1). Three layers: (1) default per-call override on user request with mandatory rationale, logged as memory record with single-call blast radius; (2) auto-detected elevation offer when user hits 5 per-call overrides on the same policy within 30 minutes (system surfaces a one-time offer to convert to a 30-minute time-bounded override scoped to that one policy, user explicitly accepts or declines); (3) optional preemptive elevation if user knows upfront they need a batch override. All overrides are temporary policy records with explicit `expires_at`, participating in the intersection semantics from 2.1. The 5-overrides-in-30-minutes counter is a memory query against `tool_policy_override` records sharing the same policy_id within the time window — no separate counter table, the count is auditable in the human debug lens like any other record query. Auto-detection threshold (5/30min) is the same for all policies in v0 and editable via meta-policy memory record. Per-policy thresholds deferred post-pilot. Decided 2026-04-25.

---

## Primitive 3: Friction-gated schema evolution with decision provenance

**Definition.** The system's typed structures (record types, tag vocabularies, tag namespaces, policy schemas, temporal_semantics values) can evolve without code deploys. Every change passes through a high-friction gate: cooldown, mandatory rationale, LLM-assisted case-law analysis, and a single named human authority. Every decision is logged with full provenance and feeds the case-law corpus for future proposals. (Note: model add/remove is NOT a schema evolution; it goes through the lighter-weight rejig review at the substrate level per Decision 0.2.)

**Problem it solves.** Closed schemas calcify and become fictions (the world has new claim shapes the old types can't hold). Open schemas sprawl into 47 types nobody can reason over. Most systems pick one and lose; the friction-gated middle path is the only sustainable answer. The mechanism also produces a compounding body of governance knowledge that gets sharper with every decision.

**Mechanism.**

1. **Trigger.** Any attempt to capture a record that doesn't fit existing types (or any agent proposing a new tag vocabulary, plan step, policy schema, etc.) creates a `schema_proposal` record.
2. **Proposal record.** Carries: proposed name, proposed schema (fields and constraints), mandatory rationale, the triggering record, system-surfaced similar existing types (embedding match), system-surfaced similar prior proposals (case law match).
3. **Cooldown.** 24-hour mandatory wait before review. Forces "do I really need this, or was that one record an exception?"
4. **Case-law analysis.** At review time, an LLM is given the proposal plus the last N relevant decisions as few-shot context. It produces a verdict recommendation with reasoning that cites the prior cases it relied on. The LLM never decides; it only advises.
5. **Authority decision.** A named human holding `schema_authority: true` reviews the LLM analysis and decides: **accept** (new type added, schema migration runs, retroactive records re-tagged via LLM where confidently mappable), **reject with reason** (logged for case law), or **merge into existing** (proposed type rejected, the triggering record mapped to an existing type with optional new subtype/tag).
6. **Decision logging.** Every decision becomes a `schema_decision` record carrying: rationale, LLM recommendation, whether the human followed it, decider, timestamp. This is the case law.
7. **Outcome audit.** Periodic review job (cadence per Decision 3.4: daily for first 7 days, weekly for first 30, monthly thereafter) audits past type-adds: did the new type get used heavily (good decision), barely (bad), or merged back later (definitely bad). Outcomes append to the `schema_decision` records, sharpening future LLM analysis.

**Schema.**

```
SchemaProposal {
  id,
  proposed_name,
  proposed_schema,            // fields, types, constraints
  proposal_kind,              // 'record_type' | 'tag_vocabulary' | 'tag_namespace' | 'policy_schema' | 'temporal_semantics_value'
  rationale,                  // mandatory, plain text
  triggering_record_id,       // the record that didn't fit
  similar_existing_types,     // system-surfaced
  similar_prior_proposals,    // system-surfaced from case law
  proposed_by,                // user_id or agent_id
  proposed_at,
  status,                     // 'cooling' | 'ready_for_review' | 'decided'
  cooldown_ends_at
}

SchemaDecision {
  id,
  proposal_id,
  llm_recommendation,         // {verdict, reasoning, cited_prior_decisions}
  human_verdict,              // 'accept' | 'reject' | 'merge'
  human_rationale,            // mandatory
  followed_llm,               // bool
  decided_by,                 // user_id with schema_authority
  decided_at,
  outcome_audit: [            // append-only, post-decision
    { audited_at, usage_count, merged_back_into, verdict_quality: 'good' | 'mediocre' | 'bad' | 'pending' }
    // 'pending' = audit ran but the decision had insufficient data (per Decision 3.4); will be re-evaluated in next audit
  ]
}
```

**Worked example.** I try to capture a record that says "Anthropic announced Computer Use as a beta capability for Sonnet 4.6." The existing types (`claim`, `benchmark_result`, `personal_observation`, `model_release`, `policy`) don't quite fit, this is a capability announcement that isn't a benchmark and isn't a release. The system creates a `schema_proposal` for type `capability_announcement` with my rationale ("capability launches are a recurring shape that deserves its own type because they have unique fields like 'beta status' and 'rollout timeline'"). 24-hour cooldown begins. Next morning the LLM reviews case law (zero similar prior proposals, this is the first), surfaces 3 existing records that could arguably fit `capability_announcement` if it existed, and recommends accept with reasoning. I review, agree, accept. The type is added; the 3 candidate records are LLM-mapped to the new type with my review.

Three months later the outcome audit runs. `capability_announcement` has 17 records, used heavily, no merges back. Decision verdict_quality: good. The successful pattern feeds future case-law analyses.

**Authority model.**

- `schema_authority: bool` is a declared user flag. It governs who can approve schema proposals through the friction-gated review process. Deployments may implement additional user flags (admin operations, conflict resolution authority, etc.) as deployment-specific concerns; the protocol does not define them.
- For solo / friends deployments, only the deployment owner holds `schema_authority`. Friends can propose, cannot decide.
- For team deployments, the deployment owner decides who holds `schema_authority` (typically a small set of trusted operators).
- Multiple holders are allowed; any one can decide. Decisions log who decided.
- The LLM never holds `schema_authority`. It only produces recommendations. This is a deliberate v0 stance and reviewed for relaxation post-pilot when the case law has 100+ decisions (see Decision 3.5 for the post-pilot relaxation flag).

### Onboarding as the first schema-decision session

The very first run of a new deployment is itself a schema-decision session, with one carve-out: the standard cooldown does not apply during onboarding. This is necessary because onboarding produces 3-7 type proposals in one synchronous sitting and a 24-hour-per-type cooldown would block the user for days before first capture.

**Onboarding flow:**

1. The system enters onboarding mode (a one-time, irreversible deployment-init flag).
2. The LLM prompts the user for: what they will capture, what sources they will use, and 3-5 example records they would want to store.
3. The LLM drafts a seed type vocabulary (typically 3-7 types) with rationale per type and a deferred list of types it considered but did not propose.
4. The user reviews, edits, drops, requests additions, and accepts.
5. Each accepted type becomes a `schema_decision` record (the first entries in case law).
6. The deployment exits onboarding mode permanently; future schema changes go through the standard cooldown gate.

**Anti-over-specification guardrails (apply only during onboarding):**

- **Empirical grounding (structural).** The LLM can only propose a type if at least 2 of the user's provided example records map to it. Single-example types go onto the deferred list, not into the seed.
- **System prompt bias toward minimalism.** The onboarding LLM is explicitly instructed to favor the smallest workable seed and, for each proposed type, justify why it cannot be expressed as a subtype or tag of another proposed type. The deferred list is surfaced to the user as part of the proposal so exclusion reasoning is visible.
- **Soft ceiling with friction-gated override.** The LLM cannot propose more than 8 types in one onboarding session by default. To accept 9+, the user must write a one-paragraph rationale per type beyond the 8th explaining why it cannot be deferred to the cooldown gate. The rationales are persisted in the `schema_decision` records and feed case law for future onboardings.

**Decisions inline:**

- **[LOCKED 3.1]** Authority model: solo authority for v0 (just me). Friends propose, cannot decide. Friends do not earn schema authority over time in v0; reserved for the deployment owner. Decided 2026-04-24.
- **[LOCKED 3.2]** Onboarding cooldown handling: onboarding-mode exception (Option A). Standard 24-hour cooldown applies post-onboarding. Onboarding mode is a one-time, irreversible deployment-init flag. Anti-over-specification handled via three layers: empirical grounding (2+ examples per type), system-prompt minimalism bias, soft ceiling at 8 types with friction-gated human override (per-type rationale for each beyond 8). Decided 2026-04-24.
- **[LOCKED 3.3]** Case-law window: last 20 schema decisions (chronological) plus any prior decisions surfaced via semantic match against the new proposal, capped at confidence threshold 0.6 (low-confidence matches not surfaced). LLM sees this combined context as few-shot when producing its verdict recommendation. Adaptive reranking deferred to post-pilot if case law exceeds 100+ decisions. Decided 2026-04-25.
- **[LOCKED 3.4]** Outcome audit cadence: daily for first 7 days, weekly for first 30 days, monthly thereafter. Schedule editable via meta-policy memory record. Audit job produces (1) a digest of recent decisions, usage patterns, and pending proposals on every run, plus (2) verdict assignment (`good` / `mediocre` / `bad`) for decisions where the LLM has confidence based on usage data. Decisions with insufficient data are flagged "verdict pending" and re-evaluated next audit. Verdicts feed the case-law corpus per Decision 3.3. Decided 2026-04-25.
- **[LOCKED 3.5]** LLM-decides-alone criterion (Option B, hard flag): post-pilot, when case law reaches 100+ decisions AND >90% human-followed-LLM-recommendation rate, the deployment owner can flip a hard on/off flag in admin settings. ON = LLM auto-decides ALL schema proposals (record types, tags, policies, temporal_semantics, everything). OFF = human-in-the-loop on every proposal. No partial mode, no exclusion list in v0. Auto-decisions are still logged with the same `schema_decision` schema; `decided_by` is set to the LLM model identifier. Owner can flip the flag off at any time if quality degrades. Per-kind exclusions or other refinements deferred to post-pilot if needed. Decided 2026-04-25.
- **[LOCKED 3.6]** Post-onboarding cooldown duration: flat 24 hours for all schema proposal kinds. Configurable via meta-policy memory record. Per-kind durations (blast-radius scaling) deferred to post-pilot if real usage shows the flat duration is wrong for some kinds. Decided 2026-04-25.

**Out of scope:** *Forking inheritance.* The protocol does not define cross-deployment relationships. Code distribution is a git concern (the spec + reference implementation lives in a public git repo; anyone clones to start their own deployment). Data-level sharing between deployments, if needed, happens via standard memory-record export and import through the existing schema_proposal mechanism. Each deployment is fully independent.

---

## How the three compose (and what the substrate does for them)

Each primitive on its own is incomplete. Together they form a closed loop:

- **Conflict-flagging typed memory** (Primitive 1) gives you trustable storage AND trustable synthesis (the grounding contract on synthesis records means synthesis cites and stays inside the captured records).
- **Tool self-governance** (Primitive 2) gives you safe action.
- **Friction-gated schema evolution** (Primitive 3) gives you a system that stays trustable as the world changes shape.

A system missing any one leaks the others. Without conflict-flagging, contradictions are silently smoothed and synthesis becomes confident misinformation. Without tool self-governance, policies are hardcoded and brittle and there is no audit trail of what was denied or why. Without schema evolution, the system calcifies as soon as reality stops fitting the original types. The three are a set, not a menu.

The Foundational Substrate underneath them does the cross-cutting work: it carries the `trace_id` that links every action in a query, it emits typed activity records that feed both the agent context lens and the human debug lens, it declares what models the deployment has available with priority-ordered preferences per agent, and it makes the system observable to itself (via the agent lens) and to the user (via the human lens) using the same memory primitives that observe the world. Without the substrate, each of the three primitives would still function but none would be debuggable, replayable, or auditable.

**Cost optimization** (the tier-sticky delegation insight from earlier drafts, where heavy parents delegate cheap work to lightweight sub-agents) is now a deployment-level concern handled via per-agent `preferred_models` priority lists at the substrate. It is not a protocol primitive. *"It works" precedes "it works cost-effectively"*: the protocol defines what makes the system trustable; cost is a refinement built on top.

---

## Decisions to lock (priority order)

The decisions inline above are summarized here in the order they need to be answered. Earlier decisions gate later ones.

| # | Decision | Why it's first |
|---|---|---|
| 0.1 | ✓ LOCKED. Hybrid agent context filter (tag at emit + LLM-mediated escape hatch). | (Locked 2026-04-24) |
| 0.2 | ✓ LOCKED. Model selection: agents declare priority-ordered `preferred_models`; runtime picks first available + within-budget. Rejig review on model add (optional) / remove (mandatory, blocks until approved). | (Locked 2026-04-25) |
| 1.1 | ✓ LOCKED. No pre-defined seed; LLM drafts during onboarding from user examples. Functional universal minimum: 8 types listed. | (Locked 2026-04-24) |
| 1.2 | ✓ LOCKED. Hybrid: exact match at capture + bounded LLM-suggested aliases (max 3, conf >=0.7, narrow, non-transitive, reversible). | (Locked 2026-04-24) |
| 1.3 | ✓ LOCKED. LLM-built backlog of suggested resolutions; human takes final call with mandatory ≥1 sentence rationale. Resolved conflicts stay visible. | (Locked 2026-04-25) |
| 1.4 | ✓ LOCKED. Per-type `temporal_semantics`: `recency_wins` / `always_flag` / `window_based`. Declared at type creation, changeable via schema evolution gate. | (Locked 2026-04-25) |
| 1.5 (contract) | ✓ LOCKED. Synthesis grounding contract: every claim cites a source, no ungrounded claims, "I don't know" required when records can't support an answer, post-synthesis verification removes ungrounded claims. | (Locked 2026-04-25) |
| 1.5 (impl) | ✓ LOCKED. Compact IDs for agent render, numbered-with-key for human render. Empty `answer_segments` + populated `ungrounded_segments` for "I don't know." Silent removal in prose; verification feeds `confidence`; human render shows metadata header with confidence + removal count. | (Locked 2026-04-25) |
| 2.1 | ✓ LOCKED. Intersection semantics: execute within intersection if non-empty; deny if empty; substance disagreements flagged but non-blocking. | (Locked 2026-04-25) |
| 2.2 | ✓ LOCKED. Default-allow + 2 universal policies (cost cap set in onboarding; rate limit defaults to 60/min). | (Locked 2026-04-25) |
| 2.3 | ✓ LOCKED. Per-call override default + auto-elevation offer at 5/30min + preemptive opt-in. | (Locked 2026-04-25) |
| 2.4 | ✓ LOCKED. Cost cap enforced via cumulative trace check; pre-call worst-case estimate from configured pricing. | (Locked 2026-04-25) |
| 3.1 | ✓ LOCKED. Solo authority for v0; friends propose, cannot decide. | (Locked 2026-04-24) |
| 3.2 | ✓ LOCKED. Onboarding-mode exception with empirical grounding + minimalism bias + soft ceiling at 8 (friction-gated override). | (Locked 2026-04-24) |
| 3.3 | ✓ LOCKED. Last 20 + semantic-matched priors at confidence ≥0.6. | (Locked 2026-04-25) |
| 3.4 | ✓ LOCKED. Daily first 7 days, weekly first 30, monthly thereafter. Digest always; verdicts when data permits. | (Locked 2026-04-25) |
| 3.5 | ✓ LOCKED. Hard on/off flag in admin settings. Eligible post-pilot when case law ≥100 decisions and >90% follow rate. ON = LLM auto-decides everything; OFF = full human-in-the-loop. | (Locked 2026-04-25) |
| 3.6 | ✓ LOCKED. Flat 24h for all proposal kinds. Per-kind scaling deferred to post-pilot. | (Locked 2026-04-25) |

**Removed during spec evolution (kept for historical clarity):**
- *Old Primitive 2 (Plan-as-the-assumptions-register):* removed 2026-04-25, reduced to grounding contract on synthesis records (Decision 1.5). Full plan/edit/rerun is a deployment extension.
- *Old Primitive 3 (Tier-sticky sub-agent delegation):* removed 2026-04-25, reduced to model selection at substrate level (Decision 0.2). Cost-economics framing is a deployment extension.
- *Old 4.5 (Forking inheritance):* removed 2026-04-25, out of scope. Cross-deployment relationships are a git/tooling concern, not protocol.

Seventeen decisions locked across 0.1, 0.2, 1.1, 1.2, 1.3, 1.4, 1.5-contract, 1.5-impl, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6. **All decisions made between 2026-04-24 and 2026-04-25. Spec v0 is fully decided.**

**Substrate, Primitive 1, Primitive 2, and Primitive 3 are fully locked.**
