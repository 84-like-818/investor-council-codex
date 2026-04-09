# Memory Schema

The skill keeps one lightweight session file so follow-up questions can inherit context.

## Fields

- `last_stock`
  - `code`
  - `name`
  - `industry`
- `last_position`
  - `pct`
  - `text`
- `watchlist`
- `last_market_notes`
- `recent_questions`
- `last_answer_summary`
- `updated_at`

## How To Use It

1. Read memory before answering a follow-up.
2. Update memory after a substantive answer.
3. If the user changes stock or position, overwrite the stored value.
4. Keep memory lightweight; it is session context, not a diary.

## When To Trust Memory

Trust memory for:
- last discussed stock
- latest stated position
- latest market notes

Do not trust memory over explicit new user input.
