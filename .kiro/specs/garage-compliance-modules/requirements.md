# Requirements Document

## Introduction

This feature closes three compliance gaps identified in the AutoWorld AutoShop & Garage Management System audit, plus two minor model enhancements. The system is a Django/PostgreSQL application with a Bootstrap 5 frontend housed in `ecommerceapp`.

The three gaps are:
1. **Supplier Management** — procurement workflow from purchase orders through stock receipt.
2. **Customer Vehicle Registry** — a dedicated record for each customer's owned vehicle, separate from the sales-catalogue `Vehicle` model.
3. **Stock Movement Log** — a full audit trail for every change to `SparePart.stock_quantity`.

Minor enhancements:
- Add an availability `status` field to the `Mechanic` model.
- Add `engine_number` and `chassis_number` to the catalogue `Vehicle` model.

---

## Glossary

- **System**: The AutoWorld garage management application as a whole.
- **Supplier**: An external business entity that supplies spare parts to the garage.
- **PurchaseOrder (PO)**: A formal request issued by staff to a Supplier to procure spare parts.
- **POLineItem**: A single line within a PurchaseOrder specifying one SparePart, quantity ordered, and unit cost.
- **StockReceipt**: A record confirming that goods from a PurchaseOrder have physically arrived at the garage.
- **ReceiptLineItem**: A single line within a StockReceipt specifying one SparePart and the quantity actually received.
- **SparePart**: An existing catalogue model representing a spare part held in inventory (`ecommerceapp.SparePart`).
- **CustomerVehicle**: A vehicle owned and registered by a Customer user, distinct from the sales catalogue.
- **Vehicle**: The existing sales-catalogue model (`ecommerceapp.Vehicle`) listing vehicles for sale.
- **JobCard**: The existing workshop job card model (`ecommerceapp.JobCard`) tracking repair/service work.
- **StockMovement**: An immutable audit record of one change to a SparePart's stock level.
- **Mechanic**: The existing model (`ecommerceapp.Mechanic`) representing a workshop mechanic.
- **Customer**: A registered Django `User` with the customer role.
- **Staff**: A Django `User` with `is_staff=True` or superuser status.
- **CartItem**: The existing model representing an item in a shopping cart (`ecommerceapp.CartItem`).
- **Order**: The existing model representing a completed purchase order from the shop (`ecommerceapp.Order`).
- **Signal**: A Django `post_save` or `post_delete` signal used to trigger side-effects automatically.
- **Admin Panel**: The Django admin interface at `/admin/`.
- **Control Panel**: The custom staff-facing views accessible under `/control-panel/`.

---

## Requirements

---

### Requirement 1: Supplier Model

**User Story:** As a staff member, I want to maintain a directory of suppliers so that I can track which companies we source spare parts from and contact them when needed.

#### Acceptance Criteria

1. THE System SHALL provide a `Supplier` model with the fields: `name` (CharField, max 200), `contact_person` (CharField, max 100, blank), `phone` (CharField, max 30, blank), `email` (EmailField, blank), `address` (TextField, blank), and `is_active` (BooleanField, default True).
2. WHEN a Supplier is saved with `name` empty, THE System SHALL raise a validation error preventing the save.
3. THE System SHALL expose all Supplier CRUD operations in the Admin Panel.
4. WHEN Staff access the supplier list view, THE System SHALL display all Supplier records ordered by `name` ascending.
5. WHEN Staff submit a valid supplier creation form, THE System SHALL persist the Supplier and redirect to the supplier list view.
6. WHEN Staff submit an invalid supplier creation form (e.g., missing `name`), THE System SHALL re-render the form with descriptive field-level error messages.
7. WHEN Staff edit an existing Supplier and submit a valid form, THE System SHALL update the Supplier record and redirect to the supplier list view.

---

### Requirement 2: Purchase Order Model

**User Story:** As a staff member, I want to create purchase orders for spare parts so that I can formally track procurement from suppliers.

#### Acceptance Criteria

1. THE System SHALL provide a `PurchaseOrder` model with the fields: `supplier` (ForeignKey → Supplier, CASCADE), `order_date` (DateField, auto today), `expected_delivery` (DateField, null/blank), `status` (CharField, choices: Draft / Sent / Received / Cancelled, default Draft), and `notes` (TextField, blank).
2. THE System SHALL provide a `POLineItem` model with the fields: `purchase_order` (ForeignKey → PurchaseOrder, CASCADE, related_name `line_items`), `spare_part` (ForeignKey → SparePart, PROTECT), `quantity_ordered` (PositiveIntegerField), and `unit_cost` (DecimalField, max_digits=10, decimal_places=2).
3. WHEN `quantity_ordered` is set to zero or less, THE System SHALL raise a validation error on the `POLineItem`.
4. WHEN `unit_cost` is set to a negative value, THE System SHALL raise a validation error on the `POLineItem`.
5. WHEN Staff create a PurchaseOrder with at least one POLineItem and submit a valid form, THE System SHALL persist the PurchaseOrder with status `Draft` and redirect to the PO detail view.
6. WHEN a PurchaseOrder status is `Received`, THE System SHALL prevent any subsequent save from changing the status back to `Draft` or `Sent`.
7. WHEN a PurchaseOrder status is `Cancelled`, THE System SHALL prevent any subsequent save from changing the status to `Draft`, `Sent`, or `Received`.
8. THE System SHALL expose PurchaseOrder and POLineItem CRUD in the Admin Panel with inline editing of POLineItems within the PurchaseOrder admin page.

---

### Requirement 3: Stock Receipt Model

**User Story:** As a staff member, I want to record stock receipts against purchase orders so that inventory is updated when goods arrive.

#### Acceptance Criteria

1. THE System SHALL provide a `StockReceipt` model with the fields: `purchase_order` (ForeignKey → PurchaseOrder, CASCADE), `received_date` (DateField, auto today), `received_by` (ForeignKey → User, SET_NULL, null/blank), and `notes` (TextField, blank).
2. THE System SHALL provide a `ReceiptLineItem` model with the fields: `stock_receipt` (ForeignKey → StockReceipt, CASCADE, related_name `line_items`), `spare_part` (ForeignKey → SparePart, PROTECT), and `quantity_received` (PositiveIntegerField).
3. WHEN `quantity_received` is set to zero or less on a ReceiptLineItem, THE System SHALL raise a validation error.
4. WHEN Staff confirm a StockReceipt, THE System SHALL increment `SparePart.stock_quantity` by the `quantity_received` for each ReceiptLineItem within a single database transaction.
5. WHEN the transaction in criterion 4 fails for any ReceiptLineItem, THE System SHALL roll back all stock quantity increments for that StockReceipt and surface a descriptive error to the user. THE System SHALL NOT update `PurchaseOrder.status` to `Received` if the stock transaction fails.
6. WHEN the stock quantity transaction in criterion 4 succeeds, THE System SHALL atomically set the linked `PurchaseOrder.status` to `Received` in the same transaction.
7. WHEN Staff confirm a StockReceipt, THE System SHALL create one `StockMovement` record of type `purchase_receipt` for each ReceiptLineItem regardless of whether the stock quantity transaction succeeds or fails.
8. THE System SHALL expose StockReceipt and ReceiptLineItem CRUD in the Admin Panel with inline editing of ReceiptLineItems within the StockReceipt admin page.
9. WHEN Staff access the "Receive Stock" view for a PurchaseOrder, THE System SHALL pre-populate the ReceiptLineItem formset with all SpareParts from the corresponding POLineItems.

---

### Requirement 4: Supplier Performance Report

**User Story:** As a staff manager, I want a supplier performance report so that I can evaluate which suppliers deliver reliably and on time.

#### Acceptance Criteria

1. WHEN Staff access the supplier performance report view, THE System SHALL display one row per Supplier containing: total number of PurchaseOrders, total number of ReceiptLineItems received, and average delivery time in days (difference between `StockReceipt.received_date` and `PurchaseOrder.expected_delivery`).
2. WHEN a Supplier has no completed StockReceipts, THE System SHALL display "N/A" for the average delivery time for that Supplier, even when the database aggregation returns 0.0 as a default.
3. WHEN Staff access the supplier performance report, THE System SHALL compute all metrics using database-level aggregation (Django ORM `annotate`/`aggregate`) rather than Python-level loops.
4. THE System SHALL restrict the supplier performance report view to Staff only; WHEN an unauthenticated user accesses the URL, THE System SHALL redirect to the login page; WHEN an authenticated non-staff user accesses the URL, THE System SHALL display a permission-denied page.

---

### Requirement 5: Customer Vehicle Registry

**User Story:** As a customer, I want to register and manage my own vehicles so that my service history is linked to my car rather than entered as free text each time.

#### Acceptance Criteria

1. THE System SHALL provide a `CustomerVehicle` model with the fields: `owner` (ForeignKey → User, CASCADE), `registration_number` (CharField, max 30, unique), `make` (CharField, max 100), `model` (CharField, max 100), `year` (PositiveIntegerField), `engine_number` (CharField, max 100, blank), `chassis_number` (CharField, max 100, blank), `color` (CharField, max 50, blank), `mileage` (PositiveIntegerField, null/blank), and `notes` (TextField, blank).
2. WHEN a Customer submits a valid CustomerVehicle creation form, THE System SHALL persist the record with `owner` set to the currently authenticated User and redirect to the customer's vehicle list.
3. WHEN a Customer submits a CustomerVehicle creation form with a `registration_number` that already exists in the database, THE System SHALL process the form through validation and return a validation error stating the registration number is already registered; for all other cases, THE System SHALL persist the record normally.
4. WHEN an authenticated Customer accesses the vehicle edit view for a CustomerVehicle they do not own, THE System SHALL return HTTP 403 Forbidden; WHEN Staff access the vehicle edit view for any CustomerVehicle, THE System SHALL allow access.
5. WHEN Staff access the vehicle list view, THE System SHALL display all CustomerVehicle records with owner username and registration number visible.
6. WHEN a Customer accesses their vehicle list, THE System SHALL display only CustomerVehicle records where `owner` equals the authenticated User.
7. THE System SHALL add a `customer_vehicle` ForeignKey field (→ CustomerVehicle, null=True, blank=True, on_delete=SET_NULL) to the existing `JobCard` model, keeping all existing free-text vehicle fields intact.
8. WHEN Staff create or update a JobCard, THE System SHALL allow optionally selecting a CustomerVehicle via a dropdown alongside the existing free-text fields.
9. WHEN a Customer accesses the vehicle service history view for one of their CustomerVehicles, THE System SHALL display all JobCard records where `customer_vehicle` equals that CustomerVehicle, ordered by `created_at` descending.
10. WHEN an unauthenticated user attempts to access any CustomerVehicle view, THE System SHALL redirect to the login page.

---

### Requirement 6: Stock Movement Log

**User Story:** As a staff manager, I want a complete audit trail for every stock quantity change so that I can trace any discrepancy back to its source.

#### Acceptance Criteria

1. THE System SHALL provide a `StockMovement` model with the fields: `spare_part` (ForeignKey → SparePart, PROTECT), `movement_type` (CharField, choices: `stock_in` / `stock_out` / `adjustment` / `sale` / `purchase_receipt`), `quantity` (PositiveIntegerField), `reference` (CharField, max 200, blank — e.g. PO number, JobCard ID), `notes` (TextField, blank), `performed_by` (ForeignKey → User, SET_NULL, null/blank), and `created_at` (DateTimeField, auto_now_add).
2. THE System SHALL treat StockMovement records as immutable; WHEN code attempts to update an existing StockMovement, THE System SHALL raise a validation error.
3. WHEN a StockReceipt is confirmed, THE System SHALL automatically create one StockMovement of type `purchase_receipt` for each ReceiptLineItem (covered in Requirement 3, criterion 7).
4. WHEN a CartItem of type `sparepart` is added to a completed Order (Order status changes to `PAID`), THE System SHALL automatically create one StockMovement of type `sale` and decrement `SparePart.stock_quantity` so that the new value equals the prior `stock_quantity` minus the CartItem quantity.
5. WHEN `SparePart.stock_quantity` would be decremented below zero by a sale, THE System SHALL raise an error and abort the stock decrement and StockMovement creation.
6. WHEN Staff record a manual stock adjustment via the Control Panel, THE System SHALL create a StockMovement of type `adjustment`, update `SparePart.stock_quantity` so the new value equals the prior `stock_quantity` plus the signed adjustment quantity provided, and record the performing Staff user; all three actions MUST succeed atomically or none SHALL be committed.
7. WHEN Staff access the stock movement log view, THE System SHALL display all StockMovement records with filters for: spare part (by name), movement type, date range (start date and end date); WHEN no filters are applied, THE System SHALL display all records without requiring any filter to be set.
8. WHEN Staff access the stock movement log view with no filters applied, THE System SHALL display all StockMovement records ordered by `created_at` descending, paginated at 50 records per page.
9. WHEN Staff access the stock movement summary view, THE System SHALL display one row per SparePart showing: current `stock_quantity`, net movement total (sum of all `quantity` values with `stock_out` and `sale` types treated as negative), and breakdown by movement type.
10. THE System SHALL restrict all StockMovement views to Staff only; WHEN a non-staff user accesses any StockMovement URL, THE System SHALL redirect to the login page.

---

### Requirement 7: Mechanic Status Field

**User Story:** As a staff dispatcher, I want to see each mechanic's availability status so that I can assign jobs only to available mechanics.

#### Acceptance Criteria

1. THE System SHALL add a `status` field to the existing `Mechanic` model with choices: `Available` / `Busy` / `Off-Duty` and a default of `Available`.
2. WHEN a Mechanic record is created without specifying `status`, THE System SHALL set `status` to `Available`.
3. WHEN Staff update a Mechanic's `status` in the Admin Panel or Control Panel and the update persists successfully to the database, THE System SHALL atomically reflect the new status in the mechanic list view; IF either the persistence or the list-view reflection fails, THE System SHALL roll back the entire update.
4. WHEN Staff view the mechanic list, THE System SHALL display each mechanic's current status with a visual indicator (e.g., Bootstrap badge) distinguishing Available, Busy, and Off-Duty.

---

### Requirement 8: Vehicle Catalogue Additional Fields

**User Story:** As a staff member, I want to record engine and chassis numbers on catalogue vehicles so that we can cross-reference vehicles for compliance and identity checks.

#### Acceptance Criteria

1. THE System SHALL add an `engine_number` field (CharField, max 100, blank=True) to the existing `Vehicle` model.
2. THE System SHALL add a `chassis_number` field (CharField, max 100, blank=True) to the existing `Vehicle` model.
3. WHEN an existing Vehicle record has no `engine_number` or `chassis_number`, THE System SHALL not raise any error (fields are optional).
4. WHEN Staff edit a Vehicle record in the Admin Panel, THE System SHALL display the `engine_number` and `chassis_number` fields for optional completion.

---

### Requirement 9: Database Migrations

**User Story:** As a developer, I want Django migrations generated for all model changes so that the database schema stays in sync with the models.

#### Acceptance Criteria

1. THE System SHALL include a Django migration file covering: new `Supplier`, `PurchaseOrder`, `POLineItem`, `StockReceipt`, `ReceiptLineItem`, `CustomerVehicle`, and `StockMovement` models.
2. THE System SHALL include a Django migration file (or the same migration) covering: the `status` field addition to `Mechanic`, the `engine_number` and `chassis_number` field additions to `Vehicle`, and the `customer_vehicle` FK addition to `JobCard`.
3. WHEN `python manage.py migrate` is run on a clean database, THE System SHALL complete without errors.
4. WHEN `python manage.py migrate` is run on a database that already has the prior schema applied, THE System SHALL apply only the new migrations and complete without errors.

---

### Requirement 10: Access Control and Authentication

**User Story:** As a system administrator, I want all new views to enforce role-based access so that customers cannot access staff-only data and unauthenticated users are redirected to login.

#### Acceptance Criteria

1. THE System SHALL require authentication for all new views; WHEN an unauthenticated user requests any new URL, THE System SHALL redirect to the configured `LOGIN_URL`.
2. THE System SHALL restrict supplier management views, purchase order views, stock receipt views, supplier performance report, stock movement log, and stock movement summary to Staff (`is_staff=True`); WHEN an unauthenticated user accesses these URLs, THE System SHALL redirect to the configured `LOGIN_URL`; WHEN an authenticated non-staff Customer accesses these URLs, THE System SHALL return HTTP 403 Forbidden with a permission-denied page.
3. THE System SHALL restrict the customer vehicle edit and delete views to the owning Customer or Staff; WHEN any other authenticated user accesses these views, THE System SHALL return HTTP 403 Forbidden.
4. WHEN Staff access any new Control Panel view, THE System SHALL verify `user.is_staff` before rendering the response, not after.
