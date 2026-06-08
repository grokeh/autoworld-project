"""
AutoWorld Predictive Maintenance Engine
Flags vehicles/customers due for service based on:
  - Days since last booking (time-based)
  - Service type patterns (e.g. oil change every 90 days)
  - Booking frequency patterns
"""

from django.utils import timezone
from datetime import timedelta


SERVICE_INTERVALS = {
    'Maintenance': 90,   # days
    'Inspection':  180,
    'Repair':      None,  # on-demand
    'Other':       120,
}


def get_maintenance_predictions():
    """
    Predict which customers are due for maintenance.
    Returns list of predictions with urgency levels.
    """
    from ecommerceapp.models import Booking
    from django.contrib.auth.models import User

    now = timezone.now().date()
    predictions = []

    customers = User.objects.filter(
        is_staff=False, is_superuser=False,
        booking__isnull=False
    ).distinct()

    for user in customers:
        bookings = user.booking_set.filter(
            status__in=['Completed', 'Approved']
        ).order_by('-booking_date')

        if not bookings.exists():
            continue

        last_booking = bookings.first()
        days_since   = (now - last_booking.booking_date).days
        service_type = last_booking.service_type
        interval     = SERVICE_INTERVALS.get(service_type, 120)

        if interval is None:
            continue

        days_overdue = days_since - interval
        days_until   = interval - days_since

        if days_since >= interval * 0.8:  # within 20% of interval
            if days_overdue > 0:
                urgency = 'overdue'
                message = f"⚠️ {user.username} is {days_overdue} days overdue for {service_type}"
            else:
                urgency = 'due_soon'
                message = f"🔔 {user.username} is due for {service_type} in {abs(days_until)} days"

            # Count total bookings for this customer
            total_bookings = bookings.count()
            avg_interval = days_since / max(total_bookings, 1)

            predictions.append({
                'user_id':       user.id,
                'username':      user.username,
                'email':         user.email,
                'last_service':  str(last_booking.booking_date),
                'service_type':  service_type,
                'mechanic':      last_booking.mechanic.name,
                'days_since':    days_since,
                'interval':      interval,
                'days_overdue':  max(0, days_overdue),
                'days_until':    max(0, days_until),
                'urgency':       urgency,
                'message':       message,
                'total_bookings': total_bookings,
            })

    # Sort: overdue first, then by days_overdue descending
    predictions.sort(key=lambda x: (x['urgency'] != 'overdue', -x['days_overdue']))
    return predictions


def send_maintenance_notifications():
    """Create in-app notifications for overdue customers."""
    from ecommerceapp.models import Notification

    predictions = get_maintenance_predictions()
    count = 0

    for p in predictions:
        from django.contrib.auth.models import User
        try:
            user = User.objects.get(id=p['user_id'])
        except User.DoesNotExist:
            continue

        already = Notification.objects.filter(
            user=user,
            message__contains='maintenance',
            is_read=False,
        ).exists()

        if not already:
            Notification.objects.create(
                user=user,
                message=(
                    f"🔧 Maintenance reminder: Your last {p['service_type']} was "
                    f"{p['days_since']} days ago. "
                    f"{'You are overdue!' if p['urgency'] == 'overdue' else 'Consider booking soon.'} "
                    f"Book at autoworld.com/mechanics/"
                )
            )
            count += 1

    return count
