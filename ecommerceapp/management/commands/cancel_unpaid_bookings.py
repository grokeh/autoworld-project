"""
Management command: cancel_unpaid_bookings

Cancels bookings that have not been paid within the timeout window.
Run manually:  python manage.py cancel_unpaid_bookings
Schedule with cron or Windows Task Scheduler for automation.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from ecommerceapp.models import Booking, Notification


# How long to wait before cancelling an unpaid booking (default: 30 minutes)
PAYMENT_TIMEOUT_MINUTES = 30


class Command(BaseCommand):
    help = 'Cancel bookings that have not been paid within the timeout window.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=PAYMENT_TIMEOUT_MINUTES,
            help='Minutes to wait before cancelling unpaid bookings (default: 30)',
        )

    def handle(self, *args, **options):
        timeout = options['timeout']
        cutoff = timezone.now() - timedelta(minutes=timeout)

        unpaid = Booking.objects.filter(
            is_paid=False,
            status='Pending',
            created_at__lt=cutoff,
            created_at__isnull=False,
        )

        count = unpaid.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No unpaid bookings to cancel.'))
            return

        for booking in unpaid:
            booking.status = 'Cancelled'
            booking.save()

            Notification.objects.create(
                user=booking.user,
                message=(
                    f"❌ Your booking with {booking.mechanic.name} on {booking.booking_date} "
                    f"was automatically cancelled because payment was not received within "
                    f"{timeout} minutes."
                )
            )
            self.stdout.write(
                self.style.WARNING(f'Cancelled booking #{booking.id} for {booking.user.username}')
            )

        self.stdout.write(self.style.SUCCESS(f'Done. {count} booking(s) cancelled.'))
