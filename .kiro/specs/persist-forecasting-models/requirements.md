# Requirements: Persist & Schedule Forecasting Model Training

## Overview
The current forecasting engine in `aiapp/forecasting.py` refits scikit-learn models on every
request, which is slow and produces inconsistent results when data changes mid-session.
This feature persists trained models to disk and serves predictions from the cached files,
with a management command for scheduled retraining.

## Requirements

### REQ-1: Persist trained models to disk
The system shall serialize trained scikit-learn models to `.pkl` files using `joblib`,
stored in `aiapp/models/` (gitignored). A companion `model_meta.json` file shall store
training metadata (timestamp, sample count, R² score where applicable) for each model.

### REQ-2: Load from disk at prediction time
`forecasting.py` prediction functions shall load saved `.pkl` files instead of refitting
on every call. Model objects shall be cached in-process after the first load so repeated
calls within the same process do not hit disk repeatedly.

### REQ-3: Graceful fallback
If a model file is missing, corrupted, or older than `FORECAST_MODEL_MAX_AGE_DAYS`
(default: 7, configurable in `settings.py`), the system shall fall back to the existing
live-fit behavior and log a warning. Predictions must never raise an unhandled exception
due to a missing model.

### REQ-4: `train_forecasting_models` management command
A Django management command at
`aiapp/management/commands/train_forecasting_models.py` shall:
- Pull current data from the database
- Fit all four models (weekly bookings, mechanic demand, service demand, spare part demand)
- Serialize each model + metadata to disk
- Print a formatted summary table showing model name, sample count, R² (where applicable),
  and file size
- Support a `--force` flag to retrain even if models are fresh

### REQ-5: Scheduled retraining documentation
The command shall include inline documentation showing how to schedule it via:
- Windows Task Scheduler (the platform already in use for `cancel_unpaid_bookings`)
- Unix cron (for reference)

### REQ-6: Forecast dashboard model freshness
The existing forecast dashboard (`aiapp/templates/aiapp/forecast_dashboard.html`) shall
display a "Model last trained" badge showing the timestamp and sample size from
`model_meta.json`, so admins know whether predictions are stale.

### REQ-7: Directory and gitignore setup
The `aiapp/models/` directory shall be created with a `.gitkeep` placeholder.
A `.gitignore` entry in that directory shall exclude `*.pkl` files from version control
(model files can be large and are environment-specific), while keeping `model_meta.json`
tracked so the last-trained timestamp survives deployments.
