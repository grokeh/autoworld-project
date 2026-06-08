from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from .utils import generate_access_token
from django.utils import timezone

import base64
from ecommerceapp.models import (
    Vehicle, SparePart, CartItem, Order, OrderItem, Booking
)

import paypalrestsdk
import stripe
import requests

# --- Constants ---
CURRENCY = 'usd'

# --- PayPal Configuration ---
paypalrestsdk.configure({
    "mode": "sandbox",
    "client_id": settings.PAYPAL_CLIENT_ID,
    "client_secret": settings.PAYPAL_SECRET
})

# --- Stripe Configuration ---
stripe.api_key = settings.STRIPE_SECRET_KEY

# paymentapp/views.py (or cart views file)
from django.shortcuts import redirect, get_object_or_404
from django.http import JsonResponse
from ecommerceapp.models import Vehicle, SparePart, CartItem
from django.contrib import messages

def add_to_cart(request, product_type, product_id):
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key

    user = request.user if request.user.is_authenticated else None

    # Determine the product
    if product_type == "vehicle":
        product = get_object_or_404(Vehicle, id=product_id)
        lookup = {'vehicle': product}
    elif product_type == "sparepart":
        product = get_object_or_404(SparePart, id=product_id)
        lookup = {'spare_part': product}
    else:
        return JsonResponse({"error": "Invalid product type"}, status=400)

    cart_item, created = CartItem.objects.get_or_create(
        user=user,
        session_key=session_key,
        product_type=product_type,
        **lookup
    )

    if not created:
        cart_item.quantity += 1
        cart_item.save()

    messages.success(request, f"{product} added to cart.")
    return redirect(request.META.get('HTTP_REFERER', '/'))




from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from ecommerceapp.models import CartItem  # adjust if your model lives elsewhere

@login_required
def cart_view(request):
    cart_items = CartItem.objects.filter(user=request.user)

    for item in cart_items:
        vehicle = getattr(item, 'vehicle', None)
        spare_part = getattr(item, 'spare_part', None)
        if vehicle:
            item.subtotal = vehicle.price * item.quantity
        elif spare_part:
            item.subtotal = spare_part.price * item.quantity
        else:
            item.subtotal = 0

    total = sum(item.subtotal for item in cart_items)

    return render(request, 'paymentapp/view_cart.html', {
        'cart_items': cart_items,
        'total': total,
    })


@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, user=request.user)
    item.delete()
    return redirect('cart_view')

from ecommerceapp.models import CartItem, Order, OrderItem
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
@login_required
def checkout(request):
    user = request.user
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key

    # Migrate guest cart to user
    session_cart_items = CartItem.objects.filter(session_key=session_key, user__isnull=True)
    for item in session_cart_items:
        item.user = user
        item.save()

    cart_items = CartItem.objects.filter(user=user)

    if not cart_items.exists():
        return render(request, 'paymentapp/no_order.html')

    # 🔍 Check if an unpaid order already exists (optional)
    order = Order.objects.create(user=user, is_paid=False)

    for cart_item in cart_items:
        OrderItem.objects.create(
            order=order,
            cart_item=cart_item
            # Removed 'quantity=cart_item.quantity' since it's not a valid argument
        )

    # ❌ Do not delete cart yet – wait until payment success

    return render(request, 'paymentapp/checkout.html', {
        'order_id': order.id,
        'cart_items': cart_items,
        'total': sum(item.subtotal() for item in cart_items),
        'STRIPE_PUBLIC_KEY': settings.STRIPE_PUBLIC_KEY
    })



@login_required
def create_payment_intent(request, order_id):
    try:
        order = Order.objects.get(id=order_id, user=request.user)
        total_price = order.total_amount()

        intent = stripe.PaymentIntent.create(
            amount=int(total_price * 100),  # Stripe uses cents
            currency=CURRENCY,
            metadata={'order_id': order.id}
        )

        return JsonResponse({'client_secret': intent.client_secret})

    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ------------------------ PAYPAL VIEWS ------------------------

def get_paypal_access_token():
    url = f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token"
    auth = (settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET)
    headers = {"Accept": "application/json", "Accept-Language": "en_US"}
    data = {"grant_type": "client_credentials"}

    response = requests.post(url, headers=headers, data=data, auth=auth)
    return response.json().get("access_token")


@csrf_exempt
def create_paypal_order(request):
    user = request.user
    order = Order.objects.filter(user=user, is_paid=False).last()

    if not order:
        return JsonResponse({'error': 'No unpaid order found'}, status=404)

    total_amount = f"{order.total_amount():.2f}"
    access_token = get_paypal_access_token()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    body = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {
                "currency_code": "USD",
                "value": total_amount,
            }
        }]
    }

    response = requests.post(f"{settings.PAYPAL_BASE_URL}/v2/checkout/orders", json=body, headers=headers)
    return JsonResponse(response.json())


@csrf_exempt
def capture_paypal_order(request, order_id):
    access_token = get_paypal_access_token()
    url = f"{settings.PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    response = requests.post(url, headers=headers)

    if response.status_code in [200, 201]:
        return JsonResponse({"message": "Payment captured", "details": response.json()})
    else:
        return JsonResponse({"error": "Failed to capture order", "details": response.json()}, status=400)


# ------------------------ OPTIONAL LEGACY PAYPAL ------------------------

@login_required
def initiate_payment(request):
    order = Order.objects.filter(user=request.user, is_paid=False).last()

    if not order:
        return render(request, "paymentapp/no_order.html")

    total = f"{order.total_amount():.2f}"

    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "redirect_urls": {
            "return_url": "http://localhost:8000/paymentapp/payment_success/",
            "cancel_url": "http://localhost:8000/paymentapp/payment_cancelled/"
        },
        "transactions": [{
            "amount": {
                "total": total,
                "currency": "USD"
            },
            "description": f"AutoWorld Order #{order.id}"
        }]
    })

    if payment.create():
        for link in payment.links:
            if link.method == "REDIRECT":
                return redirect(link.href)
    else:
        return render(request, "paymentapp/payment_error.html", {'error': payment.error})


# ------------------------ PAYMENT PAGES ------------------------

@login_required
def payment_success(request):
    return render(request, 'paymentapp/payment_success.html')


@login_required
def payment_cancelled(request):
    return render(request, 'paymentapp/payment_cancelled.html')
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from ecommerceapp.models import Booking

# ------------------------ MECHANIC BOOKING PAYMENT ------------------------

def mechanic_payment(request):
    booking_id = request.session.get('booking_id')
    if not booking_id:
        messages.error(request, "No booking found. Please start over.")
        return redirect('mechanics_list')

    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    deposit_amount = 500  # Static or calculated deposit for booking

    context = {
        'booking': booking,
        'deposit_amount': deposit_amount
    }

    return render(request, 'mechanic_payment.html', context)


    # If you're using paymentapp's template folder:
    return render(request, 'paymentapp/mechanic_payment.html', context)
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from ecommerceapp.models import Order

import requests
import base64
import json

@csrf_exempt
def stk_push_payment(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            phone = data.get("phone", "").strip()
            order_id = data.get("order_id", "").strip()
            booking_id = data.get("booking_id", "").strip()

            if not phone:
                return JsonResponse({"success": False, "error": "Phone number is required."}, status=400)

            # Determine amount and reference
            if booking_id:
                try:
                    from ecommerceapp.models import Booking as BookingModel
                    booking = BookingModel.objects.get(id=booking_id)
                    amount = int(data.get("amount", 500))
                    account_ref = f"AutoWorld-{booking_id}"
                    desc = f"Booking deposit #{booking_id}"
                except BookingModel.DoesNotExist:
                    return JsonResponse({"success": False, "error": "Booking not found."}, status=404)
            elif order_id:
                try:
                    order = Order.objects.get(id=order_id, is_paid=False)
                    amount = int(order.total_amount())
                    account_ref = f"AutoWorld-{order_id}"
                    desc = f"Payment for Order #{order_id}"
                except Order.DoesNotExist:
                    return JsonResponse({"success": False, "error": "Invalid or already paid order."}, status=404)
            else:
                return JsonResponse({"success": False, "error": "Order ID or Booking ID is required."}, status=400)

            # ✅ Normalize phone to 254 format
            if phone.startswith("0"):
                phone = "254" + phone[1:]
            elif phone.startswith("+"):
                phone = phone[1:]
            elif phone.startswith("7") or phone.startswith("1"):
                phone = "254" + phone

            # 🔐 Access Token
            auth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
            r = requests.get(auth_url, auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET))
            access_token = r.json().get("access_token")

            # ⏰ Timestamp & Password
            timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
            password = base64.b64encode(
                (settings.MPESA_SHORTCODE + settings.MPESA_PASSKEY + timestamp).encode()
            ).decode()

            # 📦 STK Push Payload
            payload = {
                "BusinessShortCode": settings.MPESA_SHORTCODE,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": amount,
                "PartyA": phone,
                "PartyB": settings.MPESA_SHORTCODE,
                "PhoneNumber": phone,
                "CallBackURL": settings.MPESA_CALLBACK_URL,
                "AccountReference": account_ref,
                "TransactionDesc": desc,
            }

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            mpesa_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
            response = requests.post(mpesa_url, headers=headers, json=payload)

            mpesa_response = response.json()
            if mpesa_response.get("ResponseCode") == "0":
                return JsonResponse({"success": True, "message": "STK push sent. Check your phone."})
            else:
                return JsonResponse({
                    "success": False,
                    "error": mpesa_response.get("errorMessage", "Failed to initiate payment")
                }, status=500)

        except Exception as e:
            return JsonResponse({"success": False, "error": f"STK push failed: {str(e)}"}, status=500)

    return JsonResponse({"success": False, "error": "Invalid request method."}, status=405)

@csrf_exempt
def mpesa_callback(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        print("Callback data received:", json.dumps(data, indent=2))

        # Extract result from callback
        stk_callback = data.get('Body', {}).get('stkCallback', {})
        result_code = stk_callback.get('ResultCode')
        merchant_request_id = stk_callback.get('MerchantRequestID', '')

        if result_code == 0:
            # Payment successful — extract metadata
            items = stk_callback.get('CallbackMetadata', {}).get('Item', [])
            meta = {item['Name']: item.get('Value') for item in items}

            account_ref = meta.get('AccountReference', '')  # e.g. "AutoWorld-30"
            amount = meta.get('Amount')
            mpesa_receipt = meta.get('MpesaReceiptNumber', '')

            # Extract booking_id from AccountReference
            if account_ref.startswith('AutoWorld-'):
                booking_id = account_ref.split('-')[-1]
                try:
                    booking = Booking.objects.get(id=booking_id)
                    booking.is_paid = True
                    booking.status = 'Approved'
                    booking.save()

                    # Notify user
                    from ecommerceapp.models import Notification
                    Notification.objects.create(
                        user=booking.user,
                        message=f"✅ Payment of KES {amount} confirmed (Ref: {mpesa_receipt}). Your booking with {booking.mechanic.name} is approved."
                    )
                    print(f"Booking {booking_id} marked as paid.")
                except Booking.DoesNotExist:
                    print(f"Booking {booking_id} not found.")
        else:
            print(f"STK push failed with ResultCode: {result_code}")

        return JsonResponse({"ResultCode": 0, "ResultDesc": "Callback received successfully"})
    except Exception as e:
        print("Callback error:", e)
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Failed to process callback"})
from .utils import generate_access_token
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from ecommerceapp.models import Booking
from django.http import HttpResponse

@csrf_exempt
def process_mechanic_payment(request):
    if request.method == 'POST':
        booking_id = request.POST.get('booking_id')
        amount = request.POST.get('amount')

        if not booking_id or not amount:
            messages.error(request, "Missing booking information.")
            return redirect('mechanic_payment')

        booking = get_object_or_404(Booking, id=booking_id)

        # TODO: Add real payment logic here (e.g., Stripe, M-Pesa, etc.)

        # Simulate successful payment
        booking.status = 'Paid'
        booking.save()

        messages.success(request, f"Payment of ${amount} for {booking.mechanic.name} processed successfully.")

        #  Redirect to the e-commerce checkout
        return redirect('checkout')

    messages.error(request, "Invalid payment request.")
    return redirect('mechanic_payment')
import json
import stripe
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from ecommerceapp.models import Order

stripe.api_key = settings.STRIPE_SECRET_KEY

@csrf_exempt
def create_checkout_session(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        order_id = data.get('order_id')

        try:
            order = Order.objects.get(id=order_id)

            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'kes',
                        'product_data': {
                            'name': f"AutoWorld Order #{order.id}",
                        },
                        'unit_amount': int(order.total_amount() * 100),  # Stripe wants amount in cents
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=request.build_absolute_uri(f"/payment/success/{order.id}/"),
                cancel_url=request.build_absolute_uri("/paymentapp/checkout/"),
            )
            return JsonResponse({'id': session.id})
        except Order.DoesNotExist:
            return JsonResponse({'error': 'Order not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from ecommerceapp.models import Order
from django.contrib import messages

@login_required
def cash_on_delivery(request):
    try:
        order = Order.objects.filter(user=request.user, is_paid=False).latest('created_at')
        order.payment_method = 'Cash on Delivery'
        order.is_paid = False
        order.save()
        messages.success(request, "Order placed with Cash on Delivery.")
        return redirect('payment_success')
    except Order.DoesNotExist:
        messages.error(request, "No unpaid order found.")
        return redirect('checkout')
@csrf_exempt
def stk_callback(request):
    data = json.loads(request.body)
    print("STK Callback received:", data)
    # Optionally update booking status here
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Received"})
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
from ecommerceapp.models import CartItem

@login_required
def clear_cart(request):
    CartItem.objects.filter(user=request.user).delete()
    messages.success(request, "🛒 Your cart has been cleared successfully.")
    return redirect('cart_view')  # or wherever you want to redirect

# ------------------------ ADMIN: MANUAL PAYMENT CONFIRMATION ------------------------

from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone as tz

@staff_member_required
def confirm_booking_payment(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    if request.method == 'POST':
        booking.is_paid = True
        booking.status = 'Approved'
        booking.payment_confirmed_by = request.user
        booking.payment_confirmed_at = tz.now()
        booking.save()

        from ecommerceapp.models import Notification
        Notification.objects.create(
            user=booking.user,
            message=f"✅ Your payment for the booking with {booking.mechanic.name} on {booking.booking_date} has been manually confirmed."
        )
        messages.success(request, f"Payment confirmed for booking #{booking.id}.")
        return redirect('pending_payments')

    return render(request, 'paymentapp/confirm_payment.html', {'booking': booking})


@staff_member_required
def pending_payments(request):
    """Lists all bookings awaiting payment confirmation."""
    bookings = Booking.objects.filter(is_paid=False, status='Pending').order_by('created_at')
    return render(request, 'paymentapp/pending_payments.html', {'bookings': bookings})

# ------------------------ PAYMENT STATUS POLLING ------------------------

@login_required
def booking_payment_status(request, booking_id):
    """Called by the frontend to check if payment has been confirmed."""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    return JsonResponse({'is_paid': booking.is_paid, 'status': booking.status})
