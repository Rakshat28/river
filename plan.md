# Riverline Voice Finance Assistant — Implementation Plan

**Stack:** Next.js (frontend) + Pipecat (Python voice agent) + Daily (WebRTC transport)

> **Start here if time is short:** the single highest-risk, highest-leverage part of this system is not the voice plumbing — it's the layer that turns live, corrected, sometimes-conflicting speech into structured, trustworthy financial facts. See **Section 13 (Deep Dive)** at the end of this document before writing any tool-calling code. Everything else in this plan is comparatively low-risk plumbing by comparison.

---

## 0. Framing: how we improve on the reference demo

The brief explicitly says not to copy the video. Three concrete improvements to build in, each cheap:

1. **Explicit uncertainty labeling.** Every number the agent holds is tagged `confirmed` or `estimated`. Cards visually distinguish these (e.g. estimated values shown with a dashed border / "you said ~₹15k, unconfirmed"). This directly serves the "avoid presenting guesses as facts" requirement and is a good live-demo talking point.
2. **Explicit unsolvable-case handling.** If the 30-day plan cannot be balanced even after cutting all optional expenses, the agent says so plainly and shows *which* obligations will be missed and by how much — instead of quietly producing a plan that doesn't actually work. Most naive builds skip this.
3. **A visible calculation trail.** The final plan card shows a day-by-day ledger (or at least the arithmetic), not just a conclusion. This is what makes the calculations "visible and testable," which is explicitly graded.

Keep these three in your back pocket for the live session — they're genuine product decisions, not generated flourishes.

---

## 1. High-Level Architecture

```
┌─────────────────────┐        WebRTC audio         ┌──────────────────────────┐
│   Next.js Frontend   │ ───────────────────────────▶│   Daily Room             │
│  (browser, mic/spkr) │◀─────────────────────────── │   (transport only)       │
└──────────┬───────────┘        app-messages          └────────────┬─────────────┘
           │ REST (session create,                                 │ joins as
           │ state snapshot fallback)                               │ a participant
           ▼                                                        ▼
┌─────────────────────┐                              ┌──────────────────────────┐
│  Next.js API routes  │──── POST /api/session ─────▶│  Agent Backend (FastAPI)│
│  (thin proxy)        │                              │  - creates Daily room    │
└──────────────────────┘                              │  - spawns Pipecat bot    │
                                                       │  - holds SessionState    │
                                                       └────────────┬─────────────┘
                                                                    │
                                                       ┌────────────▼─────────────┐
                                                       │ Pipecat Pipeline          │
                                                       │ Daily in → VAD → STT      │
                                                       │ → context → LLM(tools)   │
                                                       │ → TTS → Daily out         │
                                                       └────────────┬─────────────┘
                                                                    │ tool calls
                                                       ┌────────────▼─────────────┐
                                                       │ Deterministic Finance     │
                                                       │ Engine (plain Python,     │
                                                       │ no LLM math)              │
                                                       └───────────────────────────┘
```

Key architectural commitment: **the LLM never does arithmetic.** It only extracts structured facts via tool calls and narrates results that the Python engine computed. This is the single most important decision for satisfying "calculations must be visible and testable" and "must not invent numbers" — say this explicitly if asked in the live session.

---

## 2. Design Decisions — Options, Pros/Cons, Recommendation

### 2.1 Voice pipeline shape: cascaded (STT→LLM→TTS) vs. speech-to-speech realtime

| | Cascaded (Pipecat default) | Realtime speech-to-speech (e.g. OpenAI Realtime) |
|---|---|---|
| Pros | Full text intermediate → reliable function calling, easy to log/test/replay, vendor-swappable, matches the assignment's "use Pipecat" instruction | Lower end-to-end latency, more natural interruption/prosody handling out of the box |
| Cons | Extra latency from 3 hops; must handle interruption/turn-taking yourself (Pipecat gives you VAD + interruption primitives) | Function-calling reliability and text auditability are weaker; harder to unit test; you lose the clean transcript needed for the eval track |

**Decision: cascaded.** The grading criteria (testable calculations, no invented numbers, decision journal defending methodology) reward auditability over raw latency. Pipecat is built around this pattern anyway.

### 2.2 STT vendor

| | Deepgram (nova-2/3) | AssemblyAI | Whisper (self-hosted/streaming) |
|---|---|---|---|
| Pros | Mature Pipecat connector, low streaming latency, keyword-boosting for numbers/financial terms | Good accuracy, decent Pipecat support | Free/open, no per-minute cost |
| Cons | Per-minute cost | Slightly less mature Pipecat integration at time of writing | Not truly streaming-friendly; chunk-based, adds latency; more infra work |

**Decision: Deepgram.** Fastest path to a working real-time loop; add a `keywords`/boost list for currency amounts and terms like "EMI," "credit card," "minimum due."

### 2.3 TTS vendor

| | Cartesia (Sonic) | ElevenLabs | OpenAI TTS |
|---|---|---|---|
| Pros | Very low latency streaming, native Pipecat support, good for real-time feel | Best perceived naturalness/emotion | Cheap, one fewer vendor if already using OpenAI for LLM, decent quality |
| Cons | Slightly less expressive than ElevenLabs | Higher latency, more expensive | Middling latency, less control over voice |

**Decision: Cartesia for latency**, with OpenAI TTS as a fallback if you want to cut a vendor/API-key out of the 2-day setup. Document whichever you pick and why in the journal — this is exactly the kind of trade-off they want to hear defended live.

### 2.4 LLM

- Arithmetic is never delegated to the LLM (see engine section), so model choice mainly affects conversational quality and tool-calling reliability, not correctness.
- Any current strong tool-calling model works (GPT-4o-class or Claude Sonnet-class). Pick whichever you have reliable API access to; Pipecat supports both via its LLM service adapters.
- **Recommendation:** whichever model you're most fluent debugging under time pressure — familiarity beats marginal quality differences here.

### 2.5 Card delivery transport: Daily app-messages vs. separate WebSocket vs. polling

| | Daily app-message (data channel over the existing WebRTC connection) | Dedicated WebSocket server | REST polling |
|---|---|---|---|
| Pros | No extra connection/infra, low latency, reuses auth already established by joining the room | Decoupled from Daily, easier to reason about independently, can replay history server-side | Simplest possible code |
| Cons | Message-size limits, no built-in replay if the client reconnects mid-call, ties your UI update path to Daily's SDK | Another connection to stand up, auth, and debug inside a 2-day budget | Not real-time, cards visibly lag — fails the "cards remain consistent during conversation" bar |

**Decision:** Daily app-messages for the live push, **plus** a plain `GET /api/state/:room` REST endpoint that returns a full state snapshot. The frontend calls this once on join and on any detected reconnect, so you get real-time updates without building a second live channel, and you still have a clean recovery path.

### 2.6 State storage: in-memory vs. Redis vs. DB

| | In-memory dict keyed by room id | Redis | Full DB |
|---|---|---|---|
| Pros | Zero setup, fastest to build, sufficient for a single demo session | Restart-safe, supports multiple backend instances | Persistence, query-ability |
| Cons | Lost on process restart, no horizontal scaling | Extra Docker service and plumbing for a benefit you don't need in 2 days | Way more time than this scope needs |

**Decision: in-memory.** State scoped for the lifetime of one call. Explicitly list this as a known limitation in the "what would you build next" section — that's the honest, gradeable answer, not a weakness to hide.

### 2.7 Bot process model

| | asyncio task per room inside one FastAPI process | Subprocess per session | Container per session |
|---|---|---|---|
| Pros | Simplest single service, fast startup, matches Pipecat's own quickstart pattern | Crash isolation between sessions | Full isolation |
| Cons | A crash in one session's task can be sloppy to isolate if you're not careful with exception handling | More process lifecycle code to write and clean up | Way too heavy for a 2-day, single-demo-session scope |

**Decision:** asyncio task per room in one process. Wrap the pipeline run in try/except so one bad session doesn't take down the FastAPI process.

### 2.8 Conversation control: strict script vs. fully open-ended vs. hybrid

| | Fixed questionnaire (FSM) | Fully open-ended LLM | Hybrid: soft slot-tracking + hard guard on finalize |
|---|---|---|---|
| Pros | Guarantees required fields collected, easy to test | Natural, adaptive — matches "avoid fixed questionnaire" | Natural conversation *and* guaranteed data completeness |
| Cons | Explicitly against the brief; feels scripted; awkward with corrections | Risk of skipping required info or finalizing too early | More prompt + code engineering; must test that the guard actually fires |

**Decision: hybrid.** Track a `missing_fields` list server-side (code-computed, not LLM-remembered). Inject it into the LLM's context each turn so it knows what to still ask about, but the LLM decides phrasing/order. Critically: the `finalize_plan` tool call is **rejected in code** if minimum required fields are missing, returning a tool-error message the LLM must react to ("I still need X before I can finalize"). Never rely on the LLM to remember this on its own — verify it with a test.

### 2.9 Calculation engine: LLM math vs. deterministic code

**Deterministic Python only.** Non-negotiable given the brief says calculations must be "visible and testable" and the agent "must not invent numbers." LLM-computed arithmetic is not reproducible or unit-testable, and is a very likely place for hallucination. All money math is a pure function: `SessionState → PlanResult`, unit-tested independently of any LLM call.

### 2.10 Frontend structure

- **Next.js App Router**, not Pages Router — cleaner route handlers for the thin backend-proxy endpoints (`/api/session`, `/api/state/[room]`), and you don't need most of what Pages Router offers here.
- **Daily React SDK (`@daily-co/daily-react`)** over raw `daily-js` — hooks (`useDaily`, `useParticipantIds`, `useAppMessage`) save meaningful boilerplate versus manually managing event listeners; worth the small extra dependency given the time budget.
- **State management:** React context + `useReducer` is enough for card state; don't reach for Redux/Zustand for a single-session demo — that's scope you don't need to build or explain live.

### 2.11 Optional depth track: A vs. B

| | Track A (conversational intelligence) | Track B (evaluation & regression testing) |
|---|---|---|
| Pros | Directly visible in the demo video; good if voice UX is your strength | Produces concrete artifacts (test suite, before/after evidence) that are easy to defend live and don't depend on live voice quality on demo day |
| Cons | Hard to prove rigorously — mostly "look how good this sounds," harder to show a controlled before/after | Less flashy in a video |

**Recommendation:** do the required core extremely well first. If time remains, do a **lightweight Track B**: a text-only harness that feeds scripted user turns directly into the LLM+tools pipeline (bypassing STT/TTS entirely) so you can assert on tool-call outputs and final plan correctness without needing live audio for every test run. This is also your safety net if voice API latency is flaky on demo day — you'll have already validated the logic independently.

---

## 3. Data Model

```python
class Entry(BaseModel):
    id: str
    name: str
    amount: float
    date: str            # ISO date within the 30-day window, or recurrence rule
    confidence: Literal["confirmed", "estimated"]

class Debt(Entry):
    kind: Literal["loan", "credit_card"]
    min_payment: float
    balance: float | None = None
    interest_rate: float | None = None

class Conflict(BaseModel):
    field: str
    old_value: float
    new_value: float
    resolved: bool = False

class SessionState(BaseModel):
    income: list[Entry] = []
    essential_expenses: list[Entry] = []
    optional_expenses: list[Entry] = []
    debts: list[Debt] = []
    conflicts: list[Conflict] = []
    plan: PlanResult | None = None
    updated_at: datetime
```

`missing_fields` and `shortfall/surplus` are **derived**, never stored directly — compute them from the above every time state changes, so cards can never drift out of sync with each other.

---

## 4. LLM Tool Schema

Keep the tool surface small and explicit — this is also what you'll be asked to walk through live.

- `add_income(name, amount, date, confidence)`
- `add_expense(category: "essential"|"optional", name, amount, date, confidence)`
- `add_debt(name, kind, min_payment, date, balance?, interest_rate?, confidence)`
- `update_entry(id, field, new_value)` — triggers conflict detection if overwriting a `confirmed` value with a materially different one
- `resolve_conflict(field, chosen_value)`
- `finalize_plan()` — **guarded in code**: returns a tool error listing missing fields if the minimum required set isn't present yet; otherwise calls the deterministic engine and stores the result
- `confirm_user_understood(bool)` — set only after the agent has explicitly checked comprehension, per the brief's "confirm the user understands the plan" requirement

Conflict detection rule of thumb: if a new value differs from a `confirmed` value by more than ~15%, don't silently overwrite — call `resolve_conflict`-eligible state and have the agent ask the user which is right.

---

## 5. Deterministic Finance Engine

Pseudocode:

```
function build_plan(state, today):
    ledger = []
    balance = 0
    for day in 1..30:
        date = today + day
        balance += sum(income due on date)
        for debt in sorted(debts, priority = essential > secured_loan > credit_card, then by date):
            if debt due on date:
                balance -= debt.min_payment
        for expense in essential_expenses due on date:
            balance -= expense.amount
        ledger.append((date, balance))

    if min(balance in ledger) >= 0:
        return PlanResult(status="surplus", ledger=ledger, cuts=[])

    # try cutting optional expenses, cheapest-impact-first or user-priority-first
    for cut_set in candidate_cuts(optional_expenses):
        recompute ledger with cuts applied
        if solved: return PlanResult(status="solved_with_cuts", ledger, cuts=cut_set)

    return PlanResult(status="unsolvable", ledger=worst_case_ledger,
                       shortfall=min(balance), missed_obligations=[...])
```

Priority ordering rationale to state explicitly in the journal and be ready to defend live: essential expenses and secured debts (risk of losing an asset / larger penalty) are prioritized over unsecured credit-card minimums, which is a genuine judgment call, not an obvious default — good material for the live defense.

Unit test cases to write (minimum set):
- Clean surplus, no action needed
- Exact break-even
- Shortfall resolved entirely by optional-expense cuts
- Shortfall that survives all possible cuts → `unsolvable` with correct missed-obligation list
- Missing income date → engine must refuse to run (caught by the `finalize_plan` guard, not the engine itself)
- Conflicting duplicate entries → resolved before reaching the engine

---

## 6. Card Types

| Card | Purpose | Updates when |
|---|---|---|
| Income | Sources + total, confidence-tagged | any `add_income`/`update_entry` on income |
| Essential Expenses | Rent/utilities/etc with due dates | any expense mutation |
| Debts | Loans + cards, min payments, due dates | any debt mutation |
| Missing Information | Live list of what's still needed | recomputed after every mutation |
| Cash Position | Running "money available" number | any mutation affecting balance |
| Shortfall/Surplus Summary | The headline number, color-coded | any mutation |
| Proposed Actions | Suggested cuts (only from user-provided optional expenses — never invented) | after `finalize_plan` |
| Final 30-Day Plan | Day-by-day ledger + explanation, or explicit "not solvable" | after `finalize_plan` |

All cards are pure renders of `SessionState` + its derived fields — never independently stateful on the frontend beyond what the backend snapshot says. This is what guarantees "if the user corrects an amount, every affected card updates."

---

## 7. Repo Structure

```
/frontend            # Next.js app (App Router)
  /app
  /components/cards
  /lib/daily-client.ts
/agent                # Python
  /app
    main.py           # FastAPI: /api/session, /api/state/{room}
    bot.py            # Pipecat pipeline wiring
    tools.py          # tool-call implementations, mutate SessionState
    engine.py         # deterministic finance engine
    state.py          # SessionState + derived-field computation
  /tests
    test_engine.py
    test_tools.py
    test_conversation_harness.py   # text-only scripted scenarios
docker-compose.yml
.env.example
README.md
DECISION_JOURNAL.md  # written by hand, not generated
```

---

## 8. Docker Compose & Environment

Two services: `web` (Next.js) and `agent` (FastAPI + Pipecat). No Redis/DB for MVP (documented limitation).

`docker compose up --build` must bring up both with one command — spawn the Pipecat bot as an asyncio task inside the `agent` process when a session is created, not as a separate container, to keep this true.

`.env.example`:
```
DAILY_API_KEY=
DAILY_DOMAIN=
LLM_PROVIDER=openai   # or anthropic
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEEPGRAM_API_KEY=
TTS_PROVIDER=cartesia # or openai
CARTESIA_API_KEY=
NEXT_PUBLIC_AGENT_URL=http://localhost:8000
```

README must state, per the brief: what each var does, which are required vs. optional (e.g. only one of OPENAI/ANTHROPIC key needed depending on `LLM_PROVIDER`), the exact `docker compose up --build` command, and the exact local URL to open.

Trade-off to note explicitly: running Next.js in dev mode inside the container (`npm run dev`) is faster to get working than a production build within a 2-day window, at the cost of not being production-grade — an intentional, defensible scope call for this assignment.

---

## 9. Two-Day Timeline

**Day 1 — core pipeline working end to end**
- 0–1h: repo scaffold, docker-compose skeleton, `.env.example`
- 1–3h: Daily room-creation API + minimal Next.js join screen (audio only, no agent yet) — verify raw connectivity
- 3–6h: Pipecat pipeline: Daily transport + STT + LLM-echo + TTS, verify round-trip voice loop and latency
- 6–9h: Define `SessionState` + tool schema; wire real tool calls that mutate state; confirm via logs (no cards yet)
- 9–11h: App-message broadcasting of state → minimal JSON-dump card on frontend, confirm the full loop
- 11–13h: System-prompt tuning for natural, non-scripted questioning and memory of prior answers

**Day 2 — engine, real cards, correction handling, packaging**
- 0–3h: Deterministic finance engine + unit tests
- 3–5h: Wire `finalize_plan` end to end, guarded on missing fields
- 5–8h: Real card UI components, styled, wired to state
- 8–10h: Conflict/correction flow: verbally contradict an earlier number, verify detection + card updates
- 10–12h: Lightweight Track B harness: scripted text scenarios, at least one documented failure → fix → re-test
- 12–14h: README, env docs, clean `docker compose up --build` run from scratch
- 14–16h: Demo video, "what works / what doesn't / what's next / where AI helped or failed" writeup, finalize decision journal entries

Leave real buffer — this list is intentionally tight, not padded.

---

## 10. Explicit Guardrails Mapped to Requirements

| Requirement | How the design satisfies it |
|---|---|
| Don't invent numbers | Deterministic engine only; every entry tagged `confirmed`/`estimated`; LLM never states a final number the engine didn't produce |
| Don't promise approval / settlement offers | No tool exists for these actions; system prompt explicitly forbids them; nothing in the tool surface could produce one |
| Don't claim completed actions | Agent only reports plan contents, never "I've paid X" — no such tool exists |
| Handle corrections | `update_entry` + conflict detection, single source of truth state, all cards derived from it |
| Ask useful, non-scripted questions | Soft slot-tracking injected into context, LLM controls phrasing/order |
| Calculations visible/testable | Pure Python engine, unit tested independently of the LLM |

---

## 11. Explicit Cut Scope (say this plainly in your submission, don't hide it)

Not building, and why: persistence across restarts (Redis/DB — no benefit for a single demo session in 2 days), multi-user auth, non-English support (out of scope per brief), production-grade Next.js build, robust reconnect/resume mid-call, horizontal scaling of the bot manager. Each of these is a legitimate "what I'd build next" answer.

---

## 12. Decision Journal — reminder

This plan is *not* your decision journal, and you cannot use it (or any AI output) as your journal — the brief disqualifies AI-written or AI-rewritten journals. Use this plan only as your working reference; write your own entries by hand as you actually make and change decisions (timestamps, what you tried, what broke, what changed your mind, AI suggestions you rejected). A useful discipline: keep a plain text file open the whole time and jot a line every time you deviate from this plan or hit something unexpected — that's the real content they're grading.

---

## 13. DEEP DIVE — The State Extraction & Consistency Layer

*(This is the most crucial part of the entire project. Read this before writing tool-calling code.)*

### 13.0 Why this is "the" crucial part, and not the engine or the voice pipeline

Three candidate pieces could each claim to be "the hard part": the real-time voice pipeline (Daily + Pipecat plumbing), the deterministic finance engine, and the layer in between that turns conversation into structured facts. Ranking them by risk and by how much of the grading rubric they touch:

| Candidate | Genuine difficulty | Why it's *not* the crux |
|---|---|---|
| Voice pipeline (STT/LLM/TTS/Daily wiring) | Mostly integration work | Pipecat + Daily solve the hard real-time-audio problems for you; this is following documentation and debugging latency, not a design problem with many defensible branches |
| Finance engine | Requires care, but is a closed problem | Once the input schema is fixed, "simulate 30 days, prioritize payments, try cuts" is mechanical and fully deterministic — hard to get subtly wrong if you write the unit tests first |
| **State extraction & consistency layer** | High | This is where *every* qualitative requirement in the brief actually lives: "ask the right questions," "remember information already provided," "ask for clarification when information conflicts," "allow corrections," "avoid presenting guesses as facts," "cards remain consistent." None of these are solved by picking a library — each is a genuine design decision with real trade-offs, and getting it wrong silently corrupts the engine's input (so a perfect engine still produces a wrong plan) |

This layer is also exactly what a live interrogator will poke at, because it's where judgment (not code-generation) lives: *"what happens if the user interrupts mid-correction," "how do you know 'my other loan' means the one from three turns ago," "how do you stop the agent from asking forever."* Being able to answer these with a reasoned trade-off, not a shrug, is the actual point of the assignment per its own framing.

### 13.1 The core problem, stated precisely

You have a continuous, interruptible, real-time stream of natural language. You need to maintain a single canonical structured object (`SessionState`) such that, at every point in time:

1. Every fact in the state is traceable to something the user actually said (no invention).
2. Facts have a confidence level, and low-confidence facts are visibly distinct.
3. When the user restates a fact differently, the system can tell whether that's a **new** fact, a **correction** of an existing one, or a **duplicate** mention of the same thing — and this distinction must be made correctly almost all the time, because getting it wrong either silently loses information or silently creates phantom duplicate obligations.
4. The state is always in a form the deterministic engine can consume without any further interpretation.
5. Every mutation is immediately reflected in whatever the frontend cards show, with no drift between cards.

That's five different correctness properties riding on one design. Below are the real design axes, in the order you'll actually need to decide them.

### 13.2 Design Axis 0 — How does the LLM communicate a change in facts at all?

This is the most foundational choice; everything else (entity resolution, conflict detection, validation) is downstream of it.

| Approach | How it works | Pros | Cons |
|---|---|---|---|
| **A. Full state overwrite per turn** | LLM is asked to output the *entire* updated `SessionState` as JSON after every user turn | Conceptually simple; one payload to validate | **Catastrophic forgetting risk**: if the model doesn't re-mention a fact it already knows, it may drop it from the new JSON; large payload every turn hurts latency; a single malformed field fails the whole turn; no natural hook for per-field validation or audit history |
| **B. LLM-authored diff/patch (JSON Patch style)** | LLM emits `[{op: "replace", path: "/income/0/amount", value: 18000}]`-style patches | Explicit, auditable, small payloads | Novel pattern for function-calling APIs — less battle-tested than plain tool calls; path-syntax errors are a new failure class you'd be debugging live; higher implementation risk in a 2-day window for uncertain benefit over C |
| **C. Scoped tool calls (`add_income`, `add_expense`, `add_debt`, `update_entry`, ...)** | Standard function-calling; LLM calls small, purpose-specific tools; backend mutates canonical state | Each tool has a narrow, validate-able schema; maps directly onto standard LLM function-calling (best supported, most predictable); naturally supports partial updates without forgetting other fields (backend, not the LLM, owns the full state); easy to unit test each tool handler in isolation | More tools for the model to choose between (mitigated by keeping the tool count small — 6–8); still need a separate mechanism for the LLM to *refer back* to an existing entry (see Axis 1) |
| **D. Hybrid: scoped tools + periodic full-state confirmation** | Mostly C, but the agent periodically reads back a full summary to the user ("so far I have: income ₹X on the 3rd, rent ₹Y...") and the user's response can trigger bulk corrections | Combines C's safety with a built-in error-correction opportunity that also satisfies the "confirm understanding" brief requirement | Adds conversational overhead; only do this near the end of intake, not every turn |

**Recommendation: C, with D's readback used once before finalizing.** Approach A is the one most teams reach for first because it "feels" simple, and it's also the one most likely to silently lose data mid-conversation — flag this explicitly if you ever prototype it and reject it, that rejection itself is good decision-journal material.

### 13.3 Design Axis 1 — Entity resolution: how does "fix my rent, actually it's 18k" find the right existing entry?

This is the single hardest sub-problem in the whole system, because it's a coreference problem, not a data-validation problem.

| Approach | How it works | Pros | Cons |
|---|---|---|---|
| **A. Fuzzy string matching in code** | On every `add_*` call, compare the new entry's name against existing entries (e.g. normalized Levenshtein/embedding similarity); if similarity > threshold, treat as an update instead of a new entry | Deterministic, testable, no dependency on LLM judgment | Brittle: "rent" vs "house rent" vs "monthly rent" have to be tuned by hand; thresholds are guesswork; will both over-merge (two genuinely different debts with similar names) and under-merge (same debt described differently) in ways that are hard to predict |
| **B. LLM-mediated resolution via required IDs** | Every turn, inject a compact, ID-labeled summary of current known facts into the LLM's context (e.g. `[inc_1] Salary ₹50k on 1st (confirmed); [debt_1] Bajaj EMI ₹4k due 5th (confirmed)`); the `update_entry` tool *requires* an existing ID; the LLM decides which ID a correction refers to using full conversational context, which is exactly the kind of judgment call language models are good at | Leverages the LLM's actual strength (contextual coreference) instead of fighting it with string heuristics; scales naturally to "actually, the other loan too" style references | Requires careful context construction so the ID list stays current and readable every turn; if the LLM picks the wrong ID, the error is silent unless you add a safety net (see below) |
| **C. Always ask, never auto-resolve** | Any time a new mention *might* refer to an existing entry, the agent explicitly asks "is this the rent we discussed, or a new expense?" | Zero silent errors | Very annoying in practice — violates the spirit of a natural, low-friction conversation, and the brief explicitly wants natural correction handling, not a confirmation prompt for every mention |

**Recommendation: B, with a code-level safety net borrowed from A.** Let the LLM resolve references using ID-labeled context (B), because that's the only approach that actually handles natural language coreference. But add a cheap, non-blocking duplicate check in the tool handler: when `add_income`/`add_expense`/`add_debt` is called with a name that's a close normalized-string match to an *existing* entry, don't silently create a duplicate — flag it as `possible_duplicate: true` on the new entry, surface it on the "Missing Information" card as "possible duplicate — please confirm," and let the agent ask one clarifying question. This turns a silent failure mode (C's fear) into a visible, cheap-to-resolve one, without paying the "ask about everything" tax of pure Option C.

### 13.4 Design Axis 2 — Confidence & provenance model

Minimum viable version (from the original plan): a field is `confirmed` or `estimated`. For the deep version, treat every field as having a small **history**, not just a current value:

```python
class FieldHistory(BaseModel):
    value: float
    confidence: Literal["confirmed", "estimated"]
    turn_index: int
    timestamp: datetime

class Entry(BaseModel):
    id: str
    name: str
    current: FieldHistory
    history: list[FieldHistory] = []   # append-only; current corrections push here
```

**Why bother with history instead of just overwriting `current`:** it lets the final plan explanation be honest in a way a single-value model can't — "you originally said ₹15,000 for rent, then corrected it to ₹18,000; the plan below uses ₹18,000." That's a small addition that meaningfully upgrades trustworthiness and gives you something concrete to show in the demo video ("look, it remembers the correction and explains it").

**Trade-off:** append-only history costs a little more memory and a little more code (never mutate, always append + repoint `current`), but for a 30-day, single-session, in-memory object this cost is negligible — there's no real reason not to do this one.

### 13.5 Design Axis 3 — Conflict detection thresholds

Once entity resolution says "this update targets `debt_1`," you still need to decide whether the new value is a *correction* (needs no confirmation) or a *conflict* (needs the user to confirm before overwriting).

| Approach | Rule | Pros | Cons |
|---|---|---|---|
| Always auto-overwrite | Newest stated value always wins silently | Simplest, zero friction | Violates the brief directly ("ask for clarification when information conflicts") |
| Always confirm | Every update, however small, triggers "did you mean to change X from A to B?" | Never wrong | Tedious; most restatements are the user simply repeating themselves, not correcting |
| **Threshold-based (recommended)** | If `confirmed` and the new value differs by more than ~15% (tune this), treat as a conflict requiring confirmation; smaller deltas or updates to `estimated` fields auto-apply | Balances friction against safety; the 15% figure is an explicit, arguable, defensible design choice — good live-defense material | Threshold is a judgment call, not a provably correct number; document why you picked it (e.g. "small rounding restatements shouldn't interrupt the flow, but a change from 15k to 30k almost certainly is a real correction, not noise") |

Also treat a correction to a `confirmed` field as *always* worth a lightweight acknowledgment even below threshold ("got it, updated to ₹15,200") — cheap, and reinforces to the user that corrections are being tracked, which matters more for trust than for the underlying math.

### 13.6 Design Axis 4 — "When do we have enough information?" (the stopping heuristic)

This is a precision/recall trade-off, worth naming as exactly that in your journal.

| Approach | Behavior | Failure mode if wrong |
|---|---|---|
| Hard required-field checklist only | Stop asking as soon as minimum fields (≥1 income, ≥1 obligation) are present | Under-collects — plan technically runs but ignores expenses the user never got asked about, producing a falsely optimistic plan |
| Pure LLM discretion | Model decides conversationally when it has "enough" | Unpredictable — could stop too early (same risk as above) or badly over-ask (annoying, wastes the user's time, feels robotic) |
| **Hybrid (recommended)**: hard minimum enforced in code (blocks `finalize_plan`) + a soft prompt instruction to make **one reasonable extra pass** ("before finalizing, briefly check if there's anything else — any other loans, subscriptions, or upcoming bills?") + a hard cap (e.g. after ~2 such passes with no new info, proceed) | Guarantees a non-trivial minimum, actively invites completeness once, then stops instead of looping forever | The "one extra pass" wording needs actual testing — too aggressive and it feels naggy, too soft and it does nothing; this is a good candidate for your Track B scripted-scenario tests |

Frame the trade-off explicitly this way if asked live: *asking more questions increases plan accuracy but costs conversational friction and user patience; the hybrid caps the downside of both extremes rather than optimizing purely for one.*

### 13.7 Design Axis 5 — Turn boundaries, interruptions, and state-mutation races

Two real race conditions to design for, not just hope don't happen:

1. **Interim STT results triggering premature tool calls.** Only ever send a **finalized** (end-of-turn / VAD-endpointed) user utterance into the LLM context — never interim/partial transcripts. Pipecat's standard context-aggregator pattern already buffers this way by default; the concrete action item is to verify (with a test, not just an assumption) that your pipeline configuration is using the aggregator's end-of-turn signal and not accidentally wired to fire on every interim STT frame.
2. **User interrupts the agent mid-response, after a tool call already fired but before TTS finished.** Pipecat will cancel the in-flight TTS/LLM completion on interruption (its interruption strategy handles this), but the **tool call and its state mutation should be treated as already committed** the moment the tool handler returns — never make a tool handler's effect on `SessionState` depend on whether the resulting speech was fully played back. In practice: make tool handlers synchronous and side-effect-complete before returning, so cancellation of downstream TTS can never leave `SessionState` half-updated. This also means: if the user corrects something *while* the agent is mid-sentence about the old value, the state is already right — the agent will just sound slightly out of date for one sentence, which is a much better failure mode than an inconsistent state.

### 13.8 Design Axis 6 — Idempotency and duplicate suppression

Two realistic sources of duplicate tool calls: (a) an LLM occasionally repeating a tool call when a completion is retried after a transient error, and (b) the user genuinely repeating the same fact in different words later in the conversation (should not always be an error, but should not blindly duplicate either — see Axis 1's duplicate-flagging).

Cheap guard: in each tool handler, before creating a new entry, check for an existing entry with the same normalized name **and** the same value within a short time window (e.g. same turn or the immediately preceding one) — if found, no-op and return the existing ID rather than creating a new row. This is a narrow, low-risk heuristic (unlike full fuzzy entity resolution) because it only fires on near-exact repeats in close time proximity, so it's very unlikely to misfire on genuinely distinct facts.

### 13.9 Design Axis 7 — Validation and the self-correction loop

Every tool call's arguments should be validated (Pydantic) **before** touching `SessionState`. On failure, don't crash the pipeline or silently drop the call — return a structured tool-error string as the tool result (standard function-calling behavior: the "tool" can return an error, which goes back into the LLM's context like any other tool result), e.g. `"error: amount must be a positive number"`. This lets the model self-correct in the next turn instead of the conversation silently losing the fact. Test this path explicitly — deliberately send a malformed value in a scripted test and assert the system asks a sane follow-up rather than failing silently.

### 13.10 Recommended composite architecture (putting it all together)

```
User speech
  → STT (finalized utterance only, per 13.7)
  → Context aggregator appends:
        - full conversation history
        - a compact, ID-labeled "current known facts" summary (per 13.3-B)
        - the current `missing_fields` list (per Section 2.8 of this plan)
  → LLM turn: decides what to say + which scoped tools to call (per 13.2-C)
  → Tool handler, for each call:
        1. Pydantic-validate args (13.9) → on failure, return tool-error, stop here
        2. Duplicate/idempotency check (13.8) → no-op if near-exact repeat
        3. Duplicate-name heuristic (13.3 safety net) → flag `possible_duplicate` if fuzzy match to a different existing entry
        4. If updating an existing ID: conflict check against threshold (13.5)
             - within threshold or field is `estimated` → apply, push old value to history (13.4)
             - exceeds threshold on a `confirmed` field → do NOT overwrite yet; store as a pending conflict, return a tool result telling the LLM to confirm with the user
        5. Recompute all derived fields (missing_fields, shortfall/surplus) from canonical state
        6. Broadcast full updated snapshot via Daily app-message (per Section 2.5 of this plan)
  → TTS speaks the LLM's response
```

Every arrow above is something you can point to directly when asked "walk me through what happens when I say X" in the live session — that's the actual test this diagram is built to pass.

### 13.11 Failure-mode catalogue (use this as a live-defense cheat sheet)

| Failure mode | Root cause if unhandled | Mitigation in this design |
|---|---|---|
| Phantom duplicate expense | Entity resolution fails to link a restatement to the existing entry | 13.3: ID-labeled context + duplicate-name safety net |
| Silently lost fact | Full-state-overwrite approach (13.2-A) drops a field the model forgot to restate | 13.2-C: backend, not the LLM, owns the canonical state; tools only patch |
| Overwritten correct value with a mis-heard one | No conflict threshold | 13.5: threshold-based conflict flow |
| Plan looks fine but is missing a real expense | Stopping too early | 13.6: hard minimum + one soft completeness pass |
| Cards briefly show different numbers from each other | Cards computed independently instead of from one canonical state | Section 6 of this plan: all cards are pure renders of one `SessionState` |
| Tool call fires on a half-spoken sentence | Wired to interim STT instead of end-of-turn | 13.7: verify aggregator config with a test |
| State half-updated after user interrupts | Tool handler side effects tied to TTS completion | 13.7: tool handlers commit fully before returning, independent of playback |
| Duplicate entries from retried tool calls | No idempotency check | 13.8: near-exact-repeat no-op guard |
| Pipeline crashes on malformed LLM tool arguments | No validation layer | 13.9: Pydantic validation + tool-error return path |

### 13.12 Testing this layer specifically

This is the part of Track B (Section 2.11 / 9 of this plan) that matters most — prioritize it over testing the engine, which is comparatively low-risk:

- **Golden transcripts**: fixed sequences of scripted user turns (text, bypassing STT/TTS) with an asserted expected final `SessionState`. Include at least: a plain happy-path intake, a mid-conversation correction, a conflicting restatement that should trigger confirmation, an ambiguous reference ("the other one"), and a malformed/nonsensical amount.
- **Adversarial variants**: same underlying facts, phrased differently across multiple runs (paraphrase robustness) — assert the *final state* converges to the same values even though the wording differs.
- **Regression discipline**: the first time you find a real failure (e.g. a duplicate entry from a restated expense), turn that exact transcript into a permanent golden test before fixing the bug — that before/after pair is precisely the evidence the brief asks for in the optional depth track.

### 13.13 If challenged live on this section

Likely questions and the one-line answer each design choice earns you:

- *"Why not just have the LLM output the whole state as JSON each turn?"* → Catastrophic forgetting risk (13.2-A) and no natural per-field validation hook; scoped tools keep the backend as the single source of truth.
- *"How do you know 'fix the other loan' refers to the right entry?"* → ID-labeled context lets the LLM use full conversational judgment (13.3-B), backed by a cheap fuzzy-duplicate safety net so a wrong resolution surfaces visibly instead of silently.
- *"What if the user talks over the agent mid-update?"* → Tool handlers are synchronous and commit before TTS plays; Pipecat cancels playback, never a half-applied state (13.7).
- *"How do you decide a number is a correction versus a mishearing?"* → It isn't decided at the mishearing level — it's a threshold on confirmed-value deltas, an explicit and named trade-off, not a claim of certainty (13.5).
- *"How do you stop it from asking forever?"* → Hard minimum in code plus one bounded completeness pass, not indefinite LLM discretion (13.6).
