# Implementation Plan: Garage Compliance Modules

## Overview

Implement three compliance modules (Supplier Management, Customer Vehicle Registry, Stock Movement Log) plus two minor model enhancements (`Mechanic.status`, `Vehicle.engine_number`/`chassis_number`) inside the existing `ecommerceapp` Django application.
All new models are appended to `models.py`; views and URLs are appended to the existing files; new files `signals.py` and `decorators.py` are created.

---

## Tasks

---

### Module 0 — Foundation (shared infrastructure)

- [ ] 0. Create shared infrastructure files and test package
  - [ ] 0.1 Create `ecommerceapp/decorators.py` with the `owner_or_staff_required` decorator
    - Implement `owner_or_staff_required(view_func)`: allow access when `request.user.is_staff` is True OR `CustomerVehicle.owner == request.user`; return `HttpResponseForbidden` otherwise
    - The decorator must look up `CustomerVehicle` using the `pk` kwarg from the URL
    - _Requirements: 10.3_
  - [ ] 0.2 Create `ecommerceapp/tests/` package with `__init__.py`
    - Create the `tests/` directory and an empty `__init__.py` so that Django discovers individual test modules in subsequent tasks
    - _Requirements: 9.3_

---

### Module 1 — Model Amendments + Migration

- [ ] 1. Add minor model fields and create the compliance migration
  - [ ] 1.1 Amend `Vehicle` model in `ecommerceapp/models.py`
    - Append `engine_number = models.CharField(max_length=100, blank=True)` and `chassis_number = models.CharField(max_length=100, blank=True)` to the existing `Vehicle` class
    - _Requirements: 8.1, 8.2, 8.3_
  - [ ] 1.2 Amend `Mechanic` model in `ecommerceapp/models.py`
    - Append `STATUS_CHOICES` and `status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Available')` to the existing `Mechanic` class
    - _Requirements: 7.1, 7.2_
  - [ ] 1.3 Append new models to `ecommerceapp/models.py` — Supplier through StockMovement
    - Append in this order (matching the migration operation sequence): `Supplier`, `PurchaseOrder`, `POLineItem`, `CustomerVehicle`, `StockMovement`, `StockReceipt`, `ReceiptLineItem`
    - Include all fields, `Meta`, `__str__`, `clean()`, and `save()` overrides exactly as specified in the design document
    - Add `_stock_processed = models.BooleanField(default=False)` to the existing `Order` model
    - Add `customer_vehicle = models.ForeignKey('CustomerVehicle', on_delete=models.SET_NULL, null=True, blank=True, related_name='job_cards')` to the existing `JobCard` model
    - _Requirements: 1.1, 2.1, 2.2, 3.1, 3.2, 5.1, 5.7, 6.1, 9.1, 9.2_
  - [ ] 1.4 Create migration `ecommerceapp/migrations/0024_garage_compliance_modules.py`
    - `dependencies` must reference `('ecommerceapp', '0023_mechanicrating')`
    - Operations in order: `AddField Vehicle.engine_number`, `AddField Vehicle.chassis_number`, `AddField Mechanic.status`, `CreateModel Supplier`, `CreateModel PurchaseOrder`, `CreateModel POLineItem`, `CreateModel CustomerVehicle`, `AddField JobCard.customer_vehicle`, `CreateModel StockMovement`, `CreateModel StockReceipt`, `CreateModel ReceiptLineItem`, `AddField Order._stock_processed`
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

---

### Module 2 — Supplier Management

- [ ] 2. Implement Supplier CRUD (forms, views, URLs, templates)
  - [ ] 2.1 Add `SupplierForm` to `ecommerceapp/forms.py`
    - `ModelForm` for `Supplier` including all fields; call `full_clean()` so the model-level `clean()` runs
    - _Requirements: 1.5, 1.6, 1.7_
  - [ ] 2.2 Append supplier views to `ecommerceapp/views.py`
    - Implement `supplier_list`, `supplier_create`, `supplier_edit`, `supplier_delete` — all decorated with `@staff_member_required`
    - `supplier_list`: queryset ordered by `name`, paginated 25/page
    - `supplier_create` / `supplier_edit`: validate form, save, redirect to `supplier_list`; re-render with errors on invalid input
    - `supplier_delete`: GET renders confirmation; POST deletes and redirects
    - _Requirements: 1.4, 1.5, 1.6, 1.7, 10.2_
  - [ ] 2.3 Append supplier URL patterns to `ecommerceapp/urls.py`
    - Add `suppliers/`, `suppliers/create/`, `suppliers/<int:pk>/edit/`, `suppliers/<int:pk>/delete/` as specified in the design
    - _Requirements: 1.4, 10.2_
  - [ ] 2.4 Create supplier templates
    - Create `ecommerceapp/templates/ecommerceapp/suppliers/supplier_list.html` — Bootstrap 5 table with Create button
    - Create `ecommerceapp/templates/ecommerceapp/suppliers/supplier_form.html` — shared create/edit form
    - Create `ecommerceapp/templates/ecommerceapp/suppliers/supplier_confirm_delete.html` — delete confirmation
    - All templates extend `base.html`
    - _Requirements: 1.4, 1.5, 1.6, 1.7_
  - [ ]* 2.5 Write unit tests for supplier model and views in `ecommerceapp/tests/test_supplier.py`
    - Test `Supplier.clean()` raises `ValidationError` when `name` is blank
    - Test supplier list view orders by name ascending
    - Test create/edit/delete views redirect correctly on valid input; re-render on invalid
    - Test unauthenticated and non-staff access returns redirect/403
    - _Requirements: 1.1–1.7, 10.2_
  - [ ]* 2.6 Write property test for Supplier in `ecommerceapp/tests/test_properties.py`
    - **Property 1: Supplier name emptiness is always rejected**
    - Use `@given(name=st.one_of(st.just(''), st.text(alphabet=...whitespace...)))`, `@settings(max_examples=100)`
    - **Validates: Requirements 1.2**

---

### Module 3 — Purchase Order Management

- [ ] 3. Implement Purchase Order CRUD (forms, views, URLs, templates)
  - [ ] 3.1 Add `PurchaseOrderForm` and `POLineItemFormSet` to `ecommerceapp/forms.py`
    - `ModelForm` for `PurchaseOrder`; inline `modelformset_factory` / `inlineformset_factory` for `POLineItem` with `extra=1`
    - Include `clean()` delegation so model-level validation fires
    - _Requirements: 2.5, 2.6, 2.7_
  - [ ] 3.2 Append purchase order views to `ecommerceapp/views.py`
    - Implement `po_list`, `po_create`, `po_detail`, `po_edit` — all `@staff_member_required`
    - `po_create`: save PO header + formset inside `transaction.atomic()`; redirect to `po_detail`
    - `po_edit`: raise 403 if `po.status in ['Received', 'Cancelled']`
    - `po_list`: ordered by `-order_date`, paginated 25/page
    - _Requirements: 2.5, 2.6, 2.7, 2.8, 10.2_
  - [ ] 3.3 Append purchase order URL patterns to `ecommerceapp/urls.py`
    - Add `suppliers/po/`, `suppliers/po/create/`, `suppliers/po/<int:pk>/`, `suppliers/po/<int:pk>/edit/`
    - _Requirements: 2.5, 10.2_
  - [ ] 3.4 Create purchase order templates
    - `suppliers/po_list.html` — table with status badges
    - `suppliers/po_form.html` — PO header form + `POLineItem` formset rows (JavaScript `add row` button)
    - `suppliers/po_detail.html` — PO header + line items table
    - All extend `base.html`
    - _Requirements: 2.5, 2.8_
  - [ ]* 3.5 Write unit tests for purchase order in `ecommerceapp/tests/test_purchase_order.py`
    - Test `PurchaseOrder.clean()` blocks `Received→Draft`, `Received→Sent`, `Cancelled→*`
    - Test `POLineItem.clean()` rejects `quantity_ordered ≤ 0` and `unit_cost < 0`
    - Test `po_create` persists with status `Draft` and redirects to detail
    - Test `po_edit` returns 403 when PO is Received or Cancelled
    - _Requirements: 2.3–2.8, 10.2_
  - [ ]* 3.6 Write property tests for POLineItem in `ecommerceapp/tests/test_properties.py`
    - **Property 3: POLineItem rejects non-positive quantity_ordered**
    - **Property 4: POLineItem rejects negative unit_cost**
    - **Property 5: PurchaseOrder terminal state immutability**
    - Use `@given` + `@settings(max_examples=100)` for each
    - **Validates: Requirements 2.3, 2.4, 2.6, 2.7**

---

### Module 4 — Stock Receipt

- [ ] 4. Implement Stock Receipt (forms, views, URLs, templates)
  - [ ] 4.1 Add `StockReceiptForm` and `ReceiptLineItemFormSet` to `ecommerceapp/forms.py`
    - `ModelForm` for `StockReceipt`; `inlineformset_factory` for `ReceiptLineItem`
    - Pre-populate formset initial data from `POLineItem` records in the view
    - _Requirements: 3.9_
  - [ ] 4.2 Append stock receipt views to `ecommerceapp/views.py`
    - Implement `receive_stock(request, po_pk)` and `receipt_detail(request, pk)` — both `@staff_member_required`
    - `receive_stock` POST: inside `transaction.atomic()` — create `StockReceipt`, create `ReceiptLineItem` records, call `StockReceipt.confirm()` which increments stock and creates `StockMovement` records
    - On DB failure: rollback and display `messages.error`
    - _Requirements: 3.4, 3.5, 3.6, 3.7, 3.9, 10.2_
  - [ ] 4.3 Append stock receipt URL patterns to `ecommerceapp/urls.py`
    - Add `suppliers/po/<int:po_pk>/receive/` and `suppliers/receipts/<int:pk>/`
    - _Requirements: 3.4, 10.2_
  - [ ] 4.4 Create stock receipt templates
    - `suppliers/receive_stock.html` — receipt header form + `ReceiptLineItem` formset with pre-populated part names and quantities
    - `suppliers/receipt_detail.html` — receipt header + received quantities table
    - All extend `base.html`
    - _Requirements: 3.9, 3.8_
  - [ ]* 4.5 Write unit tests for stock receipt in `ecommerceapp/tests/test_stock_receipt.py`
    - Test `confirm()` increments all `SparePart.stock_quantity` values correctly
    - Test `confirm()` sets `PurchaseOrder.status` to `'Received'`
    - Test partial DB failure rolls back all stock changes (simulate with `side_effect`)
    - Test `ReceiptLineItem.clean()` raises `ValidationError` for `quantity_received ≤ 0`
    - _Requirements: 3.3–3.7_
  - [ ]* 4.6 Write property tests for stock receipt in `ecommerceapp/tests/test_properties.py`
    - **Property 6: ReceiptLineItem rejects non-positive quantity_received**
    - **Property 7: Stock receipt confirmation is atomic and complete**
    - Use `@given` + `@settings(max_examples=100)` for each
    - **Validates: Requirements 3.3, 3.4, 3.6, 3.7, 6.3**

---

### Module 5 — Supplier Performance Report

- [ ] 5. Implement Supplier Performance Report (view, URL, template)
  - [ ] 5.1 Append `supplier_performance` view to `ecommerceapp/views.py`
    - Decorated with `@staff_member_required`
    - Annotate `Supplier` queryset with `total_pos`, `total_items`, `avg_delivery` using ORM `annotate`/`aggregate` as specified in the design
    - Post-process: replace `avg_delivery == None` (or zero-receipt suppliers) with `'N/A'`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 10.2_
  - [ ] 5.2 Append performance URL to `ecommerceapp/urls.py`
    - Add `suppliers/performance/` → `supplier_performance`
    - _Requirements: 4.4_
  - [ ] 5.3 Create `suppliers/supplier_performance.html` template
    - Bootstrap 5 table: one row per supplier with columns for PO count, items received, avg delivery time (showing "N/A" where applicable)
    - Extends `base.html`
    - _Requirements: 4.1, 4.2_
  - [ ]* 5.4 Write unit tests for supplier performance in `ecommerceapp/tests/test_supplier_performance.py`
    - Test aggregation correctness against known fixture data
    - Test "N/A" shown when supplier has no completed receipts
    - Test unauthenticated/non-staff access returns redirect/403
    - _Requirements: 4.1–4.4_

---

### Module 6 — Customer Vehicle Registry

- [ ] 6. Implement Customer Vehicle Registry (forms, views, URLs, templates)
  - [ ] 6.1 Add `CustomerVehicleForm` to `ecommerceapp/forms.py`
    - `ModelForm` for `CustomerVehicle`; exclude `owner` (set in view); include `unique` validation for `registration_number` with field-level error message
    - _Requirements: 5.2, 5.3_
  - [ ] 6.2 Append customer vehicle views to `ecommerceapp/views.py`
    - Implement `my_vehicle_list`, `vehicle_create`, `vehicle_edit`, `vehicle_delete`, `vehicle_service_history`, `all_vehicle_list`
    - `vehicle_create`: set `form.instance.owner = request.user` before saving; decorate with `@login_required`
    - `vehicle_edit` / `vehicle_delete`: decorate with `@owner_or_staff_required` from `decorators.py`
    - `my_vehicle_list`: filter by `owner=request.user`; `@login_required`
    - `all_vehicle_list`: `select_related('owner')`; `@staff_member_required`
    - `vehicle_service_history`: return `JobCard.objects.filter(customer_vehicle=vehicle).order_by('-created_at')`; check ownership or staff before rendering
    - _Requirements: 5.2–5.10, 10.1, 10.3_
  - [ ] 6.3 Append customer vehicle URL patterns to `ecommerceapp/urls.py`
    - Add all six vehicle URLs as specified in the design
    - _Requirements: 5.2, 10.1_
  - [ ] 6.4 Create customer vehicle templates
    - `vehicles/my_vehicle_list.html` — customer's own vehicles as a Bootstrap 5 card/table list with Edit, Delete, History buttons
    - `vehicles/all_vehicle_list.html` — staff view with owner username column
    - `vehicles/vehicle_form.html` — shared create/edit form
    - `vehicles/vehicle_confirm_delete.html` — delete confirmation
    - `vehicles/vehicle_service_history.html` — ordered list of linked `JobCard` records
    - All extend `base.html`
    - _Requirements: 5.4, 5.5, 5.6, 5.9_
  - [ ] 6.5 Update `JobCard` form and admin to expose `customer_vehicle` dropdown
    - In `ecommerceapp/forms.py`: add `customer_vehicle` to the existing `JobCardForm` (or create it if absent) so staff can optionally select a `CustomerVehicle`
    - The field must be optional (not required)
    - _Requirements: 5.8_
  - [ ]* 6.6 Write unit tests for customer vehicle in `ecommerceapp/tests/test_customer_vehicle.py`
    - Test `vehicle_create` sets `owner` to `request.user`
    - Test duplicate `registration_number` returns validation error
    - Test `my_vehicle_list` returns only requesting user's vehicles
    - Test `vehicle_edit` returns 403 for non-owner non-staff user
    - Test `vehicle_service_history` returns correct ordered job cards
    - Test unauthenticated access redirects to login
    - _Requirements: 5.2–5.10, 10.1, 10.3_
  - [ ]* 6.7 Write property tests for customer vehicle in `ecommerceapp/tests/test_properties.py`
    - **Property 12: Customer vehicle creation always sets owner to request.user**
    - **Property 13: Duplicate registration_number is always rejected**
    - **Property 14: Customer vehicle list shows only the requesting user's vehicles**
    - **Property 15: Vehicle service history returns all and only linked JobCards, ordered**
    - Use `@given` + `@settings(max_examples=100)` for each
    - **Validates: Requirements 5.2, 5.3, 5.6, 5.9**

---

### Module 7 — Signals (Order → StockMovement)

- [ ] 7. Create `ecommerceapp/signals.py` and wire it into `apps.py`
  - [ ] 7.1 Create `ecommerceapp/signals.py` with the `handle_order_paid` signal handler
    - Import `Order`, `StockMovement` from `.models`
    - `@receiver(post_save, sender=Order)`: guard with `if instance.status != 'PAID': return` and `if instance._stock_processed: return`
    - Inside `transaction.atomic()`: for each sparepart `CartItem`, check `stock_quantity >= qty`, decrement stock, create `StockMovement(type='sale')`, then set `instance._stock_processed = True` and save with `update_fields=['_stock_processed']`
    - On insufficient stock: raise `ValidationError`, which triggers rollback
    - _Requirements: 6.4, 6.5_
  - [ ] 7.2 Update `ecommerceapp/apps.py` to import signals in `EcommerceappConfig.ready()`
    - Add `import ecommerceapp.signals  # noqa: F401` inside the `ready()` method
    - _Requirements: 6.4_
  - [ ]* 7.3 Write unit tests for signals in `ecommerceapp/tests/test_stock_movement.py`
    - Test sale signal decrements `SparePart.stock_quantity` and creates `StockMovement(type='sale')`
    - Test sale is aborted and rolled back when stock would go below zero
    - Test idempotency: saving same `PAID` Order twice does not double-decrement
    - Test `StockMovement.save()` raises `ValidationError` on update attempt
    - _Requirements: 6.2, 6.4, 6.5_
  - [ ]* 7.4 Write property tests for signals/movement in `ecommerceapp/tests/test_properties.py`
    - **Property 8: StockMovement records are immutable**
    - **Property 9: Sale signal decrements stock and creates movement atomically**
    - **Property 10: Sale is aborted when stock would go below zero**
    - Use `@given` + `@settings(max_examples=100)` for each
    - **Validates: Requirements 6.2, 6.4, 6.5**

---

### Module 8 — Stock Movement Views

- [ ] 8. Implement Stock Movement log, summary, and adjustment views
  - [ ] 8.1 Add `StockAdjustmentForm` to `ecommerceapp/forms.py`
    - Fields: `spare_part` (ModelChoiceField → `SparePart`), `signed_quantity` (IntegerField, non-zero), `notes` (CharField, optional)
    - _Requirements: 6.6_
  - [ ] 8.2 Append stock movement views to `ecommerceapp/views.py`
    - Implement `stock_movement_log`, `stock_movement_summary`, `stock_adjustment` — all `@staff_member_required`
    - `stock_movement_log`: filter by `spare_part__name__icontains`, `movement_type`, `date_start`, `date_end`; order by `-created_at`; paginate 50/page; no filter required to show all records
    - `stock_movement_summary`: annotate `SparePart` queryset with net movement (treat `stock_out`/`sale` as negative)
    - `stock_adjustment`: inside `transaction.atomic()` — update `SparePart.stock_quantity`, create `StockMovement(type='adjustment', performed_by=request.user)`; rollback on failure
    - _Requirements: 6.6, 6.7, 6.8, 6.9, 6.10, 10.2_
  - [ ] 8.3 Append stock movement URL patterns to `ecommerceapp/urls.py`
    - Add `stock/movements/`, `stock/movements/summary/`, `stock/movements/adjust/`
    - _Requirements: 6.7, 6.10_
  - [ ] 8.4 Create stock movement templates
    - `stock/movement_log.html` — filter form (part name, type, date range) + paginated Bootstrap 5 table ordered by newest first
    - `stock/movement_summary.html` — per-part table: current stock, net movement, breakdown by type
    - `stock/stock_adjustment.html` — adjustment form with spare part selector and signed quantity input
    - All extend `base.html`
    - _Requirements: 6.7, 6.8, 6.9, 6.6_
  - [ ]* 8.5 Write unit tests for stock movement views in `ecommerceapp/tests/test_stock_movement.py`
    - Test `stock_movement_log` with each filter in isolation and combined
    - Test `stock_adjustment` increments/decrements stock atomically and creates movement record
    - Test unauthenticated/non-staff access returns redirect/403
    - _Requirements: 6.6–6.10, 10.2_
  - [ ]* 8.6 Write property tests for movement log/adjustment in `ecommerceapp/tests/test_properties.py`
    - **Property 11: Manual adjustment is atomic**
    - **Property 16: Stock movement log filter returns only matching records**
    - **Property 17: Stock movement summary net calculation is correct**
    - Use `@given` + `@settings(max_examples=100)` for each
    - **Validates: Requirements 6.6, 6.7, 6.9**

---

### Module 9 — Admin Registrations

- [ ] 9. Register all new models in `ecommerceapp/admin.py`
  - [ ] 9.1 Append new model admin classes to `ecommerceapp/admin.py`
    - Register `Supplier`, `PurchaseOrder` (with `POLineItemInline`), `StockReceipt` (with `ReceiptLineItemInline`), `CustomerVehicle`, `StockMovement` exactly as specified in the design
    - `StockMovementAdmin`: set `readonly_fields` for all fields; override `has_add_permission` and `has_change_permission` to return `False`
    - _Requirements: 1.3, 2.8, 3.8, 6.1, 9.1_
  - [ ] 9.2 Amend existing `VehicleAdmin` and `MechanicAdmin` in `ecommerceapp/admin.py`
    - `VehicleAdmin`: add `engine_number` and `chassis_number` to `fields` tuple
    - `MechanicAdmin`: add `status` to `list_display` and `list_filter`
    - _Requirements: 7.3, 7.4, 8.4_

---

### Module 10 — Checkpoint & Access Control Tests

- [ ] 10. Final checkpoint — verify access control and run all tests
  - [ ] 10.1 Write access control tests in `ecommerceapp/tests/test_access_control.py`
    - Test unauthenticated requests to every new URL redirect to `LOGIN_URL`
    - Test authenticated non-staff requests to staff-only URLs return 403
    - Test customer accessing another customer's vehicle edit/delete returns 403
    - Test `owner_or_staff_required` decorator in isolation using a mock view
    - _Requirements: 10.1, 10.2, 10.3, 10.4_
  - [ ]* 10.2 Write property tests for mechanic default status in `ecommerceapp/tests/test_properties.py`
    - **Property 18: Mechanic default status is always 'Available'**
    - Use `@given(name=st.text(min_size=1, max_size=100))`, `@settings(max_examples=100)`
    - **Validates: Requirements 7.2**
  - [ ] 10.3 Checkpoint — ensure all tests pass, ask the user if questions arise
    - Run `python manage.py check` to verify no system check errors
    - Run `python manage.py test ecommerceapp` and confirm all tests pass

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- All views must import `owner_or_staff_required` from `ecommerceapp.decorators`
- The migration file is named `0024_garage_compliance_modules.py` and depends on `('ecommerceapp', '0023_mechanicrating')`
- Property tests require `hypothesis` (`pip install hypothesis`); add it to `requirements.txt`
- `StockMovement` records are append-only at the ORM level — never pass existing instances to `.save()`
- `StockReceipt.confirm()` should be called from inside the `receive_stock` view's `transaction.atomic()` block
- The `_stock_processed` guard on `Order` prevents double-decrement if admin saves the same paid order twice
- Each task references specific requirements for traceability; the design document is the authoritative reference for exact field names and signatures

---

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["0.1", "0.2"] },
    { "id": 1, "tasks": ["1.1", "1.2"] },
    { "id": 2, "tasks": ["1.3"] },
    { "id": 3, "tasks": ["1.4"] },
    { "id": 4, "tasks": ["2.1", "3.1", "4.1", "6.1", "8.1"] },
    { "id": 5, "tasks": ["2.2", "3.2", "4.2", "5.1", "6.2", "7.1", "8.2"] },
    { "id": 6, "tasks": ["2.3", "3.3", "4.3", "5.2", "6.3", "7.2", "8.3"] },
    { "id": 7, "tasks": ["2.4", "3.4", "4.4", "5.3", "6.4", "8.4"] },
    { "id": 8, "tasks": ["6.5", "9.1"] },
    { "id": 9, "tasks": ["9.2"] },
    { "id": 10, "tasks": ["2.5", "3.5", "4.5", "5.4", "6.6", "7.3", "8.5", "10.1"] },
    { "id": 11, "tasks": ["2.6", "3.6", "4.6", "6.7", "7.4", "8.6", "10.2"] },
    { "id": 12, "tasks": ["10.3"] }
  ]
}
```
