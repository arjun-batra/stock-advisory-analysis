"""Pure wallet-walk state machine + P&L (design.md §17.2, FR31).

The single shared implementation of the Buy->holding / Sell->flat / Hold->no-op
position machine. `run_shadow.py` and `run_shadow_nse.py` both call `walk()` to
derive each ticker's live position from its own shadow-table history;
`eval_shadow.py` calls the same function to reconstruct that history for
evaluation. Same code, same answer -- the position that drove a prompt and the
position the harness reconstructs can never silently diverge.

No I/O, no Supabase, no network -- a pure function over plain dicts, so it is
trivially unit-testable and its output is deterministic for a given input.
"""

Row = dict   # {"verdict": "Buy"|"Sell"|"Hold", "timestamp": <orderable>, "price": float|None}


def walk(rows: list[Row], *, mark_price: float | None = None) -> dict:
    """Walk one ticker's history (oldest -> newest) and return its position,
    every closed round-trip, and (if `mark_price` is given) the still-open
    position marked to that price.

    Rules: a Buy only opens a position while flat (a Buy while already holding
    is a no-op); a Sell only closes a position while holding (a Sell while flat
    is a no-op); a Hold (including every fail-safe Hold) is always a no-op.
    Empty input -> flat, no round-trips, no open position.

    Returns:
        {
          "position": {"state": "holding"|"flat", "entry_price": float|None, "entry_date": <ts>|None},
          "round_trips": [{"entry_price", "entry_date", "exit_price", "exit_date", "return_pct"}],
          "open": None | {"entry_price", "entry_date", "mark_price", "unrealized_return_pct"},
        }
    """
    state_flag, entry_price, entry_date = "flat", None, None
    round_trips: list[dict] = []

    for row in rows:
        verdict = row.get("verdict")
        price = row.get("price")
        ts = row.get("timestamp")

        if verdict == "Buy" and state_flag == "flat":
            state_flag, entry_price, entry_date = "holding", price, ts
        elif verdict == "Sell" and state_flag == "holding":
            round_trips.append({
                "entry_price": entry_price, "entry_date": entry_date,
                "exit_price": price, "exit_date": ts,
                "return_pct": _return_pct(entry_price, price),
            })
            state_flag, entry_price, entry_date = "flat", None, None
        # Hold, Buy-while-holding, Sell-while-flat: no-op.

    open_position = None
    if state_flag == "holding":
        open_position = {
            "entry_price": entry_price, "entry_date": entry_date,
            "mark_price": mark_price,
            "unrealized_return_pct": _return_pct(entry_price, mark_price),
        }

    return {
        "position": {"state": state_flag, "entry_price": entry_price, "entry_date": entry_date},
        "round_trips": round_trips,
        "open": open_position,
    }


def _return_pct(entry_price: float | None, exit_price: float | None) -> float | None:
    if entry_price in (None, 0) or exit_price is None:
        return None
    return round((exit_price / entry_price - 1) * 100, 4)
