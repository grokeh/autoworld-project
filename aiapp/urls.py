from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.chat_api, name='ai_chat'),
    path('insights/', views.admin_insights_api, name='ai_insights'),
    path('forecast/', views.forecast_dashboard, name='forecast_dashboard'),
    path('forecast/data/', views.forecast_api, name='forecast_api'),
    path('inventory/', views.inventory_dashboard, name='inventory_dashboard'),
    path('inventory/data/', views.inventory_api, name='inventory_api'),
    path('inventory/update-stock/', views.update_stock, name='update_stock'),
    path('reports/', views.reports_page, name='reports_page'),
    path('reports/download/<str:report_type>/', views.download_report, name='download_report'),
    path('alerts/run/', views.run_alerts, name='run_alerts'),
    path('rfm/', views.rfm_dashboard, name='rfm_dashboard'),
    path('rfm/data/', views.rfm_api, name='rfm_api'),
    path('evaluation/', views.evaluation_dashboard, name='evaluation_dashboard'),
    path('evaluation/data/', views.evaluation_api, name='evaluation_api'),
    path('maintenance/', views.maintenance_dashboard, name='maintenance_dashboard'),
    path('maintenance/data/', views.maintenance_api, name='maintenance_api'),
    path('maintenance/send/', views.send_maintenance_alerts, name='send_maintenance_alerts'),
    path('docs/', views.api_docs, name='api_docs'),
    path('vehicle-analysis/', views.vehicle_analysis, name='vehicle_analysis'),
    path('vehicle-analysis/analyze/', views.analyze_vehicle, name='analyze_vehicle'),
]
