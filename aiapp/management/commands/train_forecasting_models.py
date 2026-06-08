"""
Management command: train_forecasting_models

Trains and persists all AutoWorld demand forecasting models to disk.
Persisted models are loaded at prediction time instead of refitting on every request,
making forecasts faster and more consistent.

Run manually:
    python manage.py train_forecasting_models
    python manage.py train_forecasting_models --force

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCHEDULING — Windows Task Scheduler (recommended for this project)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Open Task Scheduler → Create Basic Task
2. Name: "AutoWorld - Retrain Forecasting Models"
3. Trigger: Daily at 02:00 AM
4. Action: Start a program
   Program:    python
   Arguments:  manage.py train_forecasting_models
   Start in:   C:\\Users\\zegie\\Desktop\\autoworld_project
5. Finish → OK

SCHEDULING — Unix/Linux cron
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Add to crontab (crontab -e):
    0 2 * * * cd /path/to/autoworld_project && python manage.py train_forecasting_models
"""

import json
import joblib
import numpy as np
from datetime import datetime, timezone as dt_tz
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Train and persist demand forecasting models to disk for faster predictions.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            default=False,
            help='Force retraining even if models are fresh (not stale).',
        )

    def handle(self, *args, **options):
        from aiapp.forecasting import (
            _models_dir, _meta_path, get_model_meta, _is_stale,
            save_model, get_booking_dataframe, get_sparepart_dataframe,
        )

        self.stdout.write(self.style.HTTP_INFO('\nAutoWorld Forecasting Model Training'))
        self.stdout.write('=' * 53)

        force = options['force']

        # Check if retraining is needed (unless --force)
        if not force:
            meta = get_model_meta()
            all_fresh = all(
                name in meta and meta[name].get('trained_at') and not _is_stale(meta[name]['trained_at'])
                for name in ['weekly_bookings', 'mechanic_demand', 'service_demand', 'sparepart_demand']
            )
            if all_fresh:
                self.stdout.write(self.style.SUCCESS(
                    'All models are fresh. Use --force to retrain anyway.'
                ))
                return

        # Load DataFrames once
        self.stdout.write('Loading data from database...')
        booking_df = get_booking_dataframe()
        sparepart_df = get_sparepart_dataframe()

        booking_samples = len(booking_df) if not booking_df.empty else 0
        sparepart_samples = len(sparepart_df) if not sparepart_df.empty else 0

        trained_at = datetime.now(dt_tz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        meta_updates = {}
        results = []

        # ── 1. Weekly Bookings (LinearRegression) ────────────────────────────
        row = self._train_weekly_bookings(booking_df, trained_at)
        results.append(row)
        if row['status'] == 'saved':
            meta_updates['weekly_bookings'] = {
                'trained_at': trained_at,
                'samples': booking_samples,
                'score': row.get('score'),
                'file': 'weekly_bookings.pkl',
            }

        # ── 2. Mechanic Demand (aggregation) ─────────────────────────────────
        row = self._train_mechanic_demand(booking_df, trained_at)
        results.append(row)
        if row['status'] == 'saved':
            meta_updates['mechanic_demand'] = {
                'trained_at': trained_at,
                'samples': booking_samples,
                'file': 'mechanic_demand.pkl',
            }

        # ── 3. Service Demand (aggregation) ──────────────────────────────────
        row = self._train_service_demand(booking_df, trained_at)
        results.append(row)
        if row['status'] == 'saved':
            meta_updates['service_demand'] = {
                'trained_at': trained_at,
                'samples': booking_samples,
                'file': 'service_demand.pkl',
            }

        # ── 4. Spare Part Demand (aggregation) ───────────────────────────────
        row = self._train_sparepart_demand(sparepart_df, trained_at)
        results.append(row)
        if row['status'] == 'saved':
            meta_updates['sparepart_demand'] = {
                'trained_at': trained_at,
                'samples': sparepart_samples,
                'file': 'sparepart_demand.pkl',
            }

        # Write model_meta.json
        meta_path = _meta_path()
        existing_meta = {}
        if meta_path.exists():
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    existing_meta = json.load(f)
            except Exception:
                pass
        existing_meta.update(meta_updates)
        meta_path.parent.mkdir(exist_ok=True)
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(existing_meta, f, indent=2)

        # Print summary table
        self.stdout.write('')
        self.stdout.write(f"{'Model':<22} {'Samples':>7}  {'Score':>8}  {'File Size':>10}  Status")
        self.stdout.write('-' * 62)
        for r in results:
            score_str = f"R²={r['score']:.2f}" if r.get('score') is not None else '—'
            size_str = r.get('size_str', '—')
            status_str = self.style.SUCCESS('✅ saved') if r['status'] == 'saved' else self.style.WARNING(f"⚠️  {r['status']}")
            self.stdout.write(
                f"{r['name']:<22} {r['samples']:>7}  {score_str:>8}  {size_str:>10}  {status_str}"
            )

        models_dir = _models_dir()
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Models saved to: {models_dir}'))
        self.stdout.write(f'Metadata:        {meta_path}')
        self.stdout.write('')

    # ── Training helpers ──────────────────────────────────────────────────────

    def _train_weekly_bookings(self, df, trained_at: str) -> dict:
        """Fit LinearRegression on weekly booking counts."""
        from sklearn.linear_model import LinearRegression
        from aiapp.forecasting import save_model

        name = 'weekly_bookings'
        try:
            if df.empty or len(df) < 5:
                save_model(name, {'results': None, 'insufficient_data': True})
                return {'name': name, 'samples': 0, 'score': None, 'status': 'saved (no data)', 'size_str': '—'}

            weekly = df.groupby(['year', 'week']).size().reset_index(name='count')
            weekly = weekly.sort_values(['year', 'week']).reset_index(drop=True)
            weekly['t'] = range(len(weekly))

            if len(weekly) < 3:
                avg = float(weekly['count'].mean())
                bundle = {'model': None, 'n_weeks': len(weekly), 'historical_avg': avg, 'insufficient_data': True}
                save_model(name, bundle)
                return {'name': name, 'samples': len(df), 'score': None, 'status': 'saved', 'size_str': self._file_size(name)}

            X = weekly[['t']].values
            y = weekly['count'].values

            model = LinearRegression()
            model.fit(X, y)
            score = max(0.0, min(1.0, float(model.score(X, y))))
            slope = model.coef_[0]
            trend = 'up' if slope > 0.1 else ('down' if slope < -0.1 else 'stable')

            bundle = {
                'model': model,
                'n_weeks': len(weekly),
                'historical_avg': round(float(weekly['count'].mean()), 1),
                'trend': trend,
                'score': round(score, 2),
            }
            save_model(name, bundle)
            return {'name': name, 'samples': len(df), 'score': score, 'status': 'saved', 'size_str': self._file_size(name)}

        except Exception as e:
            return {'name': name, 'samples': 0, 'score': None, 'status': f'error: {str(e)[:40]}', 'size_str': '—'}

    def _train_mechanic_demand(self, df, trained_at: str) -> dict:
        """Pre-compute mechanic demand ranking."""
        import pandas as pd
        from aiapp.forecasting import save_model

        name = 'mechanic_demand'
        try:
            if df.empty:
                save_model(name, {'results': []})
                return {'name': name, 'samples': 0, 'score': None, 'status': 'saved (no data)', 'size_str': '—'}

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
                predicted = max(1, int(share * 10))
                load = 'high' if predicted >= 4 else ('medium' if predicted >= 2 else 'low')
                results.append({
                    'mechanic': row['mechanic__name'],
                    'predicted_bookings': predicted,
                    'load': load,
                    'recent_bookings': int(row['count']),
                })

            save_model(name, {'results': results[:8]})
            return {'name': name, 'samples': len(df), 'score': None, 'status': 'saved', 'size_str': self._file_size(name)}

        except Exception as e:
            return {'name': name, 'samples': 0, 'score': None, 'status': f'error: {str(e)[:40]}', 'size_str': '—'}

    def _train_service_demand(self, df, trained_at: str) -> dict:
        """Pre-compute service demand ranking."""
        from aiapp.forecasting import save_model

        name = 'service_demand'
        try:
            if df.empty:
                save_model(name, {'results': []})
                return {'name': name, 'samples': 0, 'score': None, 'status': 'saved (no data)', 'size_str': '—'}

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

            save_model(name, {'results': results})
            return {'name': name, 'samples': len(df), 'score': None, 'status': 'saved', 'size_str': self._file_size(name)}

        except Exception as e:
            return {'name': name, 'samples': 0, 'score': None, 'status': f'error: {str(e)[:40]}', 'size_str': '—'}

    def _train_sparepart_demand(self, df, trained_at: str) -> dict:
        """Pre-compute spare part demand ranking."""
        from aiapp.forecasting import save_model

        name = 'sparepart_demand'
        try:
            if df.empty:
                save_model(name, {'results': []})
                return {'name': name, 'samples': 0, 'score': None, 'status': 'saved (no data)', 'size_str': '—'}

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

            save_model(name, {'results': results[:10]})
            return {'name': name, 'samples': len(df), 'score': None, 'status': 'saved', 'size_str': self._file_size(name)}

        except Exception as e:
            return {'name': name, 'samples': 0, 'score': None, 'status': f'error: {str(e)[:40]}', 'size_str': '—'}

    def _file_size(self, name: str) -> str:
        """Return human-readable file size of a saved .pkl file."""
        from aiapp.forecasting import _models_dir
        pkl_path = _models_dir() / f'{name}.pkl'
        if not pkl_path.exists():
            return '—'
        size = pkl_path.stat().st_size
        if size < 1024:
            return f'{size} B'
        elif size < 1024 * 1024:
            return f'{size / 1024:.1f} KB'
        else:
            return f'{size / (1024 * 1024):.1f} MB'
