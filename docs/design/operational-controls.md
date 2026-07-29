# Operational controls — kill-switch & AI provider abstraction

Part of `docs/design.md`'s module split. See `docs/design.md` for the index, module map, §0
load-bearing decisions, increment plan, and requirement coverage map — read that first for
orientation. Section numbers below (§13–§14) continue the pre-split numbering; §15 (coverage map)
stays in `docs/design.md` itself, so this file skips it.

**Status: IMPLEMENTED** — covers the 2026-07-26 change request (kill-switch, FR24–FR26; AI provider
abstraction, FR33). Both increments have shipped: INC-3 (kill-switch) and INC-4 (AI provider abstraction)
were dev-built, qa-tested, and reviewer-cleared with zero blockers through Pass 14
(`docs/review-log.md`). This file is now as-built documentation for §13–§14, not draft design. Two
verification items remain open and are tracked in `docs/review-log.md`, not here: INC-3's
`sql/kill_switch.sql` **is applied and live** in the Supabase project — what's deferred (Arjun's
instruction, REV-070) is the functional pause/resume verification test (AC1–AC5), to be run as part of a
final end-to-end pass covering all increments; and INC-4's AC6 (live-Gemini smoke test) is deferred
pending real credentials (`docs/handoff.md`).

---

## 13. Kill-switch (FR24, FR25, FR26, NFR2)

### 13.1 Enforcement point — the single dispatch choke point

All five scheduled dispatch paths (watchlist US/TSX, watchlist NSE, discovery NA, discovery IN,
publish-prices) already funnel through **one** function: `public.dispatch_github_workflow(workflow_file,
inputs)` (`sql/scheduler_pgcron.sql`) — the gates (`dispatch_watchlist_if_open`,
`dispatch_watchlist_nse_if_open`) and the three direct-call crons (discovery ×2, publish-prices) all
call it as their last step before the `pg_net` HTTP POST to GitHub's Actions API.

**Design decision:** enforce the pause **inside `dispatch_github_workflow` itself**, not in each of the
five callers separately. One `if paused then return null` at the top of the one function every dispatch
path already shares is (a) a smaller, lower-risk diff than touching five call sites, (b) impossible to
miss a path on (adding a sixth workflow later inherits the guard automatically as long as it dispatches
through this function, which is the established convention), and (c) matches FR24's "enforced at the
`pg_cron` dispatch layer (the `SECURITY DEFINER` dispatch functions)" — this *is* the dispatch layer.
While paused, the function returns before constructing the `pg_net` request, so no HTTP call is made:
zero AI calls, zero Yahoo fetches, zero pushes, zero price-snapshot updates, exactly as FR24 requires.

```sql
-- inside public.dispatch_github_workflow, before the pg_net POST:
declare v_paused boolean;
begin
  select paused into v_paused from public.kill_switch_state where id = true;
  if v_paused then
    raise notice 'dispatch_github_workflow: kill-switch paused, skipping %', workflow_file;
    return null;
  end if;
  -- ...existing PAT lookup + pg_net.http_post unchanged below...
```

**Accepted risk (new):** a **manual** `workflow_dispatch` — a human clicking "Run workflow" in the
GitHub UI, or `gh workflow run`, bypassing pg_cron entirely — is **not** blocked by this design. FR24's
text scopes the guarantee to "no **scheduled** workflow dispatches"; this mirrors the existing
`FORCE_RUN` manual-override pattern (`components.md` §4.1) that the system already relies on for
testing/backfill. Only Arjun has write access to trigger `workflow_dispatch` manually, so the exposure
is low. If this ever needs closing, the fix is a second, Python-layer check at the top of
`run_hourly.py`/`run_discovery.py`/`publish_prices.py` — deliberately **not** built now, since FR24
explicitly rejects a Python-layer suppression as the *primary* mechanism.

### 13.2 Data model

```sql
create table public.kill_switch_state (
  id         boolean primary key default true,   -- singleton row; CHECK (id) below
  paused     boolean not null default false,
  updated_at timestamptz not null default now(),
  updated_by text                                  -- actor of the last change
);
alter table public.kill_switch_state add constraint kill_switch_state_singleton check (id);
insert into public.kill_switch_state (id, paused) values (true, false);
alter table public.kill_switch_state enable row level security;
-- No policy is created here — REV-033 fix, 2026-07-28. With RLS enabled and
-- zero policies, PostgREST denies anon/authenticated ALL access (Supabase's
-- default public-schema grants to those roles are not enough by themselves;
-- RLS is the actual gate and it was simply never turned on for this table).
-- The table owner (and set_kill_switch()/check_pipeline_health(), both
-- SECURITY DEFINER functions that run as the owner) is exempt from RLS by
-- Postgres default and keeps reading/writing exactly as designed above — no
-- functional change, this closes only the anon/authenticated exposure.
-- INC-7 (admin-portal.md §16.6) adds the first real policy — an
-- `authenticated`+`is_admin()`-gated SELECT — when the portal needs to read
-- the flag; until then this table is fully deny-all for every non-owner role.

create table public.kill_switch_audit (            -- append-only, never updated/deleted
  id         uuid primary key default gen_random_uuid(),
  action     text not null check (action in ('pause','resume')),
  actor      text not null,                         -- email (portal, from INC-7) or 'sql-direct'/session_user
  source     text not null default 'sql-direct',     -- 'admin-portal' | 'sql-direct'
  changed_at timestamptz not null default now()
);
alter table public.kill_switch_audit enable row level security;
alter table public.kill_switch_audit force row level security;
revoke insert, update, delete on public.kill_switch_audit from public, anon, authenticated;
-- REV-033 fix, 2026-07-28 (append-only was previously asserted in a comment
-- only, enforced by nothing). Two layers, each independently sufficient:
--   1. The REVOKE above removes the base insert/update/delete grant from
--      every non-owner role — this alone blocks anon/authenticated regardless
--      of any RLS policy that might be added later by mistake.
--   2. `enable` + `force` row level security with ZERO policies denies
--      SELECT/INSERT/UPDATE/DELETE to every role, including the table owner,
--      UNLESS that role has the `BYPASSRLS` attribute — which Supabase's
--      built-in `postgres` role has (used by the SQL editor, migrations, and
--      every SECURITY DEFINER function's owner in this codebase), so
--      `set_kill_switch()`'s insert and Arjun's own ad-hoc `select * from
--      kill_switch_audit` in the SQL editor are both unaffected. FORCE exists
--      here specifically so a future non-bypassrls context (a different
--      owner, a self-hosted Postgres fork, a stricter role assignment) is
--      still safe by construction, not by convention. **No policy grants
--      anon or authenticated any access to this table at all** — this is the
--      one new table in the whole change request with zero live write path
--      other than through `set_kill_switch()`.
-- Dev must confirm at INC-3 build time (already covered by the existing AC4
-- below: "Each set_kill_switch call inserts exactly one kill_switch_audit
-- row ... verified across ≥2 toggles") that the insert still succeeds
-- post-RLS — if the live project's `postgres` role does NOT carry BYPASSRLS
-- (unexpected, but worth verifying empirically rather than assuming), an
-- explicit `for insert to public with check (true)` policy would be needed
-- in addition to the REVOKE (the REVOKE alone still blocks anon/authenticated
-- in that case; only the function's own insert would need the extra policy).
```

`kill_switch_state` is the fast-read flag `dispatch_github_workflow` and `check_pipeline_health` check
on every invocation; `kill_switch_audit` is FR26's append-only history. Both are written **only** through
`set_kill_switch()` below — never directly — so the audit trail can't be bypassed by a stray `UPDATE`.
**Neither table grants the `anon`/`authenticated` roles any access as of INC-3** (REV-033) — the only
callers are the two `SECURITY DEFINER` functions above and a trusted direct-SQL/service-role connection.

### 13.3 The only write path

```sql
create or replace function public.set_kill_switch(
  p_paused boolean,
  p_source text default 'sql-direct'
) returns void
language plpgsql security definer set search_path = '' as $$
declare
  v_actor text := coalesce(auth.jwt() ->> 'email', session_user);
begin
  update public.kill_switch_state
     set paused = p_paused, updated_at = now(), updated_by = v_actor
   where id = true;

  insert into public.kill_switch_audit(action, actor, source)
  values (case when p_paused then 'pause' else 'resume' end, v_actor, p_source);
end; $$;

revoke execute on function public.set_kill_switch(boolean, text) from public, anon, authenticated;
```

At INC-3 time this function is callable **only** via the SQL editor / service-role connection (Arjun
directly) — same lockdown posture as every other `SECURITY DEFINER` function in this codebase
(`dispatch_github_workflow`, `send_ntfy`, etc., all revoke from `public, anon, authenticated`). There is
no Supabase Auth user population yet (the portal doesn't exist until INC-5), so `auth.jwt()` is always
null at this point and `actor` resolves to `session_user` (`'sql-direct'` toggles: `select
set_kill_switch(true);` / `select set_kill_switch(false);`). **FR24–FR26 are fully satisfiable with zero
portal dependency** — this is what makes the increment self-contained, per the approved build order.

**Forward reference (INC-7 extends this, doesn't replace it):** when the admin portal's kill-switch UI
ships, INC-7 (`admin-portal.md` §16.5) adds an internal `is_admin()` authorization check inside this same
function and `grant execute ... to authenticated`, so the function gains a second, admin-gated caller
(the portal, `source='admin-portal'`, `actor` = the signed-in Google email) without changing its
contract. No redesign needed at that point — additive only.

### 13.4 Dead-man monitor pause-awareness (FR25, NFR2)

`check_pipeline_health()` (`components.md` §4.8, `sql/phase5_monitoring.sql`) must treat a deliberate
pause as expected-quiet, not a failure.

```sql
-- at the top of check_pipeline_health, before any of the existing staleness checks:
declare
  v_paused boolean;
  v_resume_baseline timestamptz;
begin
  select paused, (case when not paused then updated_at end)
    into v_paused, v_resume_baseline
    from public.kill_switch_state where id = true;

  if v_paused then
    return;   -- FR25: no alert evaluation at all while deliberately paused
  end if;
  ...
```

**Resume-baseline refinement (load-bearing, not optional):** a naive "just skip while paused, evaluate
normally once unpaused" reintroduces a false alarm — if the system was paused for 2 hours, the watchlist
heartbeat is legitimately >70 min stale the instant it's unpaused, and the very next monitor tick (≤30
min later) would fire a "stalled" alert for staleness that is **entirely an artifact of the pause**, not
a real failure. FR25 says "no monitor alert fires for a missed/skipped run caused by a deliberate pause"
— a stale-on-resume alert is exactly that. Fix: every staleness comparison uses
`GREATEST(last_run_at, resume_baseline)` instead of `last_run_at` alone, where `resume_baseline` is the
timestamp of the most recent resume (`kill_switch_state.updated_at` when `paused = false`). This resets
the staleness clock at the moment of resume, so the monitor gives the system one full dispatch cycle to
catch up before it can alert — while a never-paused system is unaffected (`resume_baseline` stays far in
the past, `GREATEST` always picks the real `last_run_at`). Apply this to all four staleness checks in
`check_pipeline_health` (watchlist `wl_last`, discovery `disc_last`, discovery-in `disc_in_last`,
publish-prices `pp_last`) — the *display text* in the alert message still shows the real, un-adjusted
`last_run_at` so the operator sees honest data age; only the **stale/not-stale decision** uses the
adjusted baseline.

### 13.5 Requirement coverage

| Requirement | Covered by |
|---|---|
| FR24 (full-system pause at dispatch layer) | §13.1, §13.2 |
| FR25 (monitor pause-awareness) | §13.4 |
| FR26 (audit every toggle) | §13.2, §13.3 |
| NFR2 (extended: pause-aware dead-man monitor) | §13.4 |
| NFR7 (RLS scopes access to what each surface needs, incl. these two new tables) | §13.2 (REV-033 fix) |

---

## 14. AI provider abstraction (FR33)

### 14.1 LiteLLM vs. hand-rolled — decision

**Decision: hand-rolled provider interface. Do not adopt LiteLLM for this increment.**

Evaluated on normal engineering tradeoffs, as requirements.md's design-time note for tech-lead asks:

**LiteLLM's case:** a unified `completion()` call across 100+ providers, built-in retry/fallback/cost
tracking, and if a second provider is ever picked, it's a model-string change with zero new code. That's
a real advantage — *if* a second provider is imminent.

**Why hand-rolled wins here anyway:**
1. **No concrete second provider exists or is planned (Decision #26).** FR33 is deliberately
   interface-only; "no second provider is built or wired up as part of this requirement." Adopting a
   multi-provider SDK today to serve a provider nobody has chosen is the same premature-generality this
   project already argues against elsewhere (Decision #26's own rationale: "building a second provider
   with no concrete target risks guessing the interface shape wrong" — the same logic applies to
   committing to LiteLLM's provider-shape assumptions before there's a target).
2. **This system's Gemini integration has load-bearing, hard-won behavior that a generic wrapper
   risks re-breaking.** `docs/design.md` §0 load-bearing #3: the historical "quota" fallbacks were
   actually a client-side timeout firing on slow-but-valid, already-token-billed responses — fixed by
   setting an explicit `GEMINI_TIMEOUT_MS=180000` directly on the `google-genai` client's
   `http_options`. LiteLLM wraps each provider's SDK with its **own** timeout/retry/exception-mapping
   layer; routing through a second abstraction on top of the one already root-caused and fixed
   reintroduces exactly the risk class that produced that bug, and any recurrence would now be one layer
   further from the code the team already understands, not closer to debuggable.
3. **The actual new code is small.** `_client()` / `_generate()` / `_is_retryable()` — at decision time
   (pre-INC-4) all three lived in `ai_judge.py` — already isolate 100% of the Gemini-SDK-specific surface;
   this is a refactor (extract to a class behind an interface), not new functionality. Estimated net new
   code: ~80–120 lines in one file. (Post-refactor: `_client()`/`_classify()` now live in
   `ai_provider.py`, `_generate()`'s provider-neutral retry loop stays in `ai_judge.py` — §14.3.)
4. **Zero new dependency.** No new entry in `requirements.txt`, no new supply-chain surface to track for
   a public, single-maintainer repo — consistent with this codebase's existing minimalism (no
   `candidate_universe` table, single ingest wrapper, etc., `docs/design.md` §0 #7 / `foundations.md`).
5. **Schema-enforced structured output stays exact.** The current implementation uses Gemini's typed
   `response_schema` (constrained decoding, not just a JSON-mode flag) — LiteLLM's cross-provider
   `response_format` normalization does not guarantee the same enum-constrained decoding guarantee for
   every backend, and mapping it faithfully for Gemini specifically is exactly the kind of
   provider-specific work a hand-rolled adapter does anyway, gaining nothing from the wrapper for the
   one provider actually in use.

**Revisit condition:** if/when a second provider is actually selected with a concrete target, re-evaluate
LiteLLM then (a Router-based fallback across genuinely different vendors is closer to what it's built
for) — that decision doesn't need to be made now, and this interface doesn't foreclose it: a second
hand-rolled `AIProvider` implementation is exactly as pluggable as a LiteLLM-backed one would be, from
`judge_batch()`'s point of view.

### 14.2 Interface (new module: `scripts/ai_provider.py`)

```python
@dataclass(frozen=True)
class TokenUsage:
    prompt: int | None
    output: int | None
    thoughts: int | None      # provider-specific ("thinking" tokens); None if not applicable
    total: int | None

@dataclass(frozen=True)
class ProviderResult:
    text: str
    usage: TokenUsage | None

class ErrorClass(str, Enum):
    RETRYABLE = "retryable"   # transient transport/capacity error — safe to retry
    FATAL = "fatal"           # deterministic (bad request/auth/model name) — retrying wastes nothing but time

class ProviderError(Exception):
    """The ONLY exception type ai_judge.py catches from a provider. Every
    AIProvider implementation must translate its SDK's raw exceptions into
    this, classified via ErrorClass, so ai_judge.py never needs a
    provider-specific except clause."""
    def __init__(self, detail: str, error_class: "ErrorClass"):
        super().__init__(detail)
        self.detail = detail
        self.error_class = error_class

@dataclass(frozen=True)
class BatchVerdictSchema:
    """Provider-neutral description of the expected batch response shape —
    the array-of-{ticker,verdict,confidence,rationale} contract. Each
    AIProvider implementation is responsible for translating this into its
    own SDK's schema/response-format type internally."""
    verdicts: tuple[str, ...] = ("Buy", "Sell", "Hold")
    confidences: tuple[str, ...] = ("high", "medium", "low")

class AIProvider(ABC):
    @abstractmethod
    def generate(self, *, model: str, system_prompt: str, user_prompt: str,
                 schema: BatchVerdictSchema, timeout_ms: int) -> ProviderResult:
        """One request/response. Must raise ProviderError (never a bare SDK
        exception) on any failure."""
```

`GeminiProvider` (same file, or `scripts/ai_provider.py`'s only concrete class today — no subpackage;
one provider doesn't earn a package) implements `generate()` using exactly today's `google.genai` call
shape (`genai.Client(http_options=types.HttpOptions(timeout=timeout_ms))`,
`response_mime_type="application/json"`, typed `response_schema` built from `BatchVerdictSchema`,
`temperature=config.AI_TEMPERATURE`, decided REV-078 — see below) and an internal `_classify(exc) ->
ErrorClass` carrying over `_is_retryable()`'s exact
logic unchanged (`httpx.TimeoutException` / bare `TimeoutError` → retryable; `.code in {429,503,504}` or
`.status in {UNAVAILABLE, DEADLINE_EXCEEDED, RESOURCE_EXHAUSTED}` → retryable; everything else → fatal).
The **call shape** (parameters, schema, temperature) is preserved exactly as above; the **construction
cadence** is not automatic from that and is specified separately in §14.3 (REV-076) — do not infer "1
client per batch" from this paragraph alone.

```python
def get_provider(name: str | None = None) -> AIProvider:
    name = (name or config.AI_PROVIDER).lower()
    providers = {"gemini": lambda: GeminiProvider(config.GEMINI_API_KEY)}
    if name not in providers:
        raise SystemExit(f"Unknown AI_PROVIDER '{name}'; supported: {sorted(providers)}")
    return providers[name]()
```

### 14.3 `ai_judge.py` after the refactor

- **Prompt construction (`BATCH_SYSTEM_PROMPT`, `_ticker_block`, the user-prompt assembly) is
  unchanged** — that's product logic (the actual investment-judgment prompt), not provider plumbing; it
  has nothing to do with FR33.
- **`_parse_batch()` is unchanged** — it already only touches JSON text, no Gemini types.
- **`_generate()` becomes the provider-neutral retry loop**, taking an `AIProvider` instead of a
  `genai.Client`:
  ```python
  def _generate(provider, model, system_prompt, user_prompt, schema, timeout_ms,
                max_retries, retry_base_ms) -> tuple[str, bool, str | None, TokenUsage | None, int]:
      retries = 0
      while True:
          try:
              result = provider.generate(model=model, system_prompt=system_prompt,
                                          user_prompt=user_prompt, schema=schema, timeout_ms=timeout_ms)
              return result.text, False, None, result.usage, retries
          except ProviderError as e:
              if e.error_class != ErrorClass.RETRYABLE or retries >= max_retries:
                  return "", True, e.detail, None, retries
              cap_s = retry_base_ms * (2 ** retries) / 1000.0
              delay_s = random.uniform(0, cap_s)
              retries += 1
              print(f"  [ai_judge] {model}: transient error ({e.detail}); retry "
                    f"{retries}/{max_retries} in {delay_s:.1f}s (cap {cap_s:.0f}s)")
              time.sleep(delay_s)
  ```
  Retry count/backoff/jitter policy stays centrally controlled by `config.GEMINI_MAX_RETRIES` /
  `GEMINI_RETRY_BASE_MS` / `GEMINI_TIMEOUT_MS`, identical to today — only the transport call and error
  classification move behind `AIProvider`.
- **`judge_batch(items, models=None, provider=None)`** — new optional `provider` parameter, defaulting
  to `get_provider(config.AI_PROVIDER)`. **No caller outside `ai_judge.py` needs to change**:
  `run_hourly.py` and `run_discovery.py` keep calling `judge_batch(items)` / `judge_batch(items,
  models=config.discovery_models())` exactly as today. Return contract (`{ticker: {verdict, confidence,
  rationale, raw_model_response, parse_status, model_used, usage, fallback_from, retry_count}}`) is
  byte-identical.
- `google.genai` / `google.genai.types` imports move entirely into `ai_provider.py`; `ai_judge.py` no
  longer imports them.

**Client construction cadence — decided REV-076 (2026-07-28).** Putting `timeout_ms` on `generate()`
rather than on `GeminiProvider.__init__` (so a single provider instance could in principle serve calls at
different timeouts) has a real consequence the initial cut missed: `GeminiProvider` is instantiated once
per `judge_batch()` call (§14.2's `get_provider()`, called once at the top of `judge_batch`) and then
reused across every model in the try-list and every retry within `_generate()`'s loop — but if `generate()`
calls `_client()` itself on every invocation, that reuse buys nothing, and a fresh `genai.Client` (fresh
httpx transport, fresh TLS handshake) is built on every attempt: up to `(GEMINI_MAX_RETRIES + 1)` per model
× up to 2 models × up to 2 parse attempts, vs. exactly 1 per batch pre-INC-4.

**Decision: cache the client on the `GeminiProvider` instance, keyed by `timeout_ms`.** In every live call
path `timeout_ms` is always `config.GEMINI_TIMEOUT_MS` — a single process-wide config value, never varied
per model or per retry — so within one `judge_batch()` call the cache key never changes and this restores
the pre-INC-4 cadence exactly (1 client per batch, matching `config.py`'s "logged at call setup" comment
and `judge_batch()`'s own once-per-batch config-log line, REV-075). The key (rather than an unconditional
single cached client) is kept anyway, at negligible cost, so the interface's per-call `timeout_ms`
parameter stays honest for any future caller that *does* vary it — a construction, not a correctness,
concern: `AIProvider.generate()`'s signature does not change, and no test seam changes (`get_provider()`
still runs inside `judge_batch()` after monkeypatching, per `docs/handoff.md`'s existing test approach).
No downside was found: nothing in the Gemini SDK requires a fresh client per request (the client is a thin
transport wrapper, not a stateful session tied to one call), and connection reuse across retries is
strictly better for a batch that's already retrying because of transient transport trouble.

```python
class GeminiProvider(AIProvider):
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = None
        self._client_timeout_ms = None

    def generate(self, *, model, system_prompt, user_prompt, schema, timeout_ms) -> ProviderResult:
        if self._client is None or self._client_timeout_ms != timeout_ms:
            self._client = _client(self._api_key, timeout_ms)
            self._client_timeout_ms = timeout_ms
        # ...unchanged below: build cfg, call self._client.models.generate_content(...)
```

**Dev action required:** apply the caching shown above to `scripts/ai_provider.py`'s `GeminiProvider`
(currently constructs a fresh client on every `generate()` call, `ai_provider.py:145`). No other file
changes; no test or interface changes.

**Temperature tunable — decided REV-078 (2026-07-28).** `temperature=0.2` was a bare literal in
`ai_provider.py:150`, moved verbatim from pre-INC-4 `ai_judge.py` and never entered into either config
audit baseline. **Decision: promote it to a tunable, `AI_TEMPERATURE`, following the exact pattern already
used for `GEMINI_TIMEOUT_MS`/`GEMINI_MAX_RETRIES`/`GEMINI_RETRY_BASE_MS`** — those are the other three
Gemini call-shape parameters in this codebase and all three are already `config.py` env-var tunables with
a literal default; treating `temperature` differently (as a permanent bare constant) would be the one
exception to that pattern with no principled reason for it. This is **not** the "genuinely fixed
toolchain/structural fact" carve-out §9 already documents (`runs-on`, action pins, etc.) — temperature is
a model-behavior parameter exactly like the three it sits next to in the same `GenerateContentConfig`
call. `requirements_docs/SD.md`'s "low, to reduce run-to-run drift" rationale is preserved as the
**default value**, not as a reason to forbid operator override — an operator who deliberately raises it
accepts the drift tradeoff explicitly, the same way an operator who raises `GEMINI_MAX_RETRIES` accepts a
longer worst-case run time. Default stays `0.2`; nothing about current behavior changes until an operator
edits the value. Not on the admin portal's curated list (FR30) — same rationale as `AI_PROVIDER`, no
proven need for at-runtime (no-commit) editing yet; a `config.py`/repo-Variable-level tunable is
sufficient today.

**Dev action required:** add to `scripts/config.py` (non-curated set, same section as the other Gemini
call-shape tunables, near `GEMINI_TIMEOUT_MS`):
```python
# Sampling temperature for the Gemini call (ai_provider.GeminiProvider.generate). Kept LOW by default
# to reduce run-to-run verdict drift (requirements_docs/SD.md); tunable per CLAUDE.md's no-hardcoded-
# tunables rule, same pattern as GEMINI_TIMEOUT_MS/GEMINI_MAX_RETRIES/GEMINI_RETRY_BASE_MS.
AI_TEMPERATURE = float(os.environ.get("AI_TEMPERATURE", "0.2"))
```
and change `ai_provider.py:150`'s `temperature=0.2` to `temperature=config.AI_TEMPERATURE` (already
reflected in §14.2 above). No interface or test-seam change; `config` is already imported in
`ai_provider.py`.

### 14.4 Configuration addition

| Key | Default | Purpose |
|---|---|---|
| `AI_PROVIDER` | `"gemini"` | Selects the `AIProvider` implementation `judge_batch()` uses. Only `"gemini"` is implemented (FR33/Decision #26 — no second provider built). Not on the admin portal's curated tunables list (FR30) — no reason to expose a single-valued selector; adding a second provider is a future change request that would also update FR30's curated list if it should be portal-editable. |
| `AI_TEMPERATURE` | `0.2` | Sampling temperature for the Gemini call (REV-078, 2026-07-28). Kept low by default to reduce run-to-run verdict drift; operator-tunable like the other three Gemini call-shape parameters. Not on the admin portal's curated list (FR30) — same rationale as `AI_PROVIDER`. |

### 14.5 Requirement coverage

| Requirement | Covered by |
|---|---|
| FR33 (provider-neutral interface, Gemini sole live provider) | §14.1–§14.4 |
