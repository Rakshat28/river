# Riverline Voice Finance Assistant — Phase-by-Phase Implementation Guide

**Companion documents:** `riverline-implementation-plan.md` (architecture + trade-offs), `rules.md` (coding standards). Keep both open in VS Code alongside this file — reference them in your Copilot prompts (e.g. "per rules.md Section 3") so Copilot's output stays consistent with the decisions already made.

## How to use this document

- Each **Step** is sized to be one Copilot Chat/edit session — small enough that Copilot can't wander into unrelated files or invent architecture you haven't decided on yet.
- Do steps **in order within a phase**. Do not start a phase until the previous phase's acceptance checks all pass — this guide exists specifically so you never end up debugging three half-finished layers at once.
- Every step has four parts:
  - **Prompt for Copilot** — copy this near-verbatim into chat.
  - **Files touched** — if Copilot edits something outside this list, stop and review before accepting.
  - **Why / trade-off** — one line tying the step back to a decision in the implementation plan, so you can explain it live.
  - **Acceptance check** — a concrete thing you personally verify before moving on. Don't skip these; this is what keeps "mostly working" from silently becoming "broken in three places."
- After every step, **commit** (per `rules.md` Section 7 — small, atomic, conventional-commit messages). This gives you a clean history to reconstruct your decision journal from afterward.
- If Copilot's output does something Section 1 of `rules.md` forbids (e.g. it quietly has the LLM compute a total), reject it and re-prompt — don't accept it "for now."

---

## Critical Path Notice — Read This Before You Start

Per `riverline-implementation-plan.md` Section 13.0, the **state-extraction-and-consistency layer** (Phases 3, 4, and 5 below) is the single most crucial part of this system — every qualitative grading criterion in the brief ("ask the right questions," "remember information," "handle corrections and conflicts," "avoid presenting guesses as facts," "cards remain consistent") lives entirely inside this layer, and a silent bug here corrupts everything downstream even if the voice pipeline and UI are flawless. The **deterministic finance engine** (Phase 7) is the second most critical piece: it is explicitly, directly graded ("Are the calculations correct?") and is the most algorithmically dense code in the entire project.

**Phases 3, 4, 5, and 7 below are deliberately far more granular and prescriptive than the other phases** — exact data types, exact algorithms, exact thresholds, exact worked numeric examples, and exact edge-case tables are spelled out so that Copilot (and you) have as close to zero room for silent misinterpretation as possible. Two decisions worth knowing before you start, since they run through all four phases:

1. **All money is represented as integer paise (1 rupee = 100 paise), never as `float` or `Decimal`, anywhere in the system — backend, API payloads, or frontend.** Floating-point rounding error in financial math is one of the most common and hardest-to-notice bug classes; representing money as integers eliminates the entire bug class outright, at the cost of needing a small conversion utility at input/display boundaries. This is worth defending live as a deliberate choice, not an accident of typing.
2. **`today` (the start of the 30-day window) is captured once per session, at session creation, and reused everywhere for the rest of that call** — not re-evaluated as "the current wall-clock date" on every tool call or engine run. This avoids the window silently shifting if a call happens to span midnight.

Do not compress, merge, or skip sub-steps within Phases 3, 4, 5, or 7, even where they feel repetitive — the granularity is deliberate. A single oversized prompt covering two of these sub-steps at once is exactly the situation where Copilot (or a tired human) gets one of them subtly wrong without noticing.

---

## Phase 0 — Repository Scaffolding

**Goal by end of phase:** empty-but-correct project skeleton, `docker compose up --build` boots two "hello world" services. No business logic yet.

### Step 0.1 — Create the directory skeleton
**Prompt:** "Create the following empty directory structure with placeholder `.gitkeep` or minimal stub files, no logic: `/frontend`, `/agent/app`, `/agent/tests`, root `docker-compose.yml`, `.env.example`, `README.md`. Match this exact tree: [paste the tree from `rules.md` Section 2]."
**Files touched:** directory structure only.
**Why:** Locking the structure in before any code exists stops Copilot from later "helpfully" reorganizing things mid-feature.
**Acceptance check:** `tree` (or VS Code's explorer) matches `rules.md` Section 2 exactly.

### Step 0.2 — Initialize the Next.js app
**Prompt:** "Inside `/frontend`, initialize a Next.js app using the App Router, TypeScript, and Tailwind CSS. Use strict TypeScript config per rules.md Section 4. Don't add any pages beyond the default yet."
**Files touched:** `/frontend/*` (generated scaffold).
**Why:** App Router + strict TS is a locked decision (plan Section 2.10) — verify Copilot didn't default to Pages Router.
**Acceptance check:** `npm run dev` inside `/frontend` shows the default Next.js page at `localhost:3000`.

### Step 0.3 — Initialize the Python backend
**Prompt:** "Inside `/agent`, create a minimal FastAPI app in `app/main.py` with a single `GET /health` endpoint returning `{\"status\": \"ok\"}`. Create `requirements.txt` with `fastapi`, `uvicorn`, `pydantic`. Add `black` and `ruff` as dev dependencies in a `requirements-dev.txt`."
**Files touched:** `/agent/app/main.py`, `/agent/requirements.txt`, `/agent/requirements-dev.txt`.
**Why:** Establishes the FastAPI-as-thin-host pattern (plan Section 1) before any Pipecat complexity is layered on.
**Acceptance check:** `uvicorn app.main:app --reload` from `/agent` and `curl localhost:8000/health` returns `{"status": "ok"}`.

### Step 0.4 — `.env.example` and README skeleton
**Prompt:** "Create `.env.example` at the repo root with these keys, each with a one-line comment: `DAILY_API_KEY`, `DAILY_DOMAIN`, `LLM_PROVIDER`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPGRAM_API_KEY`, `TTS_PROVIDER`, `CARTESIA_API_KEY`, `NEXT_PUBLIC_AGENT_URL`. Create a `README.md` with empty section headers: Overview, Setup, Environment Variables, Running the App, Testing."
**Files touched:** `.env.example`, `README.md`.
**Why:** Getting the env var contract written down before code exists prevents "I'll document it later" drift (rules.md Section 8).
**Acceptance check:** Every env var Copilot introduces in later phases must already appear here, or you add it in the same step — don't let this file fall behind.

### Step 0.5 — Docker Compose skeleton
**Prompt:** "Create a root `docker-compose.yml` with two services, `web` (builds from `/frontend`, runs `npm run dev`, exposes port 3000) and `agent` (builds from `/agent`, runs `uvicorn app.main:app --host 0.0.0.0 --port 8000`, exposes port 8000). No volumes or networking beyond defaults yet. Create minimal `Dockerfile`s for each."
**Files touched:** `docker-compose.yml`, `/frontend/Dockerfile`, `/agent/Dockerfile`.
**Why:** Verifying the one-command boot works *before* any real logic exists means any future breakage is caused by your new code, not by Docker plumbing you never actually tested.
**Acceptance check:** `docker compose up --build` from a clean checkout brings up both services; `localhost:3000` and `localhost:8000/health` both respond.

---

## Phase 1 — Daily Transport Skeleton (audio only, no agent brain yet)

**Goal by end of phase:** two people can join a Daily room created by your backend and hear each other. No LLM, no STT/TTS, no bot — this isolates "does WebRTC work" from "does the agent work."

### Step 1.1 — Daily room + token helper
**Prompt:** "In `/agent/app/daily_client.py`, write two async functions: `create_room() -> DailyRoom` and `create_meeting_token(room_name: str, is_owner: bool = False) -> str`, calling the Daily REST API using `DAILY_API_KEY`. Return typed Pydantic models. Do not call these functions from anywhere yet — just define them, with unit tests using a mocked HTTP client."
**Files touched:** `/agent/app/daily_client.py`, `/agent/tests/test_daily_client.py`.
**Why:** Isolating the Daily API calls behind a tested function means later phases can't accidentally scatter raw HTTP calls through the codebase.
**Acceptance check:** `pytest agent/tests/test_daily_client.py` passes with mocked HTTP, no real network call needed.

### Step 1.2 — `POST /api/session` endpoint (room creation only)
**Prompt:** "Add `POST /api/session` to `main.py`. It should call `create_room()` and `create_meeting_token()`, and return `{room_url, token}` as JSON. Do not spawn any bot yet — this endpoint only creates the room."
**Files touched:** `/agent/app/main.py`.
**Why:** Keeping room-creation and bot-spawning as separate steps means you can verify Daily connectivity in isolation before Pipecat enters the picture (this is exactly the debugging isolation the 2-day timeline in the plan relies on).
**Acceptance check:** `curl -X POST localhost:8000/api/session` returns a real, joinable Daily room URL and a token.

### Step 1.3 — Frontend join screen (audio only)
**Prompt:** "In `/frontend`, install `@daily-co/daily-react` and `@daily-co/daily-js`. Build a single page with a 'Start Call' button that calls `POST /api/session` on the agent backend, then joins the returned Daily room using the Daily React SDK, with mic enabled. Show a simple 'Connected' status once joined. No card UI yet."
**Files touched:** `/frontend/app/page.tsx`, `/frontend/lib/daily-client.ts`.
**Why:** Confirms the Daily React SDK integration (a locked decision, plan Section 2.10) works before layering anything else on top.
**Acceptance check:** Open the page in two separate browser tabs/profiles, click "Start Call" in both (or manually join the same room URL in the second), and confirm you can hear yourself between the two tabs.

### Step 1.4 — Start/End call UI
**Prompt:** "Add an 'End Call' button that leaves the Daily room and resets the UI to the pre-call state. Handle the case where the call fails to connect with a visible error message, not a silent failure."
**Files touched:** `/frontend/app/page.tsx`.
**Why:** The assignment explicitly requires start/end call as a core capability, and rules.md Section 5 requires visible failure states, not silent ones.
**Acceptance check:** Clicking "End Call" actually leaves the room (verify via Daily's dashboard or console logs); killing your network mid-call shows an error state, not a frozen UI.

---

## Phase 2 — Pipecat Voice Loop Skeleton (no tools, no financial logic yet)

**Goal by end of phase:** you can speak into the browser and hear a spoken LLM response, round-tripped through Deepgram → LLM → TTS → Daily. This isolates "does the voice pipeline work" from "does the financial logic work."

### Step 2.1 — Add voice pipeline dependencies
**Prompt:** "Add `pipecat-ai`, the Deepgram STT service, your chosen LLM service integration, and your chosen TTS service integration to `requirements.txt`. Do not write pipeline code yet, just get dependencies installing cleanly."
**Files touched:** `/agent/requirements.txt`.
**Why:** Isolate dependency/installation issues from pipeline-logic issues — a very common source of wasted debugging time.
**Acceptance check:** `pip install -r requirements.txt` (or your container build) completes without conflicts.

### Step 2.2 — Minimal echo pipeline
**Prompt:** "In `/agent/app/bot.py`, build a minimal Pipecat pipeline: Daily transport in → Deepgram STT → an LLM service with the system prompt 'You are a test assistant. Briefly acknowledge what the user just said, nothing else.' (no tools) → TTS → Daily transport out. Write a function `async def run_bot(room_url: str, token: str)` that constructs and runs this pipeline."
**Files touched:** `/agent/app/bot.py`.
**Why:** No tools, no financial prompt yet — the only thing being tested here is whether the raw voice loop functions and at what latency (plan Section 2.1–2.3 trade-offs).
**Acceptance check:** Not yet callable end-to-end (no spawn wiring) — just confirm it constructs without runtime errors via a quick manual script.

### Step 2.3 — Wire bot spawning into session creation
**Prompt:** "Modify `POST /api/session` so that after creating the room and token, it spawns `run_bot(room_url, bot_token)` as an `asyncio.create_task`, using a separate owner token for the bot. Wrap the task body in a try/except that logs any crash instead of letting it die silently, per rules.md Section 3."
**Files touched:** `/agent/app/main.py`.
**Why:** Locks in the "asyncio task per room in one process" decision (plan Section 2.7) — verify Copilot didn't default to spawning a subprocess or container instead.
**Acceptance check:** Calling `POST /api/session` results in a bot joining the created room within a few seconds (check the Daily dashboard's participant list, or bot-side logs).

### Step 2.4 — End-to-end manual voice test
**Prompt:** none — this is a manual test step, not a code-generation step.
**Why:** This is the first point where you can judge real latency and decide if your STT/TTS vendor choices (plan Sections 2.2–2.3) need revisiting before more logic is built on top.
**Acceptance check:** Join a call from the frontend, speak a sentence, hear a spoken acknowledgment back within an acceptable delay (subjectively note the latency — you'll want this number for the live defense).

### Step 2.5 — Verify interruption handling
**Prompt:** "Confirm the pipeline is using Pipecat's standard VAD-based interruption strategy so that speaking while the bot is talking cancels its current TTS output. If not already the default, configure it explicitly and add a code comment referencing why (see implementation-plan.md Section 13.7)."
**Files touched:** `/agent/app/bot.py`.
**Why:** This is a named race-condition concern in the deep-dive (plan Section 13.7) — verify it now, not after tool calls make the state of "what was mid-flight" more complicated.
**Acceptance check:** Start talking while the bot is mid-response; its speech stops promptly rather than talking over you.

---

## Phase 3 — Data Model & State Layer  ⚠️ CRITICAL PATH

**Goal by end of phase:** the `SessionState` model exists, is testable in isolation, has zero dependency on Pipecat/FastAPI, represents all money as integer paise, and has every field-level constraint enforced by Pydantic before a single tool handler is written.

This phase is the *foundation* of the crucial layer named in the Critical Path Notice above. Every ambiguity left unresolved here (what unit is money in? what does "missing" mean exactly? can two writers race on the same state?) turns into a much harder-to-diagnose bug once Phase 4's tool handlers and Phase 7's engine are built on top of it. Take the extra time here.

### Step 3.1 — Money utility module (build this *before* any model that touches money)
**Prompt:** "Create `/agent/app/money.py`. Define: `rupees_to_paise(rupees: str | float) -> int` which converts a rupee amount (accept either a string like `'15000'`/`'15,000.50'` or a float) to an integer number of paise, rounding to the nearest paisa using `ROUND_HALF_UP` (use Python's `decimal.Decimal` internally *only inside this function*, never elsewhere in the codebase, and never let a `Decimal` or `float` escape this module's public functions). Define `paise_to_rupees_display(paise: int) -> str` returning a human-readable string like `'₹15,000'` (no decimal places if the paise amount is a whole number of rupees, otherwise show two decimal places). Define `paise_to_rupees_float(paise: int) -> float` for cases where a float is unavoidable (e.g. a chart library) with a docstring warning it must never be used for arithmetic, only display. Write exhaustive unit tests in `test_money.py`: `rupees_to_paise('15000')` → `1500000`; `rupees_to_paise(15000.5)` → `1500050`; `rupees_to_paise('15,000.505')` → `1500051` (rounds up); `rupees_to_paise('0')` → `0`; `paise_to_rupees_display(1500000)` → `'₹15,000'`; `paise_to_rupees_display(1500050)` → `'₹15,000.50'`."
**Files touched:** `/agent/app/money.py`, `/agent/tests/test_money.py`.
**Why:** Every downstream money bug this project could have — rounding drift, silent precision loss, JSON serialization surprises with `Decimal` — is prevented by confining all unit conversion to one tested module and using plain `int` everywhere else. Building this first, before any model exists, means there is never a point in the codebase where a raw `float` dollar amount is passed around "just for now."
**Acceptance check:** `pytest agent/tests/test_money.py -v` all green, including the rounding edge cases above. Grep the rest of the (currently empty) `/agent/app` directory — there should be no other file with `Decimal` or a bare money-typed `float` in it once this phase is done.

### Step 3.2 — Core Pydantic models
**Prompt:** "In `/agent/app/state.py`, define the following, using `amount_paise: int` (never `float`/`Decimal`) for every monetary field, and Python's `date` type (not `datetime`) for every due-date field, since we only care about day-level granularity within a 30-day window:

```
Confidence = Literal['confirmed', 'estimated']

class FieldHistory(BaseModel):
    amount_paise: int
    confidence: Confidence
    turn_index: int          # which conversation turn produced this value
    timestamp: datetime

class Entry(BaseModel):
    id: str                  # format: 'entry_' + 8 hex chars, generated via uuid4
    name: str
    current: FieldHistory
    history: list[FieldHistory] = []   # append-only; never mutate existing entries
    possible_duplicate: bool = False
    duplicate_of: str | None = None    # id of the entry this might duplicate

class Debt(Entry):
    kind: Literal['loan', 'credit_card']
    due_date: date
    min_payment_paise: int
    balance_paise: int | None = None
    interest_rate_bps: int | None = None   # basis points, e.g. 1250 = 12.50%, to avoid float here too

class Conflict(BaseModel):
    id: str
    entry_id: str
    field_name: str
    old_amount_paise: int
    new_amount_paise: int
    resolved: bool = False
    created_at: datetime

class SessionState(BaseModel):
    room_name: str
    today: date               # captured once at session creation, reused for the whole call — see Critical Path Notice
    income: list[Entry] = []
    essential_expenses: list[Entry] = []
    optional_expenses: list[Entry] = []
    debts: list[Debt] = []
    conflicts: list[Conflict] = []
    plan: PlanResult | None = None    # PlanResult defined in Phase 7 — forward-reference or Optional[Any] for now
    turn_index: int = 0
    state_version: int = 0    # incremented on every mutation — used by Phase 5's out-of-order-message guard
    updated_at: datetime
```

Add validators: `amount_paise`/`min_payment_paise` must be `> 0` (reject zero and negative); reject any field that is a `float` type at the Pydantic level using strict mode. Do not import FastAPI, Pipecat, or any LLM SDK in this file — see rules.md Section 2. Add a module-level docstring explaining the paise convention so nobody 'fixes' it back to float later without reading this first."
**Files touched:** `/agent/app/state.py`.
**Why:** Every field above has a specific reason tied back to a named design decision: `possible_duplicate`/`duplicate_of` exist for Phase 4's duplicate safety net (plan 13.3); `history` is append-only for the audit trail (plan 13.4); `state_version` exists purely to let Phase 5's frontend reducer reject stale/out-of-order updates; `today` being stored on the state itself (not read from the OS clock on demand) is what makes the 30-day window stable for the whole call.
**Acceptance check:** `python -c "import app.state"` succeeds with zero network/framework imports; `mypy app/state.py` clean; a unit test constructing `Entry(current=FieldHistory(amount_paise=1.5, ...))` (a float where an int is expected) raises a validation error rather than silently coercing.

### Step 3.3 — `compute_missing_fields`: exact truth table
**Prompt:** "In `state.py`, add `compute_missing_fields(state: SessionState) -> list[str]` implementing exactly this truth table — do not add any other condition beyond these two:

| Condition | Returned item |
|---|---|
| `state.income` is empty | `'income'` |
| `state.essential_expenses` is empty **and** `state.debts` is empty | `'obligations'` |

Both conditions are checked independently — a state can be missing both, one, or neither. Return an empty list if neither condition holds. This function must not consider `optional_expenses`, `conflicts`, or anything about confidence levels — those are handled elsewhere (see Phase 4.12's `compute_blocking_issues`, which is a *different, broader* function than this one)."
**Files touched:** `/agent/app/state.py`.
**Why:** Writing this as an exact table rather than a prose description removes the ambiguity that would otherwise let Copilot (reasonably) guess at edge cases like "what if there's one debt but no essential expenses" — the table already answers that (not missing, since `debts` is non-empty).
**Acceptance check:** Unit test table: empty state → `['income', 'obligations']`; income-only state → `['obligations']`; income + one essential expense → `[]`; income + one debt (no essential expenses) → `[]`; income + one optional expense only (no essential, no debt) → `['obligations']` (optional expenses do not count).

### Step 3.4 — `compute_cash_position`: exact formula and worked example
**Prompt:** "In `state.py`, add `compute_cash_position(state: SessionState) -> int` (returns paise) implementing exactly: `sum(e.current.amount_paise for e in state.income if e.current.confidence == 'confirmed') - sum(e.current.amount_paise for e in state.essential_expenses if e.current.confidence == 'confirmed')`. Entries with `confidence == 'estimated'` are excluded entirely from this calculation — do not include them at a discount or partial weight, exclude them completely, since this is a placeholder pre-engine number, not the real 30-day simulation (that's Phase 7's `build_plan`). Debts and optional expenses are not included in this particular number. Add a docstring stating explicitly that this is NOT the final plan calculation."
**Files touched:** `/agent/app/state.py`.
**Why:** Worked example to lock the exact semantics: income of ₹50,000 (confirmed) + ₹10,000 (estimated) and essential expenses of ₹15,000 (confirmed) must return `(5000000) - (1500000) = 3500000` paise (₹35,000) — the estimated ₹10,000 income must NOT appear in the result at all.
**Acceptance check:** Unit test reproduces the exact worked example above and asserts `compute_cash_position(state) == 3_500_000`.

### Step 3.5 — Concurrency-safe in-memory session store
**Prompt:** "Create `/agent/app/session_store.py` with an in-memory dict keyed by `room_name`, holding one `SessionState` per room, PLUS one `asyncio.Lock` per room (stored alongside the state, e.g. in a small `RoomSession` wrapper dataclass holding `{state, lock}`). Provide `get_or_create(room_name, today) -> RoomSession`, and an async context manager `async with locked_state(room_name) as state:` that acquires the room's lock, yields the mutable `SessionState`, and releases the lock on exit — this is what every Phase 4 tool handler will use to mutate state, so that if the LLM issues multiple tool calls within the same turn (parallel function calling), they cannot race on the same `SessionState` object. Add a code comment explaining this race condition and citing implementation-plan.md Section 13.7. Also add a comment noting the store is intentionally non-persistent (lost on process restart) per implementation-plan.md Section 2.6 — a documented, deliberate limitation, not an oversight."
**Files touched:** `/agent/app/session_store.py`.
**Why:** This is a genuine, easy-to-miss correctness issue: without a lock, two tool calls resolved concurrently within one LLM turn could both read the same `state_version`, both mutate, and one write could silently clobber the other. A single `asyncio.Lock` per room, acquired for the duration of each individual tool handler's mutation, closes this gap with almost no added complexity.
**Acceptance check:** Unit test: spawn two concurrent coroutines that each try to mutate the same room's state via `locked_state`, using `asyncio.sleep(0)` to force interleaving; assert both mutations are present in the final state (neither was lost) and `state_version` incremented by exactly 2, not 1.

### Step 3.6 — Unit tests for Phase 3 (consolidated)
**Prompt:** "Write `test_state.py` covering, at minimum: (1) the full `compute_missing_fields` truth table from Step 3.3; (2) the `compute_cash_position` worked example from Step 3.4, plus two more input combinations you construct yourself; (3) that constructing an `Entry` with a negative or zero `amount_paise` raises a validation error; (4) that `FieldHistory.amount_paise` rejects a `float` input; (5) the concurrency test from Step 3.5. Every test must use concrete, hand-calculated expected values in paise — no test may assert 'a positive number' or similar vague conditions."
**Files touched:** `/agent/tests/test_state.py`.
**Why:** This file becomes the regression backstop for the entire state layer — since Phase 4 and Phase 7 both build directly on these functions, a bug caught here is a bug prevented in two other phases at once.
**Acceptance check:** `pytest agent/tests/test_state.py -v` — every test passes, and you can read each assertion and independently verify the expected number by hand without re-running the code.

### Step 3.7 — Mirror types on the frontend, in paise
**Prompt:** "In `/frontend/lib/types.ts`, define TypeScript interfaces `Entry`, `Debt`, `Conflict`, `SessionState` structurally matching the Pydantic models in `agent/app/state.py` exactly — every money field is typed `number` but named with an explicit `_paise` suffix (e.g. `amountPaise: number` mapped from `amount_paise` — decide on and document one consistent casing convention across the JSON boundary, either keep snake_case as-is or convert to camelCase, but be consistent). Add a `lib/money.ts` utility mirroring `paise_to_rupees_display` from the backend, so the frontend never does its own rupee/paise math. Add a comment stating these types must be kept in sync with `state.py` manually (rules.md Section 4)."
**Files touched:** `/frontend/lib/types.ts`, `/frontend/lib/money.ts`.
**Why:** JavaScript has no native arbitrary-precision decimal type and `0.1 + 0.2 !== 0.3`-style float errors are a classic source of frontend money bugs — keeping paise as a plain integer on the frontend too means the exact same bug class that Step 3.1 eliminated on the backend is eliminated on the frontend as well, for free.
**Acceptance check:** Manually diff the two type files side by side — every backend field has a corresponding frontend field with a matching type and unit (paise, not rupees); `paise_to_rupees_display` and its TS mirror produce byte-identical output strings for at least five hand-picked test values.

---

## Phase 4 — Tool Schema & Handlers  ⚠️ CRITICAL PATH — THE CORE OF THE PROJECT

**Goal by end of phase:** the LLM can mutate `SessionState` only through validated, tested, concurrency-safe tool calls — no free-text parsing, no direct state edits from the prompt layer, no way for a duplicate or an unconfirmed correction to silently corrupt the numbers the engine will later compute over.

This phase implements the design worked out in implementation-plan.md Section 13 in full. It is broken into 15 sub-steps on purpose — each one is small enough to fully verify before moving to the next, because this is the layer where a subtle, unnoticed mistake silently falsifies the product's central claims (no invented numbers, honest handling of corrections, consistent cards). **Do not let Copilot combine two of these sub-steps into one prompt, even if it offers to.**

### Step 4.1 — Define all 8 tool JSON schemas (schema only, no logic)
**Prompt:** "In `/agent/app/tools.py`, define function-calling tool schemas (name, description, JSON parameter schema, required vs. optional fields) for exactly these 8 tools — no more, no fewer:

| Tool | Required params | Optional params | Purpose |
|---|---|---|---|
| `add_income` | `name: string`, `amount_rupees: number`, `date: string (ISO YYYY-MM-DD)`, `confidence: 'confirmed'\|'estimated'` | — | Register a new income source |
| `add_expense` | `category: 'essential'\|'optional'`, `name: string`, `amount_rupees: number`, `date: string`, `confidence: 'confirmed'\|'estimated'` | — | Register a new expense |
| `add_debt` | `name: string`, `kind: 'loan'\|'credit_card'`, `min_payment_rupees: number`, `date: string`, `confidence: 'confirmed'\|'estimated'` | `balance_rupees: number`, `interest_rate_percent: number` | Register a new loan/credit-card obligation |
| `update_entry` | `entry_id: string`, `new_amount_rupees: number`, `confidence: 'confirmed'\|'estimated'` | — | Correct an existing entry the LLM has identified by ID |
| `resolve_duplicate` | `entry_id: string`, `is_same_as_existing: boolean` | `existing_entry_id: string` (required if `is_same_as_existing` is true) | Resolve a `possible_duplicate` flag raised by the backend |
| `resolve_conflict` | `conflict_id: string`, `chosen_amount_rupees: number` | — | Resolve a pending conflict raised by the backend |
| `finalize_plan` | *(none)* | — | Trigger the deterministic engine — backend-guarded, see Step 4.13 |
| `confirm_user_understood` | `understood: boolean` | — | Record that the agent explicitly checked comprehension |

Note tool arguments use `_rupees`/`_percent` (human units, since that's what the LLM naturally produces from speech) — conversion to paise/basis-points happens in the validation layer (Step 4.3), not in the schema itself. Write each tool's `description` field as a precise instruction to the model (e.g. `add_expense`'s description should explicitly state 'Do NOT call this to correct a previously mentioned amount — use update_entry instead if you can identify the existing entry by ID'). Just the schemas for now — no handler logic yet, and do not write `bot.py` wiring yet."
**Files touched:** `/agent/app/tools.py`.
**Why:** Writing all 8 schemas as one deliberate, reviewed table before any handler exists forces you to commit to the full tool surface (a rules.md "ask first" item) in one auditable place, rather than letting it grow accidentally alongside handler code. `resolve_duplicate` is the tool that closes the loop opened by the Step 4.8 safety net — without it, a flagged duplicate would be a permanent dead end in the state, exactly like an unresolved conflict would be without `resolve_conflict`.
**Acceptance check:** Schemas are valid JSON-schema (validate with a JSON-schema linter, not just "it looks right"); read each `description` aloud and confirm it disambiguates the tool from its nearest neighbor (e.g. `add_expense` vs `update_entry`) without you needing to explain further — this is literally what the LLM sees.

### Step 4.2 — `ToolResult` envelope type
**Prompt:** "In `/agent/app/tools.py` (or a new `tool_result.py`), define a single `ToolResult` Pydantic model used as the return type of every tool handler in this phase, with exactly these three constructors and nothing else: `ToolResult.ok(**data) -> ToolResult` (status='ok'), `ToolResult.warning(message: str, **data) -> ToolResult` (status='warning', used for possible-duplicate flags), `ToolResult.error(message: str) -> ToolResult` (status='error', used for validation failures and the finalize_plan guard). Every handler in this phase must return one of these three, never raise an exception for an expected business-rule outcome (only genuine bugs should raise)."
**Files touched:** `/agent/app/tools.py`.
**Why:** Without one canonical return shape, it's easy for different handlers written at different times to drift into slightly different error conventions (one returns `None`, another raises, another returns a bare string) — that inconsistency is exactly the kind of thing that causes a caller (the LLM-facing dispatch code in Step 4.13) to mishandle a case it wasn't written to expect.
**Acceptance check:** Unit test: each of the three constructors produces a `ToolResult` with the expected `status` field and the extra data/message accessible as expected; no other status value is representable (enforce via `Literal['ok', 'warning', 'error']`).

### Step 4.3 — Validation schemas with the exact constraint table
**Prompt:** "In `/agent/app/validation.py`, define a Pydantic input model per tool (e.g. `AddIncomeArgs`, `AddExpenseArgs`, ...) matching Step 4.1's parameter tables, with these exact constraints:

| Field pattern | Constraint |
|---|---|
| any `*_rupees` field | must be `> 0`; reject `0` and negative values with message `'amount must be greater than zero'` |
| `date` fields | must parse as ISO `YYYY-MM-DD`; business-rule check (not a Pydantic field validator, since it needs `state.today`) that the date falls within `[state.today, state.today + 29 days]` inclusive happens in the *handler*, not here — this file only validates the date is syntactically well-formed |
| `confidence` | must be exactly `'confirmed'` or `'estimated'` — no other string accepted |
| `kind` (debts) | must be exactly `'loan'` or `'credit_card'` |
| `interest_rate_percent` | if present, must be `>= 0` and `<= 100` |
| `entry_id`/`conflict_id` | must match the pattern `^(entry|conflict)_[0-9a-f]{8}$` — reject malformed IDs before they ever reach a lookup |

Each model must convert `*_rupees` to `*_paise` (via `money.rupees_to_paise`) and `interest_rate_percent` to `interest_rate_bps` as part of validation, so handlers only ever see paise/bps, never rupees/percent. Write unit tests for every row of the table above: one valid case and at least one invalid case per constraint."
**Files touched:** `/agent/app/validation.py`, `/agent/tests/test_validation.py`.
**Why:** Doing the rupees→paise conversion inside validation (not inside the handler) means every handler downstream can assume paise without re-deriving the conversion each time — one conversion point, matching Step 3.1's "confine unit conversion to one place" principle.
**Acceptance check:** `pytest agent/tests/test_validation.py -v` — every row of the constraint table has a passing valid-case test and a passing invalid-case test (asserting the specific validation error, not just "it raised something").

### Step 4.4 — Concurrency-safe handler decorator
**Prompt:** "Create a decorator `@state_mutation` (in `tools.py` or a small `decorators.py`) that wraps a tool handler so that it: (1) acquires the room's lock via Step 3.5's `locked_state`, (2) runs the handler body with the locked `SessionState`, (3) on any state mutation, increments `state.state_version` and calls `broadcast_state_update(room_name)` (stub this call for now — Step 5.1 implements it for real), (4) releases the lock. Apply this decorator to every handler you write in the remaining steps of this phase."
**Files touched:** `/agent/app/tools.py`.
**Why:** Centralizing the lock-acquire / version-bump / broadcast sequence in one decorator means it is structurally impossible to write a new tool handler later (in this phase or a future one) that forgets to lock, forgets to bump the version, or forgets to broadcast — those three things happen automatically for every handler that carries the decorator.
**Acceptance check:** Unit test: a handler decorated with `@state_mutation` that raises inside its body still releases the lock (test via a subsequent lock-acquire not hanging); `state_version` increments by exactly 1 per successful mutating call.

### Step 4.5 — `add_income` handler (happy path only)
**Prompt:** "Implement `add_income(room_name, args: AddIncomeArgs) -> ToolResult` in `tools.py`, decorated with `@state_mutation`. Steps, in exact order: (1) business-rule check that `args.date` is within `[state.today, state.today + 29 days]` — if not, return `ToolResult.error('date must be within the next 30 days')` and do not mutate state; (2) call `find_near_duplicate` (not implemented until Step 4.8 — for now, stub it to always return `None` so this step is testable in isolation); (3) construct a new `Entry` with a fresh `id`, `current=FieldHistory(amount_paise=args.amount_paise, confidence=args.confidence, turn_index=state.turn_index, timestamp=now())`, empty `history`; (4) append to `state.income`; (5) return `ToolResult.ok(entry_id=entry.id)`. Do NOT implement duplicate detection or conflict handling logic in this step beyond the stub call — that is Steps 4.8 and 4.10."
**Files touched:** `/agent/app/tools.py`.
**Why:** Writing the numbered step sequence into the prompt itself (not just describing the outcome) removes room for Copilot to reorder operations in a way that matters — e.g., checking the date range *after* constructing the entry would be a real bug (a partially-applied side effect on an error path).
**Acceptance check:** Unit test: valid args → exactly one new `Entry` in `state.income` with correct paise amount and confidence; `state_version` incremented by 1; a date 31 days out → `ToolResult.error`, and `state.income` remains empty (verify the error path truly did not mutate state).

### Step 4.6 — `add_expense` handler (happy path only)
**Prompt:** "Implement `add_expense(room_name, args: AddExpenseArgs) -> ToolResult`, identical structure to Step 4.5's `add_income`, but appending to `state.essential_expenses` or `state.optional_expenses` depending on `args.category`. Reuse the exact same date-range check and duplicate-detection stub call pattern — do not write a second, slightly different implementation of either."
**Files touched:** `/agent/app/tools.py`.
**Why:** Explicitly instructing "reuse the exact same pattern" guards against a subtle drift bug where `add_income` and `add_expense` end up with slightly different validation order or error messages purely because they were written in separate Copilot sessions.
**Acceptance check:** Unit test: `category='essential'` lands in `state.essential_expenses`; `category='optional'` lands in `state.optional_expenses`; both share the same date-range and error-message behavior as `add_income`'s tests.

### Step 4.7 — `add_debt` handler (happy path only)
**Prompt:** "Implement `add_debt(room_name, args: AddDebtArgs) -> ToolResult`, same structural pattern again, appending a `Debt` (not a plain `Entry`) to `state.debts`, including `kind`, `min_payment_paise`, `balance_paise`, `interest_rate_bps` where provided."
**Files touched:** `/agent/app/tools.py`.
**Why:** Completes the three `add_*` handlers with one consistent pattern before any cross-cutting concern (duplicates, conflicts) is layered on top of all three at once in the next steps.
**Acceptance check:** Unit test: a `loan` and a `credit_card` debt both construct correctly with all optional fields present and absent (test both cases).

### Step 4.8 — Duplicate-detection algorithm: exact specification
**Prompt:** "Implement `find_near_duplicate(existing_entries: list[Entry], new_name: str) -> Optional[str]` in a new `/agent/app/entity_resolution.py`. Algorithm, in exact order: (1) normalize `new_name` and every existing entry's name by lowercasing, stripping leading/trailing whitespace, and removing the filler words `{'my', 'the', 'a', 'monthly', 'payment'}` as whole words (not substrings); (2) for each existing entry, compute similarity using `difflib.SequenceMatcher(None, normalized_new, normalized_existing).ratio()`; (3) if any similarity is `>= 0.75`, return that entry's `id`; if multiple exceed the threshold, return the one with the highest ratio (ties broken by earliest-created entry); (4) otherwise return `None`. Write a dedicated test file `test_entity_resolution.py` with this exact table of cases (all must produce the documented result):

| New name | Existing names | Expected result |
|---|---|---|
| `'Rent'` | `['House Rent']` | duplicate found (ratio ≈0.77 after normalization removes nothing here — verify your normalization doesn't over-strip; adjust threshold/test if your actual computed ratio differs, but document the real number in the test) |
| `'Netflix subscription'` | `['Spotify subscription']` | no duplicate (different core word, ratio should be well below 0.75) |
| `'Credit card 1'` | `['Credit card 2']` | duplicate found — this is a **known false-positive risk**, document it in a code comment; it is an accepted trade-off of the heuristic (see implementation-plan.md Section 13.3), not a bug to silently 'fix' by adding number-suffix-awareness under time pressure |
| `'My rent'` | `['Rent']` | duplicate found (filler word 'my' stripped) |

Do not wire this into the `add_*` handlers yet — that's Step 4.9."
**Files touched:** `/agent/app/entity_resolution.py`, `/agent/tests/test_entity_resolution.py`.
**Why:** Writing the algorithm as a numbered, literal specification (not "use fuzzy matching") plus a fixed test table — including a documented *false positive* the algorithm is known to produce — means you go into the live defense already knowing and having chosen this trade-off, rather than discovering it under questioning.
**Acceptance check:** `pytest agent/tests/test_entity_resolution.py -v` — every row of the table passes with the ratio behavior documented inline in the test (print/assert the actual computed ratio, don't just assert true/false blindly).

### Step 4.9 — Wire duplicate detection into the `add_*` handlers, and the `resolve_duplicate` handler
**Prompt:** "Replace the Step 4.5–4.7 stub (`find_near_duplicate` always returning `None`) with a real call to Step 4.8's function, checked against the same category's existing entries (income against income, essential expenses against essential expenses, etc. — never cross-category). If a duplicate is found: still create the new `Entry` (do not discard the user's new information), but set `possible_duplicate=True` and `duplicate_of=<found_id>` on it, and return `ToolResult.warning('possible duplicate of an existing entry — please confirm with the user whether this is the same item or a genuinely separate one', entry_id=new_entry.id, duplicate_of=found_id)`. Then implement `resolve_duplicate(room_name, args: ResolveDuplicateArgs) -> ToolResult`: if `is_same_as_existing` is true, merge by treating the new entry's amount as a correction to the existing entry (reuse Step 4.10's `update_entry` logic internally) and remove the flagged duplicate entry from its list entirely; if false, simply clear `possible_duplicate`/`duplicate_of` on the flagged entry and leave both entries in place as genuinely separate."
**Files touched:** `/agent/app/tools.py`.
**Why:** The explicit 'still create the new Entry, don't discard' instruction is the load-bearing decision here — silently dropping the new information on a possible-duplicate match would be a worse failure mode than a temporary visible duplicate, because a dropped fact is invisible while a flagged duplicate is visible on the Missing Information card and gets resolved through natural conversation.
**Acceptance check:** Unit test: adding 'Rent' then 'House Rent' (similar amount) results in **two** entries in state, the second flagged with `possible_duplicate=True`; calling `resolve_duplicate` with `is_same_as_existing=True` collapses them to one entry with the corrected amount; calling it with `False` leaves both as independent, unflagged entries.

### Step 4.10 — `update_entry` with the exact conflict-threshold formula
**Prompt:** "Implement `update_entry(room_name, args: UpdateEntryArgs) -> ToolResult`. Look up the target entry by `args.entry_id` across all four lists (`income`, `essential_expenses`, `optional_expenses`, `debts`) — if not found in any, return `ToolResult.error('no entry with that id')`. Then, exact logic:

```
old = entry.current
delta_ratio = abs(args.new_amount_paise - old.amount_paise) / old.amount_paise   # old.amount_paise is guaranteed > 0 by Step 3.2's validator

if old.confidence == 'confirmed' and delta_ratio > 0.15:
    conflict = Conflict(entry_id=entry.id, field_name='amount', old_amount_paise=old.amount_paise,
                         new_amount_paise=args.new_amount_paise, resolved=False, created_at=now())
    state.conflicts.append(conflict)
    return ToolResult.warning(
        f'this changes a confirmed value by more than 15% — ask the user to confirm before it takes effect',
        conflict_id=conflict.id)
else:
    entry.history.append(old)   # push the OLD value into history before overwriting
    entry.current = FieldHistory(amount_paise=args.new_amount_paise, confidence=args.confidence,
                                  turn_index=state.turn_index, timestamp=now())
    return ToolResult.ok(entry_id=entry.id)
```

Note the `>` (strictly greater than 0.15), not `>=` — a change of exactly 15% auto-applies. Note also this only ever *creates* a conflict and returns early; it never overwrites `entry.current` on the conflict path — the actual overwrite only happens later, in `resolve_conflict` (Step 4.11)."
**Files touched:** `/agent/app/tools.py`.
**Why:** Spelling out the exact operator (`>` not `>=`) and the exact order of operations (push history *before* reassigning `current`) removes two classic off-by-one/ordering bugs that would otherwise be easy to introduce without noticing, since both would still 'look right' in casual manual testing.
**Acceptance check:** Unit tests, with concrete numbers: entry at 1,000,000 paise (confirmed) updated to 1,100,000 (10% delta) → auto-applies, `history` now contains the old 1,000,000 value; same entry updated to 1,200,000 (20% delta) → returns `warning`, a `Conflict` is created, `entry.current` is still 1,000,000 (unchanged); an entry at `confidence='estimated'` updated by 50% → auto-applies regardless of delta size; an update of exactly 15.0% delta on a confirmed entry → auto-applies (boundary case, confirms `>` not `>=`).

### Step 4.11 — `resolve_conflict` handler
**Prompt:** "Implement `resolve_conflict(room_name, args: ResolveConflictArgs) -> ToolResult`. Look up the conflict by `args.conflict_id` — if not found or already `resolved=True`, return `ToolResult.error('no pending conflict with that id')`. Otherwise: find the target entry via `conflict.entry_id`, push `entry.current` into `entry.history`, set `entry.current` to a new `FieldHistory` with `amount_paise=args.chosen_amount_paise` (note: the user may choose neither the old nor the new value from the original conflict — accept whatever amount is passed, per implementation-plan.md Section 13.5), mark `conflict.resolved = True`, return `ToolResult.ok(entry_id=entry.id)`."
**Files touched:** `/agent/app/tools.py`.
**Why:** Allowing `chosen_amount_paise` to be a third value (neither the original nor the disputed one) matters in practice — a user resolving a conflict might say "actually it's neither, it's ₹16,000" — and the handler must not artificially restrict them to picking one of the two original numbers.
**Acceptance check:** Unit test: create a conflict via Step 4.10's boundary-exceeding case, resolve it with a third value not equal to either original number, confirm `entry.current.amount_paise` equals the chosen value, `history` contains the pre-conflict value, and `conflict.resolved == True`; resolving an already-resolved or nonexistent conflict ID returns `ToolResult.error`.

### Step 4.12 — `compute_blocking_issues`: the single source of truth for "can we finalize?"
**Prompt:** "In `state.py`, add `compute_blocking_issues(state: SessionState) -> list[str]` that returns the union of: (1) everything `compute_missing_fields` (Step 3.3) returns; (2) `'unresolved_conflict'` if any `Conflict` in `state.conflicts` has `resolved == False`; (3) `'unresolved_duplicate'` if any `Entry` across all four lists has `possible_duplicate == True`. This is a strictly broader check than `compute_missing_fields` alone, and is the ONLY function `finalize_plan` (Phase 8.1) is allowed to consult when deciding whether to proceed — do not let `finalize_plan` call `compute_missing_fields` directly."
**Files touched:** `/agent/app/state.py`.
**Why:** Without this consolidation, it would be easy for `finalize_plan`'s guard (Phase 8.1) to check only the original missing-fields condition and let a plan finalize while an unresolved possible-duplicate is silently double- or under-counted in the engine — this function exists specifically to make that impossible by construction.
**Acceptance check:** Unit test matrix: complete state with no issues → `[]`; complete state with one unresolved conflict → `['unresolved_conflict']`; complete state with one unresolved possible-duplicate → `['unresolved_duplicate']`; incomplete state with both issues too → all three items present in the list.

### Step 4.13 — Wire tools into the LLM and write the real system prompt
**Prompt:** "Replace bot.py's placeholder echo prompt with a real system prompt describing the assistant's purpose (30-day financial planning), instructing it to: ask natural, non-scripted questions; remember prior answers; never state a number it hasn't received from a tool result; when a tool returns `status='warning'` (a possible duplicate or a pending conflict), explicitly ask the user a clarifying question and then call `resolve_duplicate`/`resolve_conflict` with their answer, rather than ignoring the warning or guessing. Register the Step 4.1 tool schemas with the LLM service and route tool calls to the Step 4.5–4.12 handlers via the `@state_mutation`-wrapped dispatch."
**Files touched:** `/agent/app/bot.py`.
**Why:** This is where the voice pipeline (Phase 2) and the state/tools layer (Phases 3–4) actually connect — keep the system prompt itself in a separate constant/file if it grows, so it's easy to iterate on independently of pipeline wiring.
**Acceptance check:** In a live call, say "My salary is 50000 rupees on the 1st." Check backend logs or a debug endpoint and confirm an `Entry` was created with `amount_paise == 5000000` and the correct date. Then say something that should trigger the possible-duplicate path (per Step 4.8's test table) and confirm the agent actually asks a clarifying question rather than silently proceeding.

### Step 4.14 — Inject "current known facts" + blocking issues into context each turn
**Prompt:** "Modify the context aggregation so that each turn, before the LLM generates its response, two things are injected: (1) a compact, ID-labeled summary of every entry currently in state, in the exact format `[entry_id] Name ₹amount (confidence) [on date]`, e.g. `[entry_a1b2c3d4] Salary ₹50,000 (confirmed) on 2026-10-01` — using `money.paise_to_rupees_display` for the amount, never a raw paise number; (2) the current `compute_blocking_issues(state)` list, phrased as an internal note the model should act on (e.g. `INTERNAL: cannot finalize yet, missing: obligations`). Both must be freshly recomputed every turn from the current `SessionState`, never cached from a previous turn."
**Files touched:** `/agent/app/bot.py`.
**Why:** This is what makes entity resolution ("fix the other one") and the soft slot-tracking approach (plan Section 2.8) actually work — without a fresh, correctly-formatted ID-labeled summary every single turn, the LLM has no reliable way to reference existing entries by ID, and a stale cached copy would silently reintroduce exactly the "cards drift out of sync" failure mode this whole phase exists to prevent.
**Acceptance check:** Say a fact, then verbally correct it using a vague reference ("actually, make that 55000"). Confirm via logs that `update_entry` was called with the correct existing `entry_id`, not that a new entry was created. Log the injected context string for one full turn and manually verify every entry ID and amount in it matches the actual current state exactly.

### Step 4.15 — Full Phase 4 regression sweep before moving on
**Prompt:** "Run the full `agent/tests` suite. For any failure, fix the specific handler — do not modify a test's expected value to make it pass unless you can show by hand-calculation that the test's original expectation was wrong."
**Files touched:** varies, likely none if everything above was verified incrementally.
**Why:** This is the checkpoint before Phase 5 starts consuming this layer's output — per the Critical Path Notice, a bug that survives past this point gets much more expensive to trace once broadcast and card rendering are layered on top.
**Acceptance check:** `pytest agent/tests -v` fully green; manually re-run the Step 4.8 duplicate table and the Step 4.10 conflict boundary tests one more time by hand (not just via pytest) to build your own confidence in the exact numbers, since these are the ones most likely to come up in live questioning.

---

## Phase 5 — State Broadcast to Frontend  ⚠️ CRITICAL PATH

**Goal by end of phase:** the frontend has a live, correct copy of `SessionState` at all times — with an explicit, tested guarantee that it can never render a stale or out-of-order snapshot, which is what "cards remain consistent" actually requires under the hood.

### Step 5.1 — Define the exact broadcast payload shape
**Prompt:** "Define a `BroadcastPayload` Pydantic model (in `state.py` or a new `broadcast.py`) that is a *trimmed* view of `SessionState`: include everything except each entry's `history` list (history is audit-trail detail needed only for the REST snapshot in Step 5.3, not for live card rendering) and include `state_version` at the top level. Add a `to_broadcast_payload(state: SessionState) -> BroadcastPayload` conversion function. Add a code comment explaining why `history` is excluded here: Daily app-messages have a practical size limit (commonly cited around a few KB), and a growing audit trail on every entry would eventually risk exceeding it — trimming it from the live-update path avoids that risk entirely rather than hoping it never comes up."
**Files touched:** `/agent/app/broadcast.py` (or `state.py`).
**Why:** This is a real, concrete risk (payload size growing unboundedly with conversation length) addressed before it can ever manifest as a demo-day failure, rather than being a "we'll deal with it if it happens" gap.
**Acceptance check:** Unit test: `to_broadcast_payload` on a state with a 5-entry history on one `Entry` produces a payload with that entry's `history` field absent or empty, while `current`, `state_version`, and every other field are present and correct.

### Step 5.2 — Broadcast function, batched once per turn (not once per tool call)
**Prompt:** "Add `broadcast_state_update(room_name)` in `broadcast.py` that builds a `BroadcastPayload` via Step 5.1's function and sends it as a single Daily app-message to all participants in the room. Then modify Step 4.4's `@state_mutation` decorator: instead of broadcasting immediately after every individual tool handler call, set a per-room 'dirty' flag when any mutation happens, and have `bot.py`'s turn-processing loop call `broadcast_state_update` exactly once after all tool calls for that LLM turn have completed (an LLM turn may issue multiple tool calls in parallel — see Step 3.5's concurrency lock). Add a comment explaining that batching per-turn, rather than per-tool-call, avoids a rapid burst of out-of-order messages when several facts are extracted from one utterance at once."
**Files touched:** `/agent/app/tools.py`, `/agent/app/broadcast.py`, `/agent/app/bot.py`.
**Why:** If a single user utterance produces three tool calls (e.g. stating income, rent, and a loan all in one sentence), broadcasting after each of the three individually risks the frontend receiving and rendering three rapid, partially-overlapping snapshots — batching to one broadcast per turn means the frontend only ever sees one clean, fully-consistent state per user utterance.
**Acceptance check:** Manually state three facts in one sentence in a live call; add a temporary counter on the frontend for incoming app-messages; confirm exactly one message arrives for that turn, not three, and it contains all three new facts.

### Step 5.3 — REST snapshot fallback endpoint (full state, for reconnect)
**Prompt:** "Add `GET /api/state/{room_name}` returning the FULL current `SessionState` as JSON (including `history` — this endpoint, unlike the broadcast, has no size-sensitivity concern since it's a one-off request/response, not a live-update channel), for reconnect/hydration use, per implementation-plan.md Section 2.5. Return a 404 with a clear error body if the room doesn't exist."
**Files touched:** `/agent/app/main.py`.
**Why:** This is the documented recovery path for the known limitation of app-messages having no replay — build it now while it's cheap, not after a demo-day reconnect glitch. Deliberately full (untrimmed) here, unlike the broadcast payload, since a REST response isn't subject to the same channel size pressure.
**Acceptance check:** `curl localhost:8000/api/state/{room}` returns valid JSON matching the current state including entry histories; requesting a nonexistent room returns 404 with a JSON error body, not a raw stack trace (per rules.md Section 5).

### Step 5.4 — Frontend reducer with an explicit out-of-order guard
**Prompt:** "In `/frontend/lib/session-context.tsx`, create a React Context + `useReducer` store for `SessionState`, per rules.md Section 4 (no Redux/Zustand). The reducer's update action must compare the incoming payload's `stateVersion` against the currently held state's `stateVersion` and **ignore the incoming update entirely (no-op) if the incoming version is less than or equal to the currently held version** — do not simply always overwrite. Add a code comment explaining this guards against the theoretical case of two broadcasts arriving out of order over the data channel."
**Files touched:** `/frontend/lib/session-context.tsx`.
**Why:** Even though Step 5.2's per-turn batching makes out-of-order delivery unlikely, 'unlikely' is not 'impossible' over a WebRTC data channel — a one-line version check removes the entire failure mode for the cost of a single comparison, which is a very cheap insurance policy for a guarantee ("cards remain consistent") that's explicitly graded.
**Acceptance check:** Unit test (can be a plain Jest/Vitest test on the reducer function in isolation, no need for a live Daily connection): dispatching a payload with `stateVersion: 5` after one with `stateVersion: 7` already applied leaves the state at version 7's values, unchanged.

### Step 5.5 — Hydration on join + live subscription
**Prompt:** "On joining a call, call the Step 5.3 REST endpoint once to hydrate the initial state into the Step 5.4 reducer (dispatch a special 'hydrate' action that always applies regardless of version, since it's establishing the baseline). Then subscribe to Daily app-messages using `useAppMessage` and dispatch the regular version-checked update action for every subsequent message."
**Files touched:** `/frontend/lib/session-context.tsx`.
**Why:** Separating "hydrate" (always applies, establishes the baseline `state_version`) from "live update" (version-checked) as two distinct reducer actions avoids a chicken-and-egg problem where the very first update would otherwise need special-casing inside the general version-check logic.
**Acceptance check:** Join a call after some facts have already been stated (e.g. reload the page mid-conversation, or open a second tab pointed at the same room); confirm the cards immediately show the already-known facts (via hydration), not a blank state that only fills in from that point forward.

### Step 5.6 — Manual race/ordering test
**Prompt:** none — manual test, following a script you write yourself.
**Why:** This is where you personally verify the version-guard (Step 5.4) and per-turn batching (Step 5.2) actually behave correctly together under real conversational timing, not just under a synthetic unit test.
**Acceptance check:** In a live call, state a fact and then, as quickly as possible, verbally correct it (rapid-fire, minimal gap). Confirm the final rendered card state matches the final backend state exactly — no card ever visibly "flickers back" to the pre-correction value after the correction was already spoken.

### Step 5.7 — Message envelope with a `type` discriminator (needed before the new UI can distinguish message kinds)
**Prompt:** "Change every Daily app-message this backend sends to be wrapped in a small envelope: `{'type': 'state_update' | 'agent_utterance' | 'user_utterance', 'payload': ...}`. Update `broadcast_state_update` (Step 5.2) to send `type='state_update'` with `payload=BroadcastPayload`. Do not send any un-enveloped message from anywhere in the codebase — grep for existing `send_app_message` calls and update all of them."
**Files touched:** `/agent/app/broadcast.py`.
**Why:** Section 6 below adds two new message kinds (focus changes and live captions) that must travel over the same single data channel (plan Section 2.5's locked-in decision) without being confused for state snapshots — a discriminated envelope is the standard, low-risk way to multiplex several message kinds over one channel.
**Acceptance check:** Temporarily log every outgoing app-message on the frontend; confirm every single one has a `type` field, with no bare/un-enveloped payloads reaching the client.

### Step 5.8 — Derive `current_focus`: exact priority table, computed in code, never by the LLM
**Prompt:** "In `/agent/app/focus.py`, define `FocusTarget = Literal['idle', 'income', 'essential_expenses', 'optional_expenses', 'debts', 'conflict', 'duplicate', 'missing_info', 'plan']`. Add `derive_focus(previous_focus: FocusTarget, tool_calls_this_turn: list[ToolCallRecord]) -> FocusTarget` where `ToolCallRecord` is a small dataclass `{tool_name: str, status: Literal['ok','warning','error'], target_list: str | None}` that Step 4.13's dispatch loop already has enough information to construct (add it now if it doesn't yet — one record per tool call executed in the turn). Exact priority table, lowest rank number wins when multiple tool calls fired in the same turn:

| Rank | Condition | Focus |
|---|---|---|
| 1 | any `finalize_plan` call with `status='ok'` | `'plan'` |
| 2 | any `update_entry` call with `status='warning'` (a conflict was just created) | `'conflict'` |
| 3 | any `add_income`/`add_expense`/`add_debt` call with `status='warning'` (a possible duplicate was just flagged) | `'duplicate'` |
| 4 | any call touching `state.debts` with `status='ok'` | `'debts'` |
| 5 | any call touching `state.essential_expenses` with `status='ok'` | `'essential_expenses'` |
| 6 | any call touching `state.optional_expenses` with `status='ok'` | `'optional_expenses'` |
| 7 | any call touching `state.income` with `status='ok'` | `'income'` |

If `tool_calls_this_turn` is empty (a purely conversational turn — the agent asked a question but mutated nothing), return `previous_focus` unchanged, UNLESS `previous_focus == 'idle'` and `state.turn_index == 0`, in which case return `'missing_info'` (the very first turn should surface the missing-info card as a natural 'here's what I'll need' starting point, not stay on a blank idle screen indefinitely). This function is pure, synchronous, and takes no LLM input whatsoever — it is derived entirely from which tools actually fired and their result status, exactly like every other consistency guarantee in Phase 4/5."
**Files touched:** `/agent/app/focus.py`, `/agent/tests/test_focus.py`.
**Why:** This is the same design principle as the rest of the critical layer, applied to the UI: the LLM never decides what's 'currently relevant' by free-text judgment (which would be unpredictable and untestable) — the backend derives it deterministically from the same tool-call events that already drive state mutation, so a live interrogator's question 'how does the UI know what to show' has a precise, code-level answer rather than 'the model figures it out.'
**Acceptance check:** Unit tests for every row of the priority table, plus: two tool calls in one turn (e.g. an `add_expense` and an `add_debt`, both `ok`) → the higher-priority one (`debts`, rank 4) wins even though `add_expense` may have executed first; an empty turn → focus unchanged from `previous_focus`; the very first turn of a session with no tool calls → `'missing_info'`.

### Step 5.9 — Broadcast focus changes and utterance captions
**Prompt:** "In `bot.py`'s per-turn batching point (the same place Step 5.2 already batches the state broadcast), after computing `new_focus = derive_focus(...)`: if `new_focus != previous_focus`, send an app-message `{'type': 'focus_update', 'payload': {'focus': new_focus}}` and update the stored `previous_focus` for the room. Separately, whenever the LLM's response text for a sentence/chunk is ready (use Pipecat's sentence-aggregation boundary, so captions arrive roughly in sync with TTS playback of that sentence, not all at once at the end of a possibly-long response), send `{'type': 'agent_utterance', 'payload': {'text': <sentence>}}`. When STT finalizes a user turn, send `{'type': 'user_utterance', 'payload': {'text': <transcript>}}`. Add a code comment noting the caption/audio sync is sentence-level approximate, not frame-accurate, as a deliberate, documented simplification for this timeline."
**Files touched:** `/agent/app/bot.py`.
**Why:** Sentence-level (not whole-response) caption broadcasting is what keeps the on-screen subtitle roughly synchronized with what's actually being spoken, rather than dumping an entire multi-sentence answer on screen the instant the LLM finishes generating, well before TTS has caught up reading it aloud.
**Acceptance check:** In a live call, confirm the subtitle text updates progressively, roughly sentence-by-sentence, as the agent speaks a multi-sentence response — not all at once, and not noticeably lagging behind the audio by more than about a sentence.

---

## Phase 6 — Voice-First UI: Agent Orb, Live Subtitle, and One Focused Card

**Goal by end of phase:** the screen shows only three things while a call is active — a central animated agent presence, a live caption of what's being said, and exactly one card, chosen automatically by `current_focus` (Step 5.8), showing only the information relevant to what's currently being discussed. Every other card from the original design still exists as a component and is still driven by the exact same `SessionState` — it simply isn't shown until it's the relevant one, plus an optional expandable view for anyone who wants to see everything at once.

**Why this replaces the dashboard layout (design rationale, for your own reference and for the live defense):** a permanent grid of 7–8 cards asks the user to visually search for what changed every time they speak, which fights against the conversational, low-friction voice experience the brief asks for. Routing to a single relevant card via `current_focus` means the screen always shows exactly the thing the user just talked about, with no search cost — at the trade-off of requiring the extra `focus.py` derivation logic from Phase 5.8 and losing the ability to see everything at a glance, which is why Step 6.8 below adds a cheap opt-in "see everything" affordance rather than removing that capability entirely.

### Step 6.1 — `AgentOrb`: the central animated presence
**Prompt:** "Create `/frontend/components/AgentOrb.tsx`. Props: `state: 'idle' | 'listening' | 'speaking'`. Render a circular SVG or CSS element (a soft radial-gradient circle is enough — no need for a 3D/particle effect given the timeline) that: pulses gently and slowly when `state === 'idle'`; pulses faster and reacts to the local user's live mic audio level when `state === 'listening'` (use Daily React SDK's audio-level hook — check `@daily-co/daily-react`'s available hooks for the local participant's audio level, e.g. `useAudioLevelObserver` or equivalent — and drive the pulse amplitude from it); animates a distinct 'speaking' pattern (e.g. a smooth waveform-like scale animation, not dependent on any real audio-level data since driving it off the agent's synthesized TTS audio level, if available at all client-side, adds real complexity — a fixed, pleasant speaking animation is a fine, documented simplification) when `state === 'speaking'`. Export the component with no internal state beyond animation — `state` is fully controlled by its parent."
**Files touched:** `/frontend/components/AgentOrb.tsx`.
**Why:** Keeping `AgentOrb` a pure, controlled component (state comes in as a prop, no internal fetching or business logic) matches the same "dumb rendering" principle from the original card design (rules.md Section 4) — it should be trivial to unit-test and trivial to reason about when something visual looks wrong.
**Acceptance check:** Render the component in isolation (e.g. a quick Storybook-less test page, or just temporarily mount it in `page.tsx` with a hardcoded state) and manually cycle through all three `state` values; confirm each looks visually distinct and none of them look broken/frozen.

### Step 6.2 — Orb state derivation from the call
**Prompt:** "In `page.tsx` (or a small hook `useOrbState()`), derive the `AgentOrb`'s `state` prop from real call activity: `'listening'` when the local participant's mic audio level is above a small noise threshold (avoid flickering on background noise — pick a reasonable threshold like 0.02 and debounce briefly), `'speaking'` when an `agent_utterance` message (Step 5.9) has arrived within roughly the last few seconds and no newer `user_utterance` has superseded it, otherwise `'idle'`. Keep this derivation logic in one small, isolated function so it's easy to tune the thresholds later without touching rendering code."
**Files touched:** `/frontend/app/page.tsx` or `/frontend/lib/use-orb-state.ts`.
**Why:** Isolating the state-derivation heuristic from the rendering component means tuning the "how sensitive is listening detection" trade-off later is a one-function change, not a hunt through JSX.
**Acceptance check:** In a live call, speak and confirm the orb visibly switches to 'listening'; stop and let the agent respond, confirm it switches to 'speaking' during the response and settles to 'idle' a couple of seconds after the agent finishes.

### Step 6.3 — `SubtitleText`: live caption of the conversation
**Prompt:** "Create `/frontend/components/SubtitleText.tsx`. Props: `agentText: string | null`, `userText: string | null`. Render `agentText` prominently (larger, higher-contrast text) directly below the orb, with a brief fade-in transition on change. Render `userText`, if present and recent, smaller and more muted just below the agent text (e.g. 'You: ...') so the user can visually confirm what the system heard them say. Both should clear/fade after a reasonable idle period (e.g. ~6 seconds with no new utterance) rather than leaving stale text on screen indefinitely."
**Files touched:** `/frontend/components/SubtitleText.tsx`.
**Why:** Showing the user's own recognized transcript (not just the agent's side) gives immediate, cheap feedback if STT mis-heard something — the user can correct it verbally right away instead of only discovering a misunderstanding once a card shows a wrong number.
**Acceptance check:** In a live call, confirm both agent and user captions appear and update correctly, and that stale captions fade rather than lingering forever after the conversation has moved on.

### Step 6.4 — Extend the frontend context for `focus_update` and utterance messages
**Prompt:** "Extend the Step 5.4/5.5 reducer and its message-subscription handler to also process the two new envelope types from Step 5.7: `'focus_update'` (store `currentFocus` in context, no version-guard needed since focus changes are idempotent to re-apply and there's no ordering-sensitive derived math riding on it) and `'agent_utterance'`/`'user_utterance'` (store the latest text of each kind plus a timestamp, used by Step 6.3). Keep these as separate pieces of reducer state from the versioned `SessionState`, since they follow different consistency rules (focus/captions: last-write-wins is fine; state: version-guarded, per Step 5.4)."
**Files touched:** `/frontend/lib/session-context.tsx`.
**Why:** Explicitly using a different consistency rule for focus/captions than for financial state is a deliberate, correct choice, not an inconsistency — financial facts need the strict ordering guarantee from Step 5.4 because a stale number is a real error, while a caption that's a message or two behind is cosmetically imperfect at worst.
**Acceptance check:** Log every dispatched action in the reducer during a short live call; confirm `focus_update`, `agent_utterance`, and `user_utterance` actions all arrive and update their respective pieces of state independently of the `state_update` version-guard logic.

### Step 6.5 — Individual card components (mostly ported from the original design, unchanged internally)
**Prompt:** "Create or port these card components into `/frontend/components/cards/`, each taking only the slice of `SessionState` it needs as props, pure rendering only, confidence-tagged visual treatment per the original design (dashed border / muted styling for `confidence: 'estimated'` entries): `IncomeCard.tsx`, `EssentialExpensesCard.tsx`, `OptionalExpensesCard.tsx` (new — previously optional expenses weren't a standalone focus target, now they need their own card since `optional_expenses` is a distinct `FocusTarget`), `DebtsCard.tsx`, `MissingInformationCard.tsx` (rendering `compute_missing_fields`, i.e. the same underlying data as before). None of these components change their internal logic from the original design — only how they're mounted changes, per Step 6.7."
**Files touched:** `/frontend/components/cards/*.tsx`.
**Why:** Reusing the original card components' internals (rather than rewriting them) means the single-source-of-truth guarantee already established for them carries over unchanged — only the *mounting strategy* is new in this phase, not the data flow.
**Acceptance check:** Same as the original Step 6.1–6.4 acceptance checks: with a hand-crafted mock `SessionState`, each card renders correctly in isolation with no console errors, and confidence styling is visually distinct.

### Step 6.6 — Two new focus-specific cards: `ConflictCard` and `DuplicateCard`
**Prompt:** "Create `/frontend/components/cards/ConflictCard.tsx`, taking the most recent unresolved `Conflict` plus its target `Entry` as props, rendering the old value and new value side by side with clear labels (e.g. 'You said ₹15,000 before' / 'Just now you said ₹18,000') and the question 'Which is right?' — this card is purely informational; it does not need its own confirm button, since resolution happens by the user answering the agent's spoken question and the agent calling `resolve_conflict`, which will change `current_focus` away from `'conflict'` once resolved. Create `/frontend/components/cards/DuplicateCard.tsx` similarly, taking the flagged entry and the entry it's a possible duplicate of, rendering both side by side with a prompt like 'Are these the same thing?'"
**Files touched:** `/frontend/components/cards/ConflictCard.tsx`, `DuplicateCard.tsx`.
**Why:** These two cards didn't exist in the original dashboard design because a permanent dashboard could just show the conflicting numbers within the relevant list card with a small badge — but in a single-focused-card UI, a conflict or duplicate needs its own dedicated, unambiguous visual moment, since it's the single most important thing to communicate at that point in the conversation.
**Acceptance check:** With a mock `Conflict` and mock `Entry` objects, `ConflictCard` renders both values legibly and distinctly (e.g. old value struck through or grayed, new value highlighted); `DuplicateCard` renders both candidate entries with enough detail (name, amount, date) for a user to judge whether they're really the same thing just by reading the card.

### Step 6.7 — `FocusCard` router with transition
**Prompt:** "Create `/frontend/components/FocusCard.tsx`. Props: `focus: FocusTarget`, `state: SessionState`. Internally, a single `switch`/lookup mapping each `FocusTarget` value to exactly one of: `IncomeCard`, `EssentialExpensesCard`, `OptionalExpensesCard`, `DebtsCard`, `MissingInformationCard`, `ConflictCard` (pass it `state.conflicts` filtered to unresolved, most recent first), `DuplicateCard` (pass it the most recently flagged unresolved-duplicate entry), `FinalPlanCard` (for `'plan'`, built in Phase 8.2), and for `'idle'` render nothing (or a minimal, calm placeholder — not a card, since there's nothing to show yet). Wrap the rendered card in a simple crossfade transition (a CSS opacity/transform transition keyed on the `focus` value, so React treats a focus change as a full remount and the transition runs) so switching cards feels like a deliberate transition, not an abrupt swap."
**Files touched:** `/frontend/components/FocusCard.tsx`.
**Why:** Centralizing the focus→component mapping in exactly one place (rather than scattering conditional rendering through `page.tsx`) means adding a ninth focus target later is a one-line addition to a lookup table, not a hunt through layout code.
**Acceptance check:** Manually drive `focus` through all nine values (via a temporary debug control, or by actually triggering each one in a live conversation) and confirm exactly one appropriate card renders each time, with a visible, non-jarring transition between changes — never two cards visible at once, never a blank flash longer than the transition itself.

### Step 6.8 — Optional but recommended: expandable full-summary view
**Prompt:** "Add a small, unobtrusive button/icon (e.g. top-right corner, label 'View everything so far') that opens a slide-over panel or modal rendering all the Step 6.5/6.6 cards at once (essentially the retired dashboard layout, repurposed as an opt-in view), reusing the exact same components and the exact same `SessionState` — no new data-fetching, purely a different arrangement of the same already-built cards. Closing the panel returns to the normal single-focus-card view underneath, which continues updating live even while the panel is open."
**Files touched:** `/frontend/components/FullSummaryDrawer.tsx`, `/frontend/app/page.tsx`.
**Why:** This preserves the genuine usefulness of an at-a-glance view (someone reviewing the whole picture before agreeing to a plan, or you personally verifying nothing was missed during the live demo) without making it the default, permanent screen — cheap to build since it's just a different mount point for components that already exist from Step 6.5/6.6, and it's a good, concrete addition to mention in your "what I'd build next... actually, I did build this" submission notes.
**Acceptance check:** Open the panel mid-conversation, confirm it shows accurate, live data for every card (not a stale snapshot from when it was opened); close it and confirm the main single-focus view is unaffected and still current.

### Step 6.9 — Assemble the final layout
**Prompt:** "Rewrite `/frontend/app/page.tsx`: `AgentOrb` centered near the top (driven by Step 6.2's derived state), `SubtitleText` directly beneath it, `FocusCard` beneath that (driven by `currentFocus` from Step 6.4's context), the Step 1.4 Start/End call controls at the bottom, and the Step 6.8 'view everything' button in a corner. Remove the old permanent dashboard grid entirely — no card should be visible outside of `FocusCard`'s single active card or the opt-in drawer. Keep the layout vertically centered and uncluttered; don't worry about mobile polish, explicitly out of scope per implementation-plan.md Section 11."
**Files touched:** `/frontend/app/page.tsx`.
**Why:** This is the actual product moment — the first time the redesigned experience is visible end to end. Worth a rough screen recording here for your own before/after reference, since "we deliberately moved away from a dashboard toward a focused, single-card voice UI" is a good, concrete story for the live defense and the submission's differentiators list.
**Acceptance check:** Full manual run: join a call, have a natural conversation covering income, an expense, a debt, and a deliberate correction that should trigger a conflict; confirm the screen shows only the orb, the current caption, and exactly one contextually-correct card at every point in the conversation, with no dashboard-style clutter at any time; confirm the drawer from Step 6.8 still shows everything correctly when opened.

---

## Phase 7 — Deterministic Finance Engine  ⚠️ CRITICAL PATH

**Goal by end of phase:** `engine.py` correctly and testably produces a 30-day plan from a `SessionState`, with zero framework dependencies, using exact integer-paise arithmetic and an unambiguous, fully-specified algorithm.

This is the second most critical phase (per the Critical Path Notice) because "Are the calculations correct?" is a literal, standalone grading criterion — not an inference from other criteria, an explicit one. Three semantics must be locked down precisely before any code is written, because each is a place a reasonable-sounding implementation could quietly diverge from what's actually correct:

1. **A missed payment does not push the running balance negative.** If there isn't enough money to cover an obligation in full on its due date, that specific obligation is recorded as *missed* and the money is not spent — you cannot spend money you don't have. The balance simply carries forward unchanged by that obligation.
2. **The shortfall/surplus check is based on whether *any* obligation was missed, not on the sign of the final or minimum balance.** A scenario can end with a balance of exactly ₹0 while still having missed an earlier payment (see the worked "unsolvable" fixture in Step 7.1) — that is `unsolvable`, not solved, because a real obligation went unpaid partway through, even though the arithmetic "worked out" by the end.
3. **The shortfall condition uses strictly-less-than-zero (`< 0`), never `<= 0`,** anywhere balance is compared to zero, and a balance of exactly zero after all obligations are paid in full is a valid non-shortfall outcome. Getting this operator wrong is a classic, easy-to-miss off-by-one-style bug — call it out explicitly in code review.

### Step 7.1 — Write the failing tests first, using these exact worked fixtures
**Prompt:** "In `/agent/tests/test_engine.py`, write (currently failing) tests for a function `build_plan(state: SessionState) -> PlanResult` (note: `today` comes from `state.today`, not a separate parameter, per the Critical Path Notice's decision to store it once on the state) using these four exact fixtures — compute nothing yourself, use these numbers verbatim so the expected values are independently verifiable by hand:

**Fixture A — clean surplus.** `today` = day 0. Income: salary ₹50,000 (5,000,000 paise) on day 0. Essential: rent ₹15,000 on day 4, groceries ₹6,000 on day 10. Optional: OTT ₹500 on day 5, dining ₹4,000 on day 12. Debts: loan EMI ₹8,000 (kind=loan) on day 15, credit card min ₹3,000 on day 20. Hand-calculated running balance: day0→50,000; day4→35,000; day5→34,500; day10→28,500; day12→24,500; day15→16,500; day20→13,500. No obligation is ever missed. **Expected:** `status='surplus'`, `missed_obligations=[]`, final balance = 1,350,000 paise.

**Fixture B — exact break-even (tests the `< 0` vs `<= 0` operator specifically).** `today` = day 0. Income: ₹10,000 on day 0. Essential: rent ₹10,000 on day 0 (same day as income — income must be applied before same-day expenses). No debts, no optional expenses. Hand-calculated: day0 balance after income = 10,000, after rent = 0 exactly. **Expected:** `status='surplus'` (zero is NOT a shortfall), `missed_obligations=[]`.

**Fixture C — shortfall resolved entirely by cuts.** `today` = day 0. Income: ₹30,000 on day 0. Essential: rent ₹15,000 on day 4, groceries ₹6,000 on day 10. Optional: OTT ₹500 on day 5, dining ₹4,000 on day 12. Debts: loan EMI ₹8,000 on day 15, credit card min ₹1,000 on day 20. Base run (no cuts) hand-calculated: day0→30,000; day4→15,000; day5→14,500; day10→8,500; day12→4,500; day15→ need 8,000, only have 4,500 → **loan EMI missed**, balance stays 4,500; day20→ need 1,000, have 4,500 → paid, balance 3,500. Base status: `unsolvable` (loan EMI missed). Now cut dining (₹4,000) and OTT (₹500), total ₹4,500 in cuts: day0→30,000; day4→15,000; day10→9,000; day15→ need 8,000, have 9,000 → paid, balance 1,000; day20→ need 1,000, have 1,000 → paid exactly, balance 0. **Expected after cuts:** `status='solved_with_cuts'`, `cuts=[OTT entry, dining entry]` (both, since cutting only one of the two is insufficient — verify your greedy search actually tries combinations up to 'cut everything,' not just one at a time and stop), `missed_obligations=[]`, final balance = 0.

**Fixture D — unsolvable even after all cuts, AND balance ends at zero (proves min/final-balance alone is not a sufficient check).** `today` = day 0. Income: ₹20,000 on day 0. Essential: rent ₹15,000 on day 4. No optional expenses to cut at all. Debts: loan EMI ₹8,000 on day 15, credit card min ₹5,000 on day 20. Hand-calculated: day0→20,000; day4→15,000; day5,000; day15→ need 8,000, have 5,000 → **loan EMI missed**, balance stays 5,000; day20→ need 5,000, have 5,000 → paid exactly, balance 0. **Expected:** `status='unsolvable'` (loan EMI was missed) even though the final balance is exactly 0 and even though there is nothing left to cut — `missed_obligations` contains exactly one item: the loan EMI, with its due date and the shortfall amount (8,000 - 5,000 = 3,000 paise) at the moment it was missed.

Do not implement `build_plan` yet — these four tests must exist and fail first."
**Files touched:** `/agent/tests/test_engine.py`.
**Why:** Fixture D specifically exists to prevent the single most tempting shortcut implementation — checking only `min(balance across the ledger) >= 0` or `final_balance >= 0` — from passing when it shouldn't. Writing this fixture *before* the implementation means you can't accidentally design the algorithm around a check that happens to pass Fixtures A–C while being wrong in general.
**Acceptance check:** `pytest agent/tests/test_engine.py` — all four tests fail with `NotImplementedError`, not a typo/import error; re-read each fixture's hand-calculation once more yourself before moving on, independent of the test file, to build your own confidence in the numbers.

### Step 7.2 — Core day-by-day simulation (income + essential expenses only, no debts, no cuts)
**Prompt:** "Implement `build_plan` in `/agent/app/engine.py`. For this step only, ignore debts and optional expenses entirely (they're added in Steps 7.3–7.4) — simulate income and essential expenses only. Exact algorithm:

```
def _simulate(income, essential_expenses, debts, today):
    balance = 0
    missed = []
    events = []  # (day_offset, priority_rank, -amount_paise, entry_id) — negative amount so higher amounts sort first within a rank
    for e in income:
        events.append((day_offset(e.current_date, today), 0, None, e))  # income has no priority rank / always applied first on its day
    for e in essential_expenses:
        events.append((day_offset(e.due_date, today), 1, -e.current.amount_paise, e))
    # sort by day, then by priority_rank ascending, then by amount descending (via the negative), then by entry id ascending for full determinism
    events.sort(key=lambda ev: (ev[0], ev[1], ev[2] if ev[2] is not None else 0, ev[3].id))

    ledger = []
    for day_offset_val, priority_rank, _, entry in events:
        if priority_rank == 0:  # income: always applied
            balance += entry.current.amount_paise
        else:  # an obligation: pay in full only if funds suffice
            if balance >= entry.current.amount_paise:
                balance -= entry.current.amount_paise
            else:
                missed.append(MissedObligation(entry_id=entry.id, name=entry.name,
                                                due_date=entry.due_date,
                                                shortfall_paise=entry.current.amount_paise - balance))
        ledger.append(LedgerEntry(day_offset=day_offset_val, balance_paise=balance))
    return balance, missed, ledger
```

Wire this into `build_plan` for Fixtures A and B only (both have no debts and no optional expenses that get cut, so this partial implementation should already make them pass). `status = 'unsolvable' if missed else 'surplus'`. `engine.py` must have zero imports beyond the standard library and Pydantic, per rules.md Section 2 — no dependency on `state.py`'s `SessionState` model beyond reading plain fields is required, but importing `state.py`'s Pydantic models themselves is fine since that file is also dependency-free."
**Files touched:** `/agent/app/engine.py`.
**Why:** The tuple-based event sort with an explicit, fully-specified tie-break chain (`day, priority_rank, amount descending, entry_id ascending`) is what makes the simulation's output deterministic and reproducible — without a final `entry.id` tie-break, two same-day, same-priority, same-amount obligations could sort in either order across different Python versions/runs, which would make a test occasionally flaky for reasons that have nothing to do with a real bug.
**Acceptance check:** Fixtures A and B from Step 7.1 pass; Fixtures C and D still correctly fail (debts not implemented yet, so they'd currently show no missed obligations at all — verify they fail for *that* reason, not a crash).

### Step 7.3 — Add debts with essential-expense-first, then-secured-then-unsecured priority
**Prompt:** "Extend the `_simulate` event-building step to also include every `Debt` in `state.debts`, with `priority_rank = 2` for `kind='loan'` and `priority_rank = 3` for `kind='credit_card'` (so the full ordering is: income=0 always first, essential expenses=1, secured loans=2, credit cards=3 — lower rank number wins when funds are insufficient to cover everything due the same day). Use `min_payment_paise` as the amount for debts, not `balance_paise`. No other change to the algorithm from Step 7.2 — the same sort, same 'pay in full or record as missed' logic applies uniformly across all obligation types now."
**Files touched:** `/agent/app/engine.py`.
**Why:** This is the exact, explicit judgment call from implementation-plan.md Section 5 (essential > secured > unsecured), now expressed as a plain integer rank rather than a scattered if/else chain — this makes the ordering trivially inspectable (just read the four `priority_rank` values) when defending the choice live.
**Acceptance check:** Add a same-day-collision test not in the original fixture set: a loan EMI and a credit-card minimum both due on the same day, with only enough balance for one — assert the loan is paid and the credit card is the one recorded as missed, proving the rank is actually being applied (not just coincidentally correct due to list order).

### Step 7.4 — Optional-expense cut search: exact greedy algorithm, explicitly not optimal
**Prompt:** "Implement cut-candidate search as its own function, called by `build_plan` only when the base `_simulate` (with zero cuts) produces a non-empty `missed` list: `def _find_cuts(state) -> tuple[list[Entry], list[MissedObligation]]`. Exact algorithm: (1) sort `state.optional_expenses` by `amount_paise` descending (cut the biggest optional expenses first — this is a deliberate, simple greedy heuristic, not a guarantee of the *minimum* number of cuts needed; document this trade-off in a code comment referencing that an optimal subset-sum search is out of scope for this timeline); (2) iteratively: take the next expense from the sorted list, add it to a `cuts` list, re-run `_simulate` excluding all entries currently in `cuts`, and check if `missed` is now empty; (3) stop as soon as `missed` is empty (return the current `cuts` list and empty `missed`), or when all optional expenses have been added to `cuts` and `missed` is still non-empty (return the full `cuts` list and the final `missed` list from that last attempt). `build_plan` then sets `status = 'solved_with_cuts'` if the cut search emptied `missed`, else `status = 'unsolvable'` with the `missed` list from the 'cut everything' attempt."
**Files touched:** `/agent/app/engine.py`.
**Why:** Explicitly documenting 'not the minimum number of cuts' in a code comment is important honesty — a knapsack/subset-sum search that finds the *smallest* sufficient set of cuts is a reasonable-sounding but meaningfully harder algorithm to get right under time pressure, and greedy-by-largest-first is a defensible, simple, deterministic stand-in as long as you can name the trade-off, not accidentally claim optimality you didn't build.
**Acceptance check:** Fixture C from Step 7.1 passes, including the specific assertion that `cuts` contains *both* OTT and dining (not just one) — this proves the loop actually continues past the first cut when one cut alone isn't sufficient, rather than stopping after a single iteration by mistake.

### Step 7.5 — Unsolvable-case detail and final wiring
**Prompt:** "Finish `build_plan` per the exact three semantics stated at the top of this phase: after the Step 7.4 cut search, if `missed` is still non-empty, `status='unsolvable'` and `plan.missed_obligations` is exactly that final `missed` list (from the 'all optional expenses cut' attempt) — not from the zero-cuts base run. Confirm Fixture D passes: it has zero optional expenses to begin with, so the 'cut search' loop should run zero iterations and immediately fall through to the base run's `missed` list, which must show the loan EMI as missed with `shortfall_paise=3000_00` (₹3,000) even though the ledger's final balance is exactly 0."
**Files touched:** `/agent/app/engine.py`.
**Why:** Fixture D is the direct test of the second locked-down semantic (status depends on *whether anything was missed*, not on the sign of the final balance) — if this test passes, you have concrete, checked-in proof that the engine doesn't fall into the tempting-but-wrong final-balance-only shortcut.
**Acceptance check:** All four fixtures from Step 7.1 pass. Re-derive Fixture D's expected `shortfall_paise` value (3,000 rupees × 100 = 300,000 paise — note: write out the exact paise number in your test, e.g. `300000`, not `3000_00` as loose informal notation) by hand one more time and confirm it matches what the code produces.

### Step 7.6 — Edge cases beyond the four core fixtures
**Prompt:** "Add these additional edge-case tests and fix any bugs they reveal: (1) zero income entries at all (income list empty) — balance starts and stays 0 until any expense is missed immediately; (2) an essential expense and a debt due on the very first day (day offset 0), same day as income — confirm income is applied before either is evaluated; (3) two optional expenses with the exact same `amount_paise` — confirm the cut search's tie-break (entry `id` ascending, matching Step 7.2's sort convention) produces a deterministic, reproducible order across repeated runs, not one that happens to differ by dict/set iteration order; (4) an entry with `amount_paise` exactly equal to the remaining balance (the exact boundary of 'can afford it') — confirm it is paid in full, not treated as missed (this is the `>=` vs `>` boundary on the payment-affordability check, the mirror image of the `< 0` vs `<= 0` shortfall check called out at the top of this phase)."
**Files touched:** `/agent/tests/test_engine.py`, `/agent/app/engine.py`.
**Why:** Edge cases exactly like these are what a live interrogator will probe for by asking "what if..." questions — better to have a named, passing test for each one already than to reason about it live for the first time under questioning.
**Acceptance check:** Full `pytest agent/tests/test_engine.py -v` green, including all new edge cases; for edge case (4) specifically, confirm the test asserts the entry is NOT in `missed_obligations` when the balance exactly equals the amount owed.

---

## Phase 8 — `finalize_plan` Wiring

**Goal by end of phase:** a full conversation can end with a real, engine-computed plan, narrated (not invented) by the LLM.

### Step 8.1 — `finalize_plan` handler with the missing-fields guard
**Prompt:** "Implement the `finalize_plan` tool handler: if `compute_missing_fields(state)` is non-empty, return a `ToolResult.error` listing what's missing, without calling the engine. Otherwise call `build_plan` and store the result in `state.plan`. This guard must be enforced here in code, not left to the system prompt alone — see implementation-plan.md Section 2.8 and rules.md invariant #5."
**Files touched:** `/agent/app/tools.py`.
**Why:** This is explicitly one of the "ask first" items in rules.md if anyone (including future-you under time pressure) is tempted to remove it — the step exists specifically to make the guard's presence a deliberate, reviewable diff.
**Acceptance check:** Unit test: calling `finalize_plan` on an incomplete state returns an error and does not populate `state.plan`; calling it on a complete state populates `state.plan` correctly.

### Step 8.2 — Final Plan and Proposed Actions cards
**Prompt:** "Create `FinalPlanCard.tsx` showing the day-by-day (or weekly-summarized) ledger and the unsolvable/solved status clearly, and `ProposedActionsCard.tsx` showing any suggested cuts from `state.plan`. Pure rendering only."
**Files touched:** `/frontend/components/cards/FinalPlanCard.tsx`, `ProposedActionsCard.tsx`.
**Why:** This is the "visible calculation trail" differentiator (plan Section 0, #3) — the ledger should genuinely be shown, not summarized away.
**Acceptance check:** With a mock `unsolvable`-status plan and a mock `solved_with_cuts` plan, both render correctly and distinctly.

### Step 8.3 — System prompt: narrate, never invent
**Prompt:** "Update the system prompt so that after `finalize_plan` succeeds, the agent explains the plan using only the numbers returned by the tool result — explicitly instruct it never to state a number it hasn't received from a tool result. Add a few-shot example of good vs. bad narration in the prompt."
**Files touched:** `/agent/app/bot.py` (or wherever the system prompt lives).
**Why:** This is the prompt-side reinforcement of rules.md invariant #1 — the code-side guard (engine) and the prompt-side guard (narration instruction) work together; neither alone is sufficient.
**Acceptance check:** Run a full conversation to a finalized plan; manually verify every number spoken by the agent matches a number in `state.plan` exactly.

### Step 8.4 — `confirm_user_understood`
**Prompt:** "Implement the `confirm_user_understood` tool and add a prompt instruction that the agent must explicitly check comprehension after narrating the plan (e.g. ask if anything is unclear) before calling this tool, per the brief's 'confirm the user understands the plan' requirement."
**Files touched:** `/agent/app/tools.py`, `/agent/app/bot.py`.
**Why:** This is an explicitly graded requirement in the assignment brief, easy to forget once the engine and cards are working — worth its own dedicated step so it doesn't get skipped.
**Acceptance check:** In a full conversation, confirm the agent asks a comprehension-check question before the call would reasonably be considered "done."

---

## Phase 9 — Conversation Quality & Stopping Heuristic

**Goal by end of phase:** the agent asks a reasonable amount, not too little or too much, before finalizing.

### Step 9.1 — Verify missing-fields injection is driving question order
**Prompt:** none — this is a review/tuning step, not new code.
**Why:** Confirms Step 4.8's context injection is actually influencing the conversation, not just sitting unused in the prompt.
**Acceptance check:** Have a conversation where you deliberately withhold debt information; confirm the agent proactively asks about debts before attempting to finalize.

### Step 9.2 — Implement the bounded completeness pass
**Prompt:** "Update the system prompt so that once the hard-minimum fields are present, the agent makes exactly one additional pass asking if there's anything else (other loans, subscriptions, upcoming bills) before finalizing, then proceeds even if the user says no more — it should not ask this more than once, per implementation-plan.md Section 13.6."
**Files touched:** `/agent/app/bot.py`.
**Why:** This is the precision/recall trade-off from the deep dive, made concrete — the "exactly one pass, then proceed" framing is what prevents the annoying-vs-incomplete failure modes on both ends.
**Acceptance check:** In a test conversation, confirm the agent asks the completeness question once and does not repeat it if you say "that's everything."

### Step 9.3 — Manual conversation quality pass
**Prompt:** none — manual testing step.
**Why:** This is where you personally judge whether the conversation "feels" natural per the brief's qualitative requirements, which no unit test can fully capture.
**Acceptance check:** Run at least three full conversations with different phrasing styles/orders of information; confirm none of them feel scripted and all of them reach a finalized plan.

---

## Phase 10 — Corrections & Conflicts End-to-End

**Goal by end of phase:** verified, in live voice, that the conflict/duplicate mechanisms from Phase 4 actually work when driven by real speech and STT, not just unit tests.

### Step 10.1 — Scripted correction test
**Prompt:** none — manual test, following a script you write yourself.
**Why:** Unit tests proved the logic works on clean input; this proves it survives real STT noise and conversational phrasing.
**Acceptance check:** State an income figure, then later say something like "actually, that salary number should be higher, more like X" where X is >15% different — confirm the agent asks for confirmation rather than silently updating.

### Step 10.2 — Scripted duplicate test
**Prompt:** none — manual test.
**Acceptance check:** Mention "rent" early, then later mention "house rent" with a similar amount — confirm the system flags a possible duplicate rather than creating two full entries, and that the agent asks a clarifying question about it.

### Step 10.3 — Fix and immediately test
**Prompt:** "[Describe the specific bug found in 10.1/10.2]. Fix it in the relevant handler, and add a regression test in test_tools.py reproducing the exact scenario before fixing it."
**Files touched:** depends on the bug — likely `/agent/app/tools.py`, `/agent/tests/test_tools.py`.
**Why:** Per rules.md Section 6, every bug found this way must become a permanent regression test in the same session — this is also your evidence for the optional depth track if you pursue Track B.
**Acceptance check:** The new regression test fails against the old code (verify by temporarily reverting) and passes against the fix.

---

## Phase 11 — Lightweight Evaluation Harness (Track B)

**Goal by end of phase:** a text-only test harness exists that can run scripted conversations without audio, per implementation-plan.md Sections 2.11 and 13.12.

### Step 11.1 — Build the harness
**Prompt:** "Create `/agent/tests/test_conversation_harness.py` with a helper that feeds a list of scripted user text turns directly into the LLM+tools loop (bypassing Daily/STT/TTS entirely), and returns the final `SessionState` for assertions."
**Files touched:** `/agent/tests/test_conversation_harness.py`, possibly a small refactor of `bot.py` to expose the LLM+tools loop independently of the Daily transport.
**Why:** This harness is your safety net if live voice latency or STT accuracy is flaky on demo day — you can demonstrate correctness independent of the audio stack.
**Acceptance check:** Running the harness with a trivial scripted conversation produces a sensible final state without needing a Daily room or audio hardware.

### Step 11.2 — Golden transcript tests
**Prompt:** "Write golden-transcript tests using the harness: (1) a plain happy-path intake, (2) a mid-conversation correction, (3) an ambiguous reference ('the other one'), (4) a conflicting restatement that should trigger a pending conflict, (5) a malformed/nonsensical amount that should trigger a validation error path."
**Files touched:** `/agent/tests/test_conversation_harness.py`.
**Why:** This is the specific test set called out in implementation-plan.md Section 13.12 as the highest-value testing investment beyond the engine itself.
**Acceptance check:** All five pass; keep the exact scripted transcripts in the test file as readable, reviewable fixtures — they're good material to show live if asked "how did you test this."

### Step 11.3 — Document one found failure with before/after evidence
**Prompt:** "[Once a harness test reveals a real failure] Show me the failing assertion, then fix the underlying handler, and confirm the test now passes."
**Files touched:** varies.
**Why:** The brief's optional-depth Track B explicitly asks for "at least one failure you found, the change you made, and evidence that the change improved the system" — this step produces exactly that artifact.
**Acceptance check:** You can show a git diff spanning: failing test → code fix → passing test, as a single reviewable unit.

---

## Phase 12 — Packaging

**Goal by end of phase:** `docker compose up --build` from a clean checkout works, with everything documented.

### Step 12.1 — Finalize `docker-compose.yml`
**Prompt:** "Review docker-compose.yml end to end: confirm both services build and start correctly with the real (not placeholder) run commands, environment variables are passed through from a root `.env` file, and no manual steps are required beyond `docker compose up --build`."
**Files touched:** `docker-compose.yml`, Dockerfiles.
**Why:** This is a literal, explicit grading criterion — "the complete application must start with one command."
**Acceptance check:** From a completely fresh clone (or `git stash` everything uncommitted), run `docker compose up --build` and confirm the app is usable end to end with no extra terminal commands.

### Step 12.2 — Finalize `.env.example` and README
**Prompt:** "Review .env.example against every environment variable actually referenced in the codebase (grep for `os.environ`/`process.env`); add any missing ones with comments. Fill in the README's Setup, Environment Variables (as a table: variable, purpose, required y/n), Running the App (exact command + exact local URL), and Testing sections."
**Files touched:** `.env.example`, `README.md`.
**Why:** Directly satisfies the submission requirements around documented setup and env vars.
**Acceptance check:** Have someone else (or yourself, pretending to be a reviewer with zero context) follow the README literally and successfully get the app running.

### Step 12.3 — Full clean-machine test
**Prompt:** none — manual verification step.
**Why:** This is the actual acceptance bar the reviewers will apply — don't skip a true from-scratch test.
**Acceptance check:** `docker compose down -v`, remove any local images/volumes, `docker compose up --build` from scratch, confirm a full conversation to a finalized plan works.

### Step 12.4 — Lint/format/test final pass
**Prompt:** "Run black, ruff, and mypy across `/agent`, and eslint/prettier across `/frontend`. Fix any issues. Run the full pytest suite and confirm everything is green."
**Files touched:** varies.
**Why:** Final compliance check against rules.md Section 3/4.
**Acceptance check:** All linters/formatters/type-checkers clean; full test suite green.

---

## Phase 13 — Demo & Submission Prep

**Goal by end of phase:** everything the submission form asks for is ready.

### Step 13.1 — Demo video script
**Prompt:** none — this is a human task, not a Copilot task; but you can ask Copilot to help you draft a *neutral outline* of what to show, not the narration itself.
**Why:** The three differentiators from implementation-plan.md Section 0 (confidence tagging, explicit unsolvable handling, visible calculation trail) are exactly the moments worth highlighting on camera.
**Acceptance check:** Your recorded video shows a real correction being handled and, ideally, one unsolvable or shortfall scenario, not just a clean happy path.

### Step 13.2 — "What works / doesn't / next / AI helped / AI failed" list
**Prompt:** none — write this yourself, from your own commit history and the failures you actually hit (Phase 10.3, Phase 11.3 are good source material).
**Why:** This is a required submission item and reads much better when grounded in real, specific incidents rather than generic statements.
**Acceptance check:** Every bullet point references something concrete you can point to (a commit, a test, a specific bug) if asked to elaborate live.

### Step 13.3 — Decision journal reminder
**Prompt:** none — never delegate this to Copilot, per rules.md Section 1 and the assignment's explicit rules.
**Why:** AI-authored journal content disqualifies the submission outright.
**Acceptance check:** Your journal has entries with real timestamps spread across the two days, not all written in one sitting at the end — the assignment explicitly asks you to write while working, not only after.
