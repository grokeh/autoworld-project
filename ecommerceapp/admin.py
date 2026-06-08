from django.contrib import admin
from .models import Vehicle, SparePart, Mechanic, Booking, CartItem, Order, OrderItem, JobCard



@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('brand', 'model', 'year', 'price')
    search_fields = ('brand', 'model')
    list_filter = ('year',)
    readonly_fields = ('description',)  # Optional: make description read-only in admin form

    def save_model(self, request, obj, form, change):
        # Auto-fill the description if it's blank
        if not obj.description:
            obj.description = (
                f"{obj.brand} {obj.model} ({obj.year}) - "
                f"Priced at {obj.price} Dollar. A reliable vehicle from {obj.brand} "
                f"with great performance and specifications."
            )
        super().save_model(request, obj, form, change)

@admin.register(SparePart)
class SparePartAdmin(admin.ModelAdmin):
    list_display = ('name', 'compatible_vehicle', 'price')
    search_fields = ('name', 'compatible_vehicle')
    list_filter = ('compatible_vehicle',)
    
    def short_description(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    short_description.short_description = 'Description'


@admin.register(Mechanic)
class MechanicAdmin(admin.ModelAdmin):
    list_display = ('name', 'specialization', 'location', 'phone')
    search_fields = ('name', 'specialization', 'location')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('user', 'mechanic', 'booking_date', 'time')
    search_fields = ('user__username', 'mechanic__name')
    list_filter = ('booking_date', 'mechanic')


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'product_type', 'get_product_name', 'quantity', 'get_unit_price')
    search_fields = ('user__username', 'vehicle__brand', 'spare_part__name')
    list_filter = ('product_type',)

    def get_product_name(self, obj):
        return obj.get_product_name()
    get_product_name.short_description = 'Product Name'

    def get_unit_price(self, obj):
        return obj.get_unit_price()
    get_unit_price.short_description = 'Unit Price'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('cart_item', 'total_price')

    def total_price(self, obj):
        return obj.total_price()
    total_price.short_description = 'Total Price'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at', 'is_paid', 'total_amount')
    list_filter = ('is_paid', 'created_at')
    search_fields = ('user__username',)
    inlines = [OrderItemInline]

    def total_amount(self, obj):
        return obj.total_amount()
    total_amount.short_description = 'Order Total'
from .models import HomePageContent

@admin.register(HomePageContent)
class HomePageContentAdmin(admin.ModelAdmin):
    list_display = ['headline', 'is_active']


@admin.register(JobCard)
class JobCardAdmin(admin.ModelAdmin):
    list_display  = ('__str__', 'customer', 'mechanic', 'status', 'priority', 'created_at', 'total_cost')
    list_filter   = ('status', 'priority', 'mechanic')
    search_fields = ('title', 'customer__username', 'vehicle_make', 'vehicle_model', 'plate_number')
    readonly_fields = ('created_at', 'updated_at', 'completed_at', 'total_cost')
