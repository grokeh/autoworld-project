from django.db import models
from django.conf import settings
from django.contrib.auth.models import User


class Vehicle(models.Model):
    brand = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    year = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    image = models.ImageField(upload_to='vehicle_images/', blank=True, null=True)

    def __str__(self):
        return f"{self.brand} {self.model} ({self.year})"


class SparePart(models.Model):
    name = models.CharField(max_length=100)
    compatible_vehicle = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='sparepart_images/', blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    reorder_point = models.PositiveIntegerField(default=5,
        help_text='Alert when stock falls below this level')
    reorder_quantity = models.PositiveIntegerField(default=10,
        help_text='Suggested quantity to reorder')

    def __str__(self):
        return self.name

    @property
    def stock_status(self):
        if self.stock_quantity == 0:
            return 'out_of_stock'
        elif self.stock_quantity <= self.reorder_point:
            return 'low_stock'
        elif self.stock_quantity <= self.reorder_point * 2:
            return 'medium_stock'
        return 'in_stock'

    @property
    def needs_reorder(self):
        return self.stock_quantity <= self.reorder_point

from django.contrib.auth.models import User

class Mechanic(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)  # ✅ now safe
    name = models.CharField(max_length=100)
    specialization = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=200)
    profile_pic = models.ImageField(upload_to='mechanic_profiles/', blank=True)

    def __str__(self):
        return self.name


from django.db import models
from django.contrib.auth.models import User
from .models import Mechanic  

class Booking(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Cancelled', 'Cancelled'),
        ('Rescheduled', 'Rescheduled'),
        ('Completed', 'Completed'),
    ]

    SERVICE_CHOICES = [
        ('Repair', 'Repair'),
        ('Maintenance', 'Maintenance'),
        ('Inspection', 'Inspection'),
        ('Other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    mechanic = models.ForeignKey(Mechanic, on_delete=models.CASCADE)
    booking_date = models.DateField()
    time = models.TimeField()
    service_type = models.CharField(max_length=20, choices=SERVICE_CHOICES, default='Repair')
    details = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    rescheduled_to = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    is_paid = models.BooleanField(default=False)
    payment_confirmed_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='confirmed_bookings'
    )
    payment_confirmed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Booking for {self.mechanic.name} by {self.user.username} on {self.booking_date}"
from django.conf import settings
from django.db import models
from ecommerceapp.models import Vehicle, SparePart

class CartItem(models.Model):
    PRODUCT_TYPES = (
        ('vehicle', 'Vehicle'),
        ('sparepart', 'Spare Part'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)  # 🌟 Supports guests
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES)
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.CASCADE)
    spare_part = models.ForeignKey(SparePart, null=True, blank=True, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        identity = self.user.username if self.user else f"Session {self.session_key}"
        return f"{identity}'s cart item: {self.get_product_name()} (x{self.quantity})"

    def get_product_name(self):
        if self.product_type == 'vehicle' and self.vehicle:
            return f"{self.vehicle.brand} {self.vehicle.model}"
        elif self.product_type == 'sparepart' and self.spare_part:
            return self.spare_part.name
        return "Unknown Product"

    def get_unit_price(self):
        if self.product_type == 'vehicle' and self.vehicle:
            return self.vehicle.price or 0
        elif self.product_type == 'sparepart' and self.spare_part:
            return self.spare_part.price or 0
        return 0

    def subtotal(self):
        return self.quantity * self.get_unit_price()

    @property
    def total(self):
        return self.subtotal()



class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('PENDING_CASH', 'Pending Cash'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('MPESA', 'M-PESA'),
        ('CARD', 'Card'),
        ('PAYPAL', 'PayPal'),
        ('CASH', 'Cash on Delivery'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ecommerce_orders'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_paid = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payment = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)

    def __str__(self):
        return f"Order #{self.id} by {self.user.username}"

    def total_amount(self):
        return sum(item.total_price() for item in self.items.all())


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    cart_item = models.ForeignKey(CartItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.cart_item.get_product_name()} (x{self.cart_item.quantity})"

    def total_price(self):
        return self.cart_item.subtotal()


from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"To {self.user.username} - {self.message[:40]}"

from django.db import models
from django.utils import timezone

class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='services/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Offer(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='offers')
    title = models.CharField(max_length=150)
    description = models.TextField()
    discount_percentage = models.PositiveIntegerField()
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    is_visible = models.BooleanField(default=True)

    def is_expired(self):
        return timezone.now() > self.end_date

    def __str__(self):
        return f"{self.title} - {self.discount_percentage}%"


from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} Profile"

# Automatically create or update UserProfile when a User is saved
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        instance.userprofile.save()
class HomePageContent(models.Model):
    headline = models.CharField(max_length=200)
    subheadline = models.CharField(max_length=300, blank=True)
    banner_image = models.ImageField(upload_to='home_banners/', blank=True, null=True)
    call_to_action = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)  # Allows soft toggling

    def __str__(self):
        return self.headline


# ─── Customer Rating ──────────────────────────────────────────────────────────

class MechanicRating(models.Model):
    booking  = models.OneToOneField('Booking', on_delete=models.CASCADE,
                                    related_name='rating')
    mechanic = models.ForeignKey('Mechanic', on_delete=models.CASCADE,
                                 related_name='ratings')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name='given_ratings')
    stars    = models.PositiveSmallIntegerField(
        choices=[(i, i) for i in range(1, 6)],
        help_text='1–5 stars'
    )
    comment  = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.customer.username} → {self.mechanic.name}: {self.stars}★'


# ─── Job Card ─────────────────────────────────────────────────────────────────

class JobCard(models.Model):
    STATUS_CHOICES = [
        ('Open',        'Open'),
        ('In Progress', 'In Progress'),
        ('Awaiting Parts', 'Awaiting Parts'),
        ('Completed',   'Completed'),
        ('Cancelled',   'Cancelled'),
    ]

    PRIORITY_CHOICES = [
        ('Low',    'Low'),
        ('Medium', 'Medium'),
        ('High',   'High'),
        ('Urgent', 'Urgent'),
    ]

    # Links
    booking  = models.OneToOneField('Booking', on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='job_card')
    mechanic = models.ForeignKey('Mechanic', on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='job_cards')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name='job_cards')

    # Vehicle info (free-text so it works without a linked Vehicle record)
    vehicle_make  = models.CharField(max_length=100)
    vehicle_model = models.CharField(max_length=100)
    vehicle_year  = models.PositiveIntegerField(null=True, blank=True)
    plate_number  = models.CharField(max_length=30, blank=True)
    mileage       = models.PositiveIntegerField(null=True, blank=True,
                                                help_text='Odometer reading (km)')

    # Job details
    title       = models.CharField(max_length=200)
    description = models.TextField(help_text='Describe the problem or service required')
    priority    = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium')
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES,  default='Open')

    # Parts used (free-text notes; can be extended to M2M later)
    parts_used  = models.TextField(blank=True, help_text='List parts used, one per line')

    # Financials
    labour_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    parts_cost  = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Completion notes
    technician_notes = models.TextField(blank=True)

    # Timestamps
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"JC-{self.id:04d} | {self.title} ({self.customer.username})"

    @property
    def total_cost(self):
        return self.labour_cost + self.parts_cost
from django.db import models
from django.contrib.auth.models import User

class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    position = models.CharField(max_length=100)
    hire_date = models.DateField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Attendance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField()
    time_in = models.TimeField()
    time_out = models.TimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.employee.name} - {self.date}"


class Shift(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    shift_name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=20, choices=[
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('completed', 'Completed')
    ], default='active')

    def __str__(self):
        return f"{self.shift_name} ({self.employee.name})"
