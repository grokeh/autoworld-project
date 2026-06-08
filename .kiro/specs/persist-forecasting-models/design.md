# Design: Persist & Schedule Forecasting Model Training

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Admin Dashboard / forecast_dashboard.html              │
│  Shows "Model last trained: X mins ago, N samples"      │
└────────────────────┬────────────────────────────────────┘
                     │ reads meta
                     ▼
┌─────────────────────────────────────────────────────────┐
│  aiapp/forecasting.py  (updated)                        │
│                                                         │
│  ModelCache (module-level dict)                         │
│    weekly_bookings → loaded LinearRegression            │
│    mechanic_demand → loaded dict                        │
│    ...                                                  │
│                                                         │
│  load_model(name) → tries .pkl → falls back to live-fit │
│  get_model_meta() → reads model_meta.json               │
└────────────────────┬────────────────────────────────────┘
                     │ joblib.load / joblib.dump
                     ▼
┌─────────────────────────────────────────────────────────┐
│  aiapp/models/  (directory)                             │
│    weekly_bookings.pkl                                  │
│    mechanic_demand.pkl                                  │
│    service_demand.pkl                                   │
│    sparepart_demand.pkl                                 │
│    model_meta.json                                      │
│    .gitignore  (excludes *.pkl, keeps meta.json)        │
│    .gitkeep                                             │
└─────────────────────────────────────────────────────────┘
                     ▲
                     │ writes
┌─────────────────────────────────────────────────────────┐
│  aiapp/management/commands/train_forecasting_models.py  │
│                                                         │
│  python manage.py train_forecasting_models              │
│  python manage.py train_forecasting_models --force      │
│                                                         │
│  Scheduled via Windows Task Scheduler / cron            │
└─────────────────────────────────────────────────────────┘
```

## File Layout

```
aiapp/
  management/
    __init__.py          (may already exist)
    commands/
      __init__.py
      train_forecasting_models.py   ← NEW
  models/                           ← NEW directory
    .gitkeep
    .gitignore
    model_meta.json                 (created by command)
    *.pkl                           (gitignored, created by command)
  forecasting.py                    ← UPDATED
```

## Model Storage Schema

### `model_meta.json`
```json
{
  "weekly_bookings": {
    "trained_at": "2025-01-15T10:30:00Z",
    "samples": 147,
    "score": 0.82,
    "file": "weekly_bookings.pkl"
  },
  "mechanic_demand": {
    "trained_at": "2025-01-15T10:30:00Z",
    "samples": 147,
    "file": "mechanic_demand.pkl"
  },
  "service_demand": {
    "trained_at": "2025-01-15T10:30:00Z",
    "samples": 147,
    "file": "service_demand.pkl"
  },
  "sparepart_demand": {
    "trained_at": "2025-01-15T10:30:00Z",
    "samples": 89,
    "file": "sparepart_demand.pkl"
  }
}
```

### pkl file contents (joblib-serialized dicts)

**weekly_bookings.pkl:**
```python
{
  'model': LinearRegression(),   # fitted sklearn model
  'n_weeks': int,                # number of weekly data points
  'historical_avg': float,
}
```

**mechanic_demand.pkl / service_demand.pkl / sparepart_demand.pkl:**
```python
{
  'results': list,   # pre-computed ranked list (same shape as current return values)
}
```

Note: mechanic/service/sparepart forecasts are frequency-based aggregations, not
sklearn models — they're stored as pre-computed result lists for instant serving.

## `forecasting.py` Changes

### Module-level cache
```python
_MODEL_CACHE = {}   # name → loaded object, populated lazily
```

### New helper functions
```python
def _models_dir() -> Path
def _meta_path() -> Path
def load_model(name: str) -> dict | None
def get_model_meta() -> dict
def _is_stale(trained_at_str: str) -> bool
```

### Updated forecast functions
Each function follows this pattern:
1. Try `load_model(name)` — returns pre-computed result or fitted model
2. If loaded and not stale → use it
3. Else → live-fit (existing code path), log warning if stale
4. `forecast_weekly_bookings` additionally uses the loaded LinearRegression to
   predict instead of re-fitting

## `train_forecasting_models` Management Command

### Behavior
1. Check if models are fresh (unless `--force`)
2. Load booking + spare part DataFrames once
3. Fit / compute each of the four model bundles
4. Save each bundle to its `.pkl` file via `joblib.dump`
5. Write `model_meta.json` with training metadata
6. Print summary table

### Output example
```
AutoWorld Forecasting Model Training
=====================================
Model               Samples  Score    File Size  Status
------------------  -------  -------  ---------  -------
weekly_bookings     147      R²=0.82  12.4 KB    ✅ saved
mechanic_demand     147      —        8.1 KB     ✅ saved
service_demand      147      —        5.2 KB     ✅ saved
sparepart_demand    89       —        9.7 KB     ✅ saved

Models saved to: aiapp/models/
Next suggested run: 2025-01-16 02:00:00 UTC
```

### Scheduling (documented in command docstring)
**Windows Task Scheduler:**
```
Action:     python manage.py train_forecasting_models
Start in:   C:\Users\zegie\Desktop\autoworld_project
Trigger:    Daily at 02:00 AM
```

**Unix cron:**
```
0 2 * * * cd /path/to/autoworld_project && python manage.py train_forecasting_models
```

## Settings

Add to `settings.py`:
```python
# Forecasting model max age before stale fallback (days)
FORECAST_MODEL_MAX_AGE_DAYS = 7
```

## Forecast Dashboard Changes

In the forecast dashboard view, pass `model_meta` to template context.
In `forecast_dashboard.html`, add a small badge near the top:

```html
<div class="model-freshness-badge">
  📊 Model trained: {{ model_meta.weekly_bookings.trained_at|timesince }} ago
  &middot; {{ model_meta.weekly_bookings.samples }} samples
</div>
```

## Dependencies

No new Python packages required. `joblib` ships with scikit-learn and is already
available in any environment that has `sklearn` installed.
