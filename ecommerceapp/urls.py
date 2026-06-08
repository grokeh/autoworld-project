
from django.urls import path
from . import views
from .views import (
    dashboard_view, notifications_view,
    manage_inventory, booking_insights,
    cancel_booking, reschedule_booking,
    delete_vehicle, delete_spare,
    job_card_list, job_card_create, job_card_detail, job_card_update, job_card_delete,
    employee_list, attendance_checkin, attendance_checkout,
    attendance_history, my_shifts, attendance_today,
)

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('vehicles/', views.Vehicle_list, name='vehicle_list'),
    path('spareparts/', views.spareparts_list, name='spareparts_list'),
    path('mechanics/', views.mechanics_list, name='mechanics_list'),
    path('get-started/', views.get_started, name='get_started'),
    path('book-mechanic/<int:mechanic_id>/', views.book_mechanic, name='book_mechanic'),
    path('add-to-cart/<str:product_type>/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.view_cart, name='view_cart'),
    path('recommend/', views.recommend_anything, name='recommendation'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('vehicles/<int:vehicle_id>/', views.vehicle_detail, name='vehicle_detail'),

    # Booking management
    path('booking/cancel/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('booking/raincheck/<int:booking_id>/', views.request_raincheck, name='request_raincheck'),

    # 🔔 Notifications
    path('notifications/', notifications_view, name='notifications'),
    path('notifications/mark-all-read/', views.mark_all_as_read, name='mark_all_as_read'),
    path('api/notifications/', views.get_notifications, name='get_notifications'),
    path('notifications/read/<int:pk>/', views.mark_notification_as_read, name='mark_notification_as_read'),
    path('notifications/delete/<int:pk>/', views.delete_notification, name='delete_notification'),
    

    # ➕ Services Management
    path('control-panel/service/add/', views.add_service, name='add_service'),
    path('control-panel/service/edit/<int:pk>/', views.edit_service, name='edit_service'),
    path('control-panel/service/delete/<int:pk>/', views.delete_service, name='delete_service'),

    # 🎁 Offers Management
    path('control-panel/offer/add/', views.add_offer, name='add_offer'),
    path('control-panel/offer/edit/<int:pk>/', views.edit_offer, name='edit_offer'),
    path('control-panel/offer/delete/<int:pk>/', views.delete_offer, name='delete_offer'),
    path('control-panel/offer/list/', views.offer_list, name='offer_list'),  

    # 📦 Inventory & Booking Management (Admin)
    path('control-panel/inventory/', manage_inventory, name='manage_inventory'),
    path('control-panel/booking-insights/', booking_insights, name='booking_insights'),
    path('control-panel/booking/cancel/<int:pk>/', cancel_booking, name='cancel_booking'),
    path('control-panel/booking/reschedule/<int:pk>/', reschedule_booking, name='reschedule_booking'),
    path('control-panel/vehicle/delete/<int:pk>/', delete_vehicle, name='delete_vehicle'),
    path('control-panel/spare/delete/<int:pk>/', delete_spare, name='delete_spare'),

    path('redirect-after-login/', views.role_based_redirect, name='role_redirect'),
    path('mechanic/dashboard/', views.mechanic_dashboard, name='mechanic_dashboard'),
    path('employee/dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('customer/dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('customer/booking-history/', views.customer_booking_history, name='customer_booking_history'),
    path('customer/booking-details/<int:booking_id>/', views.customer_booking_details, name='customer_booking_details'),
    path('customer/booking/cancel/<int:booking_id>/', views.customer_cancel_booking, name='customer_cancel_booking'),
    path('customer/booking/reschedule/<int:booking_id>/', views.customer_reschedule_booking, name='customer_reschedule_booking'),
    path('dashboard/', views.mechanic_dashboard, name='mechanic_dashboard'),

    # ─── Ratings ──────────────────────────────────────────────────────────────
    path('booking/<int:booking_id>/rate/', views.rate_mechanic, name='rate_mechanic'),
    path('control-panel/mechanic-performance/', views.mechanic_performance, name='mechanic_performance'),

    # ─── Job Cards ────────────────────────────────────────────────────────────
    path('job-cards/',                    job_card_list,   name='job_card_list'),
    path('job-cards/create/',             job_card_create, name='job_card_create'),
    path('job-cards/<int:pk>/',           job_card_detail, name='job_card_detail'),
    path('job-cards/<int:pk>/edit/',      job_card_update, name='job_card_update'),
    path('job-cards/<int:pk>/delete/',    job_card_delete, name='job_card_delete'),

    # ─── Employee Management ──────────────────────────────────────────────────
    path('employees/',                    employee_list,        name='employee_list'),
    path('employees/checkin/',            attendance_checkin,   name='attendance_checkin'),
    path('employees/checkout/',           attendance_checkout,  name='attendance_checkout'),
    path('employees/attendance/',         attendance_history,   name='attendance_history'),
    path('employees/shifts/',             my_shifts,            name='my_shifts'),
    path('control-panel/attendance/',     attendance_today,     name='attendance_today'),
]


