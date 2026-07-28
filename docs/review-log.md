# Review Log — Stock Advisory Agent

**Owner:** reviewer (read-only on everything else). **Format:** ID (REV-NNN), tag, severity
(blocker/major/minor), location, description, suggested owner. Every pass is re-run in full on each
review cycle; previously logged items are re-checked and marked RESOLVED with date when fixed.

---

## Passes 1–13 (2026-07-12 through 2026-07-28) — archived

Passes 1–13 are archived in full to `docs/archive/review-log-archive.md` per `CLAUDE.md`'s doc-hygiene
rule; Pass 13 was archived 2026-07-28 at this Pass 14's close, with its per-finding closing disposition
appended there. Nothing from Passes 1–12 remains open. The still-open items from Pass 13 and earlier are
carried forward in full below and are **not** in the archive as open work. Agents never read
`docs/archive/` per `CLAUDE.md`.

---

## Carried forward — open items from Pass 13 and earlier (re-checked at Pass 14)

**Diff-scope note.** INC-4 changed nine files (`docs/archive/test-report-archive.md`,
`docs/design/non-functional-ops.md`, `docs/handoff.md`, `docs/test-report.md`, `pages/prices.json`,
`scripts/ai_judge.py`, `scripts/ai_provider.py`, `scripts/config.py`, `tests/conftest.py`). Of the items
below, only REV-065 lives in a file INC-4 touched; it was re-read this pass and its line citations
updated. The rest are in files unchanged since `5fc452a`, so they are carried verbatim — unchanged file,
unchanged finding.

**Majors (3 IDs / 2 pieces of work)**

- **REV-039 (doc half) + REV-064 — `[DESIGN-GAP]` — major — owner: release. One edit closes both.**
  `docs/runbook.md:46-51` (§2.2) still instructs the operator to create six model Variables
  (`GEMINI_MODEL`, `GEMINI_MODEL_BACKUP`, `NSE_GEMINI_MODEL`, `NSE_GEMINI_MODEL_BACKUP`,
  `DISCOVERY_GEMINI_MODEL`, `DISCOVERY_GEMINI_MODEL_BACKUP`) that nothing reads — both workflow YAMLs
  mention them only in comments (`hourly-watchlist.yml:51-52`, `daily-discovery.yml:48-49`) pointing at
  `scripts/config.py` as the source of truth; zero `${{ vars.* }}` wiring. Same staleness at
  `docs/runbook.md:339` (§7 re-lists all nine Variables) and `:390` (§8 still recommends a Variable edit
  "for model swaps", now false for exactly that case). The three retry Variables
  (`GEMINI_MAX_RETRIES`, `GEMINI_RETRY_BASE_MS`, `GEMINI_TIMEOUT_MS`) **are** still wired
  (`hourly-watchlist.yml:67`, `daily-discovery.yml:61`) and must not be removed.
- **REV-043 — `[CODE-GAP]` — major — owner: dev.** `ingest.get_price_only(ticker)` is designed
  (`components.md` §4.2, `non-functional-ops.md:65-66`) but still absent from `scripts/ingest.py`;
  `publish_prices.py` still pulls a full `get_market_data()` per ticker. Live-system efficiency fix, not
  gated on any increment.

**Minors (11 IDs)**

- **REV-063 (residual) + REV-071 — minor — owner: dev. One edit to two SQL headers.**
  `sql/kill_switch.sql:8-17` still restates the apply order inline and contains no reference to
  `docs/runbook.md` at all; `sql/schema.sql:32-37` still enumerates a five-file order that omits
  `sql/kill_switch.sql` (naming `scheduler_pgcron.sql` first, which §2.3 established is wrong), though it
  does now point at §2.3 at `:37`. REV-071: `docs/runbook.md:70` asserts that both SQL headers "point
  back here rather than restating it" — a cross-reference state that does not exist in either file. If
  the dev half is declined, `:70`'s claim must instead be softened by release to match reality.
- **REV-065 — `[DESIGN-GAP]` — minor — owner: tech-lead. Line numbers re-derived at Pass 14 (INC-4's §9
  edit shifted them ~6 lines).** `docs/design/non-functional-ops.md:161-169` still presents
  `${{ vars.X || '<default>' }}` as the repo's established convention "used throughout
  `hourly-watchlist.yml` (`GEMINI_MODEL`, `GEMINI_MAX_RETRIES`, …)" — true only for the retry keys; the
  model keys deliberately have no Variable wiring (`config.py:19-24`). `:193-196` describes the same
  abandoned wiring as a "harmless, unread vestige".
- **REV-066 + REV-052 — minor — owner: tech-lead + pm.** `NTFY_BASE_URL` / `NTFY_TIMEOUT_SECONDS`
  (`config.py:120-121`) are absent from every config audit baseline; a repo-wide grep of `docs/` still
  returns zero hits. Same root cause and same fix location as REV-074 below.
- **REV-067 — `[DESIGN-GAP]` — minor — owner: tech-lead.** `docs/design/components.md:50-56`'s citation
  table is stale after the REV-062 reconciliation: rows 5–6 cite `phase5_monitoring.sql:125`/`:153` (now
  `:182`/`:185`); row 7 says `interval '70 minutes'` appears in "three copies" at `:129,157,229` (now two,
  at `:194` and `:279` — the count is the thing the table exists to track); rows 1–4 still cite
  `scheduler_pgcron.sql:279` in a 184-line file and put `dispatch_watchlist_if_open()` in the wrong file
  (it is `phase5_monitoring.sql:318-338`).
- **REV-068 — `[REQUIREMENTS-GAP]` — minor — owner: pm.** `docs/requirements.md` still has zero
  `two-tier`/`fail-loud`/`SystemExit` hits for the INC-6 tunables chain and still names the stale
  `config/tunables_cache.json` path (the cache is repo-root, REV-046).
- **REV-070 — minor — owner: qa + release.** INC-3's AC1–AC5 remain unexecuted against a live Supabase
  project per Arjun's explicit deferral. Not a defect; a scheduling obligation owed at apply time. Phase-4
  closure must not treat FR24/FR25/FR26 as verified until it happens.
- **REV-072 — `[BLOAT]` — minor — owner: tech-lead.** `sql/phase5_monitoring.sql:274-275` re-derives
  inline the exact session predicate `:182-188` already computed into `v_session_active`, so the four
  session-bound literals appear twice each in one function. Suggested fix: `if v_session_active then`.
- **REV-048 — minor — owner: qa.** Constants/citation drift test still not built.
- **REV-049(b) — minor — owner: release.** Portal CI story still undecided; due before INC-5 starts.

---

## Pass 14 — 2026-07-28 (INC-4 diff-scoped audit: AI provider abstraction, FR33)

**Scope.** Diff-scoped to `git diff --name-only 5fc452a..HEAD` (Pass 13 cleared at `5fc452a`), supplied
pre-run by the orchestrator: `docs/archive/test-report-archive.md`, `docs/design/non-functional-ops.md`,
`docs/handoff.md`, `docs/test-report.md`, `pages/prices.json` (excluded — automated live price-snapshot
refresh, unrelated to INC-4), `scripts/ai_judge.py`, `scripts/ai_provider.py`, `scripts/config.py`,
`tests/conftest.py`. Plus traceability of the ID INC-4 claims (**FR33**) end to end, and a read of the
unchanged files the increment makes claims *about* (`scripts/run_hourly.py`, `scripts/run_discovery.py`,
`tests/test_ai_judge.py`, `tests/test_import_smoke.py`, `docs/requirements.md` §5.12/§10,
`docs/design/operational-controls.md` §14, `docs/design/increment-plan.md` INC-4).

**Method.** Every AC claim in `docs/test-report.md` and `docs/handoff.md` was treated as a claim to be
tested, not evidence. Where a claim asserted something about a file the increment did **not** change, I
opened that file (this is what produced REV-073, REV-074 and REV-076). qa's verification was genuinely
independent and its five PASSes hold up — see "What is in good shape" for the specific re-derivations.

**Method caveat (standing, unchanged since Pass 2, and materially binding this pass):** no shell/execute
tool this session. I cannot run `git diff`, `pytest`, or any live call. Consequences, stated so the
verdict's basis is not overstated:
- I verified the *current* content of every changed file directly, and verified `run_hourly.py` /
  `run_discovery.py` are untouched two ways: (a) they are absent from the orchestrator's pre-run
  changed-file list, and (b) by direct read — `run_hourly.py:82-83` and `run_discovery.py:95-98` still
  call `ai_judge.judge_batch(...)` with exactly the pre-INC-4 argument shapes design §14.3 specifies, and
  a repo-wide grep shows zero `ai_provider`/`genai`/`provider=` references in either file. That is
  independent corroboration of AC3, not a restatement of qa's `git show --stat`.
- I could **not** diff the pre-INC-4 `ai_judge.py` myself. Behavior parity is established below from four
  independent sources instead of a diff; the one residual that neither qa nor I can fully close is noted
  under "Residual risk", and it is AC6's job.

---

### 1. Pass 1 — Traceability, requirements → code (FR33)

**Complete, with one test-side gap (REV-077).**

| Link | Location | Status |
|---|---|---|
| Requirement | `docs/requirements.md` §5.12 FR33 + Decision #26 (§8 row 26) | present |
| Design | `docs/design/operational-controls.md` §14.1 (decision), §14.2 (interface), §14.3 (`ai_judge.py` after), §14.4 (config), §14.5 (coverage) | present |
| Plan | `docs/design/increment-plan.md:82-98` (6 ACs) | present |
| Config surface | `docs/design/non-functional-ops.md:138-140` (core baseline) — **but not** `requirements.md` §10 (REV-074) | partial |
| Implementation | `scripts/ai_provider.py` (whole file); `scripts/ai_judge.py:8-11,21,82-83,148-184,242-263,300-302,318-320`; `scripts/config.py:61-66` | present |
| Tests | `tests/test_ai_judge.py` (unchanged; exercises `GeminiProvider.generate` + `_classify` through the `ai_provider._client` seam); `tests/conftest.py:83-106`; `tests/test_import_smoke.py:17` (globs `scripts/*.py`, so `ai_provider.py` is auto-covered — I confirmed the glob, qa's claim is correct) | present, except `get_provider()` (REV-077) |

**§14.2 conformance, field by field.** I compared the design's fenced interface block
(`operational-controls.md:255-297`) against `scripts/ai_provider.py:21-67` line by line: `TokenUsage`
(4 optional int fields incl. `thoughts`), `ProviderResult` (`text`, `usage`), `ErrorClass` (`str, Enum`,
exactly `RETRYABLE`/`FATAL`), `ProviderError` (`detail` + `error_class`, docstring intact),
`BatchVerdictSchema` (frozen, both tuple defaults), `AIProvider` (ABC, one keyword-only abstract
`generate`). Match is exact, including docstrings. `get_provider()` (`:160-165`) matches
`operational-controls.md:307-313` character for character.

**§14.3 conformance.** `ai_judge._generate()` (`:169-184`) matches the design's reference implementation
(`operational-controls.md:327-341`) character for character: same `cap_s = retry_base_ms * (2 ** retries)
/ 1000.0`, same `delay_s = random.uniform(0, cap_s)` full-jitter draw, same increment-then-log-then-sleep
order, same log text. `_parse_batch()` and the prompt builders are untouched provider-neutral product
logic, as §14.3 requires.

**Gemini-specific logic carried over — the "did anything get dropped" check.** Every element the handoff
lists as removed from `ai_judge.py` has a live counterpart in `ai_provider.py`, and each matches the
behavior §14.2 specifies:

| Removed from `ai_judge.py` | Now at | Verified |
|---|---|---|
| `_client()` | `ai_provider.py:127-136` | `genai.Client(api_key=..., http_options=types.HttpOptions(timeout=timeout_ms))`, with the slow-but-billed-response root-cause comment preserved |
| `_usage()` | `:93-103` | all four counts, incl. `thoughts_token_count`; `None` when `usage_metadata` absent |
| `_is_retryable()` | `_classify()`, `:81-90` | httpx timeout / bare `TimeoutError` → RETRYABLE; `.code` / `.status` membership → RETRYABLE; else FATAL — the exact conditions and order §14.2:303-305 specifies |
| `_RETRYABLE_CODES` / `_RETRYABLE_STATUSES` | `:77-78` | `{429,503,504}` / `{UNAVAILABLE, DEADLINE_EXCEEDED, RESOURCE_EXHAUSTED}`, with the 2026-07-07 outage rationale preserved |
| `_RESPONSE_SCHEMA` | `_response_schema()`, `:106-124` | ARRAY of OBJECT, four properties, all four `required`, `property_ordering` preserved, enums sourced from `BatchVerdictSchema` |
| call config (`response_mime_type`, `system_instruction`, `temperature=0.2`) | `:146-151` | present, matching §14.2:301-303 |

**Behavior parity of the retry/backoff path — re-derived independently, not taken from qa.** Four
mutually independent sources agree, which is why I accept AC4 without a diff of my own:
1. The code matches the design's reference implementation character for character (above). The design was
   written before implementation, so it is not downstream of the code.
2. `scripts/config.py:73-89` — comment text that pre-dates INC-4 and was not part of this change —
   documents the intended policy as "3 retries after the initial attempt", "10s -> 20s -> 40s", "slept
   with FULL jitter (uniform 0..computed delay)". `cap_s = retry_base_ms * (2 ** retries) / 1000.0` with
   `random.uniform(0, cap_s)` reproduces exactly that, for `retries = 0,1,2`.
3. `tests/test_ai_judge.py` is unmodified (it is absent from the changed-file list) and pins the observable
   contract: `retry_count == 0` on a clean first attempt (`:51`), `retry_count == config.GEMINI_MAX_RETRIES`
   after a primary that raises `FakeAPIError(code=503, status="UNAVAILABLE")` on every attempt (`:118-130`),
   primary attempted `max_retries + 1` times then backup once (`:130`), and `retry_count == 0` with **no**
   retry for a deterministic `404 NOT_FOUND` (`:135-146`). Those are exactly the retryable/fatal
   classification boundaries, asserted by tests written against the *pre-INC-4* implementation.
4. The `fallback_from` string format documented in `docs/design/data-and-flow.md:62` —
   `f"{model}: {type(exc).__name__}: {str(exc)[:200]}"` — is still produced, now composed across the
   module boundary (`ai_provider.py:156` builds `{type}: {msg[:200]}`, `ai_judge.py:306` prefixes
   `{model}: `). The stored/logged text is byte-identical to the documented pre-INC-4 shape.

The one thing the tests do **not** pin is the jitter *formula* (`time.sleep` is stubbed and the delay is
never asserted), so that rests on sources 1 and 2 — which is sufficient, since both are independent of
the implementation.

**Residual risk neither qa nor I can close statically.** §14.2's enumeration of the pre-refactor call
shape is my only description of the old `types.GenerateContentConfig(...)`. If the pre-INC-4 call carried
a kwarg §14.2 does not enumerate (e.g. `safety_settings`, `thinking_config`, `max_output_tokens`), its
loss would be invisible to a design-conformance read, and qa's diff read did not explicitly enumerate
that check. Nothing in the config surface, the tests, or the design suggests such a kwarg existed, and the
`thoughts` token field's survival suggests thinking behavior is unchanged — so this is a low-likelihood
residual, not a finding. **It is closed by AC6's live smoke test**, which should compare a real verdict's
shape and `usage.thoughts` against a pre-INC-4 `call_log` row rather than merely checking that verdicts
come back.

### 2. Pass 2 — Traceability, code → requirements (scope creep)

**Clean. No `[SCOPE-CREEP]`.** The only public-surface addition is `judge_batch()`'s optional
`provider=None` parameter, which `operational-controls.md:346-347` explicitly specifies. `_enrich()`'s new
`dataclasses.asdict()` conversion (`ai_judge.py:284`) exists solely to preserve the pre-existing plain-dict
return contract across the new `TokenUsage` dataclass — contract preservation, not new behavior. No new
dependency (`google-genai` and `httpx` were already present; only the importing module changed). Nothing
in the diff does anything outside FR33/§14.

### 3. Pass 3 — Hardcoding audit

One minor, pre-existing and design-named: **REV-078**. `config.AI_PROVIDER` itself is correctly
env-driven with a default and correctly documented in the design's config baseline. No CI/lint output
available this session (no shell), so this pass was manual against `non-functional-ops.md` §9.

### 4. Pass 4 — Leanness audit

**No dead code from the refactor.** I checked every import and symbol in both changed scripts:
`ai_judge.py`'s imports are all live (`dataclasses`:284, `json`:207, `random`:180, `time`:184,
`datetime`:269, `BatchVerdictSchema`:82/149, `ErrorClass`:177, `ProviderError`:176, `TokenUsage`:150
annotation, `get_provider`:263, `clip`:234); `ai_provider.py`'s are too (`httpx`:85 for the exception
type only, `genai`:136, `types`:111-146, `config`:161-162). No commented-out code, no orphaned helper, no
narration comments added. `BatchVerdictSchema`'s tuple defaults are never exercised (`ai_judge.py:82-83`
always passes explicit tuples) but they are part of the §14.2 contract, so they stay. One stale
*reference* survived the refactor: **REV-075**.

### 5. Pass 5 — Security audit

**Clean. No `[SECURITY]` findings.** No gitleaks/CI output available (no shell), so this was a manual
trust-boundary read:
- **No committed secrets.** `tests/conftest.py:23-25`'s `test-fake-gemini-key` /
  `https://example.invalid.supabase.co` placeholders are pre-existing and self-evidently fake.
  `GEMINI_API_KEY` still reaches the SDK only via `config.GEMINI_API_KEY` →
  `GeminiProvider(api_key)` → `genai.Client(api_key=...)` (an SDK header, not a URL query parameter).
- **Key never lands in a log or the database.** The one new place an exception is stringified,
  `ai_provider.py:156`, clips to 200 chars and (per dev's own live invalid-key probe, handoff `:63`)
  yields `ClientError: 400 INVALID_ARGUMENT ... 'API key not valid'` with no key echoed. This string is
  printed to CI logs and stored in `fallback_from`, so the clip is load-bearing — worth keeping in mind
  if a future provider's SDK is chattier about credentials.
- **No new trust boundary.** Model output still reaches only `json.loads` + enum validation
  (`_parse_batch`), never a shell, SQL, file path, or HTML sink. `get_provider()`'s `SystemExit` echoes
  the `AI_PROVIDER` env value into the message; that value is a selector, not a credential.
- **Fail-fast on the credential is intact:** `run_hourly.py:136` and `run_discovery.py:28` still call
  `config.require_secrets()` (all three secrets) before any AI path runs.

---

### NEW FINDINGS — Pass 14

**REV-073 — `[DESIGN-GAP]` — minor — `docs/design/non-functional-ops.md` contradicts itself about whether
`scripts/ai_provider.py` exists, inside the one file INC-4 edited.**
Location: `docs/design/non-functional-ops.md:56-81` (repo map, `scripts/` listing), `:68`, `:108-111`
(DRAFT block) vs `:138-140` and `:175-178` (the INC-4 edits) in the same file.
Description: the INC-4 edit updated §9's config baseline and turned the §9 stub into
"**IMPLEMENTED (INC-4, 2026-07-28)**", but left the module's repo map untouched. Consequently the same
file now says both. Three specific stale spots: (a) the `scripts/` listing at `:56-81` does not include
`ai_provider.py` at all, though it lists every other module including DRAFT ones; (b) `:68` still
describes `ai_judge.py` as "**Gemini** batched `judge_batch(models=...)`" — the exact coupling FR33
removed, in the file that is meant to be the accurate module map; (c) `:108-111` still reads "`scripts/
ai_provider.py` (INC-4 — `AIProvider` interface + `GeminiProvider`) … **Neither exists in the repo yet**".
The same-owner batch outside the diff scope, worth doing in one edit: `docs/design/data-and-flow.md:62`
attributes the `fallback_from` detail format to `ai_judge._generate` (the format is preserved but is now
built in `ai_provider.GeminiProvider.generate`), and `docs/design/operational-controls.md:234` states in
the present tense that `_client()`/`_is_retryable()` are "in `ai_judge.py`" (defensible as §14.1 decision
history, but it now reads as current fact).
Process note attached to this finding, not logged separately: per `CLAUDE.md`'s ownership table, design
modules are tech-lead's and dev "never touches design" — yet INC-4's AC5 directed dev to edit
`non-functional-ops.md` §9, and the handoff records dev doing so. The AC set dev up for a boundary
crossing, and the half-update above is the predictable result. Future increments should route
design-doc updates to the owning agent rather than embedding them in a dev AC.
Owner: **tech-lead** (all three spots plus the two out-of-scope siblings).

**REV-074 — `[REQUIREMENTS-GAP]` — minor — `AI_PROVIDER` is missing from the configuration audit
baseline table that both the runbook and the design module call the authoritative one.**
Location: `docs/requirements.md` §10 config table (`:326-341` region) — zero `AI_PROVIDER` hits anywhere
in `requirements.md`; vs `docs/design/non-functional-ops.md:138-140` (has it) and
`docs/runbook.md:343` ("See `docs/requirements.md` §10 (Configuration audit baseline) for the full table
and current defaults").
Description: INC-4's AC5 names only `non-functional-ops.md` §9 as the baseline to update, and dev/qa
satisfied that literally. But `non-functional-ops.md:133-134` itself says its list "mirrors the
Configuration section of `docs/requirements.md` (**the reviewer's audit baseline**)", and the runbook
points operators at the requirements table as "the full table". So the key that FR33 introduces is
absent from the document two other documents designate as authoritative. This is the same rule that
produced REV-019 (`EVAL_WINDOW_DAYS`, 2026-07-15 changelog: "every tunable must appear in the config
audit baseline") and it is the same gap as REV-066/REV-052 (`NTFY_BASE_URL`, `NTFY_TIMEOUT_SECONDS`) —
all three should be added in one pm edit. Secondary: `docs/runbook.md:339-341` (§7 Configuration
Reference) also omits it; that is release's, and batches with REV-064's §7 rewrite.
Owner: **pm** (requirements §10, batched with REV-066/REV-052), then **release** (runbook §7, batched
with REV-064).

**REV-075 — `[BLOAT]` — minor — `scripts/config.py:87` points at a function that no longer exists
anywhere in the repo.**
Location: `scripts/config.py:86-87` — "The effective values are logged at call setup
(`ai_judge._client`)."
Description: `ai_judge._client` was removed by this increment; the transport constructor is now
`ai_provider._client` and the "call config" log line moved to `ai_judge.judge_batch()`
(`ai_judge.py:264-266`). `config.py` is a file INC-4 edited, so this is in-scope drift the increment
introduced and did not clean up — and it is the *only* surviving reference to the old structure anywhere
in live code or docs outside the two agent reports (repo-wide grep for `ai_judge\._`, `_is_retryable`,
`_RESPONSE_SCHEMA`, `_RETRYABLE_` returns nothing else stale; `config.py:77`'s `ai_judge._generate`
reference and `docs/runbook.md:185`'s and `scripts/state.py:191`'s are all still correct). One-word fix:
`(ai_judge.judge_batch)`.
Owner: **dev**.

**REV-076 — `[DESIGN-GAP]` — minor — the refactor changed how often a `genai.Client` is constructed, from
once per batch to once per attempt; neither the handoff, the test report, nor §14 records the delta.**
Location: `scripts/ai_provider.py:145` (inside `GeminiProvider.generate`) vs
`docs/design/operational-controls.md:322-323` and `:346-351`; claims at `docs/handoff.md:15` ("moved in,
unchanged") and `docs/test-report.md:47` ("retry/backoff logic byte-preserved").
Description: pre-INC-4, `_generate()` received an already-constructed `genai.Client` — design §14.3 says
so explicitly ("takes an `AIProvider` **instead of a `genai.Client`**"), and `config.py:87` describes the
config log as printing at "call setup" in `_client()`, i.e. once per `judge_batch()`. Post-refactor,
`_client()` is called inside `generate()`, so a fresh client (and a fresh httpx transport/connection
pool, and a fresh TLS handshake) is built on **every attempt**: up to `(GEMINI_MAX_RETRIES + 1)` per
model × up to 2 models × up to 2 parse attempts ≈ 16 client constructions per batch where there was
previously 1. This is not a correctness bug — timeout, retry counts, jitter and classification are all
unchanged, and the unmodified test suite passes — and it follows directly from §14.2 putting `timeout_ms`
on `generate()` rather than on the constructor, so it is a design consequence, not a dev deviation. But
"moved in, unchanged" and "byte-preserved" overstate it: the code text was preserved, the call frequency
was not. (Dev's relocation of the config log line to `judge_batch()` did correctly preserve *that*
cadence at once per batch — the log is fine; the client construction is the delta.) Fix: either cache the
client on the provider instance keyed by `timeout_ms` (cheap, and the `ai_provider._client` test seam
still works, since `get_provider()` runs inside `judge_batch()` after monkeypatching), or record the
accepted delta in §14.2 with its rationale. Either is fine; leaving it unwritten is not, because the next
person reading "moved in, unchanged" will assume connection reuse that does not exist.
Owner: **tech-lead** (decide and document), then **dev** if the caching option is chosen.

**REV-077 — `[TEST-GAP]` — minor — the only genuinely new behavior INC-4 adds has no permanent test.**
Location: `tests/` (no file) vs `scripts/ai_provider.py:160-165` and `scripts/config.py:66`;
`increment-plan.md:96-97` (AC5).
Description: everything else in INC-4 is moved code, and the unmodified `tests/test_ai_judge.py` covers
it well through the relocated seam. The provider-*selection* surface is the exception: nothing in `tests/`
asserts that `config.AI_PROVIDER` defaults to `"gemini"`, that `get_provider()` with no argument resolves
through `config.AI_PROVIDER`, or that an unknown name raises `SystemExit`. Both dev and qa verified all
three by hand (and qa deserves credit for testing the config-default path, not just the explicit-argument
one) — but a manual check leaves no regression net: renaming `config.AI_PROVIDER`, or a future second
provider's registration breaking the fallback, would pass the suite green. AC4 forbade touching tests
during this increment, so this is a follow-up, not a dev miss. Three small tests in
`tests/test_config.py` / a new `tests/test_ai_provider.py` close it. Worth adding before INC-5, since
`get_provider()` is now on the critical path of both production entry points.
Owner: **qa**.

**REV-078 — `[HARDCODED]` — minor — `temperature=0.2` is a model-behavior tunable that appears in no
config baseline. Pre-existing, moved unchanged, and design-named — flagged for a one-line decision, not
re-litigation.**
Location: `scripts/ai_provider.py:150`.
Description: `temperature` materially affects verdict stability and is discussed as a deliberate choice
in `requirements_docs/SD.md:525` ("low, to reduce run-to-run drift"), yet it exists only as a literal:
`config.py` has no temperature key and neither `requirements.md` §10 nor `non-functional-ops.md` §9 lists
one. `CLAUDE.md`'s "no hardcoded tunables" is a stated non-negotiable, and `non-functional-ops.md:152`
restates it as "no tunable may live only in code". Two mitigating facts, which is why this is minor and
not major: it pre-dates INC-4 (moved verbatim from `ai_judge.py`, not introduced here), and
`operational-controls.md:303` names `temperature=0.2` explicitly as part of the call shape to preserve —
so the design has seen it. The repo already has a mechanism for the other answer:
`non-functional-ops.md:168-169` records deliberate non-tunables ("stay as bare literals and are **not**
tunables"). So the ask is one line either way — add `AI_TEMPERATURE` to `config.py` + both baselines, or
record it as a deliberate constant. If an earlier pass already dispositioned this, close it as a
duplicate rather than re-opening the debate. Not flagged: `str(e)[:200]` at `:156`, which is documented
as a constant in `docs/design/data-and-flow.md:62`.
Owner: **tech-lead** (decide), then **pm** if it becomes a baseline entry.

---

### Open items after Pass 14

**Blockers: 0.**

**Majors: 3 IDs / 2 pieces of work** — unchanged from Pass 13: REV-064 + REV-039 (**release**, one
§2.2/§7/§8 edit — and §7 now also owes `AI_PROVIDER`, REV-074), REV-043 (**dev**).

**Minors: 17** — carried: REV-063 residual + REV-071 (dev), REV-065 (tech-lead), REV-066 + REV-052
(tech-lead + pm), REV-067 (tech-lead), REV-068 (pm), REV-070 (qa + release), REV-072 (tech-lead),
REV-048 (qa), REV-049(b) (release). New: REV-073 (tech-lead), REV-074 (pm + release), REV-075 (dev),
REV-076 (tech-lead + dev), REV-077 (qa), REV-078 (tech-lead + pm).

**Resolved this pass: none** — no Pass-13 item's file is in INC-4's diff, so none could be. This is
expected for a clean vertical slice, not a stall.

**Routing (batched by owner, so this is six messages, not seventeen):**
- **tech-lead** — REV-073 (+ its two out-of-scope siblings), REV-076, REV-078, plus carried REV-065,
  REV-067, REV-072. All doc edits in `docs/design/`; REV-076 may produce one small `ai_provider.py`
  change for dev.
- **dev** — REV-075 (one word in `config.py:87`), plus carried REV-063 residual + REV-071 (two SQL
  headers) and REV-043 (`get_price_only`).
- **pm** — REV-074, batched with carried REV-066/REV-052 (all three are the same edit to
  `requirements.md` §10) and REV-068.
- **release** — REV-064 + REV-039, now also adding `AI_PROVIDER` to runbook §7 (REV-074's second half),
  plus carried REV-049(b) before INC-5.
- **qa** — REV-077 (before INC-5), plus carried REV-048 and REV-070/AC6 at closure.

None of the above halts the pipeline. The single highest-value one before INC-5 is REV-077, because
`get_provider()` is now on both production entry points' critical path with zero automated coverage.

---

### What is in good shape (calibration)

- **qa's five PASSes hold up under independent re-derivation.** I re-derived the two the task singled
  out. The retry/backoff claim is correct — and I reached it without a diff, via the design's reference
  implementation, `config.py`'s pre-existing policy comment, and the *unmodified* `test_ai_judge.py`'s
  assertions on retry counts and classification boundaries, three sources that are independent of both
  the new code and qa. The "`run_hourly.py`/`run_discovery.py` untouched" claim is also correct, and
  stronger than "absent from `git diff --name-only`": their call sites still match design §14.3's
  specified shapes exactly and contain zero references to any new or removed symbol.
- **The refactor is a genuine extraction, not a rewrite.** Every Gemini-specific element the handoff
  claims to have moved has a live, behavior-matching counterpart in `ai_provider.py` (table in §1), the
  hard-won operational comments came with them (the 2026-07-07 outage rationale, the
  slow-but-token-billed timeout root cause), and `ai_judge.py` has zero SDK surface left. The interface
  matches §14.2 field for field including docstrings, which is unusual fidelity.
- **AC6 was handled correctly by both agents.** dev did not fabricate a pass, ran a real invalid-key call
  to prove the path reaches Google end to end, and escalated; qa refused to score it and carried it
  forward explicitly rather than quietly. That is exactly the INC-3/REV-070 precedent, applied
  consistently.
- **qa's regression accounting is honest** — it explains the 157 → 158 delta as `ai_provider.py` being
  picked up by `test_import_smoke.py`'s glob rather than claiming new coverage. I confirmed the glob at
  `tests/test_import_smoke.py:17`.
- **Every Pass-14 finding is a doc/coverage gap, not a code defect.** Nothing in the shipped Python is
  wrong. The pattern across REV-073/074/076 is a single one: this increment's *documentation* propagation
  stopped at the files its ACs named, while the code propagation was complete.

---

### Pass 14 summary

**New findings by tag — 6, all minor:** `[DESIGN-GAP]` 2 (REV-073, REV-076), `[REQUIREMENTS-GAP]` 1
(REV-074), `[BLOAT]` 1 (REV-075),
`[TEST-GAP]` 1 (REV-077), `[HARDCODED]` 1 (REV-078). **No new blockers, no new majors.** Pass 2 clean —
no `[SCOPE-CREEP]`. Pass 5 clean — no `[SECURITY]`, no committed secrets, no new trust boundary, the
credential fail-fast intact.

**Resolved this pass:** none (no carried item's file is in scope).

**Open blocker count: 0.**

### Verdict — INC-4

**CLEAR.** FR33's traceability holds end to end: `requirements.md` §5.12 → `operational-controls.md`
§14.1–§14.5 → `scripts/ai_provider.py` + `scripts/ai_judge.py` + `config.AI_PROVIDER` → the unmodified
`tests/test_ai_judge.py` suite exercising the new seam, with `tests/test_import_smoke.py` auto-covering
the new module. Five of six ACs verify on my own reading, independent of both dev and qa. Passes 2–5 are
clean across the increment. All six Pass-14 findings are minors, none is a correctness defect, and none
blocks a merge.

**What CLEAR does and does not mean here.** It means the extraction is faithful, the public contract is
preserved, and no production caller changed. It does **not** mean FR33 has been exercised against live
Gemini: **AC6 remains DEFERRED**, correctly and non-fraudulently, and inherits INC-3's REV-070 treatment
— Phase-4 closure must not treat FR33 as live-verified until a session with a real `GEMINI_API_KEY` runs
it. When that run happens it should also close this pass's one residual (§1, "Residual risk"): compare a
real verdict row's shape and `usage.thoughts` against a pre-INC-4 `call_log` row, which is the only
practical way left to prove no un-enumerated call kwarg was lost in the move.

### Verdict — Pass 14

**CLEAR — zero blockers.** INC-4 has now passed both qa and reviewer with zero blockers, so per
`CLAUDE.md`'s git workflow the merge-to-main gate is satisfied from the review side for **both INC-3
(cleared at Pass 13, unchanged since) and INC-4**. Neither increment is applied to a live system —
INC-3's SQL is unapplied per Arjun's deferral and INC-4 is unexercised against live Gemini — so live
behaviour is unchanged by everything above; the merge decision is Arjun's. The 3 majors and 17 minors are
all schedulable and none halts the pipeline, though REV-077 (qa) and the batched
release/dev/pm doc edits are worth closing before INC-5 adds more surface.
