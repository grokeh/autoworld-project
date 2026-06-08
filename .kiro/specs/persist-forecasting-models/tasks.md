# Tasks: Persist & Schedule Forecasting Model Training

- [x] 1. Create the aiapp/models/ directory and supporting files
  - Create `aiapp/models/.gitkeep` placeholder file
  - Create `aiapp/models/.gitignore` that excludes `*.pkl` but tracks `model_meta.json`
  - Ensure `aiapp/management/__init__.py` and `aiapp/management/commands/__init__.py` exist
  - _Requirements: REQ-7_

- [x] 2. Add settings and helper utilities to forecasting.py
  - Add `FORECAST_MODEL_MAX_AGE_DAYS = 7` to `autoworld_project/settings.py`
  - Add module-level `_MODEL_CACHE = {}` dict to `aiapp/forecasting.py`
  - Add helper functions: `_models_dir()`, `_meta_path()`, `get_model_meta()`, `_is_stale()`, `load_model()`, `save_model()` to `aiapp/forecasting.py`
  - _Requirements: REQ-2, REQ-3_
  - _Dependencies: 1_

- [x] 3. Create the train_forecasting_models management command
  - Create `aiapp/management/commands/train_forecasting_models.py`
  - Command fits weekly_bookings LinearRegression, mechanic_demand aggregation, service_demand aggregation, sparepart_demand aggregation from live DB data
  - Saves each bundle as a `.pkl` file via `joblib.dump` and writes `model_meta.json`
  - Supports `--force` flag; prints formatted summary table
  - Includes Windows Task Scheduler and cron scheduling instructions in docstring
  - _Requirements: REQ-4, REQ-5_
  - _Dependencies: 1, 2_

- [x] 4. Update forecasting.py prediction functions to load from disk
  - `forecast_weekly_bookings`: load saved LinearRegression from disk, use it for prediction, fall back to live-fit with log warning if missing/stale
  - `forecast_mechanic_demand`: return pre-computed results from disk, fall back to live compute if missing/stale
  - `forecast_service_demand`: return pre-computed results from disk, fall back to live compute if missing/stale
  - `forecast_sparepart_demand`: return pre-computed results from disk, fall back to live compute if missing/stale
  - _Requirements: REQ-1, REQ-2, REQ-3_
  - _Dependencies: 2_

- [x] 5. Update forecast dashboard to show model freshness
  - Update the forecast view in `aiapp/views.py` to pass `model_meta` from `get_model_meta()` into template context
  - Add a "Model last trained" badge to `aiapp/templates/aiapp/forecast_dashboard.html` using Django `timesince` filter and sample count
  - Show "Not yet trained" gracefully when `model_meta.json` does not exist
  - _Requirements: REQ-6_
  - _Dependencies: 2_
