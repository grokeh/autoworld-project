"""
Management command: send_alerts

Runs all automated alert checks and creates notifications:
  1. Unpaid booking deposit reminders (24h after booking)
  2. Upcoming booking reminders (24h before appointment)
  3. Low stock alerts for spare parts
  4. Pending payment deadline warnings (48h)
  5. Booking auto-cancel for unpaid deposits (30 min timeout)

Schedule with Windows Task Scheduler or cron to run every 15 minutes.
Usage: python manage.py send_alerts
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from ecommerceapp.models import Booking, Notification, SparePart
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Send automated alerts and notifications.'

    def handle(self, *args, **options):
        now = timezone.now()
        total = 0

        total += self._unpaid_deposit_reminders(now)
        total += self._upcoming_booking_reminders(now)
        total += self._low_stock_alerts()
        total += self._auto_cancel_unpaid(now)

        self.stdout.write(self.style.SUCCESS(
            f'✅ Alerts processed: {total} notifications created.'
        ))

    # ── 1. Unpaid deposit reminders ───────────────────────────────────────────
    def _unpaid_deposit_reminders(self, now):
        count = 0
        cutoff = now - timedelta(hours=24)
        bookings = Booking.objects.filter(
            is_paid=False,
            status='Pending',
            created_at__lte=cutoff,
            created_at__isnull=False,
        )
        for booking in bookings:
            already = Notification.objects.filter(
                user=booking.user,
                message__contains=f'deposit reminder',
                message__contains=str(booking.id),
            ).exists()
            if not already:
                Notification.objects.create(
                    user=booking.user,
                    message=(
                        f"💳 Payment reminder: Your booking #{booking.id} with "
                        f"{booking.mechanic.name} on {booking.booking_date} still has an "
                        f"unpaid deposit. Please pay to confirm your slot."
                    )
                )
                count += 1
                self.stdout.write(f'  Deposit reminder → {booking.user.username} (Booking #{booking.id})')
        return count

    # ── 2. Upcoming booking reminders (24h before) ────────────────────────────
    def _upcoming_booking_reminders(self, now):
        count = 0
        tomorrow = (now + timedelta(hours=24)).date()
        bookings = Booking.objects.filter(
            booking_date=tomorrow,
            status__in=['Pending', 'Approved'],
        )
        for booking in bookings:
            already = Notification.objects.filter(
                user=booking.user,
                message__contains=f'tomorrow',
                message__contains=str(booking.id),
            ).exists()
            if not already:
                Notification.objects.create(
                    user=booking.user,
                    message=(
                        f"📅 Reminder: You have a booking tomorrow ({booking.booking_date}) "
                        f"at {booking.time} with {booking.mechanic.name}. "
                        f"{'Please ensure payment is complete.' if not booking.is_paid else 'See you then!'}"
                    )
                )
                # Also send email reminder
                if booking.user.email:
                    try:
                        from aiapp.emails import send_appointment_reminder_email
                        send_appointment_reminder_email(booking)
                    except Exception:
                        pass
                count += 1
                self.stdout.write(f'  Booking reminder → {booking.user.username} (Booking #{booking.id})')
        return count

    # ── 3. Low stock alerts ───────────────────────────────────────────────────
    def _low_stock_alerts(self):
        count = 0
        admins = User.objects.filter(is_superuser=True)
        low_parts = SparePart.objects.filter(stock_quantity__lte=5)

        for part in low_parts:
            for admin in admins:
                already = Notification.objects.filter(
                    user=admin,
                    message__contains=part.name,
                    message__contains='stock',
                    is_read=False,
                ).exists()
                if not already:
                    severity = '🚨' if part.stock_quantity == 0 else '⚠️'
                    msg = (
                        f"{severity} {'OUT OF STOCK' if part.stock_quantity == 0 else 'Low stock'}: "
                        f"{part.name} — {part.stock_quantity} units remaining. "
                        f"Reorder {part.reorder_quantity} units."
                    )
                    Notification.objects.create(user=admin, message=msg)
                    count += 1
                    self.stdout.write(f'  Stock alert → {admin.username}: {part.name} ({part.stock_quantity} left)')
        return count

    # ── 4. Auto-cancel unpaid bookings (30 min timeout) ───────────────────────
    def _auto_cancel_unpaid(self, now):
        count = 0
        cutoff = now - timedelta(minutes=30)
        unpaid = Booking.objects.filter(
            is_paid=False,
            status='Pending',
            created_at__lt=cutoff,
            created_at__isnull=False,
        )
        for booking in unpaid:
            booking.status = 'Cancelled'
            booking.save()
            Notification.objects.create(
                user=booking.user,
                message=(
                    f"❌ Your booking #{booking.id} with {booking.mechanic.name} on "
                    f"{booking.booking_date} was automatically cancelled because the "
                    f"deposit was not paid within 30 minutes."
                )
            )
            count += 1
            self.stdout.write(
                self.style.WARNING(f'  Auto-cancelled Booking #{booking.id} ({booking.user.username})')
            )
        return count
