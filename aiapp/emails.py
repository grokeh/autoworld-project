"""
AutoWorld Automated Email System
Sends HTML emails for all customer touchpoints:
  1. Welcome email on registration
  2. Booking confirmation
  3. Appointment reminder (24h before)
  4. Booking status update (approved/cancelled)
  5. Post-service rating request
"""

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags


def send_autoworld_email(to_email, subject, template_name, context):
    """Base email sender with HTML template support."""
    if not to_email:
        return False
    try:
        context['site_name'] = 'AutoWorld'
        context['site_url']  = 'http://127.0.0.1:8000'
        context['support_email'] = getattr(settings, 'EMAIL_HOST_USER', 'support@autoworld.com')

        html_content  = render_to_string(f'aiapp/emails/{template_name}', context)
        text_content  = strip_tags(html_content)
        from_email    = getattr(settings, 'DEFAULT_FROM_EMAIL', 'AutoWorld <noreply@autoworld.com>')

        msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        msg.attach_alternative(html_content, 'text/html')
        msg.send()
        return True
    except Exception as e:
        print(f'[AutoWorld Email] Failed to send to {to_email}: {e}')
        return False


# ── 1. Welcome Email ──────────────────────────────────────────────────────────

def send_welcome_email(user):
    return send_autoworld_email(
        to_email=user.email,
        subject='Welcome to AutoWorld! 🚗',
        template_name='welcome.html',
        context={'user': user},
    )


# ── 2. Booking Confirmation ───────────────────────────────────────────────────

def send_booking_confirmation_email(booking):
    return send_autoworld_email(
        to_email=booking.user.email,
        subject=f'Booking Confirmed — {booking.mechanic.name} on {booking.booking_date}',
        template_name='booking_confirmation.html',
        context={'booking': booking},
    )


# ── 3. Appointment Reminder ───────────────────────────────────────────────────

def send_appointment_reminder_email(booking):
    return send_autoworld_email(
        to_email=booking.user.email,
        subject=f'Reminder: Your appointment tomorrow with {booking.mechanic.name}',
        template_name='appointment_reminder.html',
        context={'booking': booking},
    )


# ── 4. Booking Status Update ──────────────────────────────────────────────────

def send_booking_status_email(booking):
    status_subjects = {
        'Approved':  f'✅ Booking Approved — {booking.mechanic.name}',
        'Cancelled': f'❌ Booking Cancelled — {booking.booking_date}',
        'Completed': f'✅ Service Complete — How was it?',
    }
    subject = status_subjects.get(booking.status, f'Booking Update — {booking.status}')
    return send_autoworld_email(
        to_email=booking.user.email,
        subject=subject,
        template_name='booking_status.html',
        context={'booking': booking},
    )


# ── 5. Rating Request ─────────────────────────────────────────────────────────

def send_rating_request_email(booking):
    return send_autoworld_email(
        to_email=booking.user.email,
        subject=f'How was your service with {booking.mechanic.name}? ⭐',
        template_name='rating_request.html',
        context={'booking': booking},
    )
