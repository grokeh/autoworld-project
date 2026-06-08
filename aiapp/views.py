import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.shortcuts import redirect
from .services import chat_with_ai, generate_admin_insights
from .forecasting import get_full_forecast
from .inventory import get_full_inventory_report, get_reorder_recommendations


@login_required
@require_POST
@csrf_exempt
def chat_api(request):
    """Customer chatbot API endpoint."""
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        history = data.get('history', [])

        if not user_message:
            return JsonResponse({'error': 'Empty message'}, status=400)
        if len(user_message) > 500:
            return JsonResponse({'error': 'Message too long'}, status=400)

        response = chat_with_ai(history, user_message)
        return JsonResponse({'response': response})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
def admin_insights_api(request):
    """Admin AI insights endpoint."""
    insights = generate_admin_insights()
    return JsonResponse(insights)


@staff_member_required
def forecast_api(request):
    """Return full ML forecast as JSON."""
    data = get_full_forecast()
    return JsonResponse(data)


@staff_member_required
def forecast_dashboard(request):
    """Render the AI forecasting dashboard page."""
    from .forecasting import get_model_meta
    model_meta = get_model_meta()
    return render(request, 'aiapp/forecast_dashboard.html', {'model_meta': model_meta})


@staff_member_required
def inventory_dashboard(request):
    """Render the inventory optimization dashboard."""
    return render(request, 'aiapp/inventory_dashboard.html')


@staff_member_required
def inventory_api(request):
    """Return full inventory report as JSON."""
    from .inventory import get_full_inventory_report
    data = get_full_inventory_report()
    return JsonResponse(data)


@staff_member_required
@require_POST
def update_stock(request):
    """Update stock quantity for a spare part."""
    from ecommerceapp.models import SparePart
    try:
        data = json.loads(request.body)
        part_id = data.get('part_id')
        new_qty = int(data.get('quantity', 0))
        reorder_point = data.get('reorder_point')
        reorder_qty = data.get('reorder_quantity')

        part = get_object_or_404(SparePart, id=part_id)
        part.stock_quantity = max(0, new_qty)
        if reorder_point is not None:
            part.reorder_point = max(0, int(reorder_point))
        if reorder_qty is not None:
            part.reorder_quantity = max(1, int(reorder_qty))
        part.save()

        # Create notification if stock is low after update
        if part.needs_reorder:
            from ecommerceapp.models import Notification
            from django.contrib.auth.models import User
            admins = User.objects.filter(is_superuser=True)
            for admin in admins:
                Notification.objects.get_or_create(
                    user=admin,
                    message=f"⚠️ Low stock alert: {part.name} has only {part.stock_quantity} units left.",
                    is_read=False,
                )

        return JsonResponse({
            'success': True,
            'status': part.stock_status,
            'needs_reorder': part.needs_reorder,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ─── PDF Report Views ─────────────────────────────────────────────────────────

from django.http import HttpResponse


@staff_member_required
def download_report(request, report_type):
    """Generate and download a PDF report."""
    from .reports import (
        generate_bookings_report, generate_revenue_report,
        generate_inventory_report, generate_job_cards_report
    )

    days = int(request.GET.get('days', 30))

    generators = {
        'bookings':  (generate_bookings_report,  f'autoworld_bookings_{days}days.pdf',  lambda: generate_bookings_report(days)),
        'revenue':   (generate_revenue_report,   f'autoworld_revenue_{days}days.pdf',   lambda: generate_revenue_report(days)),
        'inventory': (generate_inventory_report, 'autoworld_inventory.pdf',             generate_inventory_report),
        'job_cards': (generate_job_cards_report, f'autoworld_job_cards_{days}days.pdf', lambda: generate_job_cards_report(days)),
    }

    if report_type not in generators:
        return HttpResponse('Invalid report type', status=400)

    _, filename, generator = generators[report_type]

    try:
        buffer = generator()
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        return HttpResponse(f'Report generation failed: {str(e)}', status=500)


@staff_member_required
def reports_page(request):
    """Render the reports download page."""
    return render(request, 'aiapp/reports.html')


# ─── Automated Alerts Trigger ─────────────────────────────────────────────────

@staff_member_required
def run_alerts(request):
    """Manually trigger all automated alerts from the dashboard."""
    from django.core.management import call_command
    from io import StringIO
    out = StringIO()
    try:
        call_command('send_alerts', stdout=out)
        output = out.getvalue()
        lines = [l for l in output.strip().split('\n') if l.strip()]
        return JsonResponse({'success': True, 'output': lines})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ─── RFM Customer Segmentation ────────────────────────────────────────────────

@staff_member_required
def rfm_dashboard(request):
    return render(request, 'aiapp/rfm_dashboard.html')


@staff_member_required
def rfm_api(request):
    from .rfm import get_rfm_data, get_rfm_summary
    data = get_rfm_data()
    summary = get_rfm_summary(data)
    segment_filter = request.GET.get('segment', '')
    if segment_filter:
        data = [d for d in data if d['segment'] == segment_filter]
    return JsonResponse({'customers': data, 'summary': summary})


# ─── System Evaluation Metrics ────────────────────────────────────────────────

@staff_member_required
def evaluation_dashboard(request):
    return render(request, 'aiapp/evaluation_dashboard.html')


@staff_member_required
def evaluation_api(request):
    from .evaluation import get_evaluation_metrics
    data = get_evaluation_metrics()
    return JsonResponse(data)


# ─── Predictive Maintenance ───────────────────────────────────────────────────

@staff_member_required
def maintenance_dashboard(request):
    return render(request, 'aiapp/maintenance_dashboard.html')


@staff_member_required
def maintenance_api(request):
    from .maintenance import get_maintenance_predictions
    data = get_maintenance_predictions()
    return JsonResponse({'predictions': data, 'total': len(data)})


@staff_member_required
def send_maintenance_alerts(request):
    from .maintenance import send_maintenance_notifications
    count = send_maintenance_notifications()
    return JsonResponse({'success': True, 'sent': count})


# ─── API Documentation ────────────────────────────────────────────────────────

def api_docs(request):
    """Public API documentation page."""
    return render(request, 'aiapp/api_docs.html')


# ─── Vehicle Image Analysis ───────────────────────────────────────────────────

@login_required
def vehicle_analysis(request):
    """Page for customers to upload vehicle images for AI diagnosis."""
    return render(request, 'aiapp/vehicle_analysis.html')


@login_required
@require_POST
def analyze_vehicle(request):
    """Process uploaded vehicle image and return AI diagnosis."""
    from .services import analyze_vehicle_image

    image = request.FILES.get('image')
    if not image:
        return JsonResponse({'error': 'No image uploaded.'}, status=400)

    # Validate file type
    allowed = ['image/jpeg', 'image/png', 'image/webp', 'image/jpg']
    if image.content_type not in allowed:
        return JsonResponse({'error': 'Please upload a JPEG, PNG, or WebP image.'}, status=400)

    # Limit size to 5MB
    if image.size > 5 * 1024 * 1024:
        return JsonResponse({'error': 'Image too large. Maximum size is 5MB.'}, status=400)

    result = analyze_vehicle_image(image)
    return JsonResponse(result)
