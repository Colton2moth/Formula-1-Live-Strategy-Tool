# Feature Ideas

## Leaderboard pit probability (PIT SOON) column

Add a compact pit-probability column to the live driver table so each row can show the model estimate for that driver.

Current data fit:

- `RaceState.predictions` already includes one prediction per driver when available.
- Each prediction is keyed by `driver_number`.
- `pit_within_5_laps` can be matched to the leaderboard row's driver by `driver_number`.

Practical approach:

- Build one shared prediction lookup from the race snapshot instead of requesting predictions per row.
- Pass the lookup or prediction list into `Leaderboard`.
- Show a compact value such as `72%`, with `--` when no prediction exists.
- Keep the detailed explanation in the AI strategy panel; use the leaderboard column only as a quick scan indicator.

Live-data requirement:

- The live snapshot or WebSocket payload should include prediction updates for all visible drivers, not only the selected driver.

## First-visit tooltip walkthrough

Add a short tooltip walkthrough on a user's first visit to introduce the dashboard's main controls and data areas.

- Highlight the race header, track map, live driver table, and AI strategy panel in sequence.
- Let users skip or dismiss the walkthrough at any time.
- Remember completion locally so the walkthrough does not appear on every visit.
