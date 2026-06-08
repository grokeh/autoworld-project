import africastalking
from django.conf import settings
from django.core.mail import send_mail

# Initialize Africastalking
africastalking.initialize(
    username=settings.AFRICASTALKING_USERNAME,
    api_key=settings.AFRICASTALKING_API_KEY
)
sms = africastalking.SMS

def send_booking_notification(user_email, user_phone, subject, message):
    if user_email:
        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user_email])
        except Exception:
            pass

    if user_phone:
        try:
            sms.send(message, [user_phone])
        except Exception:
            pass

def send_payment_confirmation(user_email, user_phone, amount):
    message = f"Your AutoWorld payment of KES {amount} was received. Thank you!"
    send_booking_notification(user_email, user_phone, "Payment Confirmation", message)

def send_booking_confirmation(user_email, user_phone, mechanic_name, booking_date):
    message = f"Your booking with mechanic {mechanic_name} is confirmed for {booking_date}."
    send_booking_notification(user_email, user_phone, "Booking Confirmed", message)

def send_raincheck_notification(user_email, user_phone, new_date):
    message = f"Your booking has been rescheduled to {new_date}."
    send_booking_notification(user_email, user_phone, "Booking Rescheduled", message)

def send_cancellation_notice(user_email, user_phone):
    message = "Your booking has been cancelled. Reach out if you’d like to rebook."
    send_booking_notification(user_email, user_phone, "Booking Cancelled", message)
