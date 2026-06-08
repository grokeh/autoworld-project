"""
AutoWorld RFM Customer Segmentation
Classifies customers into segments based on:
  - Recency:   Days since last booking
  - Frequency: Total number of bookings
  - Monetary:  Total amount spent (orders + booking deposits)

Segments:
  Champions       — Recent, frequent, high spend
  Loyal           — Frequent, decent spend
  At Risk         — Used to be good, haven't returned
  New Customers   — Recent first-timers
  Lost            — Haven't booked in a long time
  Potential       — Some activity, room to grow
"""

import pandas as pd
import numpy as np
from django.utils import timezone
from datetime import timedelta


def get_rfm_data():
    """Build RFM scores for all customers."""
    from ecommerceapp.models import Booking, Order
    from django.contrib.auth.models import User

    now = timezone.now()
    customers = User.objects.filter(
        is_staff=False, is_superuser=False
    ).prefetch_related('booking_set', 'ecommerce_orders')

    if not customers.exists():
        return []

    records = []
    for user in customers:
        bookings = user.booking_set.filter(created_at__isnull=False)
        orders   = user.ecommerce_orders.filter(is_paid=True)

        if not bookings.exists() and not orders.exists():
            continue

        # Recency — days since last activity
        last_booking = bookings.order_by('-created_at').first()
        last_order   = orders.order_by('-created_at').first()

        last_dates = []
        if last_booking and last_booking.created_at:
            last_dates.append(last_booking.created_at)
        if last_order and last_order.created_at:
            last_dates.append(last_order.created_at)

        if not last_dates:
            continue

        last_activity = max(last_dates)
        recency_days  = (now - last_activity).days

        # Frequency — total bookings + orders
        frequency = bookings.count() + orders.count()

        # Monetary — total spend
        booking_spend = bookings.filter(is_paid=True).count() * 500  # deposit per booking
        order_spend   = sum(o.total_amount() for o in orders)
        monetary      = float(booking_spend) + float(order_spend)

        records.append({
            'user_id':      user.id,
            'username':     user.username,
            'email':        user.email,
            'first_name':   user.first_name or user.username,
            'recency':      recency_days,
            'frequency':    frequency,
            'monetary':     monetary,
            'last_activity': last_activity.strftime('%Y-%m-%d'),
        })

    if not records:
        return []

    df = pd.DataFrame(records)

    # Score each dimension 1-5 (5 = best)
    # Recency: lower days = better score
    df['r_score'] = pd.qcut(df['recency'].rank(method='first'),
                             q=5, labels=[5, 4, 3, 2, 1]).astype(int)
    # Frequency: higher = better
    df['f_score'] = pd.qcut(df['frequency'].rank(method='first'),
                             q=5, labels=[1, 2, 3, 4, 5],
                             duplicates='drop').astype(int) if df['frequency'].nunique() > 1 else 3
    # Monetary: higher = better
    df['m_score'] = pd.qcut(df['monetary'].rank(method='first'),
                             q=5, labels=[1, 2, 3, 4, 5],
                             duplicates='drop').astype(int) if df['monetary'].nunique() > 1 else 3

    df['rfm_score'] = df['r_score'] + df['f_score'] + df['m_score']

    # Segment assignment
    def assign_segment(row):
        r, f, m = row['r_score'], row['f_score'], row['m_score']
        score = row['rfm_score']
        if r >= 4 and f >= 4 and m >= 4:
            return 'Champions'
        elif f >= 4 and m >= 3:
            return 'Loyal'
        elif r >= 4 and f <= 2:
            return 'New Customer'
        elif r <= 2 and f >= 3:
            return 'At Risk'
        elif r <= 2 and f <= 2:
            return 'Lost'
        else:
            return 'Potential'

    df['segment'] = df.apply(assign_segment, axis=1)

    # Segment colours for UI
    segment_meta = {
        'Champions':    {'color': '#11ba1f', 'icon': '🏆', 'bg': '#e8f5e9'},
        'Loyal':        {'color': '#1e1153', 'icon': '⭐', 'bg': '#f4f3ff'},
        'New Customer': {'color': '#0d6efd', 'icon': '🆕', 'bg': '#e3f2fd'},
        'At Risk':      {'color': '#fd7e14', 'icon': '⚠️', 'bg': '#fff3e0'},
        'Lost':         {'color': '#dc3545', 'icon': '💔', 'bg': '#fce4ec'},
        'Potential':    {'color': '#6c757d', 'icon': '🌱', 'bg': '#f5f5f5'},
    }

    result = []
    for _, row in df.iterrows():
        seg = row['segment']
        meta = segment_meta.get(seg, {'color': '#333', 'icon': '👤', 'bg': '#f5f5f5'})
        result.append({
            'user_id':      int(row['user_id']),
            'username':     row['username'],
            'email':        row['email'],
            'first_name':   row['first_name'],
            'recency':      int(row['recency']),
            'frequency':    int(row['frequency']),
            'monetary':     round(float(row['monetary']), 0),
            'r_score':      int(row['r_score']),
            'f_score':      int(row['f_score']),
            'm_score':      int(row['m_score']),
            'rfm_score':    int(row['rfm_score']),
            'segment':      seg,
            'last_activity': row['last_activity'],
            **meta,
        })

    result.sort(key=lambda x: x['rfm_score'], reverse=True)
    return result


def get_rfm_summary(rfm_data):
    """Summarise RFM segments for dashboard cards."""
    if not rfm_data:
        return {}

    segments = {}
    for r in rfm_data:
        seg = r['segment']
        if seg not in segments:
            segments[seg] = {'count': 0, 'total_monetary': 0,
                             'icon': r['icon'], 'color': r['color'], 'bg': r['bg']}
        segments[seg]['count'] += 1
        segments[seg]['total_monetary'] += r['monetary']

    for seg in segments:
        segments[seg]['avg_monetary'] = round(
            segments[seg]['total_monetary'] / segments[seg]['count'], 0
        )

    return segments
