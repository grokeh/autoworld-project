"""
AutoWorld Demand Forecasting Engine
Uses Scikit-learn to predict:
  1. Booking demand per mechanic (next 7 days)
  2. Spare part demand (most likely to be ordered)
  3. Service type demand trends
  4. Weekly booking volume forecast
"""

import logging
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# ─── In-process model cache ───────────────────────────────────────────────────
_MODEL_CACHE: dict = {}


# ─── Model Persistence Helpers ───────────────────────────────────────────────

def _models_dir() -> Path:
    """Return the path to the aiapp/models/ directory."""
    return Path(__file__).resolve().parent / 'models'


def _meta_path() -> Path:
    """Return the path to model_meta.json."""
    return _models_dir() / 'model_meta.json'


def get_model_meta() -> dict:
    """
    Load and return the model_meta.json contents.
    Returns an empty dict if the file does not exist or cannot be parsed.
    """
    path = _meta_path()
    if not path.exists():
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _is_stale(trained_at_str: str) -> bool:
    """
    Return True if the model was trained more than FORECAST_MODEL_MAX_AGE_DAYS ago.
    Uses UTC comparison.
    """
    from datetime import timezone as dt_tz
    try:
        max_age = getattr(settings, 'FORECAST_MODEL_MAX_AGE_DAYS', 7)
        trained_at = datetime.fromisoformat(trained_at_str.replace('Z', '+00:00'))
        age_days = (datetime.now(dt_tz.utc) - trained_at).days
        return age_days > max_age
    except Exception:
        return True  # treat parse errors as stale


def load_model(name: str) -> dict | None:
    """
    Load a model bundle from disk (with in-process caching).
    Returns the deserialized dict, or None if missing/stale/corrupt.
    """
    import joblib

    # Return cached version if available
    if name in _MODEL_CACHE:
        return _MODEL_CACHE[name]

    pkl_path = _models_dir() / f'{name}.pkl'
    if not pkl_path.exists():
        logger.warning('Forecasting model not found: %s — using live-fit fallback', pkl_path)
        return None

    # Check staleness via meta
    meta = get_model_meta()
    model_meta = meta.get(name, {})
    trained_at = model_meta.get('trained_at', '')
    if trained_at and _is_stale(trained_at):
        logger.warning('Forecasting model %s is stale (trained: %s) — using live-fit fallback', name, trained_at)
        return None

    try:
        bundle = joblib.load(pkl_path)
        _MODEL_CACHE[name] = bundle
        return bundle
    except Exception as e:
        logger.warning('Failed to load forecasting model %s: %s — using live-fit fallback', name, e)
        return None


def save_model(name: str, bundle: dict) -> None:
    """
    Serialize a model bundle to disk and invalidate the in-process cache entry.
    """
    import joblib

    models_dir = _models_dir()
    models_dir.mkdir(exist_ok=True)
    pkl_path = models_dir / f'{name}.pkl'
    joblib.dump(bundle, pkl_path)
    # Invalidate cache so next load picks up the new file
    _MODEL_CACHE.pop(name, None)


# ─── Data Extraction ─────────────────────────────────────────────────────────

def get_booking_dataframe():
    """Build a DataFrame from booking history."""
    from ecommerceapp.models import Booking
    bookings = Booking.objects.select_related('mechanic').values(
        'id', 'booking_date', 'service_type', 'mechanic__name',
        'mechanic__id', 'status', 'created_at'
    )
    if not bookings:
        return pd.DataFrame()

    df = pd.DataFrame(list(bookings))
    df['booking_date'] = pd.to_datetime(df['booking_date'])
    df['created_at'] = pd.to_datetime(df['created_at'], utc=True)
    df['day_of_week'] = df['booking_date'].dt.dayofweek
    df['week'] = df['booking_date'].dt.isocalendar().week.astype(int)
    df['month'] = df['booking_date'].dt.month
    df['year'] = df['booking_date'].dt.year
    return df


def get_sparepart_dataframe():
    """Build a DataFrame from cart/order history for spare parts."""
    from ecommerceapp.models import CartItem
    items = CartItem.objects.filter(
        spare_part__isnull=False
    ).select_related('spare_part').values(
        'spare_part__id', 'spare_part__name',
        'spare_part__compatible_vehicle', 'quantity', 'added_on'
    )
    if not items:
        return pd.DataFrame()

    df = pd.DataFrame(list(items))
    df['added_on'] = pd.to_datetime(df['added_on'], utc=True)
    df['month'] = df['added_on'].dt.month
    df['week'] = df['added_on'].dt.isocalendar().week.astype(int)
    return df


# ─── Forecasting Functions ────────────────────────────────────────────────────

def forecast_weekly_bookings():
    """
    Predict booking volume for the next 7 days using linear regression
    on historical weekly booking counts.
    Returns: {'forecast': int, 'trend': 'up'|'down'|'stable', 'confidence': float}
    """
    try:
        from sklearn.linear_model import LinearRegression

        # --- Try loading from disk first ---
        bundle = load_model('weekly_bookings')
        if bundle is not None and isinstance(bundle.get('model'), LinearRegression):
            next_t = np.array([[bundle['n_weeks']]])
            forecast = max(0, int(bundle['model'].predict(next_t)[0]))
            score = bundle.get('score', 0.0)
            trend = bundle.get('trend', 'stable')
            historical_avg = bundle.get('historical_avg', 0.0)
            return {
                'forecast': forecast,
                'trend': trend,
                'confidence': round(score, 2),
                'message': f'Predicted {forecast} bookings next week (R²={score:.2f})',
                'historical_avg': historical_avg,
            }

        # bundle exists but has no usable model (insufficient_data flag or model is None)
        # fall through to live-fit below

        # --- Live-fit fallback ---
        df = get_booking_dataframe()
        if df.empty or len(df) < 5:
            return {'forecast': 0, 'trend': 'stable', 'confidence': 0.0,
                    'message': 'Not enough data for forecasting yet.'}

        # Group by week
        weekly = df.groupby(['year', 'week']).size().reset_index(name='count')
        weekly = weekly.sort_values(['year', 'week']).reset_index(drop=True)
        weekly['t'] = range(len(weekly))

        if len(weekly) < 3:
            avg = weekly['count'].mean()
            return {'forecast': int(avg), 'trend': 'stable', 'confidence': 0.5,
                    'message': f'Based on {len(df)} bookings.'}

        X = weekly[['t']].values
        y = weekly['count'].values

        model = LinearRegression()
        model.fit(X, y)

        next_t = np.array([[len(weekly)]])
        forecast = max(0, int(model.predict(next_t)[0]))
        score = max(0.0, min(1.0, float(model.score(X, y))))

        slope = model.coef_[0]
        trend = 'up' if slope > 0.1 else ('down' if slope < -0.1 else 'stable')

        return {
            'forecast': forecast,
            'trend': trend,
            'confidence': round(score, 2),
            'message': f'Predicted {forecast} bookings next week (R²={score:.2f})',
            'historical_avg': round(float(weekly['count'].mean()), 1),
        }
    except Exception as e:
        return {'forecast': 0, 'trend': 'stable', 'confidence': 0.0,
                'message': f'Forecast error: {str(e)[:60]}'}


def forecast_mechanic_demand():
    """
    Rank mechanics by predicted demand for the next 7 days.
    Uses booking frequency per mechanic.
    Returns: list of {'mechanic': str, 'predicted_bookings': int, 'load': 'high'|'medium'|'low'}
    """
    try:
        # --- Try loading from disk first ---
        bundle = load_model('mechanic_demand')
        if bundle is not None:
            return bundle.get('results', [])

        # --- Live-compute fallback ---
        df = get_booking_dataframe()
        if df.empty:
            return []

        # Count bookings per mechanic in last 30 days
        cutoff = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=30)
        recent = df[df['created_at'] >= cutoff] if 'created_at' in df.columns else df

        if recent.empty:
            recent = df

        mechanic_counts = recent.groupby('mechanic__name').size().reset_index(name='count')
        mechanic_counts = mechanic_counts.sort_values('count', ascending=False)

        total = mechanic_counts['count'].sum()
        results = []
        for _, row in mechanic_counts.iterrows():
            share = row['count'] / total if total > 0 else 0
            predicted = max(1, int(share * 10))  # scale to next-week estimate
            load = 'high' if predicted >= 4 else ('medium' if predicted >= 2 else 'low')
            results.append({
                'mechanic': row['mechanic__name'],
                'predicted_bookings': predicted,
                'load': load,
                'recent_bookings': int(row['count']),
            })
        return results[:8]  # top 8

    except Exception as e:
        return []


def forecast_service_demand():
    """
    Predict which service types will be most in demand.
    Returns: list of {'service': str, 'demand_score': float, 'trend': str}
    """
    try:
        # --- Try loading from disk first ---
        bundle = load_model('service_demand')
        if bundle is not None:
            return bundle.get('results', [])

        # --- Live-compute fallback ---
        df = get_booking_dataframe()
        if df.empty:
            return []

        service_counts = df.groupby('service_type').size().reset_index(name='count')
        service_counts = service_counts.sort_values('count', ascending=False)
        total = service_counts['count'].sum()

        results = []
        for _, row in service_counts.iterrows():
            score = round((row['count'] / total) * 100, 1) if total > 0 else 0
            results.append({
                'service': row['service_type'],
                'demand_score': score,
                'count': int(row['count']),
                'trend': 'high' if score > 30 else ('medium' if score > 15 else 'low'),
            })
        return results

    except Exception as e:
        return []


def forecast_sparepart_demand():
    """
    Predict which spare parts will be most in demand.
    Returns: list of {'part': str, 'predicted_orders': int, 'compatible': str}

    Attempts to load a persisted model from disk first; falls back to live-compute
    if no model is available or the model is stale.
    """
    try:
        # --- Try loading from disk first ---
        bundle = load_model('sparepart_demand')
        if bundle is not None:
            return bundle.get('results', [])

        # --- Live-compute fallback ---
        df = get_sparepart_dataframe()
        if df.empty:
            # Fallback: use all spare parts with zero demand
            from ecommerceapp.models import SparePart
            parts = SparePart.objects.all()[:10]
            return [{'part': p.name, 'predicted_orders': 0,
                     'compatible': p.compatible_vehicle, 'trend': 'unknown'} for p in parts]

        part_demand = df.groupby(
            ['spare_part__name', 'spare_part__compatible_vehicle']
        )['quantity'].sum().reset_index()
        part_demand.columns = ['name', 'compatible', 'total_qty']
        part_demand = part_demand.sort_values('total_qty', ascending=False)

        results = []
        for _, row in part_demand.iterrows():
            qty = int(row['total_qty'])
            trend = 'high' if qty >= 5 else ('medium' if qty >= 2 else 'low')
            results.append({
                'part': row['name'],
                'predicted_orders': qty,
                'compatible': row['compatible'],
                'trend': trend,
            })
        return results[:10]

    except Exception as e:
        return []


def get_day_of_week_pattern():
    """
    Analyse which days of the week have the most bookings.
    Returns: list of {'day': str, 'count': int, 'pct': float}
    """
    try:
        df = get_booking_dataframe()
        if df.empty:
            return []

        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        day_counts = df.groupby('day_of_week').size().reset_index(name='count')
        total = day_counts['count'].sum()

        results = []
        for i, name in enumerate(day_names):
            row = day_counts[day_counts['day_of_week'] == i]
            count = int(row['count'].values[0]) if not row.empty else 0
            results.append({
                'day': name,
                'count': count,
                'pct': round((count / total) * 100, 1) if total > 0 else 0,
            })
        return results

    except Exception as e:
        return []


def get_full_forecast():
    """Run all forecasts and return combined results."""
    return {
        'weekly_bookings': forecast_weekly_bookings(),
        'mechanic_demand': forecast_mechanic_demand(),
        'service_demand': forecast_service_demand(),
        'sparepart_demand': forecast_sparepart_demand(),
        'day_pattern': get_day_of_week_pattern(),
    }
