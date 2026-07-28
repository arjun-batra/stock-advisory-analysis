# Review Log — Stock Advisory Agent

**Owner:** reviewer (read-only on everything else). **Format:** ID (REV-NNN), tag, severity
(blocker/major/minor), location, description, suggested owner. Every pass is re-run in full on each
review cycle; previously logged items are re-checked and marked RESOLVED with date when fixed.

---

## Passes 1–14 (2026-07-12 through 2026-07-28) — archived

Passes 1–14 are archived in full to `docs/archive/review-log-archive.md` per `CLAUDE.md`'s doc-hygiene
rule; Pass 14 was archived 2026-07-28 at this Pass 15's close, with its per-finding closing disposition
appended there. Nothing from Passes 1–12 remains open. The still-open items from Pass 13/14 and earlier
are carried forward in full below and are **not** in the archive as open work. Agents never read
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
