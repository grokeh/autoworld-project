from django.urls import path
from .views import (
    cart_view, add_to_cart, remove_from_cart,
    checkout, create_payment_intent,
    initiate_payment, payment_success, payment_cancelled,
    create_paypal_order, capture_paypal_order,
    mechanic_payment, process_mechanic_payment,
    stk_push_payment, mpesa_callback,
    confirm_booking_payment, pending_payments,
    booking_payment_status,
)
from paymentapp.views import create_checkout_session
from . import views


urlpatterns = [
    path('cart/', cart_view, name='cart_view'),
    path('add-to-cart/<str:product_type>/<int:product_id>/', add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<int:item_id>/', remove_from_cart, name='remove_from_cart'),

    path('checkout/', checkout, name='checkout'),
    path('create-payment-intent/<int:order_id>/', create_payment_intent, name='create_payment_intent'),

    path('initiate/', initiate_payment, name='initiate_payment'),
    path('payment-success/', payment_success, name='payment_success'),
    path('payment-cancelled/', payment_cancelled, name='payment_cancelled'),
    path("create-paypal-order/", create_paypal_order, name="create_paypal_order"),
    path("capture-paypal-order/<str:order_id>/", capture_paypal_order, name="capture_paypal_order"),

    # Mechanic Payment
    path('mechanic-payment/', mechanic_payment, name='mechanic_payment'),
    path('process-mechanic-payment/', process_mechanic_payment, name='process_mechanic_payment'),

    # M-Pesa Routes
    path("payment/stkpush/", stk_push_payment, name="stk_push_payment"),

    path("payment/callback/", mpesa_callback, name="mpesa_callback"),
    path('create-checkout-session/', create_checkout_session, name='create_checkout_session'),
    path('cash-on-delivery/', views.cash_on_delivery, name='cash_on_delivery'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),

    # Payment confirmation (admin)
    path('control-panel/pending-payments/', pending_payments, name='pending_payments'),
    path('control-panel/confirm-payment/<int:booking_id>/', confirm_booking_payment, name='confirm_booking_payment'),

    # Payment status polling
    path('booking-payment-status/<int:booking_id>/', booking_payment_status, name='booking_payment_status'),
]

