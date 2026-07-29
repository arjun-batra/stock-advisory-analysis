# Review Log — Stock Advisory Agent

**Owner:** reviewer (read-only on everything else). **Format:** ID (REV-NNN), tag, severity
(blocker/major/minor), location, description, suggested owner. Every pass is re-run in full on each
review cycle; previously logged items are re-checked and marked RESOLVED with date when fixed.

---

## Passes 1–14, 16, 18 (2026-07-12 through 2026-07-29) — archived

Passes 1–14 are archived in full to `docs/archive/review-log-archive.md` per `CLAUDE.md`'s doc-hygiene
rule; Pass 14 was archived 2026-07-28 at Pass 15's close, with its per-finding closing disposition
appended there. Pass 16 was archived 2026-07-29 at Pass 17's close, once all three of its findings
(REV-081/082/083) were independently re-verified RESOLVED — see its closing disposition there, and Pass
17 below for the re-verification itself and the two residual findings (REV-084, REV-085) that
verification surfaced. Pass 18 was archived 2026-07-29 at this Pass 19's close, once all four of its
findings (REV-086/087/088/089) were independently re-verified RESOLVED — see its closing disposition
there, and Pass 19 below for the re-verification itself and the one residual finding (REV-090) that
verification surfaced. Pass 15 is not yet archived: two of its own findings (REV-079, re-scoped to its
still-open AC5-wording residual, and REV-080) remain open and have not been touched by any subsequent
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

## Pass 19 — 2026-07-29 (Pass-18 fix-round verification: REV-086/087/088/089, INC-6 final clearance)

**Scope.** Not a new diff-scoped increment audit — a targeted re-verification of the four specific
findings that held INC-6 NOT CLEAR at Pass 18, per the orchestrator's brief. Files opened this pass:
`sql/admin_portal_tunables.sql` (whole file, REV-086), `sql/admin_portal_rls.sql:1-40` (the
`admin_allowlist` REVOKE pattern REV-086's fix is supposed to differ from, not mirror), `docs/
requirements.md:320-419` (§10 Core-system table and the Changelog, REV-087), `docs/test-report.md:120-189`
(REV-088), `docs/design/increment-plan.md` (title, status note, `### INC-6`/`### INC-7` headings, AC5),
`docs/design/admin-portal-tunables.md:1-18`, `docs/design/tunables-fallback.md:1-18`, `docs/design/
tunables-workflow-writeback.md:1-18` (REV-089), plus — since REV-089's fix touched files this pass's brief
did not explicitly name as in-scope but which share the same status-propagation question — `docs/
design.md:1-30,45-63,185-212` and `docs/design/admin-portal.md:1-15` (re-checked for the same class of
staleness, per the standing duty to re-check carried/adjacent items each pass).

**Method.** Each of REV-086/087/088/089's fix was verified against **current file content**, not against
the fix commits' or the orchestrator's own characterization of them — per the task's explicit instruction
not to trust the fix commits' claims. REV-086 was additionally checked character-for-character against
both the exact statement the task specified and its differentiation from `admin_allowlist`'s broader
REVOKE (REV-081), since getting that difference wrong would either leave the gap open (too narrow) or
silently break the tunables editor's save path (too broad, if UPDATE were included).

**Method caveat (standing, unchanged since Pass 2).** No shell/execute tool bound to this session — Read/
Grep/Glob only. Consequences specific to this pass: REV-086's live-application half was not independently
re-run — there is nothing live to re-check yet, since (per the task and per dev's handoff) `sql/
admin_portal_tunables.sql` has not been applied to the live project; INC-6 has not shipped. This is a
different situation from REV-081's live-half (which *had* been applied and reported), not the same
caveat restated — noted here so it isn't mistaken for an unverified live claim.

### REV-086 — `[SECURITY]` minor — RESOLVED

`sql/admin_portal_tunables.sql:25` reads exactly:
```sql
revoke insert, delete, truncate on public.tunables from public, anon, authenticated;
```
placed immediately after `alter table public.tunables enable row level security;` (`:24`) — the exact
statement and placement the task specified. Independently confirmed, not taken on the fix's own word:
- **Deliberately omits UPDATE and SELECT.** `:54-57`'s `admin_write_tunables` policy is `for select,
  update to authenticated` — both verbs are the mechanism the entire FR30 feature (the portal's tunables
  editor) depends on. In PostgreSQL an RLS policy only has effect if the role already holds the underlying
  table-level GRANT; RLS filters rows, it does not confer privilege. Revoking either would remove the
  privilege the RLS-gated portal write depends on and silently break the save button with a
  permission-denied error, not a specific, fail-loud hint — the opposite of secure.
- **Not a copy of `admin_allowlist`'s broader REVOKE.** `sql/admin_portal_rls.sql:17`:
  `revoke insert, update, delete, truncate on public.admin_allowlist from public, anon, authenticated;` —
  includes UPDATE, correctly, because *no* `authenticated`-role write path to `admin_allowlist` is
  legitimate (writes happen only via the SQL editor as table owner, or through `is_admin()`, a SECURITY
  DEFINER function exempt from both RLS and grants). `tunables` is different — the portal's UPDATE *is* a
  legitimate, RLS-filtered `authenticated`-role write path. The two REVOKE statements are materially
  different by design, not a drifted copy-paste; `:26-32`'s inline comment states this explicitly so a
  future editor doesn't "helpfully" align the two lists.
- **Live application.** Not independently re-checked and not expected to be — per dev's handoff and this
  file's own header comment (`:7-8`), the migration is not yet applied to the live project; INC-6 has not
  shipped. Nothing live exists yet to re-verify. The orchestrator applies it after this clearance, the same
  process as INC-5's `sql/admin_portal_rls.sql`/REV-081.

**Verdict: RESOLVED.**

### REV-087 — `[REQUIREMENTS-GAP]` minor — RESOLVED

`docs/requirements.md`'s §10 Core-system table now carries both rows: `TUNABLES_FETCH_TIMEOUT_MS` |
`5000` | ... (`:351`) and `SKIP_TUNABLES_FETCH` | `false` | ... (`:352`), same shape and same table as the
`AI_PROVIDER`/`AI_TEMPERATURE` rows added for REV-074/078. A dated Changelog entry (`:418`, 2026-07-29)
records the fix by name, cites REV-087, names the exact same recurring-gap class (REV-074, REV-078), and
states the archival step taken to hold the cap. Independently recounted the live Changelog: exactly 10
entries (`:409-418`) — pm's claim of archiving the oldest entry to make room is confirmed, not taken on
trust; the cap is honoured, not merely asserted.

**Verdict: RESOLVED.**

### REV-088 — doc-hygiene / `[TEST-GAP]`-adjacent minor — RESOLVED

`docs/test-report.md:136`'s AC14 row now reads "**PASS — all 3 entry points, including BUG-003 fix**" (was
"PARTIAL ... see BUG-003"). The Verdict paragraph (`:170-179`) now opens "**PASS. BUG-003 found this
session and FIXED by dev (commit `799cd35`); no bugs remain open**" and no longer lists "AC14 partial" or
"with one open bug" anywhere in that paragraph. Both are now consistent with the "Gaps / bugs found this
session" write-up (`:142-162`, already said FIXED before this fix) and the "Open bugs" section (`:183-188`,
"**FIXED**" — dev OR'd in `config.TUNABLES_DEGRADED` at the early-return branch). No remaining internal
contradiction anywhere in the file between the skimmable summary rows and the detailed sections.

**Verdict: RESOLVED.**

### REV-089 — `[DESIGN-GAP]` minor — RESOLVED as scoped; one adjacent residual found independently (REV-090, below)

All four named files now correctly state INC-6's actual status, checked directly rather than taken on the
fix's word:
- `docs/design/increment-plan.md:1` (title) — "INC-3/INC-4/INC-5 IMPLEMENTED, INC-6 built pending reviewer
  clearance, INC-7 DRAFT"; `:3-18` (status note) — "**INC-6 (admin portal: tunables editor) is
  IMPLEMENTED** — dev-built, qa-tested ..., reviewer Pass 18 verdict **NOT CLEAR pending REV-086 fix in
  progress** ... not yet reviewer-clear. **INC-7 ... remains genuinely DRAFT**"; the `### INC-6` heading
  itself (`:161`) carries the same inline marker.
- `docs/design/admin-portal-tunables.md:10-13`, `docs/design/tunables-fallback.md:10-12`, `docs/design/
  tunables-workflow-writeback.md:11-14` — all three now read "**Status: IMPLEMENTED**" (was "DRAFT ...
  INC-6 itself has not started"), "dev-built, qa-tested (PASS ...; BUG-003 found and fixed), reviewer Pass
  18 verdict **NOT CLEAR pending REV-086 fix in progress** ... not yet reviewer-clear."
This is exactly the instructed shape: dev-built/qa-tested stated plainly, reviewer-clear deliberately
**not** claimed, since that determination belongs to this pass. **INC-7 confirmed correctly untouched**:
`increment-plan.md:17-18` ("remains genuinely DRAFT — no dev work has started on it") and the `### INC-7`
heading (`:286`, "**DRAFT** (not yet built)") are both unchanged and accurate.

**REV-079's secondary residual — confirmed still open, as tech-lead's own fix disclosed.**
`increment-plan.md:117-118` (line numbers shifted from `:114-115` due to intervening edits, content
identical): AC5 still reads "added to `scripts/config.py` and the config audit baseline
(`non-functional-ops.md` §9)" — singular, one baseline only, the exact wording pattern that caused
REV-074. Tech-lead's REV-089 fix deliberately left this out of scope. **Judgment call, per this task's
brief:** this does **not** block Pass 19's clearance of INC-6. It is an INC-3/INC-4-era design-doc wording
residual (first logged against AC5 of the *AI-provider-abstraction* increment, Pass 15) — not a defect
introduced by, or specific to, INC-6's own code, security posture, or test coverage. Every prior instance
of this exact status-propagation pattern in this log (REV-073, REV-079's primary item, REV-084) has been
treated as a non-blocking minor that trails the increment it was found in without gating that increment's
clearance; there is no reason to treat this last residual differently now that it's aged into its second
pass sitting open. **Carried forward, unchanged, owner tech-lead** — not re-logged as a new ID.

**New finding, found independently this pass, not disclosed by tech-lead's fix — REV-090, below.** REV-089
named four files. `docs/design.md` — the master index every agent is told to read first for orientation,
per this log's own Pass-17 language — was not one of them, and is now stale in a way that directly
contradicts the four files this fix corrected.

**Verdict: RESOLVED** (REV-089 exactly as scoped — the four named files are fixed correctly and
completely; the AC5 residual was already known-carried, not a surprise; REV-090 is a genuinely new,
separate finding, logged fresh below rather than folded into REV-089's disposition).

---

### NEW FINDING — Pass 19

**REV-090 — `[DESIGN-GAP]` — minor — `docs/design.md`, the master index/orientation document, was outside
REV-089's fix scope and now directly contradicts the four module files that fix corrected — same recurring
propagation pattern as REV-073/079/084/089, one layer up this time (the index, not a module file). Owner:
tech-lead. Not a merge blocker.**
Location: `docs/design.md:13-14` (header status paragraph), `:27` ("No dev work starts on INC-6/INC-7
until each is reached in sequence"), `:52` (module map row for `increment-plan.md`, "INC-6–7 DRAFT"),
`:60-62` (module map rows for `admin-portal-tunables.md`, `tunables-fallback.md`,
`tunables-workflow-writeback.md`, each tagged "**(DRAFT)**"), `:196` and `:208-211` (§15 coverage-map row
for FR30/FR31/FR32, "**DRAFT** ... Not yet built; no dev work has started").
Description: every one of these spots still describes INC-6/FR30 as not-yet-built, no-dev-work-started —
directly contradicted by the four files REV-089 just fixed, which now correctly state INC-6 is IMPLEMENTED
(dev-built, qa-tested, Pass 18 NOT CLEAR pending REV-086 — now stale in its own right per this pass's
clearance, same class of one-pass-behind staleness as REV-084 before it). A dev or agent opening
`design.md` first — the document `:1` and this log's own Pass-17 text both describe as the orientation
entry point — would come away believing INC-6 hasn't started, while `increment-plan.md`'s own module-index
row one line above it (`:52`) is the thing making the contradiction visible: the row's own bracketed status
tag is what's stale, since `increment-plan.md` itself (the file it's describing) no longer says DRAFT.
This is not a new instance of a different problem; it is the identical failure this log has now named four
times (REV-073 Pass 14, REV-079 Pass 15, REV-084 Pass 17, REV-089 Pass 18) — a status edit landing in the
files a fix brief explicitly named and stopping there, leaving the one file that indexes all the others
out of sync. `design.md` was not in REV-089's four named files, so this is not a defect in that fix; it is
a gap in the fix's scope, found independently by re-reading `design.md` itself rather than trusting that
"INC-6 status sync" implicitly included the index. Fix: one tech-lead edit, the same five spots above,
updating each to IMPLEMENTED/reviewer-Pass-19-CLEAR framing (or a stable phrasing that doesn't itself go
stale next pass, e.g. citing this log by pass number rather than restating a verdict word). Not a merge
blocker — no code or requirement is described incorrectly anywhere in the codebase; only the index
document's own status pointer is behind, exactly the same non-blocking class as REV-084/089 before it.

---

### Open items after Pass 19

**Blockers: 0.**

**Majors: 3 IDs / 2 pieces of work** — unchanged since Pass 13, neither file touched this round: REV-064 +
REV-039 (**release**), REV-043 (**dev**).

**Minors: 12 IDs** — carried, unchanged (none of these files were in this round's scope): REV-063 residual
+ REV-071 (dev), REV-065 (tech-lead), REV-066 + REV-052 (tech-lead + pm), REV-067 (tech-lead), REV-068
(pm), REV-070 (qa + release), REV-072 (tech-lead), REV-048 (qa), REV-049(b) (release), REV-080 (qa) — 10
IDs. Carried, re-confirmed still open this pass: REV-079 (tech-lead — AC5 baseline-wording residual only,
judged non-gating for INC-6 above) — 1 ID. New this pass: REV-090 (tech-lead) — 1 ID.

**Resolved this pass: 4** — REV-086, REV-087, REV-088, REV-089, each independently re-verified against
current file content, not against any fix commit's own claim. All four, plus Pass 18's full write-up and
its own carried-item closures (REV-075/084/085), moved to `docs/archive/review-log-archive.md` with
closing dispositions, per doc hygiene.

**Routing (batched by owner):**
- **tech-lead** — REV-090 (five spots in `docs/design.md`) and REV-079's residual (AC5 wording,
  `increment-plan.md:117-118`, same file already open for other reasons — fold in if convenient, not
  urgent), plus carried REV-065, REV-067, REV-072, and the `non-functional-ops.md` §9 half of
  REV-066/REV-052.
- **dev** — carried REV-063 residual + REV-071 (two SQL headers) and REV-043 (`get_price_only`).
- **pm** — carried REV-066 + REV-052 (`requirements.md` §10 half) and REV-068.
- **qa** — carried REV-080 (one assertion) and REV-048.
- **release** — carried REV-064 + REV-039 (§7 now owes two keys), REV-049(b) before INC-7, and
  REV-070/AC6 at closure.

None of the above halts the pipeline.

### Pass 19 summary

**New findings by tag — 1, minor:** `[DESIGN-GAP]` 1 (REV-090, non-blocking). No new blockers, no new
majors. This pass was a targeted re-verification, not a full 5-pass audit — Pass 2/3/4/5 (scope creep,
hardcoding, leanness, security beyond REV-086) were not re-run since no new production code entered scope
this round; Pass 18's own Pass 2–5 results stand unchanged and are preserved in the archive.

**Resolved this pass: 4** (REV-086, REV-087, REV-088, REV-089) — each independently re-verified against
current file content, not against the fix commits' or orchestrator's own claims, per this pass's brief.
**Re-confirmed, still open: 1** (REV-079 — secondary AC5-wording residual, judged non-gating for INC-6).

**Open blocker count: 0.**

### Verdict — Pass 19 / INC-6

**CLEAR.** All four findings that held INC-6 NOT CLEAR at Pass 18 — REV-086 (`tunables` table TRUNCATE
grant, the gating `[SECURITY]` minor), REV-087 (requirements.md §10 baseline gap), REV-088 (test-report.md
internal inconsistency), REV-089 (stale DRAFT status headers across four design docs) — are independently
verified RESOLVED against current file content, not taken on the fix commits' word. Zero blockers, zero
majors introduced or newly found. INC-6 (FR30, and NFR6 via FR30's write path) has no outstanding
reviewer-side obstacle to being treated as closed.

**What CLEAR does and does not mean here.** REV-086's fix — the exact `revoke insert, delete, truncate`
statement, its placement, and its deliberate narrower scope relative to `admin_allowlist`'s REV-081 fix —
was verified character-for-character against the live file, including confirming it does NOT include
UPDATE/SELECT (which would have broken the feature) and is NOT a blind copy of REV-081's broader list. Its
live-production application was not independently re-run because there is nothing live yet to check —
unlike REV-081, this migration has not been applied; the orchestrator applies it after this clearance, the
same sequencing INC-5 used. REV-087/088/089 were each verified by direct inspection of the current file
content named in the finding, not by re-reading a handoff or test-report claim about the fix.

**One judgment call made explicit, per this pass's brief.** REV-079's still-open secondary residual (AC5
wording in `increment-plan.md`, naming only one config-audit baseline) is an INC-3/INC-4-era item, not an
INC-6 defect, and — consistent with how every other instance of this exact status/wording-propagation
pattern has been handled in this log — does not gate this pass's clearance of INC-6. It remains open and
routed to tech-lead.

**One new finding surfaced by this pass's own independent verification, not by the fix commits' claims.**
REV-090: `docs/design.md`, the master index, was outside REV-089's four-file fix scope and is now stale in
five spots, contradicting the very files REV-089 just corrected. Minor, non-blocking, same class and same
non-gating treatment as REV-084 and REV-089 themselves — routed to tech-lead, not held against this
clearance.

**Doc hygiene applied this pass:** Pass 18's full write-up and REV-086/087/088/089's closing dispositions
moved to `docs/archive/review-log-archive.md`, alongside the previously-recorded closures of REV-075/084/
085 (unchanged, carried in the same archive entry). The live log above keeps only the carried-forward item
list and this pass's own findings, per `CLAUDE.md`'s doc-hygiene rule.

---

## Pass 19 addendum — 2026-07-29 (post-clearance live-apply failure and hotfix, `sql/admin_portal_tunables.sql`)

**Not a new numbered pass.** Pass 19's substantive verdict (CLEAR) was correct on everything it could see;
this addendum covers a defect no static review could have caught — the orchestrator's live `apply_migration`
of the exact file Pass 19 cleared failed with a Postgres syntax error, since `CREATE POLICY ... FOR <cmd>`
only ever accepts one of `ALL | SELECT | INSERT | UPDATE | DELETE`, never a comma-separated list, and the
cleared file's single `admin_write_tunables` policy read `for select, update to authenticated`. Dev fixed it
on `claude/admin-portal-evaluation-txaehj` (commit `e46abf8`): the one invalid policy is now two valid ones,
`admin_read_tunables` (`for select`) and `admin_write_tunables` (`for update`). The orchestrator has since
applied the corrected SQL live to project `ikghqdtlbwifwnooytmm` and reports independent live re-verification
(`relrowsecurity=true`; `pg_policies` shows exactly the two new policies; `role_table_grants` for
anon/authenticated shows no INSERT/DELETE/TRUNCATE, confirming REV-086's REVOKE held; all 10 seed rows
present, `ALERTS_ENABLED='true'`). No live-DB tool is bound to this session — that report is corroborated,
not independently re-run, the same evidentiary status as every other live-only check in this project
(REV-070, REV-081's/REV-083's live halves).

**File-level fix independently verified, in full, against current content — not taken on the fix commit's
word.** `sql/admin_portal_tunables.sql:57-64` now reads:
```sql
create policy "admin_read_tunables" on public.tunables
  for select to authenticated
  using (public.is_admin());

create policy "admin_write_tunables" on public.tunables
  for update to authenticated
  using (public.is_admin())
  with check (public.is_admin());
```
- **Valid Postgres syntax.** Two separate `CREATE POLICY` statements, each with a single-verb `FOR` clause
  — the exact shape the live rejection demanded.
- **Semantically equivalent to the intended authorization, not merely syntactically legal.** Effective
  access is unchanged from what Pass 18/19 verified and what the design intends: `authenticated` role,
  `is_admin()`-gated, SELECT and UPDATE only, nothing else, for anyone. Splitting one `USING`/`WITH CHECK`
  pair across two policies does not add or remove a grantable path — Postgres evaluates all applicable
  policies for a given command, so a session satisfying `is_admin()` gets exactly the same SELECT and UPDATE
  access as the single-policy draft granted, no more.
- **REV-086's REVOKE (`:25`) is untouched by this fix and still correct**: `revoke insert, delete, truncate
  on public.tunables from public, anon, authenticated;`, still placed immediately after `enable row level
  security` — this fix did not need to and did not touch it.
- **The file's own REV-044/REV-086 comments were updated to match, not left describing the old shape.**
  `:49-56`'s comment explicitly states the reason for the split ("Postgres' `CREATE POLICY ... FOR <command>`
  clause accepts exactly one of ALL | SELECT | INSERT | UPDATE | DELETE, never a comma-separated list, so
  this is expressed as two policies rather than one") and correctly names both new policies. `:26-32`'s
  REV-086 comment already referred to "`admin_read_tunables` and `admin_write_tunables` (below)" by their
  current (post-split) names — not a leftover singular reference.

**Verdict: the fix holds. INC-6 remains CLEAR.** This was a live-execution-only defect (no static reviewer
pass, dev build, or qa test run could have surfaced a Postgres parser rejection without executing the SQL)
and is now correctly fixed, independently verified against current file content, and independently
corroborated live. Nothing in Pass 19's traceability, scope, hardcoding, leanness, or security verdicts is
disturbed by this fix.

**Two adjacent defects found independently during this re-verification, neither disclosed by the fix commit
or the orchestrator's summary — both logged fresh below, neither reopens INC-6's clearance.**

---

**REV-091 — `[TEST-GAP]` — major — owner: qa. Two permanent regression tests now hard-code the invalid,
pre-fix single-policy shape and will fail against the current, corrected `sql/admin_portal_tunables.sql`.**
Location: `tests/admin_portal/tunables_static.test.ts:46-53` (`"tunables: admin_write_tunables policy is
scoped to select/update only (REV-044), not \`for all\`"`) and `:55-62` (`"tunables: no insert/delete policy
exists for any role"`), vs. `sql/admin_portal_tunables.sql:57-64`.
Description: `:50`'s `assert.match(policyMatch![0], /for select, update to authenticated/i)` asserts a
substring that no longer exists anywhere in the file — the `admin_write_tunables` block the regex isolates
now reads `for update to authenticated` only (SELECT moved to the separate `admin_read_tunables` policy).
`:58`'s `assert.equal(policyLines.length, 1, "expected exactly one policy on tunables (admin_write_tunables)")`
asserts a count that is now 2, not 1. Both are confirmed by direct regex-vs-current-file reasoning (no
`node --test` run this session — no shell tool bound, standing method caveat since Pass 2 — but this is
static text matching against verbatim file content already read in full, the same method this log has used
throughout for JS/Python test-vs-source correctness without execution, e.g. REV-077/080). `docs/test-report.md`
carries this staleness forward: `:105` ("39 passed, 0 failed") and `:125` ("PASS (static shape); ... Policy
text confirmed `for select, update to authenticated`, not `for all`") were both true when qa ran them
against the pre-fix SQL and are now inaccurate for this exact area. The underlying security posture is
unaffected (see verdict above) — this is a test-suite regression, not a production defect, but it means the
qa "PASS" record this project relies on as evidence no longer reflects the file it describes. Fix: update
both assertions to the two-policy shape (`:50` -> match `for select to authenticated` in `admin_read_tunables`
and `for update to authenticated` in `admin_write_tunables`; `:58` -> expect 2 policy lines, still asserting
neither contains `for (all|insert|delete)`). **Not a merge blocker for INC-6 as already shipped/applied, but
gates INC-7's start** per `CLAUDE.md`'s "no increment starts before the previous one passes QA" — the
previous increment's regression suite is not currently green against its own source.

**REV-092 — `[DESIGN-GAP]`/doc-hygiene — minor — owner: tech-lead (design doc) + dev (handoff.md). Same
recurring propagation pattern as REV-073/079/084/089/090, this time triggered by a post-clearance hotfix
rather than a design-status edit.**
Location: `docs/design/admin-portal-tunables.md:42-87` (the §16.4 SQL code block, specifically `:56` and
`:72-87`) and `docs/handoff.md:64`, vs. current `sql/admin_portal_tunables.sql`.
Description: the design doc's mirrored code block still shows the single, invalid `admin_write_tunables`
policy (`:83-86`, `for select, update to authenticated`) with a REV-044 comment (`:72-82`) that never
mentions the two-policy split, and is missing REV-086's `revoke insert, delete, truncate` statement
entirely — it jumps directly from `alter table ... enable row level security;` (`:56`) to the trigger
function with no REVOKE line anywhere in the block. `docs/handoff.md:64` (dev's own Files-changed summary)
likewise still describes "`admin_write_tunables` RLS policy (`for select, update to authenticated` — not
`for all`, REV-044)" as if it were one policy, and the file contains no "Post-handoff fixes" section
recording commit `e46abf8` at all — unlike the precedent this project set for INC-5's equivalent
post-handoff TRUNCATE fix (REV-081/083, verified at Pass 17: a dated section was appended to `handoff.md`
naming the fix commit and the live re-verification). The sql file's own header comment (`:3`, "Design:
docs/design/admin-portal-tunables.md §16.4 (exact schema/trigger/policy block, REV-044)") asserts fidelity
to a design block that is now the thing that's wrong — a future reader who copies the design doc's SQL
directly (e.g. to recreate the schema, or trusting it as the canonical reference the sql file's own header
points to) would reproduce the exact syntax error this addendum exists to record. Not a runtime risk (the
live-applied SQL is correct and independently verified above; design.md and handoff.md are never executed),
but worth fixing promptly given this specific block already caused one production failure. Fix: sync
`admin-portal-tunables.md:42-87`'s code block to the current two-policy/REVOKE-included shape (tech-lead),
and add a dated "Post-handoff fixes" line to `handoff.md` naming commit `e46abf8` and this addendum
(dev) — same shape as INC-5's precedent. **Not a merge blocker.**

---

### Doc hygiene applied this addendum

Pass 18's full write-up had a stub at this log's top declaring it "archived in full," but the actual section
text had not been deleted from the live file — only duplicated into the archive, not removed here. That
leftover (the full Pass 18 Scope/Method/five-pass/findings/verdict text, previously occupying this space) is
confirmed already present in full in `docs/archive/review-log-archive.md` (from its `## Pass 18` entry,
including both the Pass-18 and Pass-19 closing dispositions for REV-086/087/088/089) and has been removed
from the live log here, per `CLAUDE.md`'s doc-hygiene rule ("agents never read `docs/archive/`" only holds if
the live log doesn't silently duplicate archived content). Nothing was lost — the archive already had the
complete, correct record.

### Open items after this addendum

**Blockers: 0.**

**Majors: 4 IDs / 3 pieces of work** — REV-064 + REV-039 (**release**), REV-043 (**dev**), unchanged since
Pass 13; **new this addendum:** REV-091 (**qa**, gates INC-7's start).

**Minors: 14 IDs** — carried unchanged: REV-063 residual + REV-071 (dev), REV-065 (tech-lead), REV-066 +
REV-052 (tech-lead + pm), REV-067 (tech-lead), REV-068 (pm), REV-070 (qa + release), REV-072 (tech-lead),
REV-048 (qa), REV-049(b) (release), REV-080 (qa), REV-079 (tech-lead, AC5-wording residual) — 11 IDs. New
this addendum: REV-090 (tech-lead, carried from Pass 19 proper), REV-092 (tech-lead + dev) — noting REV-090
was already logged at Pass 19's own close, restated here only for the routing table's completeness.

**Routing (batched by owner):**
- **qa** — **REV-091 (gates INC-7): two assertions in `tests/admin_portal/tunables_static.test.ts:50,58`**,
  plus `test-report.md:105,125`'s stale "39 passed"/"PASS (static shape)" claims for this test file, plus
  carried REV-080 and REV-048.
- **tech-lead** — REV-092's design-doc half (`admin-portal-tunables.md:42-87`), plus carried REV-090
  (`docs/design.md`, five spots), REV-079's residual, REV-065, REV-067, REV-072, and the
  `non-functional-ops.md` §9 half of REV-066/REV-052.
- **dev** — REV-092's handoff.md half (one dated "Post-handoff fixes" line naming `e46abf8`), plus carried
  REV-063 residual + REV-071 (two SQL headers) and REV-043 (`get_price_only`).
- **pm** — carried REV-066 + REV-052 (`requirements.md` §10 half) and REV-068.
- **release** — carried REV-064 + REV-039 (§7 now owes two keys), REV-049(b) before INC-7, and REV-070/AC6
  at closure.

None of the above halts anything already shipped. REV-091 gates **INC-7's start**, not any already-completed
work.

### Verdict — Pass 19 addendum

**The `sql/admin_portal_tunables.sql` fix holds. INC-6 remains CLEAR.** The corrected two-policy SQL is
valid Postgres, semantically equivalent to the single-policy draft Pass 18/19 verified (same effective
authorization: `authenticated` + `is_admin()` -> SELECT and UPDATE, nothing else, for anyone), and the file's
own REV-044/REV-086 comments were updated to describe the two-policy shape accurately. This was a
live-execution-only defect this project's verification chain had no way to catch before first live
`apply_migration` — consistent with every other live-only gap already on record in this log (REV-070,
REV-081's live half) — and is now independently corroborated fixed, both in the repo file and (via the
orchestrator's report, not independently re-run) live.

**Two adjacent defects surfaced by this re-verification, not disclosed by the fix commit, neither reopening
INC-6's clearance:** REV-091 (major) — two permanent regression tests now assert the pre-fix single-policy
shape and would fail if run against current source, gating INC-7's start rather than INC-6's already-shipped
state. REV-092 (minor) — the design doc's mirrored SQL block and dev's own handoff still describe the old
shape and omit REV-086's REVOKE, risking a future reader reproducing the exact incident this addendum
records if they trust the design doc's code block over the actual applied SQL.
