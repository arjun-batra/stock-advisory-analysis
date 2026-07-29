# Review Log — Stock Advisory Agent

**Owner:** reviewer (read-only on everything else). **Format:** ID (REV-NNN), tag, severity
(blocker/major/minor), location, description, suggested owner. Every pass is re-run in full on each
review cycle; previously logged items are re-checked and marked RESOLVED with date when fixed.

---

## Passes 1–14, 16, 18, 19, 19-addendum (2026-07-12 through 2026-07-29) — archived

Passes 1–14 are archived in full to `docs/archive/review-log-archive.md` per `CLAUDE.md`'s doc-hygiene
rule; Pass 14 was archived 2026-07-28 at Pass 15's close, with its per-finding closing disposition
appended there. Pass 16 was archived 2026-07-29 at Pass 17's close, once all three of its findings
(REV-081/082/083) were independently re-verified RESOLVED — see its closing disposition there, and Pass
17 below for the re-verification itself and the two residual findings (REV-084, REV-085) that
verification surfaced. Pass 18 was archived 2026-07-29 at Pass 19's close, once all four of its
findings (REV-086/087/088/089) were independently re-verified RESOLVED. Pass 19 and the Pass 19 addendum
were both archived 2026-07-29 at this Pass 20's close, once REV-090 (Pass 19's own residual) and REV-091/
REV-092 (the addendum's findings) were all independently re-verified RESOLVED as part of INC-7's own
diff-scoped audit — see Pass 20 below for that re-verification and the two residual findings (REV-093,
REV-094) it surfaced in turn. Pass 15 is not yet archived: two of its own findings (REV-079, re-scoped to
its still-open AC5-wording residual, and REV-080) remain open and have not been touched by any subsequent
pass's diff scope, so its full content remains live below (REV-075, Pass 15's other open item, was
resolved and archived at Pass 18's close). Pass 17 is likewise not yet archived — nothing in it is
currently open, but it has not itself been superseded by a subsequent pass clearing it, so per this log's
established convention (a pass is archived when the *next* pass re-verifies and closes it) it stays live
until that happens. Nothing from Passes 1–12 remains open. The still-open items from Pass 13/14/15 and
earlier are carried forward in full below and are **not** in the archive as open work. Agents never read
`docs/archive/` per `CLAUDE.md`.

---

## Carried forward — open items from Pass 14 and earlier (re-checked at Pass 15)

**Diff-scope note.** Pass 15's diff (`284e950..HEAD`) touched twelve files, of which four host carried
findings: `docs/requirements.md` (REV-066/REV-052, REV-068), `docs/design/non-functional-ops.md`
(REV-065, REV-066/REV-052), `scripts/config.py` (REV-075) and `docs/design/operational-controls.md`. All
four were re-read this pass and their citations re-derived. The rest are in files unchanged since
`5fc452a`, so they are carried verbatim — unchanged file, unchanged finding.

**Majors (3 IDs / 2 pieces of work)** — unchanged, neither file in this pass's diff.

- **REV-039 (doc half) + REV-064 — `[DESIGN-GAP]` — major — owner: release. One edit closes both.**
  `docs/runbook.md:46-51` (§2.2) still instructs the operator to create six model Variables
  (`GEMINI_MODEL`, `GEMINI_MODEL_BACKUP`, `NSE_GEMINI_MODEL`, `NSE_GEMINI_MODEL_BACKUP`,
  `DISCOVERY_GEMINI_MODEL`, `DISCOVERY_GEMINI_MODEL_BACKUP`) that nothing reads — both workflow YAMLs
  mention them only in comments (`hourly-watchlist.yml:51-52`, `daily-discovery.yml:48-49`) pointing at
  `scripts/config.py` as the source of truth; zero `${{ vars.* }}` wiring. Same staleness at
  `docs/runbook.md:339` (§7 re-lists all nine Variables) and `:390` (§8 still recommends a Variable edit
  "for model swaps", now false for exactly that case). The three retry Variables
  (`GEMINI_MAX_RETRIES`, `GEMINI_RETRY_BASE_MS`, `GEMINI_TIMEOUT_MS`) **are** still wired
  (`hourly-watchlist.yml:67`, `daily-discovery.yml:61`) and must not be removed. §7 now owes
  **two** additions, not one: `AI_PROVIDER` (REV-074's release half) and `AI_TEMPERATURE` (REV-078's).
- **REV-043 — `[CODE-GAP]` — major — owner: dev.** `ingest.get_price_only(ticker)` is designed
  (`components.md` §4.2, `non-functional-ops.md:65-66`) but still absent from `scripts/ingest.py`;
  `publish_prices.py` still pulls a full `get_market_data()` per ticker. Live-system efficiency fix, not
  gated on any increment.

**Minors (12 IDs)**

- **REV-063 (residual) + REV-071 — minor — owner: dev. One edit to two SQL headers.**
  `sql/kill_switch.sql:8-17` still restates the apply order inline and contains no reference to
  `docs/runbook.md` at all; `sql/schema.sql:32-37` still enumerates a five-file order that omits
  `sql/kill_switch.sql` (naming `scheduler_pgcron.sql` first, which §2.3 established is wrong), though it
  does now point at §2.3 at `:37`. REV-071: `docs/runbook.md:70` asserts that both SQL headers "point
  back here rather than restating it" — a cross-reference state that does not exist in either file. If
  the dev half is declined, `:70`'s claim must instead be softened by release to match reality.
- **REV-065 — `[DESIGN-GAP]` — minor — owner: tech-lead. Re-read at Pass 15; the file was edited this
  round for REV-073 but this paragraph was not touched, and the line numbers are unchanged.**
  `docs/design/non-functional-ops.md:175-177` still presents `${{ vars.X || '<default>' }}` as the repo's
  established convention "used throughout `hourly-watchlist.yml` (`GEMINI_MODEL`, `GEMINI_MAX_RETRIES`,
  …)" — true only for the retry keys; the model keys deliberately have no Variable wiring
  (`config.py:19-24`). `:203-204` describes the same abandoned wiring as a "harmless, unread vestige".
- **REV-066 + REV-052 — minor — owner: tech-lead + pm. Re-checked at Pass 15 and now conspicuous.**
  `NTFY_BASE_URL` / `NTFY_TIMEOUT_SECONDS` (`config.py:125-126`) are still absent from **both** config
  audit baselines: `requirements.md` §10's Core-system table (`:324-350`) and `non-functional-ops.md`
  §9's core paragraph (`:143-160`). A repo-wide grep of `docs/` still returns zero hits outside this log.
  Pass 14 stated these should be closed *in the same pm edit* as REV-074; §10 was edited twice this round
  (`AI_PROVIDER`, then `AI_TEMPERATURE`) and neither edit picked them up. Two table rows and two words in
  a paragraph.
- **REV-067 — `[DESIGN-GAP]` — minor — owner: tech-lead.** `docs/design/components.md:50-56`'s citation
  table is stale after the REV-062 reconciliation: rows 5–6 cite `phase5_monitoring.sql:125`/`:153` (now
  `:182`/`:185`); row 7 says `interval '70 minutes'` appears in "three copies" at `:129,157,229` (now two,
  at `:194` and `:279` — the count is the thing the table exists to track); rows 1–4 still cite
  `scheduler_pgcron.sql:279` in a 184-line file and put `dispatch_watchlist_if_open()` in the wrong file
  (it is `phase5_monitoring.sql:318-338`).
- **REV-068 — `[REQUIREMENTS-GAP]` — minor — owner: pm. Re-checked at Pass 15 against the edited file.**
  `docs/requirements.md` still has zero `two-tier`/`fail-loud`/`SystemExit` hits for the INC-6 tunables
  chain, and `:388` still names the stale `config/tunables_cache.json` path (the cache is repo-root,
  REV-046 — `non-functional-ops.md:106-108` has it right).
- **REV-070 — minor — owner: qa + release.** INC-3's AC1–AC5 remain unexecuted against a live Supabase
  project per Arjun's explicit deferral. Not a defect; a scheduling obligation owed at apply time. Phase-4
  closure must not treat FR24/FR25/FR26 as verified until it happens.
- **REV-072 — `[BLOAT]` — minor — owner: tech-lead.** `sql/phase5_monitoring.sql:274-275` re-derives
  inline the exact session predicate `:182-188` already computed into `v_session_active`, so the four
  session-bound literals appear twice each in one function. Suggested fix: `if v_session_active then`.
- **REV-075 — `[BLOAT]` — minor — owner: dev. PARTIALLY RESOLVED at Pass 15, re-scoped, still open.**
  `scripts/config.py:86-87` no longer names a symbol that does not exist — the Pass-14 defect (a dangling
  `ai_judge._client`) is genuinely gone. But the replacement is also wrong: the sentence now reads "The
  effective values are logged at call setup (`ai_provider._client`)", and `ai_provider._client`
  (`ai_provider.py:127-136`) contains **no logging at all** and never even receives the two values the
  comment is attached to — `GEMINI_MAX_RETRIES` and `GEMINI_RETRY_BASE_MS` are not parameters of
  `_client()`, which takes only `api_key` and `timeout_ms`. The line that actually prints all three is
  `ai_judge.judge_batch()` (`ai_judge.py:264-266`), which is what Pass 14 named as the one-word fix and
  what tech-lead's own design text assumes (`operational-controls.md:377`: "matching `config.py`'s
  'logged at call setup' comment **and `judge_batch()`'s own once-per-batch config-log line**"). A reader
  who follows this pointer lands in a function that cannot tell them what the effective retry policy was.
  Fix: `(ai_judge.judge_batch)`. Owner: **dev**.
- **REV-048 — minor — owner: qa.** Constants/citation drift test still not built.
- **REV-049(b) — minor — owner: release.** Portal CI story still undecided; due before INC-5 starts.

---

## Pass 15 — 2026-07-28 (Pass-14 fix-round verification: REV-073–REV-078 + INC-3/INC-4 status sync)

**Scope.** Diff-scoped to `git diff --name-only 284e950..HEAD` (Pass 14 cleared at `284e950`), supplied
pre-run by the orchestrator: `docs/archive/requirements-changelog-archive.md` and
`docs/archive/test-report-archive.md` (both **excluded** — `CLAUDE.md`: agents never read `docs/archive/`;
their existence is noted only as evidence the hygiene caps were honoured), `docs/design.md`,
`docs/design/data-and-flow.md`, `docs/design/non-functional-ops.md`,
`docs/design/operational-controls.md`, `docs/handoff.md`, `docs/requirements.md`, `docs/test-report.md`,
`scripts/ai_provider.py`, `scripts/config.py`, `tests/test_ai_provider.py`. Plus re-verification of
FR33's traceability chain and a read of the unchanged files this round makes claims *about*
(`scripts/ai_judge.py`, `tests/conftest.py`, `docs/design/increment-plan.md`).

**Method.** Every one of REV-073–REV-078 was re-verified against **current file content**, opening the
code or doc the fix claims to have changed and, where the finding was about a cross-document or
code-vs-doc relationship, opening *both* sides. Dev's handoff, qa's test report and tech-lead's design
prose were read as claims to be tested, not as evidence — which is what produced REV-075's re-scoping
(dev's handoff `:100-102` states the REV-075 fix plainly and confidently; the fix points somewhere that
does not do the thing the comment says) and REV-079 (the status sync propagated to the two files named
in the task and stopped there).

**Method caveat (standing, unchanged since Pass 2):** no shell/execute tool this session. I cannot run
`git diff`, `pytest`, or any live call. Consequences for this pass specifically:
- I cannot independently confirm qa's "170 passed" figure. I verified instead that
  `tests/test_ai_provider.py` contains exactly the 12 tests the report enumerates (6 + 3 + 3), that each
  imports and patches surfaces that genuinely exist (`ai_provider._client` is still a module-level
  function, so `monkeypatch.setattr` resolves; `conftest.FakeGeminiResponse` exists at
  `tests/conftest.py:54`; `tests/conftest.py:16-17` puts `scripts/` on `sys.path`, so the bare
  `import config` / `import ai_provider` work), and that the fake's `generate_content(model, contents,
  config)` signature matches `ai_provider.py:165`'s all-keyword call. The tests are consistent with a
  green run; I have not observed one.
- The REV-076 caching change alters live runtime behaviour (connection reuse across retries) in a way no
  offline test can fully exercise. See "Residual risk".

---

### 1. Pass 1 — Traceability, requirements → code (FR33 re-verified; REV-078's new key traced)

**Complete for the first time — the Pass-14 partials are closed.**

| Link | Location | Status |
|---|---|---|
| Requirement | `requirements.md:217` FR33 (text unchanged this round) + Decision #26 (`:305`) | present |
| Design | `operational-controls.md` §14.1–§14.5, incl. new §14.3 `:365-403` (client cadence, REV-076) and `:405-432` (temperature tunable, REV-078) | present |
| Config surface | `requirements.md:326` (`AI_PROVIDER`), `:334` (`AI_TEMPERATURE`) **and** `non-functional-ops.md:146-150` (both) **and** `operational-controls.md:438-439` (both) | present — was partial at Pass 14 |
| Implementation | `ai_provider.py` (whole file), `ai_judge.py:263`, `config.py:66` + `:99-102` | present |
| Tests | `tests/test_ai_judge.py` (unchanged) + **new** `tests/test_ai_provider.py` (12 tests) + `test_import_smoke.py:17` glob | present — was a gap at Pass 14 |

**REV-078's key traced both directions.** `config.py:102` defines it; `ai_provider.py:162` is its only
consumer; the literal `0.2` survives only as the env default and as documented defaults in the two
baselines and §14.4. Grepping the repo for `temperature` returns no other live literal. The exact
failure mode Pass 14 warned about — a tunable landing in only one of the two baseline tables, which is
what REV-074 itself was — did **not** recur: `AI_TEMPERATURE` is in `requirements.md` §10 *and*
`non-functional-ops.md` §9, and pm's changelog entry (`:416`) records that avoidance as the reason the
entry exists.

### 2. Pass 2 — Traceability, code → requirements (scope creep)

**Clean. No `[SCOPE-CREEP]`.** Both production-code changes are design-mandated, not invented:
`GeminiProvider`'s cache is `operational-controls.md:387-403`'s literal code block (the shipped
`ai_provider.py:140-157` matches it line for line, including the `_client_timeout_ms` key), and
`AI_TEMPERATURE` is `:422-432`'s literal instruction. No public signature changed:
`AIProvider.generate()`'s keyword-only parameter list is byte-identical to §14.2 `:299-302`, and
`get_provider()` still matches `:318-323` character for character. `tests/test_ai_provider.py`'s third
caching test (per-instance, not global — `:133-150`) exceeds what the fix brief asked for, but it is a
test asserting a property the design states, not new behaviour.

### 3. Pass 3 — Hardcoding audit

**One Pass-14 finding closed, no new ones.** No CI/lint output available this session (no shell), so this
was manual against `non-functional-ops.md` §9 and `requirements.md` §10. Every literal in the diff was
compared to the schema: `ai_provider.py`'s remaining literals are the documented constant `str(e)[:200]`
(`data-and-flow.md:45`), `"application/json"` and the schema field names — all call-shape structure, not
tunables. `config.py:102`'s `"0.2"` is an env default in the established pattern. In the tests, the
`180000`/`90000`/`1000`/`0.75` values are fixtures, not production config. **REV-078 RESOLVED.**

### 4. Pass 4 — Leanness audit

**No `[BLOAT]` in the new code.** `tests/test_ai_provider.py`'s imports are all live (`pytest`:73,
`config`:58, `FakeGeminiResponse`:41, `ai_provider`:98, and the three names from the `from` import). No
commented-out code, no dead branch, no orphaned helper. `_CapturingModels`/`_CapturingClient` duplicate
part of conftest's fake, but for a stated reason the shared fake cannot serve (it discards the
`GenerateContentConfig` the temperature tests must inspect) — the report explains this at `:22-24` and
the docstring at `:31-33` does too, so it is a justified local fake, not a redundant abstraction.
`GeminiProvider.__init__`'s three lines and `generate()`'s three-line cache guard are the minimum the
design specifies. The one surviving stale *reference* in this diff is REV-075, above, which is why it
stays open rather than being marked resolved.

*Not logged, calibration only:* the 8-line comment at `ai_provider.py:147-154` restates §14.3's rationale
in code. It is longer than the code it guards, but every rationale comment in `config.py` and
`ai_provider.py` follows the same house convention, and it does encode the one non-obvious fact a future
editor needs (why the cache is keyed at all). Consistency with the file beats a lone exception here.

### 5. Pass 5 — Security audit

**Clean. No `[SECURITY]` findings.** No gitleaks/CI output available (no shell), so this was a manual
trust-boundary read of the diff:
- **No committed secrets.** `tests/test_ai_provider.py`'s `"test-key"` / `"key-a"` / `"key-b"` are
  self-evidently fake and never leave the process (`_CapturingClient` makes no network call). No new
  credential path: `GeminiProvider` still receives the key only from `config.GEMINI_API_KEY` via
  `get_provider()` (`ai_provider.py:174`).
- **The cache does not extend the key's lifetime meaningfully.** `self._client` now holds a
  `genai.Client` (which holds the API key) for the life of one `judge_batch()` call rather than one
  attempt. The provider instance is created and discarded inside `judge_batch()` (`ai_judge.py:263`), is
  never module-global or process-cached, and is never serialised or logged — so no new exposure window.
  Worth stating explicitly because "cache a credential-bearing object" is the shape of a real finding
  when the cache is global; this one is not.
- **`AI_TEMPERATURE` adds no trust boundary.** `float(os.environ.get(...))` fails fast at import on a
  malformed value, the same as the other numeric keys, and the value reaches only the SDK's generation
  config — not a shell, SQL string, path, or template.
- **One test mutates real process state:** `test_temperature_default_via_env_var_reload` (`:181-212`)
  sets `os.environ` and calls `importlib.reload(config)`. It restores the original value and reloads
  again in a `finally`, and it follows `test_config.py`'s established pattern, so it is bounded. Noting
  it as a known sharp edge, not a finding — it is the only test in the suite that can leave global state
  altered if the interpreter is killed mid-test.

---

### VERIFICATION OF PASS-14 FINDINGS — the point of this pass

| ID | Verdict | Evidence read (current content, not reports) |
|---|---|---|
| REV-073 | **RESOLVED** | `non-functional-ops.md:68-70` now lists `ai_provider.py` in the `scripts/` repo map as "IMPLEMENTED (INC-4, 2026-07-28, FR33)"; `:71-73` rewrites the `ai_judge.py` entry to "provider-neutral `judge_batch(models=..., provider=None)` — talks only to `AIProvider`/… no Gemini-SDK coupling since INC-4", removing the exact "**Gemini** batched" coupling FR33 deleted; `:113-115` replaces "Neither exists in the repo yet" with an IMPLEMENTED stub pointing at §14. All three spots fixed, and the file no longer contradicts itself anywhere. **Both out-of-scope siblings also fixed** (I checked, because Pass 14 flagged them as the same edit): `data-and-flow.md:64-65` now attributes the `fallback_from` format to `ai_provider.GeminiProvider.generate` "since INC-4 (pre-INC-4 this was all built in `ai_judge._generate`)"; `operational-controls.md:238-242` now says "at decision time (pre-INC-4) all three lived in `ai_judge.py`" with an explicit post-refactor parenthetical. |
| REV-074 | **RESOLVED** (pm half; release half open under REV-064) | `requirements.md:326` — `AI_PROVIDER` \| `gemini` \| purpose citing FR33/Decision #26 — in the §10 Core-system table, the document the runbook and `non-functional-ops.md:142` both designate authoritative. Changelog entry at `:414` names REV-074 and the REV-019 precedent. Changelog is at exactly 10 entries (`:407-416`), cap honoured. |
| REV-075 | **PARTIALLY RESOLVED — STILL OPEN** | See the carried-forward entry above. Dangling symbol gone; the new pointer names a function that does no logging and never sees the two values described. |
| REV-076 | **RESOLVED** (both halves — decided *and* implemented) | Design: `operational-controls.md:365-372` states the cadence delta in the same terms Pass 14 derived (≈16 constructions/batch vs 1), `:374-385` records the decision and why the key is kept, `:387-399` gives the code, `:401-403` the dev action; `:313-315` adds a guard-rail sentence to §14.2 telling readers **not** to infer "1 client per batch" from the call-shape paragraph. Code: `ai_provider.py:140-143` initialises `self._client`/`self._client_timeout_ms` to `None`; `:155-157` rebuilds only when unset or the key changed; `:165` calls through `self._client`. I traced the cadence claim rather than trusting it: `ai_judge.py:263` creates the provider once per `judge_batch()`, and `:300` / `:318` pass that same instance into every `_generate()` call for every model and every parse attempt — so one instance really does span the batch, and the cache really does restore 1 construction per batch. The module-level `_client()` function survives untouched, so `conftest.py:103`'s seam still works. |
| REV-077 | **RESOLVED** (one-line residual logged as REV-080) | `tests/test_ai_provider.py` exists and genuinely exercises all three paths Pass 14 named: **explicit-arg** — `:51-63` (identity, API key, and case-insensitivity via `"GEMINI"`); **config-default** — `:66-69` monkeypatches `config.AI_PROVIDER` and calls `get_provider()` with no argument; **bogus-name `SystemExit`** — `:72-78` (explicit arg) **and** `:80-86` (through the config default), both asserting the message names the bad value *and* the supported list, so the assertion would survive a message reword but not a silent swallow. This is not a plausibly-named empty file: the fakes are wired to the real seam and the assertions bite. |
| REV-078 | **RESOLVED — and the REV-074-shaped repeat was specifically avoided** | Decision: `operational-controls.md:405-420` (promote, don't exempt — with the reasoning that temperature sits in the same `GenerateContentConfig` as the three keys that are already tunables). Code: `config.py:99-102` defines `AI_TEMPERATURE`; `ai_provider.py:162` consumes it; no `0.2` literal remains in the call. **Both** baselines carry it: `requirements.md:334` and `non-functional-ops.md:148-150`. `operational-controls.md:438-439` lists both keys in §14.4. Tests pin the default (`test_ai_provider.py:164`), an attribute override (`:168-178`) and a real env-var override (`:181-212`). |

**Score: 5 of 6 genuinely resolved. REV-075 is not.** The claim that all six were fixed does not hold —
though the one that did not close is a comment-accuracy minor, not a code defect.

### INC-3/INC-4 status sync — independently verified, accurate but incomplete

**Accurate where it was applied.** `docs/design.md:3-11` now states GATE 3 passed and "INC-3
(kill-switch, FR24–FR26) and INC-4 (AI provider abstraction, FR33) are IMPLEMENTED … INC-5, INC-6, INC-7
(admin portal, FR27–FR32, NFR5–6) remain DRAFT"; `:149`, `:156-159`, `:187-189` and `:195-200` say the
same consistently, and §15's coverage map correctly splits FR24–26/FR33 (IMPLEMENTED) from FR27–32/NFR5–6
(DRAFT). `operational-controls.md:8-14`'s header matches. Both statements are **true against the code I
read this pass and last**: INC-3's SQL and INC-4's Python are in the repo and reviewer-cleared, and both
files correctly qualify the claim — design.md `:187` carries INC-3's unapplied-SQL caveat (REV-070) and
`:189` carries INC-4's deferred AC6, so "IMPLEMENTED" is not being used to mean "live-verified".

**INC-5/6/7 were not flipped.** I checked every INC-5/INC-6/INC-7 mention in both files: `design.md:10`,
`:48`, `:58`, `:188`, `:198-200` and `operational-controls.md:78`, `:85`, `:151`, `:156-157` all still
describe them as DRAFT/not-yet-built/forward-references. `operational-controls.md`'s INC-7 forward
references ("when the admin portal's kill-switch UI ships") remain correctly in the future tense. No
accidental promotion anywhere.

**But the sync stopped one file short — see REV-079.** `docs/design/increment-plan.md`, the file
`design.md:48` indexes as "**(INC-3/INC-4 IMPLEMENTED; INC-5–7 DRAFT)**", is not in this round's diff and
still opens (`:1`) with "# Increment plan — 2026-07-26 change request (**DRAFT, pending GATE 3**)".

---

### NEW FINDINGS — Pass 15

**REV-079 — `[DESIGN-GAP]` — minor — the INC-3/INC-4 status sync propagated to `design.md` and
`operational-controls.md` and stopped before the file that actually holds the increment plan.**
Location: `docs/design/increment-plan.md:1` (title) and `:55-98` (the INC-3 and INC-4 sections), vs
`docs/design.md:3-5`, `:48`, `:149` and `:156-159`.
Description: `increment-plan.md`'s title still reads "(DRAFT, pending GATE 3)" — stale on two counts.
GATE 3 *was* passed (`design.md:3-4`, `:149` "GATE 3 approved"), and two of the five increments in the
file have shipped and been reviewer-cleared. `design.md:48` labels this exact file "(INC-3/INC-4
IMPLEMENTED; INC-5–7 DRAFT)" in the module index, so the index and the file's own front matter now
contradict each other. Inside the file, the `### INC-3` (`:55`) and `### INC-4` (`:82`) headings carry no
status marker at all, so a dev opening the project plan — which `:6-7` says is "the project plan …
referenced by the pipeline's Phase 3 increment loop" — cannot tell which increments are built; the file
reads as five pending increments. Secondary, same edit: INC-4's AC5 (`:96-97`) still names
`non-functional-ops.md` §9 as the only baseline to update, the exact instruction that caused REV-074 —
worth amending to name both baselines so the next increment's AC doesn't reproduce it a third time.
This is the identical propagation pattern as Pass 14's REV-073 (a status update landing only in the files
a task explicitly named), one document layer up. Not a blocker: no code or requirement is wrong, and
`design.md` — which every agent is told to read first for orientation — is correct.
Owner: **tech-lead**.

**REV-080 — `[TEST-GAP]` — minor — `config.AI_PROVIDER`'s default value is the one thing REV-077 asked
for that the new suite does not assert.**
Location: `tests/test_ai_provider.py:66-69` vs `scripts/config.py:66`.
Description: Pass 14's REV-077 named three assertions: that `config.AI_PROVIDER` **defaults to
`"gemini"`**, that no-arg `get_provider()` resolves through it, and that an unknown name raises
`SystemExit`. The second and third are now covered thoroughly (six tests, both paths). The first is not:
`test_get_provider_no_arg_falls_back_to_config_default` *monkeypatches* `config.AI_PROVIDER` to
`"gemini"` before calling, so it proves the resolution path but is blind to the default's value — a
change of `config.py:66`'s default to any other string would keep the whole suite green while making both
production entry points fail at startup via `get_provider()`'s `SystemExit`. Two mitigating facts, which
is why this is minor and not major: `monkeypatch.setattr` raises `AttributeError` if the attribute is
missing, so a **rename** is still caught; and the sibling temperature test does exactly the right thing
one line up (`:164`, `assert config.AI_TEMPERATURE == 0.2  # documented default`). Fix: one line,
`assert config.AI_PROVIDER == "gemini"`, in `tests/test_config.py` or alongside `:66`.
Owner: **qa**. Explicitly **not** a merge blocker.

---

### Residual risk (carried, not a finding)

REV-076's caching is the first change in this round that alters live runtime behaviour — a `genai.Client`
and its httpx connection pool now persist across retries within a batch instead of being rebuilt. Every
offline proof available has been produced (design decision recorded, code matches the design's block, 3
tests pin the construction count and the cache's instance scope, full suite green per qa), and the
failure modes are inherently ones a mock cannot show: a stale pooled connection after a long backoff
sleep, or an SDK client that is less reusable than assumed. `operational-controls.md:383-385` argues both
away on the SDK's design, and I found nothing contradicting that — but it is unexercised against live
Gemini. This does **not** need its own deferral: it is naturally covered by INC-4's already-deferred
**AC6**, and should simply be added to what that run checks — confirm a real multi-retry batch (or at
minimum a normal batch) still succeeds, alongside the `usage.thoughts`/verdict-shape comparison Pass 14
asked AC6 to make. qa's decision not to re-run end-to-end for this coverage round was correct given no
credential exists in the environment; the note belongs on AC6, not on this pass.

Second, smaller: `docs/test-report.md:68-69` says "no production code changed" for this round. Read
strictly that is inaccurate — `ai_provider.py` and `config.py` both changed (by dev, in earlier commits
of the same round); qa's own scope was coverage-only, which is what the sentence means, and the verdict
line `:84` says it precisely ("No production code was modified **by qa**"). Not logged: the full suite was
run against the changed code, so nothing was skipped that mattered.

---

### Open items after Pass 15

**Blockers: 0.**

**Majors: 3 IDs / 2 pieces of work** — unchanged since Pass 13: REV-064 + REV-039 (**release**, one
§2.2/§7/§8 edit, §7 now owing both `AI_PROVIDER` and `AI_TEMPERATURE`), REV-043 (**dev**).

**Minors: 14** — carried: REV-063 residual + REV-071 (dev), REV-065 (tech-lead), REV-066 + REV-052
(tech-lead + pm), REV-067 (tech-lead), REV-068 (pm), REV-070 (qa + release), REV-072 (tech-lead),
REV-075 (dev, re-scoped), REV-048 (qa), REV-049(b) (release). New: REV-079 (tech-lead), REV-080 (qa).

**Resolved this pass: 5** — REV-073, REV-074 (pm half), REV-076 (both halves), REV-077, REV-078. All five
moved to `docs/archive/review-log-archive.md` with their closing dispositions, per doc hygiene.

**Routing (batched by owner — four messages):**
- **dev** — REV-075 (one word in `config.py:87`: `ai_judge.judge_batch`), plus carried REV-063 residual +
  REV-071 (two SQL headers) and REV-043 (`get_price_only`).
- **tech-lead** — REV-079 (`increment-plan.md` title + INC-3/INC-4 status + AC5's baseline wording), plus
  carried REV-065, REV-067, REV-072, and the `non-functional-ops.md` §9 half of REV-066/REV-052.
- **pm** — REV-066 + REV-052 (`requirements.md` §10 — two rows, the edit that has now been missed twice)
  and REV-068.
- **qa** — REV-080 (one assertion), plus carried REV-048 and REV-070/AC6 at closure.
- **release** — REV-064 + REV-039 (§7 now owes two keys), plus carried REV-049(b) before INC-5.

None of the above halts the pipeline.

---

### What is in good shape (calibration)

- **Five of six fixes are real fixes, not paper ones.** REV-076 in particular was done properly and in the
  right order: tech-lead recorded the decision *and* its rationale *and* added a guard-rail sentence to
  §14.2 so the next reader cannot re-derive the wrong cadence from the call-shape paragraph, then dev
  implemented exactly the block the design specifies. That is the ownership boundary `CLAUDE.md` asks for,
  and it is the opposite of what Pass 14's REV-073 process note flagged.
- **REV-078 did not repeat REV-074.** The failure Pass 14 warned about by name — a tunable landing in one
  baseline table and not the other — was specifically checked for and avoided, and pm's changelog entry
  (`:416`) says so and self-corrects an over-cap changelog in the same edit. That is a team reading its
  own review log rather than just closing tickets.
- **qa wrote tests that would actually fail.** The `SystemExit` tests assert on message content, the
  caching tests assert the *sequence* of builder calls (`[180000, 90000]`) rather than a bare count, and
  the third caching test locks the cache's instance scope — a correctness property nobody asked for. The
  local capturing fake is justified against the shared one in both the report and the docstring.
- **The status sync is honest about what IMPLEMENTED means.** `design.md:187`/`:189` carry INC-3's
  unapplied-SQL and INC-4's deferred-AC6 caveats inline rather than letting "IMPLEMENTED" quietly imply
  live verification — the distinction Pass 14's verdict insisted on, now written into the design doc
  itself.

---

### Pass 15 summary

**New findings by tag — 2, both minor:** `[DESIGN-GAP]` 1 (REV-079), `[TEST-GAP]` 1 (REV-080). **No new
blockers, no new majors.** Pass 2 clean — no `[SCOPE-CREEP]`. Pass 3 clean — REV-078 closed, no new
`[HARDCODED]`. Pass 5 clean — no `[SECURITY]`, no committed secrets, no new trust boundary; the credential
cache introduced by REV-076 is call-scoped and adds no exposure window.

**Resolved this pass: 5** (REV-073, REV-074, REV-076, REV-077, REV-078). **Not resolved: 1** (REV-075).

**Open blocker count: 0.**

### Verdict — Pass 15

**CLEAR — zero blockers, zero new majors. The merge-to-main gate is satisfied from the review side.**

**With one correction Arjun should have before he merges:** the round was scoped as "fix all six Pass-14
minors", and **five of six are genuinely fixed**. **REV-075 is not** — the dangling `ai_judge._client`
reference was replaced with `ai_provider._client`, which exists but performs no logging and never
receives `GEMINI_MAX_RETRIES`/`GEMINI_RETRY_BASE_MS`; the line that logs all three is
`ai_judge.judge_batch()`. It is a one-word fix in a comment (`config.py:87`), it cannot affect runtime
behaviour, and it does not block the merge — but "all six resolved" is not an accurate statement of where
the code is, and the fix is cheap enough to fold into the merge commit if Arjun wants the round to close
as scoped.

**What CLEAR does and does not mean here.** It means the five closed findings were verified against
current file content (not against the handoff or the test report), that the two production-code changes
match their design blocks exactly, that FR33's traceability is now complete end to end for the first time
(requirement → design → config baselines ×2 → code → permanent tests), and that nothing in the diff
introduces a scope, hardcoding, or security regression. It does **not** mean FR33 or FR24–FR26 are
live-verified: **INC-4's AC6 remains DEFERRED** (no `GEMINI_API_KEY` in any build environment) and
**INC-3's SQL remains unapplied** (REV-070, Arjun's explicit deferral). REV-076's connection-reuse change
should be added to AC6's checklist when that run finally happens.

---

## Pass 16 — 2026-07-29 (INC-5 admin portal foundation — backfilled diff-scoped audit) — ARCHIVED

Archived in full to `docs/archive/review-log-archive.md` at Pass 17's close (2026-07-29), with its
per-finding closing disposition appended there — all three findings (REV-081, REV-082, REV-083) were
independently re-verified RESOLVED at Pass 17. Pass 16's original verdict was **NOT CLEAR** (one new
`[SECURITY]` minor, REV-081, plus two non-blocking doc/evidence minors, REV-082/REV-083); full finding
text and Pass 16's own method/scope notes are in the archive.

---

## Pass 17 — 2026-07-29 (Pass-16 fix-round verification: REV-081/082/083, INC-5 final clearance)

**Scope.** Not a new diff-scoped increment audit — a targeted re-verification of the three specific
findings that held INC-5 NOT CLEAR at Pass 16, per the orchestrator's brief. Files opened this pass:
`sql/admin_portal_rls.sql` (REV-081), `sql/kill_switch.sql:40-69` (the pattern REV-081's fix is supposed
to mirror), `docs/design.md:1-30`, `docs/design/admin-portal.md:1-20`, `docs/design/increment-plan.md`
(title, status note, `### INC-3` through `### INC-7` headings, AC5) (REV-082, plus incidental
re-verification of REV-079, whose file this fix also touched), `docs/handoff.md` (in full — the
"Post-handoff fixes" section, the raw-evidence block, and the original AC-by-AC section) and
`docs/test-report.md:85-130` (REV-083).

**Method.** Each of the three findings' fix was verified against **current file content**, not against
the fix commits' or the orchestrator's own characterization of them — per the task's explicit instruction
not to trust the fix commits' claims. Where a fix touched a file shared with an already-open finding
(REV-079, sharing `docs/design/increment-plan.md` with REV-082), that finding was re-checked too, since
`CLAUDE.md`'s diff-scope rule extends to any file touched this round, not just the three named findings.

**Method caveat (standing, unchanged since Pass 2).** No shell/execute tool this session — Read/Grep only.
Consequences specific to this pass:
- **REV-081's live-production half** (the orchestrator's claim that the `revoke` statement was applied to
  project `ikghqdtlbwifwnooytmm` via Supabase `apply_migration`, and re-verified via a live
  `information_schema.role_table_grants` query showing only REFERENCES/SELECT/TRIGGER remaining for
  `anon`/`authenticated`) was **not** independently re-run — I have no live-DB tool bound to this session.
  This has the same evidentiary status as every other live-only check in this project (REV-070, and
  REV-083's own raw-evidence block, which I also cannot re-run). What I verified independently instead:
  the repo-file half of the fix in full (SQL syntax, placement, comment accuracy) — see below.
- **REV-083's raw evidence** (the `pg_class`/`pg_policies`/`pg_proc`/`information_schema.role_table_grants`
  results in `docs/handoff.md`) is likewise a live query result I cannot re-run; I verified that the
  artifact exists, is dated and attributed, and that its content is internally consistent with REV-081's
  finding (the grant enumeration it records is exactly what surfaced the TRUNCATE gap), not that the
  live database still matches it today.

### REV-081 — `[SECURITY]` minor — RESOLVED (repo-file half independently verified in full; live half
corroborated by, not re-derived from, the orchestrator's report)

`sql/admin_portal_rls.sql:17` now reads:
```sql
revoke insert, update, delete, truncate on public.admin_allowlist from public, anon, authenticated;
```
placed immediately after `alter table public.admin_allowlist enable row level security;` (`:16`), exactly
as the fix was specified. Checked against the three things the task asked me to independently confirm:
- **Correct SQL.** Valid Postgres `REVOKE ... ON ... FROM ...` syntax, targeting the exact three roles
  (`public, anon, authenticated`) and covering all four verbs RLS does not gate by itself plus the one
  (`TRUNCATE`) that RLS never gates regardless.
- **Matches the `kill_switch_audit` pattern it's supposed to mirror.** `kill_switch.sql:56`:
  `revoke insert, update, delete on public.kill_switch_audit from public, anon, authenticated;` — same
  role list, same statement shape, extended with `truncate` (the actual gap on this table, per the
  finding). Not a copy-paste — a deliberate, correctly-scoped superset for the one additional verb that
  was open here and wasn't on the `kill_switch_audit` precedent.
- **Comment no longer overclaims.** Re-read `:18-35` in full. The original paragraph (`:18-28`) that
  Pass 16 flagged as overclaiming now scopes its own claim correctly — "anon/authenticated get zero rows
  for SELECT/INSERT/UPDATE/DELETE via PostgREST" (four verbs, named explicitly, not "all access"). A new,
  separate paragraph (`:29-35`) is appended specifically for the REV-081 fix, stating plainly that RLS
  does not govern TRUNCATE, that this was the gap, and that the REVOKE above closes it — citing the
  `kill_switch_audit` precedent by name. A future reader can no longer come away believing
  RLS-with-zero-policies alone was a complete lockdown on this table.

**Live application.** The orchestrator states the `revoke` statement was applied live to project
`ikghqdtlbwifwnooytmm` via Supabase `apply_migration`, and independently re-verified via
`select grantee, privilege_type from information_schema.role_table_grants where
table_name='admin_allowlist' and grantee in ('anon','authenticated')`, returning only
REFERENCES/SELECT/TRIGGER for both roles (INSERT/UPDATE/DELETE/TRUNCATE gone). I have no Supabase MCP
tool bound to this session and did not re-run that query myself — this is reported, not independently
observed, and carries the same evidentiary status as the project's other live-only checks (REV-070's
unapplied-SQL deferral, REV-083's own raw evidence block below). The reviewable, durable artifact — the
file, its SQL, and its corrected comment — is fully verified independently.

**Verdict: RESOLVED.**

### REV-082 — `[DESIGN-GAP]` minor — RESOLVED (all three files; INC-6/INC-7 correctly left untouched)

Checked every INC-5/INC-6/INC-7 status mention in the three flagged files against current content:
- `docs/design/admin-portal.md:8-13` — the acute false-negative Pass 16 flagged ("Pending GATE 3", "Not
  yet implemented") is gone. Now reads: "INC-5 sections … are IMPLEMENTED — dev-built, qa-tested,
  reviewer Pass 16 verdict NOT CLEAR pending REV-081 fix in progress"; "INC-6 … and INC-7 … remain
  genuinely DRAFT — no dev work has started on them."
- `docs/design/increment-plan.md:1-15` — title now reads "INC-3/INC-4/INC-5 IMPLEMENTED, INC-6–7 DRAFT"
  (was "DRAFT, pending GATE 3"); the status note states GATE 3 passed, INC-3/4/5 IMPLEMENTED with the
  merge/fix commits and qa-pass reference, INC-6/7 "remain genuinely DRAFT — no dev work has started."
  `### INC-5` (`:118`) now carries an inline status marker: "**IMPLEMENTED** (dev-built, live-deployed
  `f48f5f7`/`6895db0`, qa-tested with a PASS verdict …)".
- `docs/design.md:3-14` — same pattern: "INC-5 … is also IMPLEMENTED — dev-built, live-deployed,
  qa-tested with a PASS verdict"; "INC-6, INC-7 … remain DRAFT — not yet built, no dev work has started."
  §15's coverage map (`:195-196`) correctly splits FR27–29/NFR5–6 (IMPLEMENTED) from FR30–32 (DRAFT).

**INC-6/INC-7 correctly not flipped.** Every remaining INC-6/INC-7 mention in all three files (module
index at `design.md:52,59,62`, the increment-plan's own `### INC-6`/`### INC-7` headings) still reads
DRAFT / "not yet built". No accidental promotion.

**Residual, not part of REV-082's original scope — logged fresh below as REV-084.** All three files'
IMPLEMENTED language for INC-5 is qualified with "reviewer Pass 16 verdict NOT CLEAR pending REV-081 fix
in progress" — accurate when written (before this pass existed) but now stale the instant this Pass 17
verdict lands. Not a defect in the REV-082 fix itself; a necessary consequence of fixing forward of a
verdict that didn't exist yet.

**Incidental finding: REV-079 (open since Pass 15) is now partially resolved as a side effect of this
same edit**, since it touched the same file. Re-checked independently:
- **Primary item — RESOLVED.** `increment-plan.md`'s title is no longer "(DRAFT, pending GATE 3)"; the
  `### INC-3` (`:69`) and `### INC-4` (`:98`) headings now both carry inline **IMPLEMENTED** status
  markers with commit/qa references, matching the pattern REV-079 asked for.
- **Secondary item — NOT resolved.** REV-079's secondary note asked that INC-4's AC5 (`:114-115`) name
  *both* config-audit baselines, not just `non-functional-ops.md` §9, given that naming only one baseline
  is the exact instruction that caused REV-074. Re-read `:114-115` directly: it still reads "added to
  `scripts/config.py` and the config audit baseline (`non-functional-ops.md` §9)" — singular, one
  baseline, unchanged from Pass 15. **REV-079 is carried forward, re-scoped to this residual only.**
  Owner: tech-lead.

**Verdict: RESOLVED** (REV-082 as scoped — all three files' DRAFT/pending-GATE-3 language is gone,
INC-6/7 correctly untouched).

### REV-083 — `[TEST-GAP]` (evidence-trail) minor — RESOLVED

`docs/handoff.md:1-71` now opens with a dated "Post-handoff fixes (2026-07-29): reviewer Pass 16
REV-081 / REV-083" section. Its `### AC8 / REV-034 live grant-and-policy audit — raw evidence` subsection
(`:33-71`) contains exactly what AC8 and REV-083 asked for: dated (2026-07-29), attributed to "orchestrator,
live query via Supabase MCP `execute_sql` against project `ikghqdtlbwifwnooytmm`", and the raw query text
plus results for all four checks — `pg_class` (RLS-enabled flags for `admin_allowlist`/`watchlist`/
`holdings`), `pg_policies` (zero rows for `admin_allowlist`, both write policies present and
`is_admin()`-gated on `watchlist`/`holdings`), `pg_proc` (`is_admin()` is `SECURITY DEFINER`, returns
boolean), and `information_schema.role_table_grants` (the exact grant enumeration that surfaced REV-081).

`docs/test-report.md` is updated consistently: GAP-001 (`:100-107`) is marked **RESOLVED (2026-07-29)**,
citing the handoff record by name and noting it's what surfaced REV-081. AC6 (`:94`) now reads "PASS —
independently confirmed," citing the same handoff record for the live-project half of its claim
(previously "not independently verified" per Pass 16's framing). AC8 (`:96`) now reads "PASS —
independently confirmed (evidence now on record)," with the same citation. The verdict line (`:118-124`)
and "Open bugs" section (`:130`, "None currently open. GAP-001 … is resolved") are consistent with the
per-AC table — no stale contradiction between the summary and the detail rows.

**One residual staleness, not part of REV-083's original scope — logged fresh below as REV-085.**
`docs/handoff.md:225-236`, the *original* pre-fix handoff's "Deferred" section, still lists AC8 as
"needs a live Supabase MCP/SQL-editor session … I don't have Supabase MCP tool access in this session
… this is explicitly pending, not attempted or faked" — now contradicted and superseded by the dated
evidence block added 154 lines above it in the same file. Not a functional gap (the current, authoritative
record is the new section at the top, and nothing downstream cites the stale one), but a doc-hygiene
leftover worth cleaning up so a future reader skimming to the bottom doesn't get a stale answer.

**Verdict: RESOLVED.**

### NEW FINDINGS — Pass 17

**REV-084 — `[DESIGN-GAP]` — minor — the "NOT CLEAR pending REV-081" caveat in three status lines is
now stale the moment this pass's verdict lands.**
Location: `docs/design.md:11-13`, `docs/design/increment-plan.md:10-13` (top status note) and `:118`
(the `### INC-5` heading), `docs/design/admin-portal.md:10-11`.
Description: all three files' otherwise-correct "INC-5 is IMPLEMENTED" language is qualified with
"reviewer Pass 16 verdict is NOT CLEAR pending REV-081 (a minor gap, fix in progress at dev)" — true when
tech-lead wrote it (before Pass 17 existed), false as of this verdict. This is not a defect in the fix
that produced it — tech-lead could not have written "Pass 17 CLEAR" before Pass 17 ran — but it is now
the next instance of the exact propagation pattern this log has flagged twice before (REV-073, REV-079):
a status update accurate at write-time, stale the moment the next event it depends on lands, and nobody
owns the follow-up edit unless it's logged. Owner: **tech-lead** — one follow-up edit in the four spots
above, replacing the "NOT CLEAR pending REV-081" qualifier with a reference to this Pass 17 CLEAR verdict
(and, naturally, folding in REV-079's residual AC5-wording fix and REV-085 below in the same pass, since
all three touch files already open for this edit). Not a merge blocker — INC-5's substance is correctly
described; only the reviewer-verdict pointer is one pass behind.

**REV-085 — `[BLOAT]`/staleness — minor — `docs/handoff.md`'s original "Deferred" section still lists
AC8 as pending, superseded by the dated evidence block added above it in the same file.**
Location: `docs/handoff.md:232-236` (original AC8 deferral bullet), vs `:33-71` (the new, authoritative
raw-evidence section added earlier in the same file per REV-083's fix).
Description: per `CLAUDE.md`'s doc-hygiene rule ("state anything once … never restate"), the file now
says two different things about AC8's live-audit status depending on where in the file a reader lands —
resolved-with-evidence at the top, "explicitly pending, not attempted or faked" further down. No
downstream document cites the stale bullet (test-report.md correctly cites the new section only), so this
is not a functional gap, just a leftover that should be deleted or replaced with a one-line pointer to
the "Post-handoff fixes" section. Owner: **dev** (handoff.md's owner per `CLAUDE.md`'s ownership table).
Not a merge blocker.

---

### Open items after Pass 17

**Blockers: 0.**

**Majors: 3 IDs / 2 pieces of work** — unchanged since Pass 13, neither file touched this round:
REV-064 + REV-039 (**release**), REV-043 (**dev**).

**Minors: 16 IDs** — carried, unchanged (none of these files were in this round's scope): REV-063
residual + REV-071 (dev), REV-065 (tech-lead), REV-066 + REV-052 (tech-lead + pm), REV-067 (tech-lead),
REV-068 (pm), REV-070 (qa + release), REV-072 (tech-lead), REV-075 (dev), REV-048 (qa), REV-049(b)
(release), REV-080 (qa) — 14 IDs. Carried, re-scoped this pass: REV-079 (tech-lead — AC5
baseline-wording residual only, its primary item resolved) — 1 ID. New this pass: REV-084 (tech-lead),
REV-085 (dev) — 2 IDs.

**Resolved this pass: 3** — REV-081, REV-082, REV-083. All three, plus Pass 16's full write-up, moved to
`docs/archive/review-log-archive.md` with closing dispositions, per doc hygiene.

**Routing:**
- **tech-lead** — REV-084 (four status-line spots) and REV-079's residual (AC5 wording,
  `increment-plan.md:114-115`) — same file, fold into one edit — plus carried REV-065, REV-067, REV-072,
  and the `non-functional-ops.md` §9 half of REV-066/REV-052.
- **dev** — REV-085 (`handoff.md:232-236`), plus carried REV-075, REV-063 residual + REV-071 (two SQL
  headers), and REV-043 (`get_price_only`).
- **pm** — carried REV-066 + REV-052 (`requirements.md` §10) and REV-068.
- **qa** — carried REV-080 (one assertion), REV-048, and REV-070/AC6 at closure.
- **release** — carried REV-064 + REV-039 (§7 now owes two keys) and REV-049(b) before INC-6.

None of the above halts the pipeline.

### Pass 17 summary

**New findings by tag — 2, both minor:** `[DESIGN-GAP]` 1 (REV-084), `[BLOAT]`/staleness 1 (REV-085).
No new blockers, no new majors. This pass was a targeted re-verification, not a full 5-pass audit — Pass
2/3/4/5 (scope creep, hardcoding, leanness, security beyond REV-081) were not re-run since no new
production code entered scope this round; Pass 16's own Pass 2–5 results for `admin-portal/` stand
unchanged and are preserved in the archive.

**Resolved this pass: 3** (REV-081, REV-082, REV-083) — each independently re-verified against current
file content, not against the fix commits' or orchestrator's own claims, per this pass's brief.
**Re-scoped, still open: 1** (REV-079 — primary item closed as a side effect, secondary AC5-wording item
not).

**Open blocker count: 0.**

### Verdict — Pass 17 / INC-5

**CLEAR.** All three findings that held INC-5 NOT CLEAR at Pass 16 — REV-081 (`admin_allowlist` TRUNCATE
grant), REV-082 (INC-5 status staleness across three design docs), REV-083 (AC8 evidence-trail gap) —
are independently verified RESOLVED against current file content. Zero blockers, zero majors introduced
or newly found. INC-5 (FR27–FR29, NFR5, NFR6) has no outstanding reviewer-side obstacle to being treated
as closed.

**What CLEAR does and does not mean here.** REV-081's repo-file fix (the `REVOKE` statement, its
placement, and its corrected comment) was verified in full, independently, against the actual SQL file —
not taken on the fix commit's word. REV-081's *live-production* application was **not** independently
re-run (no Supabase MCP tool bound to this session) and is reported by the orchestrator, not observed by
the reviewer — the same evidentiary status as REV-070's live-only checks elsewhere in this project.
REV-083's raw evidence block is a durable, reviewable artifact now permanently in the repo; the live
database state it describes was likewise not independently re-queried this pass. Two small residuals
surfaced by this verification (REV-084, REV-085) are both minor, both non-blocking, and both simply
follow-up doc edits in files this round's fixes already touched — routed above, not holding up clearance.

**Doc hygiene applied this pass:** Pass 16's full write-up and REV-081/082/083's closing dispositions
moved to `docs/archive/review-log-archive.md`; the live log above keeps only the carried-forward item
list and this pass's own findings, per `CLAUDE.md`'s doc-hygiene rule.

---

## Pass 18 — 2026-07-29 (INC-6 admin portal tunables editor — diff-scoped audit, FR30) — ARCHIVED

Archived in full to `docs/archive/review-log-archive.md` at Pass 19's close (2026-07-29), with its
per-finding closing disposition appended there — all four findings that held INC-6 NOT CLEAR at Pass 18
(REV-086 gating `[SECURITY]`, REV-087, REV-088, REV-089) were independently re-verified RESOLVED at
Pass 19. Pass 18's original verdict was **NOT CLEAR** (one new gating `[SECURITY]` minor, REV-086, plus
three non-blocking minors, REV-087/088/089); full finding text, method notes, and the three carried-item
closures (REV-075/084/085) are in the archive.

---

## Pass 19 — 2026-07-29 (Pass-18 fix-round verification: REV-086/087/088/089, INC-6 final clearance) —
ARCHIVED

Archived in full to `docs/archive/review-log-archive.md` at Pass 20's close (2026-07-29). Summary: targeted
re-verification of the four findings holding INC-6 NOT CLEAR at Pass 18 (REV-086 `[SECURITY]`, REV-087
`[REQUIREMENTS-GAP]`, REV-088 test-report inconsistency, REV-089 `[DESIGN-GAP]` stale status headers) — all
four independently re-verified RESOLVED against current file content. Verdict: INC-6 **CLEAR**. One new
finding surfaced independently this pass, REV-090 (`docs/design.md`'s master index left stale by REV-089's
fix) — resolved at Pass 20, see below.

---

## Pass 19 addendum — 2026-07-29 (post-clearance live-apply failure and hotfix,
`sql/admin_portal_tunables.sql`) — ARCHIVED

Archived in full to `docs/archive/review-log-archive.md` at Pass 20's close (2026-07-29), with closing
dispositions for all three of its findings (REV-090, REV-091, REV-092) appended there — each independently
re-verified RESOLVED at Pass 20. Summary: a live-execution-only Postgres syntax error (`CREATE POLICY ...
FOR select, update`) surfaced when the orchestrator applied the SQL Pass 19 had cleared; dev's hotfix
(commit `e46abf8`) split it into two valid single-verb policies, independently verified correct and
semantically equivalent to the design's intent. REV-091 (major, gating INC-7's start) and REV-092 (minor)
were found during that re-verification and are now both resolved — see the archive entry for full text and
Pass 20 below for the fresh findings this same file set surfaced in turn (REV-093, REV-094).

---

## Pass 20 — 2026-07-29 (INC-7 admin portal: track-record view & kill-switch UI — diff-scoped audit,
FR31/FR32) — ARCHIVED

Archived in full to `docs/archive/review-log-archive.md` at Pass 22's close (2026-07-29), with closing
dispositions for REV-090/091/092 (resolved at Pass 20) and REV-093/094 (resolved at Pass 22) appended
there. Summary: INC-7's diff-scoped audit — all six passes clean, INC-7 (FR31/FR32) verdict **CLEAR**,
zero blockers, zero majors. Two new minors surfaced (REV-093 status-staleness, REV-094 SQL-block drift in
`admin-portal.md` §16.6) — both independently re-verified RESOLVED at Pass 22, see the archive entry.

---

## Pass 21 — 2026-07-29 (Targeted hotfix review, out-of-band — REV-095: `ClientOptions` crash fix,
`scripts/config.py._fetch_tunables()`) — CLEAR

**Scope.** Not a diff-scoped increment audit (no INC-N in flight) and not the Phase-4 six-pass audit — a
fast, targeted review of one production hotfix per the orchestrator's explicit brief, ahead of the next
scheduled `hourly-watchlist.yml` run. Branch `claude/admin-portal-evaluation-txaehj`, commit `77e535e`
(dev) + qa's verification commit immediately after. Files read: `scripts/config.py` (in full),
`docs/design/tunables-fallback.md:100-198` (REV-095's incident note + as-built code block),
`tests/test_tunables.py` (in full — fixture + AC13 tests), `tests/test_fetch_tunables_real_client_construction.py`
(in full, new file), `docs/handoff.md:1-71` (hotfix section), `docs/test-report.md:1-107` (hotfix section).
`REV-095` is the ID dev/qa already used for this fix throughout the design doc, code comments, and test
docstrings before this review ran — adopted here as this log's own ID for the same event, keeping one
identifier across all four documents rather than minting a second number for what everyone already calls
REV-095.

**Method caveat (standing, unchanged since Pass 2).** No shell/execute tool bound to this session — this
session has no installed Python packages (`supabase`/`postgrest`/`httpx` are absent from every path
searched), so `git diff`, `pytest`, and a live `create_client()` construction were not independently
re-executed. This pass's verification therefore rests on (a) direct reads of the actual current file
content — not commit messages or the handoff/test-report's own characterization — for everything a
static read can settle, and (b) qa's documented reproduction trail for the one claim that requires
executing code against the real installed library, which is treated as corroborating evidence, not taken
on faith: `docs/test-report.md:26-68` records specific, checkable technical detail (the exact
`AttributeError` text reproduced against the pre-fix code and the real installed `supabase-py==2.31.0`;
the fixed path's construction confirmed not to raise, failing instead at the network layer with a
network/proxy-class error; `204 passed, 0 failed` for the full suite) rather than a vague "it works" — the
same evidentiary posture this log has applied to every other live-only check in this project (REV-070,
REV-081's live-application half, REV-083's raw-evidence block).

### Check 1 — Does the fix achieve the same functional goal on the actual call path?

**Yes, independently re-derived.** `scripts/config.py:72-74`:
```python
client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
client.postgrest.session.timeout = httpx.Timeout(TUNABLES_FETCH_TIMEOUT_MS / 1000)
rows = client.table("tunables").select("key,value").execute().data
```
`client.table(...)` is a request built through `client.postgrest` (the client's PostgREST sub-client);
`client.postgrest.session` is that sub-client's underlying HTTP session (an `httpx.Client` in production,
per both the design doc's comment at `tunables-fallback.md:143` and `tests/test_tunables.py:85-88`'s fake
docstring, which models it as exactly that). Setting `.timeout` on that session *before* the `.table()`
call, and never rebuilding or replacing `client.postgrest` afterward, means the request the `.execute()`
call issues genuinely goes through the timeout-configured session — not an unrelated or discarded object.
This was the one claim in this fix that a static read alone cannot fully close (whether `httpx.Client`
permits post-construction attribute assignment on `.timeout` on the installed version), which is exactly
what `tests/test_fetch_tunables_real_client_construction.py`'s first test exists to prove against the real
library, and what qa's suite run (204/204 passed, including that test) corroborates having actually
executed. The old code's stated intent (`ClientOptions(postgrest_client_timeout=...)`) and the new code's
effect (setting the timeout on the constructed client's actual request session) are functionally
equivalent — a bounded timeout on the same request — achieved through a different, viable mechanism.

### Check 2 — Design doc sync

**Accurate.** `docs/design/tunables-fallback.md:126-146` (REV-095's incident note) and its code block at
`:170-181` were compared line-for-line against `scripts/config.py:60-78`. The code block is byte-identical
to the shipped function (comment included). The incident-note prose correctly states the root cause (the
`if options is None:` branch, `ClientOptions` missing the `storage` field), the practical effect
(every run silently fell to tier 2, `TUNABLES_DEGRADED=True`), and the fix (`postgrest.session.timeout`,
`ClientOptions` no longer imported) — all independently confirmed against the code in Check 1 above and
Check 4 below. No contradiction found anywhere in the section.

### Check 3 — Regression test independent read

**Genuine, not a mocked-away seam.** `tests/test_fetch_tunables_real_client_construction.py` imports
`create_client` directly `from supabase import create_client` (not through `config`'s already-resolved
symbol) and never monkeypatches it — confirmed by reading the full file; the only `monkeypatch` calls in
it target `config`'s own module attributes (`SKIP_TUNABLES_FETCH`, `SUPABASE_URL`, etc.), not the
`supabase` package. This is the real, unmocked `create_client()` → `Client.__init__` → PostgREST-client
construction path — the exact seam `tests/test_tunables.py`'s pre-existing `mock_tunables_fetch` fixture
patches around (confirmed at `test_tunables.py:119,134`: it patches `supabase_pkg.create_client` itself),
which is why the original bug shipped undetected. Test 1 asserts construction + attribute-set doesn't
raise and the resulting `httpx.Timeout` value is correct; tests 2–3 drive the real, unmocked path against
an RFC-2606 `.invalid` host and assert the failure is a network-class exception caught by
`_fetch_tunables()`'s `except Exception`, never an `AttributeError` — the precise crash this fix closes.
Agrees with qa's independent read (`docs/test-report.md:51-62`).

### Check 4 — No other call site

`grep -rn "ClientOptions" scripts/` (via search tool) returns only comment/docstring references inside
`scripts/config.py:61-67` explaining why `ClientOptions` is deliberately *not* used — no other file in
`scripts/` imports or constructs it. `scripts/config.py`'s own import block (`:8-15`) confirms
`from supabase.lib.client_options import ClientOptions` is gone; only `import httpx` (new) and
`from supabase import create_client` remain. One call site, one fix, fully closed.

### Check 5 — Change scope

No git-diff tool available this session (see method caveat), so scope was confirmed by cross-referencing
dev's and qa's own "Files changed" lists (`docs/handoff.md:43-49`, `docs/test-report.md:11-13` — both name
exactly `scripts/config.py`, `docs/design/tunables-fallback.md`, `tests/test_tunables.py`, and the one new
test file) against a full read of each: `scripts/config.py`'s only tunables-fetch-related change is
`_fetch_tunables()` and its imports (the other ~380 lines read line-for-line show no unrelated edits);
`tests/test_tunables.py`'s changes are confined to the `_FakeSession`/`_FakePostgrest`/
`_FakeSupabaseClient` fixture shapes and the one AC13 test that asserts against them — the rest of the
215-test file's content matches what Pass 18-through-20 already reviewed. No drive-by change found in
anything read.

### Verdict — Pass 21 / hotfix `77e535e` — **CLEAR**

The fix is functionally correct (bounded timeout applied to the actual request session the tunables fetch
uses, independently re-derived from the call shape, not taken on dev's or qa's word), the design doc is in
sync with the shipped code, the new regression test genuinely exercises the real unmocked construction
path that let the original bug ship, there is exactly one call site and it's fixed, and nothing outside
the fix's legitimate scope was touched. **Zero blockers, zero new findings.** Safe to merge ahead of the
next scheduled `hourly-watchlist.yml` run.

**What CLEAR does and does not mean here.** It means the four durable, reviewable artifacts (code, design
doc, new test, fixture update) were independently verified against current file content. It does **not**
mean a live tier-1 fetch success (real rows returned from a real Supabase project) was observed this pass
or by qa — that path's shape is unchanged by this fix and was already covered pre-fix by INC-6's mocked
tests; qa's own report (`docs/test-report.md:81-87`) states this limitation plainly, and it carries the
same posture as every other live-only gap already open in this project (REV-070, INC-4's AC6) — not new,
not this fix's responsibility to close.

**Open items unchanged.** This hotfix touched none of the files carrying open findings from Pass 20.
**Majors: 3 IDs / 2 pieces of work** (REV-064 + REV-039 — release; REV-043 — dev). **Minors: 13 IDs**
(REV-063 residual + REV-071, REV-065, REV-066 + REV-052, REV-067, REV-068, REV-070, REV-072, REV-048,
REV-049(b), REV-080, REV-079 — unchanged from Pass 20's list). **Open blocker count: 0.**

**Doc hygiene.** Nothing new to archive this pass — REV-095 is logged directly to a CLEAR verdict with no
open remainder, so there is no RESOLVED item to move.

---

## Pass 22 — 2026-07-29 (Phase 4 closure — FULL 6-pass audit, whole codebase, INC-3–INC-7 integrated)

**Scope.** Per CLAUDE.md's Phase 4 gate: the whole repository, not diff-scoped — `scripts/`, `admin-portal/`
(source only; `node_modules/`/`.next/` are gitignored, confirmed via `admin-portal/.gitignore`, not
audited), `sql/`, `tests/`, `pages/`, `.github/workflows/`, and all of `docs/` except `docs/archive/` (never
read, per CLAUDE.md). `docs/code-map.md` (backfilled for this closure pass) used as the structure-audit
baseline for pass 6. Every file listed in the module map was opened and read in full this pass.

**Method caveat (standing, unchanged since Pass 2).** No shell/execute tool bound to this session —
Read/Grep/Glob only. No `git diff`, `pytest`, `ruff`, or gitleaks re-run; CI configuration (`ruff.toml`,
`.github/workflows/audit.yml`) was read to confirm what tooling *would* catch (gitleaks secrets scan, ruff
`E/F/W` + `C90` mccabe complexity on `--select` override, no import-linter config present) so passes 3–4–6
below are explicitly manual for everything past that. Two live-only items this pass treats as settled per
the orchestrator's brief, not independently re-run: INC-3's AC2/AC4/AC5 (kill-switch pause/resume/audit/RLS
— dated evidence block now in `docs/handoff.md:15-76`, same evidentiary class as REV-083/REV-081's
precedent) and INC-3's AC3 / INC-4's AC6 (both remain genuinely deferred, not re-flagged).

### 1. Traceability, requirements → code

Cross-checked every FR/NFR in `docs/requirements.md` against `docs/design.md` §15's coverage map, then spot-
opened the design section and at least one implementing file + test for each row. **§15's coverage map is
accurate** — every FR1–FR23/NFR1–NFR4/NFR7 row and every 2026-07-26-CR row (FR24–FR33/NFR5–6) resolves to a
real design section, real code, and a real test; the "RETIRED" rows for the old FR24–39/NFR5–6 (shadow
pilots) correctly point at git history, not live content. No `[REQUIREMENTS-GAP]`, `[DESIGN-GAP]` (code-
level), `[CODE-GAP]`, or `[TEST-GAP]` beyond the two items already carried and re-confirmed still open below
(REV-043, REV-070's AC3/AC6 residual).

**REV-070 — status update: PARTIALLY RESOLVED.** `docs/handoff.md:15-76` now contains a dated (2026-07-29),
attributed ("orchestrator, live query via Supabase MCP `execute_sql` against project
`ikghqdtlbwifwnooytmm`"), checkable raw-evidence block for INC-3's **AC2** (paused dispatch made zero new
`pg_net` calls — `net._http_response` max id unchanged across the paused-dispatch attempt), **AC4** (audit
trail — exactly 2 rows, correct `action`/`actor`/`source`, ~5s apart), and **AC5** (RLS enabled on both
`kill_switch_state` and `kill_switch_audit`, forced on the latter) — the same dated/attributed/checkable
format this project's own precedent (REV-083) established, and qa's `docs/test-report.md:96-121` explicitly
recorded *no* such block existed as of qa's own pass, so this evidence was added after qa ran, consistent
with the task brief's note that it was "being recorded in a parallel task." Per the same evidentiary
standard this log has applied throughout (REV-070's own prior treatment, REV-081's live-application half,
REV-083's raw-evidence block), **AC2/AC4/AC5 are now treated as resolved.** **AC3 (resume-baseline / no-
false-alarm under synthetic staleness) remains genuinely deferred** — no evidence block for it exists
anywhere in the repo, and the task brief explicitly says not to re-flag it as new. FR24–FR26 can now be
treated as live-verified for AC1/AC2/AC4/AC5; AC3 is the sole residual, carried forward, owner qa+release
(unchanged owner from REV-070's original routing). INC-4's AC6 (live Gemini smoke test) remains separately
deferred, also per the brief, also not re-flagged.

**REV-043 — re-confirmed still open.** `ingest.get_price_only(ticker)` is still absent from
`scripts/ingest.py` (only `get_market_data()` exists); `scripts/publish_prices.py:45` still calls
`ingest.get_market_data(ticker)` — a full fetch (history + fundamentals + headlines + relevance filtering)
where only the current price and 1-day change are used (`publish_prices.py:47-51`). Unchanged since Pass 15.
Owner: dev.

### 2. Traceability, code → requirements (scope creep)

**Clean. No `[SCOPE-CREEP]`.** Read every entry point and every admin-portal page end to end. `run_discovery.py`'s
`DISCOVERY_REGION` region-routing (na/in) is Decision #9/Phase-6-D5, not invented. The track-record page's
filters/sort/pagination are UI-only, no new aggregation (independently confirmed — no `.reduce`, no
win-rate/score/trend computation anywhere in `admin-portal/app/(app)/track-record/page.tsx`, matching
`tests/admin_portal/kill_switch_static.test.ts`'s own regression guard for the same claim). Nothing in
`scripts/` or `admin-portal/` does anything beyond its FR's stated scope.

### 3. Hardcoding audit

Compared every literal in `scripts/config.py` against `docs/requirements.md` §10's baseline table, and
checked every embedded prompt/model-parameter per this pass's explicit brief.

**NEW — REV-096 — `[HARDCODED]` — major.** `scripts/ai_judge.py:45-76` embeds the entire Gemini system
prompt (`BATCH_SYSTEM_PROMPT`, ~30 lines of literal prompt text) directly as a Python string constant, not
in `prompts/` and not referenced by path from `config.py`. This is a direct violation of `.claude/agents/dev.md`'s
explicit, current, non-negotiable rule: **"LLM prompts are configuration, not code. Any prompt sent to a
model lives in `prompts/` as a file (or in the config schema), referenced by path from config — never
embedded in source strings. Model names, temperatures, and max_tokens are config like everything else."**
Model name/temperature/timeout/retry params ARE already tunables (`config.GEMINI_MODEL`,
`config.AI_TEMPERATURE`, `config.GEMINI_TIMEOUT_MS`, `config.GEMINI_MAX_RETRIES` — all correctly resolved
via `config.py`, confirmed in `ai_provider.py:158-163`/`ai_judge.py`), so this finding is scoped to the
prompt text only. `docs/design/components.md:177-179` documents inline placement as a considered decision
("The prompt is inline Python in `ai_judge.py`... There is no separate prompt file") with a stated rationale
("that's product logic... not provider plumbing," `operational-controls.md:330-331`) — but no exception to
the dev-rule is recorded anywhere in `docs/requirements.md`'s Decisions Log, and CLAUDE.md gives no agent
authority to silently override a stated project rule via a design-doc footnote; a genuine exception is a
requirements-level decision (routes through pm, no-inference rule) or a rule change (routes through the
user), not a tech-lead call made unilaterally. This is not new code — it predates this closure pass by
several increments — but it has never been logged against this specific rule before; it surfaces now because
this closure pass is the first to explicitly check prompt-placement against `dev.md`'s text per the task
brief. **Two resolutions, either closes it:** (a) move `BATCH_SYSTEM_PROMPT` to a `prompts/` file, have
`ai_judge.py` read it by path; or (b) pm records an explicit, reasoned exception in the Decisions Log (the
existing design-doc rationale is a reasonable starting point, but it needs to actually be *decided*, not
just narrated). Owner: **pm** (decide a or b) **+ tech-lead** (if a, update `operational-controls.md`/
`components.md` to match) **+ dev** (implement if a).

**NEW — REV-097 — `[HARDCODED]` — minor.** `scripts/config.py:251` (`MIN_HISTORY_ROWS = 21`), `:326`
(`DISCOVERY_ALLOWED_EXCHANGES = {"NYSE", "NYSEArca", ...}`), and `:332` (`DISCOVERY_ALLOWED_EXCHANGES_IN =
{"NSI"}`) are bare Python literals with no `os.environ.get(...)` wrapper — the only three tunables in the
whole file without one, everything else follows the established `os.environ.get(name, default)` pattern.
Yet all three are listed in `docs/requirements.md` §10's config audit baseline table as tunables with
documented defaults, under a section header stating tunables are "read from environment / GitHub Actions
secrets & Variables." `tests/test_config.py` confirms no test exercises an env override for any of the
three (only sibling tunables like `DISCOVERY_MIN_MARKET_CAP`, wrapped via `_tunable()`, are tested for
override — `tests/test_config.py:122-135`). Low risk (US/CA exchange sets and the 20-day history floor
rarely change), but a genuine doc-vs-code mismatch. Fix: either wrap in an env-var read (comma-split for the
two sets) or have pm annotate these three §10 rows as "code-only, not env-configurable, edit
`scripts/config.py` directly" so the doc stops implying otherwise. Owner: **dev** (code fix) **or pm** (doc
annotation) — either resolves it.

**Model-settings/prompt-parameter sweep (task brief's specific ask) — otherwise clean.** No other inline
model parameters found: `ai_provider.py`'s `GenerateContentConfig` (`:158-163`) sources every tunable value
from `config.*`; the JSON schema shape (`_response_schema`) is structural (verdict/confidence enum values,
not a tunable). `docs/design/components.md:172`'s prose is stale on this exact point — see REV-098 below.

**REV-095-class construction-risk sweep (task brief's specific ask) — clean, one call site confirmed, no
new instance.** Grepped every `create_client`/`createClient`/`createBrowserClient`/`createServerClient` call
site in the repo: `scripts/config.py:72` and `scripts/state.py:16` both call `create_client(SUPABASE_URL,
SUPABASE_SECRET_KEY)` with no `options=` kwarg — the exact fixed shape, no second guessed-constructor-shape
call exists in `scripts/`. `admin-portal/lib/supabase-client.ts:34-37` (`createBrowserClient`) and
`admin-portal/app/auth/callback/route.ts:18-33` (`createServerClient`) both call the documented `@supabase/
ssr` factory signatures exactly as that library's own docs specify (URL, key, then a plain options object
for the server variant's cookie adapter — no dataclass/options-object guessing, no internal-vs-public-type
mismatch of the kind that caused REV-095). No other library object in the repo is constructed by guessing at
an SDK's internal shape rather than its documented call form.

**No `[HARDCODED]` findings in `sql/`, `admin-portal/`, or `pages/`.** Every SQL literal (session-boundary
times, cron schedules, RLS role lists) is either a documented, load-bearing design constant (§0 items 4/9)
or matches its citing config-schema row. `admin-portal/` reads every tunable value straight from Supabase
tables (`watchlist`/`holdings`/`tunables`), nothing embedded. `pages/common.js`'s `SUPABASE_URL`/
`SUPABASE_PUBLISHABLE_KEY` are the intentionally-public anon key (NFR7 posture, already accepted).

### 4. Leanness audit

**Clean — no new `[BLOAT]`.** No `TODO`/`FIXME`/`XXX`/commented-out code/`console.log` anywhere in
`admin-portal/app` or `scripts/` (grepped explicitly). No unused imports found in any file read this pass.
`__pycache__/` and `admin-portal/node_modules/` are both gitignored (root `.gitignore:1-2`,
`admin-portal/.gitignore:4`) — not committed, not a finding. `sql/fix_missing_degraded_checks.sql` and
`sql/dedup_watchlist_health_check.sql` (the two superseded `check_pipeline_health()` drafts) are correctly
reduced to non-applyable historical markers with a header pointing at the real, live function — matches
`docs/code-map.md`'s own description of them, not dead weight.

**REV-072 — re-confirmed still open (carried).** `sql/phase5_monitoring.sql:274-275` (the PUBLISH-PRICES
session gate, `(et >= time '10:15' and et <= time '16:00') or (ist >= time '10:00' and ist <= time
'15:30')`) still re-derives the exact four session-bound literals `v_session_active` already computed at
`:182-188`, instead of reusing it. Confirmed by direct read this pass. Owner: tech-lead.

### 5. Security audit

**NEW — REV-099 — `[SECURITY]` — major.** Whole-codebase sweep for
the TRUNCATE-grant gap class (REV-081/REV-086/REV-091-class, per the task brief's explicit instruction) on
every RLS-enabled table, not only the ones already fixed. Repo-wide `grep -n "revoke" sql/*.sql` returns
REVOKE statements only for `kill_switch_state`/`kill_switch_audit` (`sql/kill_switch.sql`,
`sql/kill_switch_portal_grant.sql`), `admin_allowlist` (`sql/admin_portal_rls.sql`), `tunables`
(`sql/admin_portal_tunables.sql`), and five `revoke execute on function` statements
(`sql/scheduler_pgcron.sql`, `sql/phase5_monitoring.sql`) — **never** for any of the six tables in
`sql/schema.sql` (`watchlist`, `holdings`, `verdict_state`, `call_log`, `run_heartbeat`) or
`sql/phase5_monitoring.sql` (`monitor_alerts`, `:40-45`). All six have `alter table ... enable row level
security` and either zero policies (`holdings`, `verdict_state`, `run_heartbeat`, `monitor_alerts`) or a
SELECT-only policy (`watchlist`, `call_log`) — RLS correctly denies `anon`/`authenticated` INSERT/UPDATE/
DELETE via PostgREST for all six by construction, **but RLS never governs TRUNCATE in Postgres at all** —
that verb is gated purely by the table-level TRUNCATE privilege, which Supabase's default public-schema
grants otherwise leave live for `anon`/`authenticated` regardless of RLS, exactly as `admin_allowlist`'s own
comment (`admin_portal_rls.sql:29-35`) states about the class of gap this project has already found and
fixed three times. This is the identical gap, unfixed, on the six tables that predate the admin-portal work
— including `call_log`, the FR15/FR16 audit trail that is this system's own stated §2 success-criterion
evidence, and `watchlist`/`holdings`, the live production configuration. Broader blast radius than any of
the three prior instances (six tables in one sweep, including the core data plane, vs. one administrative/
audit table at a time). Not currently exploitable via PostgREST (which exposes no TRUNCATE HTTP verb) — same
caveat this project's own precedent has applied to every prior instance of this class — but a real least-
privilege gap this project's own established pattern says is worth closing regardless of current
exploitability. Fix (mirrors the exact established pattern, cheap): a new SQL file or an appended block,
e.g.
```sql
revoke insert, update, delete, truncate on public.watchlist, public.call_log
  from public, anon, authenticated;
revoke insert, update, delete, truncate on public.holdings, public.verdict_state,
  public.run_heartbeat, public.monitor_alerts from public, anon, authenticated;
```
(the first line's tables already have a SELECT policy so only the truncate/insert/update/delete grant is the
live gap; the second line's tables have zero policies so all four verbs are the gap, same reasoning
`admin_allowlist`'s fix used). Owner: **dev** (write the SQL, mirroring `admin_portal_rls.sql`'s exact
comment/REVOKE shape) **+ release** (apply to the live project, same process as the four prior instances).

**No committed secrets.** No `gitleaks`-class pattern (`sb_secret_`, `AIzaSy`, `ghp_`, `sk-proj-`, PEM
headers) found anywhere outside comments describing the format (`scripts/config.py:20`,
`docs/runbook.md`) and the archive. `admin-portal/.env.example` contains only placeholder values.
`pages/common.js`'s committed anon/publishable key is the deliberately-public, RLS-gated key (NFR7 posture,
already accepted and unchanged).

**XSS/trust-boundary sweep, `pages/`.** Every AI-generated or user-entered value rendered into
`dashboard.html`/`detail.html` (ticker, rationale, headlines, confidence, error messages) goes through
`common.js`'s `esc()` HTML-escaper before insertion into `innerHTML` — confirmed by grepping every
`innerHTML`/template-literal render call in both files; no unescaped interpolation found.

**SQL/shell/path-injection sweep, `admin-portal/` and `scripts/`.** Every `admin-portal/` write goes through
the Supabase JS client's parameterized query builder (`.insert()`/`.update()`/`.eq()`/`.ilike()`), never a
raw SQL string. `scripts/`'s only shell-adjacent surface is the GitHub Actions YAML `git`/`pip` steps, which
use no untrusted input. `sql/scheduler_pgcron.sql`'s `dispatch_github_workflow()` builds its HTTP request
body via `jsonb_build_object(...)`, not string concatenation, for every value except the URL path segment
(`workflow_file`) — that parameter is never client-supplied (hardcoded call sites only, `'hourly-
watchlist.yml'` etc.), so no injection surface.

### 6. Structure audit

Checked `docs/code-map.md`'s dependency rules against actual imports/reads, not just its own claims.

- **`scripts/*.py` / `admin-portal/` isolation:** confirmed — no cross-import found in either direction.
- **`ai_judge.py` depends only on `ai_provider.py`'s interface:** confirmed — `ai_judge.py` has zero
  `google.genai`/SDK import (grepped); only `ai_provider.py` imports `google.genai`.
- **`config.py` as sole tunables/`os.environ` seam:** **one violation found.** `scripts/run_discovery.py:35`
  reads `os.environ.get("DISCOVERY_REGION", "na")` directly — the only `os.environ` read anywhere in
  `scripts/` outside `config.py` itself (confirmed via `grep -rn "os\.environ" scripts/`, two files:
  `config.py` and this one). **NEW — REV-100 — `[STRUCTURE]` — minor.** Low risk (a workflow-dispatch
  routing input, not a portal-curated business tunable), but it is a literal violation of `docs/code-map.md`'s
  own stated dependency rule ("`config.py` is the sole tunables seam; nothing else reads `os.environ`... 
  directly") on the one file that isn't the seam. Fix: move the read into `config.py` (`DISCOVERY_REGION =
  os.environ.get("DISCOVERY_REGION", "na")`), same pattern as `FORCE_RUN`/the `ALERTS_ENABLED` input.
  Owner: dev.
- **RLS/`is_admin()` as the real authorization boundary:** confirmed for every write path checked (watchlist/
  holdings/tunables/kill-switch all gate through `public.is_admin()`; no server-only secret anywhere in
  `admin-portal/`, confirmed by `tests/admin_portal/static_source_checks.test.ts`'s own regression guard and
  independently re-grepped this pass).
- **Entry points hold no business logic:** confirmed — `run_hourly.py`/`run_discovery.py`/`publish_prices.py`
  and every `admin-portal/app/` page are thin glue over importable modules/the Supabase client.
- **No dumping-ground modules:** confirmed — no `utils.py`/`helpers.py`/`misc.py` anywhere; `textutil.py` is
  a single, focused `clip()` helper shared by exactly two callers (`ai_judge.py`, `notify.py`), not a
  dumping ground.
- **`docs/code-map.md` accuracy:** confirmed accurate against the code as read this pass — the one place it
  was tested against reality (the dependency-rules list) is where REV-100 was found, meaning the map itself
  is correct and dev's code is what drifted, not the reverse.

**NEW — REV-101 — `[STRUCTURE]` — minor.** File/function-size guideline overrun (`.claude/agents/dev.md`:
"Split functions over ~40 lines and files over ~300 lines"). `scripts/config.py` is 458 lines (~53% over);
`scripts/ai_judge.py` is 337 lines (~12% over) and its `judge_batch()` function spans ~95 lines (`:242-336`,
~2.4x the function guideline). Both are readable and heavily commented for a stated reason (config.py is a
flat declarative tunables list with rationale comments per key; `judge_batch()` is the model-fallback +
retry + parse orchestration loop, whose complexity is largely inherent to what it does), and no duplicated
logic or dead branch was found inside either — this is a size finding, not a correctness one. The two
clearest overruns in the codebase; nothing else in `scripts/`, `admin-portal/`, or `sql/` function bodies
exceeds the guideline by a comparable margin. Owner: tech-lead/dev — decide whether to split (e.g. extract
`judge_batch()`'s per-model attempt loop into a helper) or record a formal accepted-exception note.

**NEW — REV-098 — `[DESIGN-GAP]` — major.** `docs/runbook.md`'s fresh-deploy SQL apply order (§2.3,
`:70-77`) and its own "SQL Migrations and Schema" list (§7, `:345-372`, which explicitly states "The
migrations in `sql/`... define **the complete control-plane schema**") both omit the entire admin-portal SQL
stack: `sql/admin_portal_rls.sql` (INC-5, `admin_allowlist`/`is_admin()`), `sql/admin_portal_tunables.sql`
(INC-6, the `tunables` table), and `sql/kill_switch_portal_grant.sql` (INC-7, the portal's kill-switch
grant) are named **nowhere** in either list (confirmed via a targeted grep of the whole file for
`admin_portal|admin-portal|kill_switch_portal_grant|AI_PROVIDER|AI_TEMPERATURE|Vercel|NEXT_PUBLIC` — zero
hits). There is also no admin-portal deployment section at all: no Vercel project setup, no Google OAuth
provider configuration step in Supabase Auth, no `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY`
env var documentation, no `admin_allowlist` seeding instruction. A release engineer following only this
runbook cannot deploy FR27–FR32 (the entire admin portal) at all, and §7's "complete control-plane schema"
claim is false as written. This **broadens** the already-open REV-064+REV-039 finding (which covers only the
narrower gap of stale `GEMINI_MODEL`-family Variables in §2.2 and the missing `AI_PROVIDER`/`AI_TEMPERATURE`
rows in §7) to the entire admin-portal surface — **REV-098 supersedes REV-064+REV-039**; fixing REV-098's
scope should fold in REV-064+REV-039's original fix in the same release pass rather than as two separate
edits, since both land in §2/§7 of the same file. Given CLAUDE.md's Phase 4 gate requires "release executes/
dry-runs the deploy per runbook," the runbook as currently written cannot support that dry-run for roughly
three of the seven shipped increments. Owner: **release**.

---

### Open items after Pass 22

**Blockers: 0.**

**Majors: 4 IDs / 4 pieces of work:**
- **REV-098** (supersedes REV-064+REV-039) — `docs/runbook.md` §2.3/§7 admin-portal SQL + deploy gap —
  owner **release**.
- **REV-096** — `BATCH_SYSTEM_PROMPT` embedded in `ai_judge.py`, not in `prompts/` — owner **pm** (decide) +
  tech-lead + dev (if relocating).
- **REV-099** — TRUNCATE-grant gap on `watchlist`/`holdings`/`verdict_state`/`call_log`/`run_heartbeat`/
  `monitor_alerts` — owner **dev** (SQL) + **release** (apply live).
- **REV-043** (carried, unchanged since Pass 15) — `ingest.get_price_only()` missing — owner **dev**.

**Minors: 14 IDs** — carried, re-confirmed still open where checked this pass (REV-072, REV-066+REV-052):
REV-063 residual + REV-071 (dev), REV-065 (tech-lead), REV-066 + REV-052 (tech-lead + pm), REV-067
(tech-lead), REV-068 (pm), REV-072 (tech-lead), REV-048 (qa), REV-049(b) (release), REV-080 (qa), REV-079
(tech-lead) — 10 carried IDs, all unchanged since Pass 21, none re-opened, none newly resolved. New this
pass: REV-097 (dev or pm), REV-100 (dev), REV-101 (tech-lead/dev), REV-098's sibling **REV-070's AC3
residual** (carried forward, unchanged scope, owner qa+release) — 4 new IDs. (REV-070's AC2/AC4/AC5 are
resolved this pass, per Pass 1 above — not counted as open; only the AC3 residual remains, tracked under
its existing ID.)

**Resolved this pass: 1** (REV-070, partially — AC2/AC4/AC5 closed via `docs/handoff.md`'s dated evidence
block; AC3 remains open under the same ID, so this is not moved to the archive — the ID stays live, scoped
down). No other carried item resolved this pass (this was a whole-codebase re-audit, not a fix-verification
pass — no fix round preceded it for the other carried items).

**Routing (batched by owner):**
- **release** — REV-098 (supersedes REV-064+REV-039, one runbook edit covering both), REV-099's live-apply
  half, plus carried REV-049(b) and REV-070/AC3 (qa+release, before/at the AC3 test).
- **dev** — REV-099's SQL half, REV-096 (if relocating the prompt), REV-097 (code half), REV-100, plus
  carried REV-063 residual + REV-071 and REV-043.
- **pm** — REV-096 (decide relocate-vs-record-exception), REV-097 (doc half, alternative to dev's code fix),
  plus carried REV-066 + REV-052 and REV-068.
- **tech-lead** — REV-101, plus carried REV-065, REV-067, REV-072, REV-079, and the `non-functional-ops.md`
  §9 half of REV-066/REV-052. Also: `docs/design/components.md:172`'s stale "temperature=0.2" prose
  (logged below as REV-102, folded into this routing since it's a one-line sync in a file tech-lead already
  owns edits in this batch).
- **qa** — carried REV-080, REV-048, and REV-070/AC3 at the point that test finally runs.

**NEW — REV-102 — `[DESIGN-GAP]` — minor.** `docs/design/components.md:172` still reads "Model settings:
`temperature=0.2`, `response_mime_type=...`" as if temperature were a hardcoded literal — stale since
INC-4/REV-078 promoted it to `config.AI_TEMPERATURE` (`requirements.md:334`, `operational-controls.md
§14.2-14.4`, `config.py:282`, all correctly updated at the time). This file wasn't in REV-078's diff scope
at Pass 15 (only `operational-controls.md`, `requirements.md`, `non-functional-ops.md` were), so it was
missed — the identical propagation pattern this log has now flagged four times (REV-073, REV-079, REV-084,
now this). Not a code defect; a doc-sync line. Owner: tech-lead (folded into the same-batch edit above).

---

### Pass 22 summary

**New findings by tag:** `[SECURITY]` 1 major (REV-099). `[HARDCODED]` 1 major (REV-096), 1 minor (REV-097).
`[DESIGN-GAP]` 1 major (REV-098), 2 minor (REV-102, and REV-079's already-carried residual, not re-counted).
`[STRUCTURE]` 2 minor (REV-100, REV-101). **Total new: 8 (3 major, 5 minor).** Pass 2 clean — no
`[SCOPE-CREEP]`. Pass 4 clean beyond the one carried REV-072. Pass 5 clean beyond REV-099 — no committed
secrets, no XSS/injection gap, no new construction-risk instance of the REV-095 class.

**Resolved this pass: 1** (REV-070, AC2/AC4/AC5 only — AC3 stays open under the same ID).

**Open blocker count: 0. Open major count: 4** (REV-098 supersedes REV-064+REV-039; REV-096; REV-099;
REV-043 carried).

### Verdict — Pass 22 / Phase 4 closure

**NOT CLEAR. Closure gate not satisfied — 4 open majors, per CLAUDE.md's "zero blockers/majors" Phase-4
requirement.** Zero blockers: nothing found this pass rises to pipeline-halting severity — every finding has
a cheap, well-precedented fix path already established elsewhere in this exact codebase (REV-099 mirrors
REV-081/086/091's exact REVOKE pattern; REV-098 is a documentation-only edit; REV-096 is either a file move
or a recorded decision; REV-043 is a self-contained function to add). But four majors are open, and
CLAUDE.md is explicit that Phase 4 closure requires zero of both.

**What this pass found, in one line each:** (1) the core data-plane tables (including the FR15 audit trail)
have the same TRUNCATE-grant gap already fixed three times elsewhere in this project, never closed for the
five original tables; (2) the entire admin-portal deploy story is missing from the runbook release uses to
dry-run deploys; (3) the production judgment prompt lives in source, against this project's own stated dev
rule; (4) a designed-but-never-built efficiency function (`get_price_only`) is still missing, carried since
Pass 15.

**What is in good shape (calibration).** The requirement-to-code traceability chain is genuinely complete
and accurate for the first time this project has done a full-codebase pass — `design.md` §15's coverage map
was checked, not trusted, and held up. INC-3's kill-switch is now live-verified for four of its five ACs via
a real, dated, checkable evidence record — the exact discipline this log has been asking for since REV-070
was first opened. Zero scope creep, zero committed secrets, zero XSS/injection surface, zero new instances
of the REV-095 construction-risk class anywhere in the repo. The four new majors are all narrow, mechanical,
already-precedented fixes — not open design questions — which is a materially different risk profile than
the blockers this project has cleared at prior gates (REV-062, REV-033).

**Recommended sequencing:** REV-099 (SQL) and REV-098 (docs) can be fixed and applied in parallel with no
interdependency; REV-096 needs pm's decision first, then a short dev/tech-lead follow-through if relocating.
None of the four majors touches code any other major depends on — all four can be fixed in one batched round
and re-verified in a single follow-up pass before re-attempting closure.

**Doc hygiene applied this pass:** no new archival — the only status change (REV-070) stays live under its
existing ID with narrowed scope, not a full resolution, so it does not move to `docs/archive/
review-log-archive.md` this round.
