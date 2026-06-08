# paymentapp/models.py

from django.db import models
from django.conf import settings
from ecommerceapp.models import Order  # ✅ Import the canonical Order model

class Payment(models.Model):
    PAYMENT_METHODS = [
        ('MPESA', 'M-PESA'),
        ('CARD', 'Credit/Debit Card'),
        ('PAYPAL', 'PayPal'),
        ('CASH', 'Cash on Delivery'),
    ]

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Failed', 'Failed'),
        ('Refunded', 'Refunded'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='payments'
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.method} - {self.amount} - {self.status}"
