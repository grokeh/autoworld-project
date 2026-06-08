# Design Document — Garage Compliance Modules

## Overview

This design closes three compliance gaps and applies two minor model enhancements to the
AutoWorld AutoShop & Garage Management System (`autoworld_project / ecommerceapp`).

**Modules delivered:**

| Module | Gap closed |
|---|---|
| Supplier Management | Procurement workflow: Supplier → PurchaseOrder → StockReceipt |
| Customer Vehicle Registry | Per-customer vehicle records, separate from the sales catalogue |
| Stock Movement Log | Full immutable audit trail for every `SparePart.stock_quantity` change |
| Mechanic `status` field | Minor model enhancement |
| `Vehicle` `engine_number` / `chassis_number` fields | Minor model enhancement |

All code targets the existing `ecommerceapp` Django application.  
Framework: Django 4.x · Database: PostgreSQL · Frontend: Bootstrap 5.

---

## Architecture

The feature follows the existing monolithic Django MVC pattern:

```
ecommerceapp/
├── models.py          ← all new models appended here
├── views.py           ← all new view functions appended here
├── urls.py            ← new URL patterns appended here
├── admin.py           ← new admin registrations appended here
├── forms.py           ← new ModelForms / formsets appended here
├── signals.py         ← NEW file: post_save signal for Order → sale StockMovement
├── apps.py            ← import signals.py in AppConfig.ready()
└── templates/
    └── ecommerceapp/  ← all new templates here
```

### Key architectural decisions

1. **Append-only `models.py`** — new models follow existing ones; no restructuring.
2. **`django.db.transaction.atomic`** — wraps every stock-mutating operation (receipt
   confirmation, sale decrement, manual adjustment) so partial failures roll back cleanly.
3. **`post_save` signal on `Order`** — triggers the sale `StockMovement` and stock
   decrement when `Order.status` transitions to `PAID`, keeping views free of stock logic.
4. **`StockMovement.save()` override** — raises `ValidationError` on any update attempt,
   making the log append-only at the ORM level.
5. **`@staff_member_required`** — protects all procurement / stock-movement views.
6. **`owner_or_staff_required`** — custom decorator protects `CustomerVehicle` edit/delete.
7. **Single migration file** — one `0002_garage_compliance_modules.py` covers all additions.

---

## Data Model Diagram

```
┌─────────────────────────┐        ┌───────────────────────────────┐
│        Supplier         │        │         PurchaseOrder          │
│─────────────────────────│        │───────────────────────────────│
│ id (PK)                 │◄───────│ id (PK)                       │
│ name                    │ 1   N  │ supplier (FK → Supplier)      │
│ contact_person          │        │ order_date                    │
│ phone                   │        │ expected_delivery             │
│ email                   │        │ status [Draft|Sent|Received|  │
│ address                 │        │         Cancelled]            │
│ is_active               │        │ notes                         │
└─────────────────────────┘        └───────────────┬───────────────┘
                                                   │ 1
                                                   │ N
                                      ┌────────────▼────────────────┐
                                      │        POLineItem            │
                                      │────────────────────────────  │
                                      │ id (PK)                      │
                                      │ purchase_order (FK → PO)     │
                                      │ spare_part (FK → SparePart)  │
                                      │ quantity_ordered             │
                                      │ unit_cost                    │
                                      └──────────────────────────────┘

┌─────────────────────────┐        ┌───────────────────────────────┐
│     PurchaseOrder       │        │         StockReceipt          │
│  (shown above)          │◄───────│───────────────────────────────│
│                         │ 1   N  │ id (PK)                       │
│                         │        │ purchase_order (FK → PO)      │
│                         │        │ received_date                 │
│                         │        │ received_by (FK → User)       │
│                         │        │ notes                         │
└─────────────────────────┘        └───────────────┬───────────────┘
                                                   │ 1
                                                   │ N
                                      ┌────────────▼────────────────┐
                                      │      ReceiptLineItem         │
                                      │─────────────────────────────│
                                      │ id (PK)                      │
                                      │ stock_receipt (FK → SR)      │
                                      │ spare_part (FK → SparePart)  │
                                      │ quantity_received            │
                                      └──────────────────────────────┘

┌─────────────────────────┐
│      SparePart          │  (existing)
│─────────────────────────│
│ id (PK)                 │◄──── POLineItem.spare_part
│ name                    │◄──── ReceiptLineItem.spare_part
│ stock_quantity          │◄──── StockMovement.spare_part
│ ...                     │
└─────────────────────────┘

┌─────────────────────────┐
│    CustomerVehicle      │
│─────────────────────────│
│ id (PK)                 │
│ owner (FK → User)       │◄──── request.user on creation
│ registration_number     │
│ make                    │
│ model                   │
│ year                    │
│ engine_number           │
│ chassis_number          │
│ color                   │
│ mileage                 │
│ notes                   │
└────────────┬────────────┘
             │ 1
             │ N
  ┌──────────▼──────────────────┐
  │         JobCard             │  (existing — new FK added)
  │─────────────────────────────│
  │ ...existing fields...       │
  │ customer_vehicle (FK, null) │
  └─────────────────────────────┘

┌──────────────────────────────────┐
│         StockMovement            │
│──────────────────────────────────│
│ id (PK)                          │
│ spare_part (FK → SparePart)      │
│ movement_type [stock_in |        │
│   stock_out | adjustment |       │
│   sale | purchase_receipt]       │
│ quantity (positive)              │
│ reference (char, blank)          │
│ notes (text, blank)              │
│ performed_by (FK → User, null)   │
│ created_at (auto_now_add)        │
└──────────────────────────────────┘

Existing model amendments
  Mechanic   +status [Available|Busy|Off-Duty] default=Available
  Vehicle    +engine_number (char, blank)
             +chassis_number (char, blank)
```

---

## Components and Interfaces

### Custom Decorator

```python
# ecommerceapp/decorators.py  (new file)

def owner_or_staff_required(view_func):
    """
    Allows access when:
      - user.is_staff is True, OR
      - the CustomerVehicle's owner == request.user
    Otherwise returns HttpResponseForbidden.
    The decorated view must receive a kwarg `pk` identifying the CustomerVehicle.
    """
```

### View Function Signatures

#### Supplier Management (`@staff_member_required` on all)

```python
def supplier_list(request)
    # GET  → QuerySet(Supplier).order_by('name'), paginated 25/page
    # renders: ecommerceapp/suppliers/supplier_list.html

def supplier_create(request)
    # GET  → blank SupplierForm
    # POST → validate, save, redirect('supplier_list') | re-render with errors
    # renders: ecommerceapp/suppliers/supplier_form.html

def supplier_edit(request, pk)
    # GET  → SupplierForm(instance=supplier)
    # POST → validate, save, redirect('supplier_list') | re-render with errors
    # renders: ecommerceapp/suppliers/supplier_form.html

def supplier_delete(request, pk)
    # POST → supplier.delete(), redirect('supplier_list')
    # GET  → renders confirmation page
    # renders: ecommerceapp/suppliers/supplier_confirm_delete.html
```

#### Purchase Order Management (`@staff_member_required` on all)

```python
def po_list(request)
    # GET  → all POs ordered by -order_date, paginated 25/page
    # renders: ecommerceapp/suppliers/po_list.html

def po_create(request)
    # GET  → PurchaseOrderForm + POLineItemFormSet (extra=1)
    # POST → validate both, save in transaction.atomic(), redirect('po_detail', pk)
    # renders: ecommerceapp/suppliers/po_form.html

def po_detail(request, pk)
    # GET  → PO + line_items.all()
    # renders: ecommerceapp/suppliers/po_detail.html

def po_edit(request, pk)
    # GET  → PurchaseOrderForm(instance=po) + inline formset
    # POST → validate, save, redirect('po_detail', pk)
    # Raises 403 if po.status in ['Received', 'Cancelled']
    # renders: ecommerceapp/suppliers/po_form.html
```

#### Stock Receipt (`@staff_member_required` on all)

```python
def receive_stock(request, po_pk)
    # GET  → StockReceiptForm pre-populated with POLineItems
    # POST → in transaction.atomic():
    #          1. create StockReceipt
    #          2. for each ReceiptLineItem: spare_part.stock_quantity += qty_received
    #          3. PO.status = 'Received'
    #          4. create StockMovement(type='purchase_receipt') per line item
    #        On failure → rollback, show error
    # renders: ecommerceapp/suppliers/receive_stock.html

def receipt_detail(request, pk)
    # GET  → StockReceipt + line_items
    # renders: ecommerceapp/suppliers/receipt_detail.html
```

#### Supplier Performance Report (`@staff_member_required`)

```python
def supplier_performance(request)
    # GET  → annotate Supplier queryset with:
    #          - total_pos     = Count('purchaseorder')
    #          - total_items   = Sum('purchaseorder__stockreceipt__line_items__quantity_received')
    #          - avg_delivery  = Avg(ExpressionWrapper(
    #                               F('purchaseorder__stockreceipt__received_date')
    #                               - F('purchaseorder__expected_delivery'),
    #                               output_field=DurationField()))
    #        Python post-process: replace avg_delivery==None with 'N/A'
    # renders: ecommerceapp/suppliers/supplier_performance.html
```

#### Customer Vehicle Registry

```python
@login_required
def my_vehicle_list(request)
    # GET  → CustomerVehicle.objects.filter(owner=request.user)
    # renders: ecommerceapp/vehicles/my_vehicle_list.html

@staff_member_required
def all_vehicle_list(request)
    # GET  → CustomerVehicle.objects.all().select_related('owner')
    # renders: ecommerceapp/vehicles/all_vehicle_list.html

@login_required
def vehicle_create(request)
    # GET  → blank CustomerVehicleForm
    # POST → form.instance.owner = request.user, validate, save
    #        redirect('my_vehicle_list')
    # renders: ecommerceapp/vehicles/vehicle_form.html

@owner_or_staff_required
def vehicle_edit(request, pk)
    # GET  → CustomerVehicleForm(instance=vehicle)
    # POST → validate, save, redirect('my_vehicle_list')
    # renders: ecommerceapp/vehicles/vehicle_form.html

@owner_or_staff_required
def vehicle_delete(request, pk)
    # POST → vehicle.delete(), redirect('my_vehicle_list')
    # GET  → confirmation page
    # renders: ecommerceapp/vehicles/vehicle_confirm_delete.html

@login_required
def vehicle_service_history(request, pk)
    # GET  → get CustomerVehicle (403 if not owner or staff)
    #        JobCard.objects.filter(customer_vehicle=vehicle).order_by('-created_at')
    # renders: ecommerceapp/vehicles/vehicle_service_history.html
```

#### Stock Movement Log (`@staff_member_required` on all)

```python
def stock_movement_log(request)
    # GET  → filter by GET params: spare_part (name icontains),
    #          movement_type, date_start, date_end
    #        paginate 50/page, order by -created_at
    # renders: ecommerceapp/stock/movement_log.html

def stock_movement_summary(request)
    # GET  → SparePart queryset annotated with:
    #          net_movement = Sum of quantity (stock_out/sale as negative)
    #          breakdown by movement_type counts
    # renders: ecommerceapp/stock/movement_summary.html

def stock_adjustment(request)
    # GET  → StockAdjustmentForm
    # POST → in transaction.atomic():
    #          1. SparePart.stock_quantity += signed_quantity
    #          2. StockMovement(type='adjustment', performed_by=request.user)
    #        On failure → rollback, show error
    # renders: ecommerceapp/stock/stock_adjustment.html
```

---

## Data Models

All new models are appended to `ecommerceapp/models.py`.

### Supplier

```python
class Supplier(models.Model):
    name           = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True)
    phone          = models.CharField(max_length=30,  blank=True)
    email          = models.EmailField(blank=True)
    address        = models.TextField(blank=True)
    is_active      = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def clean(self):
        if not self.name or not self.name.strip():
            raise ValidationError({'name': 'Supplier name cannot be empty.'})
```

### PurchaseOrder

```python
class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('Draft',      'Draft'),
        ('Sent',       'Sent'),
        ('Received',   'Received'),
        ('Cancelled',  'Cancelled'),
    ]
    # Transitions that are forbidden after reaching a terminal state
    TERMINAL_TRANSITIONS = {
        'Received':  {'Draft', 'Sent'},
        'Cancelled': {'Draft', 'Sent', 'Received'},
    }

    supplier          = models.ForeignKey(Supplier, on_delete=models.CASCADE,
                                          related_name='purchase_orders')
    order_date        = models.DateField(auto_now_add=True)
    expected_delivery = models.DateField(null=True, blank=True)
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                         default='Draft')
    notes             = models.TextField(blank=True)

    class Meta:
        ordering = ['-order_date']

    def __str__(self):
        return f"PO-{self.id:05d} ({self.supplier.name}) [{self.status}]"

    def clean(self):
        if self.pk:
            original = PurchaseOrder.objects.get(pk=self.pk)
            forbidden = self.TERMINAL_TRANSITIONS.get(original.status, set())
            if self.status in forbidden:
                raise ValidationError(
                    f"Cannot change status from '{original.status}' to '{self.status}'."
                )
```

### POLineItem

```python
class POLineItem(models.Model):
    purchase_order   = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE,
                                         related_name='line_items')
    spare_part       = models.ForeignKey('SparePart', on_delete=models.PROTECT,
                                         related_name='po_line_items')
    quantity_ordered = models.PositiveIntegerField()
    unit_cost        = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.spare_part.name} x{self.quantity_ordered} @ {self.unit_cost}"

    def clean(self):
        errors = {}
        if self.quantity_ordered is not None and self.quantity_ordered <= 0:
            errors['quantity_ordered'] = 'Quantity ordered must be greater than zero.'
        if self.unit_cost is not None and self.unit_cost < 0:
            errors['unit_cost'] = 'Unit cost cannot be negative.'
        if errors:
            raise ValidationError(errors)

    @property
    def line_total(self):
        return self.quantity_ordered * self.unit_cost
```

### StockReceipt

```python
class StockReceipt(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE,
                                       related_name='stock_receipts')
    received_date  = models.DateField(auto_now_add=True)
    received_by    = models.ForeignKey(User, on_delete=models.SET_NULL,
                                       null=True, blank=True,
                                       related_name='stock_receipts_received')
    notes          = models.TextField(blank=True)

    class Meta:
        ordering = ['-received_date']

    def __str__(self):
        return f"Receipt-{self.id:05d} for {self.purchase_order}"

    def confirm(self):
        """
        Atomically:
          1. Increment SparePart.stock_quantity for each ReceiptLineItem.
          2. Set PurchaseOrder.status = 'Received'.
          3. Create StockMovement(type='purchase_receipt') per line item.
        Raises ValidationError and rolls back on any failure.
        """
        from django.db import transaction
        with transaction.atomic():
            for item in self.line_items.select_related('spare_part').all():
                item.spare_part.stock_quantity += item.quantity_received
                item.spare_part.save(update_fields=['stock_quantity'])
                StockMovement.objects.create(
                    spare_part=item.spare_part,
                    movement_type='purchase_receipt',
                    quantity=item.quantity_received,
                    reference=str(self.purchase_order),
                    performed_by=self.received_by,
                )
            self.purchase_order.status = 'Received'
            self.purchase_order.save(update_fields=['status'])
```

### ReceiptLineItem

```python
class ReceiptLineItem(models.Model):
    stock_receipt     = models.ForeignKey(StockReceipt, on_delete=models.CASCADE,
                                          related_name='line_items')
    spare_part        = models.ForeignKey('SparePart', on_delete=models.PROTECT,
                                          related_name='receipt_line_items')
    quantity_received = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.spare_part.name} x{self.quantity_received}"

    def clean(self):
        if self.quantity_received is not None and self.quantity_received <= 0:
            raise ValidationError(
                {'quantity_received': 'Quantity received must be greater than zero.'}
            )
```

### CustomerVehicle

```python
class CustomerVehicle(models.Model):
    owner               = models.ForeignKey(User, on_delete=models.CASCADE,
                                             related_name='customer_vehicles')
    registration_number = models.CharField(max_length=30, unique=True)
    make                = models.CharField(max_length=100)
    model               = models.CharField(max_length=100)
    year                = models.PositiveIntegerField()
    engine_number       = models.CharField(max_length=100, blank=True)
    chassis_number      = models.CharField(max_length=100, blank=True)
    color               = models.CharField(max_length=50, blank=True)
    mileage             = models.PositiveIntegerField(null=True, blank=True)
    notes               = models.TextField(blank=True)

    class Meta:
        ordering = ['registration_number']

    def __str__(self):
        return f"{self.registration_number} — {self.make} {self.model} ({self.year})"
```

### StockMovement

```python
class StockMovement(models.Model):
    MOVEMENT_TYPE_CHOICES = [
        ('stock_in',         'Stock In'),
        ('stock_out',        'Stock Out'),
        ('adjustment',       'Adjustment'),
        ('sale',             'Sale'),
        ('purchase_receipt', 'Purchase Receipt'),
    ]

    spare_part    = models.ForeignKey('SparePart', on_delete=models.PROTECT,
                                      related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE_CHOICES)
    quantity      = models.PositiveIntegerField()
    reference     = models.CharField(max_length=200, blank=True)
    notes         = models.TextField(blank=True)
    performed_by  = models.ForeignKey(User, on_delete=models.SET_NULL,
                                      null=True, blank=True,
                                      related_name='stock_movements')
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (f"{self.movement_type} | {self.spare_part.name} "
                f"x{self.quantity} @ {self.created_at:%Y-%m-%d %H:%M}")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(
                "StockMovement records are immutable and cannot be updated."
            )
        super().save(*args, **kwargs)
```

### Model Amendments

```python
# Appended to Mechanic:
STATUS_CHOICES = [
    ('Available', 'Available'),
    ('Busy',      'Busy'),
    ('Off-Duty',  'Off-Duty'),
]
status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Available')

# Appended to Vehicle:
engine_number  = models.CharField(max_length=100, blank=True)
chassis_number = models.CharField(max_length=100, blank=True)

# Appended to JobCard:
customer_vehicle = models.ForeignKey(
    'CustomerVehicle',
    on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name='job_cards',
)
```

---

## URL Patterns

Appended to `ecommerceapp/urls.py`:

```python
# ─── Supplier Management ──────────────────────────────────────────────────────
path('suppliers/',                          views.supplier_list,         name='supplier_list'),
path('suppliers/create/',                   views.supplier_create,       name='supplier_create'),
path('suppliers/<int:pk>/edit/',            views.supplier_edit,         name='supplier_edit'),
path('suppliers/<int:pk>/delete/',          views.supplier_delete,       name='supplier_delete'),

# ─── Purchase Orders ──────────────────────────────────────────────────────────
path('suppliers/po/',                       views.po_list,               name='po_list'),
path('suppliers/po/create/',                views.po_create,             name='po_create'),
path('suppliers/po/<int:pk>/',              views.po_detail,             name='po_detail'),
path('suppliers/po/<int:pk>/edit/',         views.po_edit,               name='po_edit'),

# ─── Stock Receipt ────────────────────────────────────────────────────────────
path('suppliers/po/<int:po_pk>/receive/',   views.receive_stock,         name='receive_stock'),
path('suppliers/receipts/<int:pk>/',        views.receipt_detail,        name='receipt_detail'),

# ─── Supplier Performance ─────────────────────────────────────────────────────
path('suppliers/performance/',              views.supplier_performance,  name='supplier_performance'),

# ─── Customer Vehicles ────────────────────────────────────────────────────────
path('vehicles/my/',                        views.my_vehicle_list,       name='my_vehicle_list'),
path('vehicles/my/create/',                 views.vehicle_create,        name='vehicle_create'),
path('vehicles/my/<int:pk>/edit/',          views.vehicle_edit,          name='vehicle_edit'),
path('vehicles/my/<int:pk>/delete/',        views.vehicle_delete,        name='vehicle_delete'),
path('vehicles/my/<int:pk>/history/',       views.vehicle_service_history, name='vehicle_service_history'),
path('vehicles/all/',                       views.all_vehicle_list,      name='all_vehicle_list'),

# ─── Stock Movements ──────────────────────────────────────────────────────────
path('stock/movements/',                    views.stock_movement_log,    name='stock_movement_log'),
path('stock/movements/summary/',            views.stock_movement_summary, name='stock_movement_summary'),
path('stock/movements/adjust/',             views.stock_adjustment,      name='stock_adjustment'),
```

---

## Template List

All templates extend `base.html` and use Bootstrap 5 components.

```
ecommerceapp/templates/ecommerceapp/
│
├── suppliers/
│   ├── supplier_list.html            # table of all suppliers + create btn
│   ├── supplier_form.html            # create / edit form (shared)
│   ├── supplier_confirm_delete.html  # delete confirmation
│   ├── po_list.html                  # table of purchase orders + status badges
│   ├── po_form.html                  # PO header form + POLineItem formset rows
│   ├── po_detail.html                # PO header + line items table
│   ├── receive_stock.html            # receipt form + ReceiptLineItem formset
│   ├── receipt_detail.html           # receipt header + received quantities
│   └── supplier_performance.html    # performance table per supplier
│
├── vehicles/
│   ├── my_vehicle_list.html          # customer: own vehicles list
│   ├── all_vehicle_list.html         # staff: all vehicles with owner column
│   ├── vehicle_form.html             # create / edit form (shared)
│   ├── vehicle_confirm_delete.html   # delete confirmation
│   └── vehicle_service_history.html # job cards linked to a vehicle
│
└── stock/
    ├── movement_log.html             # filterable + paginated movement log
    ├── movement_summary.html         # per-part net movement summary table
    └── stock_adjustment.html         # manual adjustment form
```

Each template structure:

```html
{% extends "base.html" %}
{% block content %}
  <div class="container mt-4">
    <h2>...</h2>
    <!-- Bootstrap 5 table / form / badges -->
  </div>
{% endblock %}
```

---

## Admin Registrations

Appended to `ecommerceapp/admin.py`:

```python
from .models import (
    Supplier, PurchaseOrder, POLineItem,
    StockReceipt, ReceiptLineItem,
    CustomerVehicle, StockMovement,
)

# ─── POLineItem inline ────────────────────────────────────────────────────────
class POLineItemInline(admin.TabularInline):
    model  = POLineItem
    extra  = 1
    fields = ('spare_part', 'quantity_ordered', 'unit_cost')

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display   = ('name', 'contact_person', 'phone', 'email', 'is_active')
    search_fields  = ('name', 'contact_person', 'email')
    list_filter    = ('is_active',)

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display   = ('__str__', 'supplier', 'order_date', 'expected_delivery', 'status')
    list_filter    = ('status', 'supplier')
    search_fields  = ('supplier__name',)
    inlines        = [POLineItemInline]

# ─── ReceiptLineItem inline ───────────────────────────────────────────────────
class ReceiptLineItemInline(admin.TabularInline):
    model  = ReceiptLineItem
    extra  = 1
    fields = ('spare_part', 'quantity_received')

@admin.register(StockReceipt)
class StockReceiptAdmin(admin.ModelAdmin):
    list_display   = ('__str__', 'purchase_order', 'received_date', 'received_by')
    list_filter    = ('received_date',)
    search_fields  = ('purchase_order__supplier__name',)
    inlines        = [ReceiptLineItemInline]

@admin.register(CustomerVehicle)
class CustomerVehicleAdmin(admin.ModelAdmin):
    list_display   = ('registration_number', 'owner', 'make', 'model', 'year')
    search_fields  = ('registration_number', 'owner__username', 'make', 'model')
    list_filter    = ('make', 'year')

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display   = ('spare_part', 'movement_type', 'quantity', 'reference',
                      'performed_by', 'created_at')
    list_filter    = ('movement_type', 'created_at')
    search_fields  = ('spare_part__name', 'reference')
    readonly_fields = ('spare_part', 'movement_type', 'quantity', 'reference',
                       'notes', 'performed_by', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
```

Additionally, update `VehicleAdmin` and `MechanicAdmin` in the existing registrations to expose the new fields:

```python
# Amend existing VehicleAdmin:
@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    # ... existing config ...
    fields = ('brand', 'model', 'year', 'price', 'description', 'image',
              'engine_number', 'chassis_number')

# Amend existing MechanicAdmin list_display:
@admin.register(Mechanic)
class MechanicAdmin(admin.ModelAdmin):
    list_display  = ('name', 'specialization', 'location', 'phone', 'status')
    list_filter   = ('status',)
    search_fields = ('name', 'specialization', 'location')
```

---

## Signal / Hook Design for StockMovement Automation

### File: `ecommerceapp/signals.py` (new)

```python
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError

from .models import Order, StockMovement


@receiver(post_save, sender=Order)
def handle_order_paid(sender, instance, **kwargs):
    """
    Fires after every Order save.
    When Order.status transitions to 'PAID', for each CartItem of type 'sparepart':
      1. Verify stock_quantity >= cart_item.quantity, else raise ValidationError.
      2. Decrement SparePart.stock_quantity.
      3. Create StockMovement(type='sale').
    All three actions are wrapped in a single atomic block.
    """
    if instance.status != 'PAID':
        return

    # Guard: only process once (avoid re-processing already handled orders)
    from .models import OrderItem
    spare_items = instance.items.filter(
        cart_item__product_type='sparepart'
    ).select_related('cart_item__spare_part')

    if not spare_items.exists():
        return

    with transaction.atomic():
        for order_item in spare_items:
            cart_item   = order_item.cart_item
            spare_part  = cart_item.spare_part
            qty_sold    = cart_item.quantity

            if spare_part.stock_quantity < qty_sold:
                raise ValidationError(
                    f"Insufficient stock for {spare_part.name}: "
                    f"available {spare_part.stock_quantity}, requested {qty_sold}."
                )

            spare_part.stock_quantity -= qty_sold
            spare_part.save(update_fields=['stock_quantity'])

            StockMovement.objects.create(
                spare_part    = spare_part,
                movement_type = 'sale',
                quantity      = qty_sold,
                reference     = f"Order #{instance.id}",
                performed_by  = instance.user,
            )
```

### Wiring in `ecommerceapp/apps.py`

```python
class EcommerceappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ecommerceapp'

    def ready(self):
        import ecommerceapp.signals  # noqa: F401 — registers signal handlers
```

### Signal Flow Diagram

```
Order.save(status='PAID')
        │
        ▼ post_save fires
handle_order_paid()
        │
        ▼
transaction.atomic() ─────────────────────────────────────────┐
        │                                                      │
        ├─ for each sparepart CartItem in Order.items          │
        │       ├─ check stock_quantity >= qty_sold            │
        │       │       └─ if not → raise ValidationError ─►  ROLLBACK
        │       ├─ SparePart.stock_quantity -= qty_sold        │
        │       └─ StockMovement(type='sale').create()         │
        │                                                      │
        └────────────────────────── COMMIT ───────────────────┘
```

**Design note — idempotency**: If the same Order is saved twice with status `PAID` (e.g.
admin double-save), the signal fires twice and will double-decrement stock. To prevent
this, add a `_stock_processed` boolean field to `Order` (default `False`), set it to
`True` inside the atomic block, and guard the signal handler with
`if instance._stock_processed: return`. This field is added in the same migration.

---

## Migration Strategy

### Single migration file

`ecommerceapp/migrations/0002_garage_compliance_modules.py`

**Operations in order:**

1. `AddField` — `Vehicle.engine_number`
2. `AddField` — `Vehicle.chassis_number`
3. `AddField` — `Mechanic.status`
4. `CreateModel` — `Supplier`
5. `CreateModel` — `PurchaseOrder` (depends on `Supplier`)
6. `CreateModel` — `POLineItem` (depends on `PurchaseOrder`, `SparePart`)
7. `CreateModel` — `CustomerVehicle` (depends on `User`)
8. `AddField` — `JobCard.customer_vehicle` (depends on `CustomerVehicle`)
9. `CreateModel` — `StockMovement` (depends on `SparePart`, `User`)
10. `CreateModel` — `StockReceipt` (depends on `PurchaseOrder`, `User`)
11. `CreateModel` — `ReceiptLineItem` (depends on `StockReceipt`, `SparePart`)
12. `AddField` — `Order._stock_processed` (BooleanField, default=False)

**Dependency chain:**
```
0001_initial ──► 0002_garage_compliance_modules
```

All prior migrations in `ecommerceapp` are assumed to be captured in `0001_initial`.
If additional numbered migrations exist, `dependencies` should reference the latest one.

**Running on clean DB:**
```bash
python manage.py migrate   # applies 0001 then 0002
```

**Running on existing DB:**
```bash
python manage.py migrate   # applies only 0002 (0001 already recorded)
```

**Generating the file (developer step):**
```bash
python manage.py makemigrations ecommerceapp --name garage_compliance_modules
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid
executions of a system — essentially, a formal statement about what the system should
do. Properties serve as the bridge between human-readable specifications and
machine-verifiable correctness guarantees.*

### Property 1: Supplier name emptiness is always rejected

*For any* string that is empty or composed entirely of whitespace, creating a `Supplier`
with that value as `name` and calling `full_clean()` SHALL raise `ValidationError`.

**Validates: Requirements 1.2**

---

### Property 2: Supplier list is always ordered by name ascending

*For any* collection of `Supplier` records in the database, the default queryset
`Supplier.objects.all()` SHALL return them in case-insensitive ascending `name` order.

**Validates: Requirements 1.4**

---

### Property 3: POLineItem rejects non-positive quantity_ordered

*For any* integer `q ≤ 0`, a `POLineItem` with `quantity_ordered = q` SHALL raise
`ValidationError` on `full_clean()`.

**Validates: Requirements 2.3**

---

### Property 4: POLineItem rejects negative unit_cost

*For any* decimal `c < 0`, a `POLineItem` with `unit_cost = c` SHALL raise
`ValidationError` on `full_clean()`.

**Validates: Requirements 2.4**

---

### Property 5: PurchaseOrder status machine — terminal state immutability

*For any* `PurchaseOrder` in `Received` status, attempting to save it with
`status ∈ {Draft, Sent}` SHALL raise `ValidationError` without persisting the change.
*For any* `PurchaseOrder` in `Cancelled` status, attempting to save it with
`status ∈ {Draft, Sent, Received}` SHALL raise `ValidationError` without persisting
the change.

**Validates: Requirements 2.6, 2.7**

---

### Property 6: ReceiptLineItem rejects non-positive quantity_received

*For any* integer `q ≤ 0`, a `ReceiptLineItem` with `quantity_received = q` SHALL raise
`ValidationError` on `full_clean()`.

**Validates: Requirements 3.3**

---

### Property 7: Stock receipt confirmation is atomic and complete

*For any* `StockReceipt` with N `ReceiptLineItem` records, after calling
`StockReceipt.confirm()` successfully, ALL of the following SHALL hold simultaneously:

- Each `SparePart.stock_quantity` equals its value before confirmation plus the
  corresponding `quantity_received`.
- Exactly N new `StockMovement` records of `movement_type='purchase_receipt'` exist
  referencing those spare parts.
- The linked `PurchaseOrder.status` equals `'Received'`.

**Validates: Requirements 3.4, 3.6, 3.7, 6.3**

---

### Property 8: StockMovement records are immutable

*For any* saved `StockMovement` instance, calling `.save()` on it again SHALL raise
`ValidationError` and SHALL NOT alter any field of the persisted record.

**Validates: Requirements 6.2**

---

### Property 9: Sale signal decrements stock and creates movement atomically

*For any* `Order` that transitions to `status='PAID'` containing spare-part `CartItem`
records where `stock_quantity ≥ quantity`, after the save:

- Each `SparePart.stock_quantity` equals its prior value minus the cart quantity.
- Exactly one `StockMovement` of `movement_type='sale'` exists per spare-part line item,
  with `quantity` equal to the cart quantity.

**Validates: Requirements 6.4**

---

### Property 10: Sale is aborted when stock would go below zero

*For any* `Order` transitioning to `PAID` where any `CartItem.quantity` exceeds the
corresponding `SparePart.stock_quantity`, the entire transaction SHALL be rolled back:
`SparePart.stock_quantity` remains unchanged and no `StockMovement` record of type
`'sale'` is created for any item in that order.

**Validates: Requirements 6.5**

---

### Property 11: Manual adjustment is atomic

*For any* signed integer `delta` submitted via the stock adjustment view, after a
successful adjustment:

- `SparePart.stock_quantity` equals its prior value plus `delta`.
- Exactly one `StockMovement` of `movement_type='adjustment'` exists recording `delta`
  (absolute value) and the performing staff user.

If any step fails, neither the stock update nor the movement record SHALL be committed.

**Validates: Requirements 6.6**

---

### Property 12: Customer vehicle creation always sets owner to request.user

*For any* authenticated user submitting a valid `CustomerVehicle` creation form, the
persisted `CustomerVehicle.owner` SHALL equal `request.user`.

**Validates: Requirements 5.2**

---

### Property 13: Duplicate registration_number is always rejected

*For any* `registration_number` that already exists in the database, submitting a
`CustomerVehicle` creation form with the same value SHALL produce a validation error and
SHALL NOT persist a second record.

**Validates: Requirements 5.3**

---

### Property 14: Customer vehicle list shows only the requesting user's vehicles

*For any* authenticated customer with K owned `CustomerVehicle` records out of N total,
the `my_vehicle_list` view SHALL return exactly K records all having `owner == request.user`.

**Validates: Requirements 5.6**

---

### Property 15: Vehicle service history returns all and only linked JobCards, ordered

*For any* `CustomerVehicle` with N associated `JobCard` records, the
`vehicle_service_history` view SHALL return exactly N records ordered by `created_at`
descending.

**Validates: Requirements 5.9**

---

### Property 16: Stock movement log filter returns only matching records

*For any* combination of filter parameters (spare part name, movement type, date range),
every `StockMovement` record returned by `stock_movement_log` SHALL satisfy all supplied
filter conditions, and no record failing any condition SHALL appear in the results.

**Validates: Requirements 6.7**

---

### Property 17: Stock movement summary net calculation is correct

*For any* set of `StockMovement` records for a given `SparePart`, the summary view SHALL
compute net movement as:

```
net = Σ quantity(stock_in, purchase_receipt, adjustment+)
    − Σ quantity(stock_out, sale, adjustment−)
```

where the result equals `current_stock_quantity − initial_stock_quantity`.

**Validates: Requirements 6.9**

---

### Property 18: Mechanic default status is Always 'Available'

*For any* `Mechanic` created without an explicit `status` value, `mechanic.status` SHALL
equal `'Available'`.

**Validates: Requirements 7.2**

---

## Error Handling

| Scenario | Handling |
|---|---|
| Supplier `name` blank | `ValidationError` in `clean()`, form re-renders with error |
| POLineItem `quantity_ordered ≤ 0` | `ValidationError` in `clean()` |
| POLineItem `unit_cost < 0` | `ValidationError` in `clean()` |
| ReceiptLineItem `quantity_received ≤ 0` | `ValidationError` in `clean()` |
| Receipt confirmation DB error | `transaction.atomic()` rollback; view shows `messages.error` |
| PO terminal status rollback attempt | `ValidationError` in `PurchaseOrder.clean()` |
| Sale stock goes negative | `ValidationError` in signal handler; full `atomic()` rollback |
| StockMovement update attempt | `ValidationError` raised in `save()` override |
| Duplicate `registration_number` | `IntegrityError` caught by form; field-level error shown |
| Non-owner vehicle access | `owner_or_staff_required` returns `HttpResponseForbidden (403)` |
| Non-staff access to staff views | `@staff_member_required` redirects to `LOGIN_URL` or returns 403 |
| Unauthenticated access | `@login_required` / `@staff_member_required` redirects to `LOGIN_URL` |

---

## Testing Strategy

### Dual Testing Approach

**Unit / example tests** (`ecommerceapp/tests/`)

- `test_supplier.py` — model `clean()` validation, CRUD views, list ordering
- `test_purchase_order.py` — model state machine, line item validation, form workflows
- `test_stock_receipt.py` — `confirm()` atomicity, partial failure rollback, PO status update
- `test_customer_vehicle.py` — owner-setting, duplicate registration, access control (403/redirect)
- `test_stock_movement.py` — immutability, sale signal, adjustment atomicity, below-zero prevention
- `test_access_control.py` — unauthenticated redirect, non-staff 403, owner-or-staff enforcement
- `test_supplier_performance.py` — aggregation correctness, N/A for zero receipts

**Property-based tests** (`ecommerceapp/tests/test_properties.py`)

Use **Hypothesis** (Python property-based testing library).  
Each test runs a minimum of **100 iterations** via `@settings(max_examples=100)`.

```python
from hypothesis import given, settings
from hypothesis import strategies as st

# Tag format: Feature: garage-compliance-modules, Property N: <text>

# Feature: garage-compliance-modules, Property 1: Supplier name emptiness rejected
@given(name=st.one_of(st.just(''), st.text(alphabet=st.characters(whitelist_chars=' \t\n\r'))))
@settings(max_examples=100)
def test_prop1_supplier_empty_name_rejected(name): ...

# Feature: garage-compliance-modules, Property 3: POLineItem rejects non-positive quantity
@given(qty=st.integers(max_value=0))
@settings(max_examples=100)
def test_prop3_po_line_item_nonpositive_quantity_rejected(qty): ...

# Feature: garage-compliance-modules, Property 4: POLineItem rejects negative unit_cost
@given(cost=st.decimals(max_value=-0.01, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_prop4_po_line_item_negative_cost_rejected(cost): ...

# Feature: garage-compliance-modules, Property 5: PO terminal state immutability
@given(forbidden_status=st.sampled_from(['Draft', 'Sent']))
@settings(max_examples=100)
def test_prop5_received_po_cannot_revert(forbidden_status): ...

# Feature: garage-compliance-modules, Property 6: ReceiptLineItem rejects non-positive quantity
@given(qty=st.integers(max_value=0))
@settings(max_examples=100)
def test_prop6_receipt_line_item_nonpositive_quantity_rejected(qty): ...

# Feature: garage-compliance-modules, Property 7: Stock receipt confirmation atomicity
@given(line_count=st.integers(min_value=1, max_value=5),
       quantities=st.lists(st.integers(min_value=1, max_value=100), min_size=1, max_size=5))
@settings(max_examples=100)
def test_prop7_receipt_confirmation_atomic(line_count, quantities): ...

# Feature: garage-compliance-modules, Property 8: StockMovement immutability
@settings(max_examples=100)
def test_prop8_stock_movement_immutable(): ...

# Feature: garage-compliance-modules, Property 12: Vehicle owner set to request.user
@given(username=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_chars='abcdefghijklmnopqrstuvwxyz')))
@settings(max_examples=100)
def test_prop12_vehicle_owner_set_to_request_user(username): ...

# Feature: garage-compliance-modules, Property 13: Duplicate registration rejected
@given(reg=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
@settings(max_examples=100)
def test_prop13_duplicate_registration_rejected(reg): ...

# Feature: garage-compliance-modules, Property 16: Movement log filter correctness
@given(movement_type=st.sampled_from(['stock_in','stock_out','adjustment','sale','purchase_receipt']))
@settings(max_examples=100)
def test_prop16_movement_log_filter_returns_matching_only(movement_type): ...

# Feature: garage-compliance-modules, Property 18: Mechanic default status Available
@given(name=st.text(min_size=1, max_size=100))
@settings(max_examples=100)
def test_prop18_mechanic_default_status_available(name): ...
```

**Integration tests**

- Confirm admin is reachable and shows correct models.
- Run `python manage.py check` to verify no system check errors.
- Run `python manage.py migrate --run-syncdb` on a test DB to verify migration completeness.
