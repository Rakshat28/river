# Project Rules — Riverline Voice Finance Assistant

**For: Gemini Antigravity (and any other agentic coding tool reading this file)**

> **Placement note:** Antigravity reads a root-level `AGENTS.md`/`GEMINI.md`, or files under `.agents/rules/`. If Antigravity in your environment isn't picking this up automatically, copy this file to `AGENTS.md` at the repo root, or split it into `.agents/rules/*.md` — the content is what matters, not the filename.

---

## 0. How to use this file

This is not a generic style guide. Section 1 encodes **decisions already made for this project** — the agent must not silently re-decide them while generating code. Sections 2+ are conventional clean-code/structure rules. If a task seems to require violating Section 1, **stop and ask the human instead of proceeding** — these are the decisions the project owner is expected to defend live and cannot discover mid-review that the agent quietly changed.

---

## 1. Non-Negotiable Architectural Invariants

These come directly from the project's design document. Violating any of these is not a style issue — it breaks the grading criteria of the assignment this project is built for.

1. **The LLM never performs financial arithmetic.** All money math lives in `agent/app/engine.py` as plain, deterministic Python. No prompt, tool description, or system message may ask the model to compute a sum, balance, or shortfall itself. If a feature seems to need the LLM to "just calculate something," that calculation belongs in the engine, exposed via a tool, not inline in a completion.
2. **`SessionState` is the single source of truth.** No card, no frontend component, and no LLM-facing summary may maintain its own derived numbers. Every displayed value must be computed from `SessionState` (or its derived fields) at read time — never cached independently in a way that can drift.
3. **Every financial fact carries a confidence tag** (`confirmed` | `estimated`) and, where corrected, a history entry (see the implementation plan, Section 13.4). Do not add a field to the data model that skips this.
4. **Tool calls are the only way the LLM mutates state.** Never parse free-text LLM output for facts with regex/string-matching as a shortcut — that bypasses the validation and conflict-detection layer entirely.
5. **`finalize_plan` must be blocked in code, not just discouraged in the prompt**, when minimum required fields are missing. If asked to "make this simpler" by removing the guard and relying on prompting alone, refuse and flag it — this is an explicit, tested requirement, not a nicety.
6. **State is in-memory, per-session, non-persistent by design** (documented limitation, not an oversight). Do not add a database or Redis without being explicitly asked — it's out of scope on purpose and changes the Docker Compose story.
7. **No secrets, tokens, or API keys in code, comments, logs, or test fixtures — ever**, including in "temporary" debug code. All secrets come from environment variables documented in `.env.example`.
8. **The decision journal (`DECISION_JOURNAL.md`) is human-authored and off-limits to the agent.** Never create, edit, append to, or suggest content for this file. If asked to "help write the journal," decline and explain why (per the assignment rules).
9. **English only.** Do not add i18n/locale scaffolding — it's explicitly out of scope.

---

## 2. Repository Structure (authoritative — do not restructure without approval)

```
/frontend
  /app                    # Next.js App Router routes
  /components/cards       # One component per card type (Section 6 of the plan)
  /components/ui          # Small shared presentational components
  /lib                     # Daily client wrapper, API client, types
  /lib/types.ts            # Mirrors the backend Pydantic models — keep in sync
/agent
  /app
    main.py               # FastAPI app: /api/session, /api/state/{room}
    bot.py                # Pipecat pipeline construction/wiring only
    tools.py              # Tool-call handlers (add_income, add_expense, ...)
    engine.py             # Deterministic finance engine — pure functions only
    state.py              # SessionState model + derived-field computation
    validation.py         # Pydantic schemas for tool arguments
  /tests
    test_engine.py
    test_tools.py
    test_conversation_harness.py
docker-compose.yml
.env.example
README.md
```

Rules:
- New files go where this tree implies, not wherever is convenient. If a new concept doesn't obviously fit, ask rather than inventing a new top-level folder.
- `bot.py` wires the pipeline; it must not contain business logic. If you find calculation or validation logic creeping into `bot.py`, move it to `engine.py` / `validation.py`.
- `engine.py` must have **zero imports from Pipecat, FastAPI, or any LLM SDK**. It should be importable and testable with nothing but the standard library plus Pydantic. This is a hard boundary — if `engine.py` ever needs to import an LLM/network client, that's a sign logic is misplaced.

---

## 3. Python / Backend Standards

- **Formatting/linting:** `black` (default settings) + `ruff`. Run both before considering any change done. No manual formatting debates — defer to the tools.
- **Typing:** full type hints on every function signature, including return types. `mypy`-clean is the target; don't suppress type errors with `# type: ignore` without a one-line comment explaining why.
- **Data crossing any boundary (tool args, API request/response bodies, state) must be a Pydantic model.** Plain dicts are acceptable only as short-lived local variables, never as function signatures across module boundaries.
- **Async correctness:** Pipecat's pipeline is async; tool handlers should be `async def` even if the body is currently synchronous, to keep the calling convention consistent and avoid blocking the event loop later if a handler grows I/O.
- **No bare `except:`.** Catch specific exceptions. When a tool handler fails validation, return a structured tool-error string (per the plan's Section 13.9) instead of raising — raising should be reserved for genuine bugs, not expected user-input problems.
- **Logging, not `print`.** Use the standard `logging` module. Structured, leveled logs (`logger.info`, `logger.warning`). **Never log full financial figures at a level that could end up in shared/aggregated logs** — log field *names* and *event types* ("income entry updated"), not necessarily raw amounts, if you're ever wiring up anything beyond local dev logging.
- **Function length:** if a function exceeds ~40 lines or is doing more than one clearly nameable thing, split it. This applies especially to tool handlers and pipeline setup in `bot.py`.
- **Docstrings:** every public function/class gets a one-to-three-line docstring stating *what* it does and, if non-obvious, *why* (e.g. why a threshold is 15%, why a check exists) — cross-reference the implementation plan's section number when a design rationale lives there, so future readers (including you, live, in the interview) can find the reasoning fast.
- **Dependency management:** pin versions in `requirements.txt`. Don't add a new dependency for something the standard library or an existing dependency already covers.

Example of the expected shape for a tool handler:

```python
async def add_income(name: str, amount: float, date: str, confidence: Confidence) -> ToolResult:
    """Register a new income entry. See implementation-plan.md Section 13.3 for
    the duplicate-detection safety net applied here."""
    validated = IncomeInput(name=name, amount=amount, date=date, confidence=confidence)
    if (existing_id := find_near_duplicate(state.income, validated)) is not None:
        flag_possible_duplicate(existing_id)
        return ToolResult.warning(f"possible duplicate of existing entry {existing_id}")
    entry = state.add_entry(validated)
    broadcast_state_update()
    return ToolResult.ok(entry_id=entry.id)
```

---

## 4. TypeScript / Next.js Frontend Standards

- **App Router only.** No `pages/` directory.
- **Strict TypeScript.** `strict: true` in `tsconfig.json`. No `any` — if a type is genuinely unknown (e.g. a raw Daily SDK event payload), narrow it with a type guard rather than casting.
- **One component per card type**, matching the card list in the implementation plan's Section 6. Each card component takes the relevant slice of state as props — it does not fetch or compute anything itself. Cards are dumb renderers; all computation happens server-side in `engine.py`/`state.py`.
- **State management:** React `useReducer` + Context only. Do not introduce Redux/Zustand/Jotai — the state shape is small and this would be unjustified complexity for a 2-day, single-session app.
- **Styling:** Tailwind utility classes only; no inline `style={{}}` unless truly dynamic (e.g. a computed width for a progress bar), and no separate CSS-in-JS library.
- **Types mirror the backend.** `lib/types.ts` should structurally match the backend Pydantic models in `state.py`. If you change one, change the other in the same commit — do not let them drift.
- **Naming:** PascalCase for components (`IncomeCard.tsx`), camelCase for functions/variables, kebab-case for non-component file names (`daily-client.ts`).
- **No business logic in components.** Formatting/currency display helpers are fine in components; shortfall calculations, prioritization logic, etc. are not — those already exist server-side and should be trusted, not recomputed client-side.

---

## 5. Cross-Cutting Concerns

### Environment variables & secrets
- Every environment variable used anywhere in the codebase must have a corresponding entry in `.env.example` with a comment explaining what it's for and whether it's required.
- Never commit a real `.env` file. If one is accidentally created during a task, delete it before finishing, don't just `.gitignore` it after the fact.
- When adding a new third-party service (a new STT/TTS vendor, for instance), add its key to `.env.example` and update the README's env-var table in the same change — don't leave documentation for later.

### Error handling & user-facing failures
- Any backend error surfaced to the frontend must be a clean, typed error response — never a raw stack trace or exception string leaked to the client.
- Frontend must handle the "agent/session failed to start" and "call dropped" cases explicitly with a visible UI state — not a silent blank screen.

### Privacy
- This system handles real financial data. Treat all income/expense/debt figures as sensitive by default: no analytics/telemetry calls that would transmit raw figures to a third party, no verbose request logging that dumps full request bodies containing financial details.

---

## 6. Testing Standards

- **Engine tests (`test_engine.py`) are the highest-priority tests in the repo.** Every function in `engine.py` must have unit tests covering: surplus case, exact break-even, shortfall solved by cuts, shortfall unsolvable even after cuts, and at least one edge case with zero/missing income.
- **Tool-handler tests (`test_tools.py`)** must cover: successful add, successful update, conflict-threshold triggering, duplicate-detection triggering, and malformed-input rejection (validation error path).
- **Conversation harness tests (`test_conversation_harness.py`)** run scripted text-only user turns through the LLM+tools pipeline (bypassing STT/TTS) and assert on the resulting `SessionState`. At minimum: a plain happy path, a mid-conversation correction, an ambiguous reference, and a conflicting restatement.
- **Test-first for the engine.** When implementing or modifying `engine.py`, write or update the relevant test in the same change — this file is the one place in the codebase where "looks right" is not an acceptable substitute for "asserted correct."
- Frontend component tests are lower priority given the timeline; if added, use React Testing Library and focus on card rendering given a fixed state snapshot, not on Daily/WebRTC integration (not worth mocking under time pressure).
- Every bug found during manual testing gets turned into a regression test in the same session it's fixed — don't defer this "for later."

---

## 7. Git & Commit Conventions

- **Conventional Commits** style: `feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`. Example: `feat(engine): add cut-prioritization for optional expenses`.
- **Small, atomic commits.** One logical change per commit — this also makes it easier to reconstruct your own timeline when writing the (human-authored) decision journal afterward.
- Never bundle a dependency bump with a feature change in the same commit.
- Do not commit generated artifacts (`node_modules/`, `__pycache__/`, `.next/`, build output).

---

## 8. Documentation Requirements

- Update `README.md` in the same change whenever you: add an environment variable, add an API endpoint, add a new Docker service, or change the startup command.
- Keep the repository structure in this file (Section 2) in sync with reality — if you add a new top-level module, add it here too, in the same change.
- Prefer a short comment explaining *why* a non-obvious decision was made (e.g. "15% threshold — see implementation-plan.md §13.5") over a longer comment explaining *what* the code does, which should be clear from naming.

---

## 9. What the Agent Should Do Autonomously vs. Ask First

**Proceed autonomously:**
- Formatting, linting, type-fixing.
- Writing tests for existing untested code.
- Fixing a clearly-identified bug with a test proving the fix.
- Adding a missing `.env.example` entry for an already-used variable.
- Refactoring within a single file that doesn't change behavior.

**Ask first:**
- Any change to the tool schema (`tools.py` function signatures) — this is a core, defended design decision (implementation plan Section 4/13).
- Any change to conflict thresholds, priority ordering, or stopping heuristics in the engine or prompt — these are explicit judgment calls the project owner must be able to defend, not something to be silently tuned.
- Adding any new third-party dependency, service, or infrastructure component (Redis, a DB, a new voice vendor).
- Anything touching `DECISION_JOURNAL.md` — never do this; always decline.
- Any change that would make `docker compose up --build` require more than one command or a manual step.

---

## 10. Quick Reference

| Do | Don't |
|---|---|
| Compute all financial numbers in `engine.py` | Ask the LLM to compute or double-check a total |
| Mutate `SessionState` only via tool handlers | Regex/parse free text for facts as a shortcut |
| Tag every fact `confirmed`/`estimated` | Add an untagged numeric field to the data model |
| Return structured tool-errors on invalid input | Let a malformed tool call raise an unhandled exception |
| Keep `engine.py` dependency-free (stdlib + Pydantic) | Import FastAPI/Pipecat/LLM SDKs into the engine |
| Write/update tests in the same change as logic changes | Defer testing "until everything is built" |
| Ask before changing thresholds/priorities/schema | Silently "improve" a judgment-call design decision |
| Keep `.env.example` and README in sync with real usage | Leave an env var undocumented |
| Write conventional, atomic commits | Bundle unrelated changes into one commit |
| Leave `DECISION_JOURNAL.md` untouched | Draft, edit, or suggest journal content |