# intervals-icu-fitnotes

Sync strength training sessions from [Fit Notes](https://play.google.com/store/apps/details?id=com.github.jamesgay.fitnotes) (Android) to [intervals.icu](https://intervals.icu) activity descriptions.

Mainly vibe coded so be careful.

## What it does

Garmin syncs strength activities to intervals.icu but without any set-by-set detail. Fit Notes logs every set with weight, reps, RPE, etc. This tool matches them by timestamp and pastes the Fit Notes detail into the corresponding intervals.icu activity description.

It's purely informational. No graphs, no training load calculations, no fitness metrics. Just so when you scroll through your activities on intervals.icu, your strength sessions actually show what you did.

Example output in an activity description:

```
Séance A + Core — 31 sets across 9 exercises, 5.7t

Bench Press: 5×50kg RPE7 · 5×53kg RPE8 · 5×53kg RPE8 · 5×53kg RPE9
Overhead Press: 5×30kg RPE7 · 5×30kg RPE7 · 5×30kg RPE6 · 5×33kg RPE7
Pullup: 3×5kg RPE7 · 4×BW RPE6 · 3×BW RPE6
Barbell Row: 5×70kg RPE6 · 5×75kg RPE7 · 5×75kg RPE8 · 5×70kg RPE7
Hollow hold: 3×30s
Dead bug: 3×10 reps
```

## How it works

1. Export your Fit Notes data as CSV (Settings → Export → Workouts)
2. The tool reads the CSV and groups sets into sessions
3. It fetches your recent strength activities from intervals.icu (`WeightTraining` or `Workout` type)
4. Sessions are matched to activities by time overlap (±2h tolerance)
5. Matched sessions are formatted and written to the activity description

Multiple Fit Notes sessions overlapping one activity get aggregated (e.g. main session + core finisher).

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/melvinrdn/intervals-icu-fitnotes.git
cd intervals-icu-fitnotes
uv sync
```

Copy `.env.example` to `.env` and fill in:

```
ICU_API_KEY=your_api_key_here          # from intervals.icu → Settings → Developer Settings
ICU_ATHLETE_ID=your_ahlete_id_here     # same
FITNOTES_CSV=data/FitNotesWorkouts.csv # path to your Fit Notes export
```

## Usage

```bash
# See what strength activities exist on intervals.icu
uv run icu-sync list-activities --since 2026-05-01

# Preview what would be written (no changes)
uv run icu-sync dry-run --since 2026-05-01

# Actually write to intervals.icu
uv run icu-sync sync --since 2026-05-01 --apply
```

The `--apply` flag is required to actually write. Without it, `sync` runs as dry-run.

## Tests

```bash
uv run pytest
```

## License

MIT