"""
AutoWorld Django Signals
Automatically triggers emails on model events.
"""

from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Booking


@receiver(post_save, sender=User)
def send_welcome_on_register(sender, instance, created, **kwargs):
    """Send welcome email when a new user registers."""
    if created and instance.email:
        try:
            from aiapp.emails import send_welcome_email
            send_welcome_email(instance)
        except Exception as e:
            print(f'[Signal] Welcome email failed: {e}')


@receiver(post_save, sender=Booking)
def send_booking_emails(sender, instance, created, **kwargs):
    """Send emails on booking creation and status changes."""
    if not instance.user.email:
        return

    try:
        from aiapp.emails import (
            send_booking_confirmation_email,
            send_booking_status_email,
            send_rating_request_email,
        )

        if created:
            # New booking — send confirmation
            send_booking_confirmation_email(instance)

        else:
            # Status changed — send update
            status_triggers = ['Approved', 'Cancelled', 'Completed']
            if instance.status in status_triggers:
                send_booking_status_email(instance)

            # Completed — also send rating request
            if instance.status == 'Completed':
                send_rating_request_email(instance)

    except Exception as e:
        print(f'[Signal] Booking email failed: {e}')
