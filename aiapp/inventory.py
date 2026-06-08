"""
AutoWorld Inventory Optimization Engine
Implements:
  - ABC Analysis (classify parts by demand value)
  - EOQ (Economic Order Quantity)
  - Reorder point recommendations
  - Stock health scoring
  - Low stock alerts
"""

import math
from django.utils import timezone
from datetime import timedelta


# ─── ABC Analysis ─────────────────────────────────────────────────────────────

def abc_analysis():
    """
    Classify spare parts into A (high value), B (medium), C (low) categories
    based on demand × price (annual usage value).
    Returns: list of parts with ABC classification
    """
    from ecommerceapp.models import SparePart, CartItem

    parts = SparePart.objects.all()
    if not parts.exists():
        return []

    # Calculate demand from cart history (last 90 days)
    cutoff = timezone.now() - timedelta(days=90)
    results = []

    for part in parts:
        demand = CartItem.objects.filter(
            spare_part=part,
            added_on__gte=cutoff
        ).values_list('quantity', flat=True)
        total_demand = sum(demand) if demand else 0
        annual_demand = total_demand * 4  # extrapolate to annual
        usage_value = float(part.price) * annual_demand

        results.append({
            'id': part.id,
            'name': part.name,
            'compatible': part.compatible_vehicle,
            'price': float(part.price),
            'stock': part.stock_quantity,
            'reorder_point': part.reorder_point,
            'reorder_qty': part.reorder_quantity,
            'annual_demand': annual_demand,
            'usage_value': round(usage_value, 2),
            'status': part.stock_status,
            'needs_reorder': part.needs_reorder,
        })

    # Sort by usage value descending
    results.sort(key=lambda x: x['usage_value'], reverse=True)

    if not results:
        return results

    total_value = sum(r['usage_value'] for r in results)
    cumulative = 0

    for r in results:
        cumulative += r['usage_value']
        pct = (cumulative / total_value * 100) if total_value > 0 else 0
        if pct <= 70:
            r['abc_class'] = 'A'
            r['abc_label'] = 'High Value'
            r['abc_color'] = '#dc3545'
        elif pct <= 90:
            r['abc_class'] = 'B'
            r['abc_label'] = 'Medium Value'
            r['abc_color'] = '#fd7e14'
        else:
            r['abc_class'] = 'C'
            r['abc_label'] = 'Low Value'
            r['abc_color'] = '#6c757d'

    return results


# ─── EOQ Calculation ──────────────────────────────────────────────────────────

def calculate_eoq(annual_demand, ordering_cost=500, holding_cost_pct=0.25, unit_price=100):
    """
    Economic Order Quantity formula:
    EOQ = sqrt(2 * D * S / H)
    D = annual demand, S = ordering cost, H = holding cost per unit per year
    """
    if annual_demand <= 0:
        return 0
    H = holding_cost_pct * unit_price
    if H <= 0:
        return annual_demand
    eoq = math.sqrt((2 * annual_demand * ordering_cost) / H)
    return max(1, int(round(eoq)))


# ─── Stock Health Score ────────────────────────────────────────────────────────

def get_inventory_health():
    """
    Calculate overall inventory health score (0-100).
    Returns: {'score': int, 'grade': str, 'summary': str, 'alerts': list}
    """
    from ecommerceapp.models import SparePart

    parts = SparePart.objects.all()
    if not parts.exists():
        return {
            'score': 0, 'grade': 'N/A',
            'summary': 'No spare parts in inventory.',
            'alerts': [], 'stats': {}
        }

    total = parts.count()
    out_of_stock = parts.filter(stock_quantity=0).count()
    low_stock = parts.filter(
        stock_quantity__gt=0,
        stock_quantity__lte=models_reorder_point()
    ).count()
    healthy = total - out_of_stock - low_stock

    # Score: penalise out-of-stock heavily, low stock moderately
    score = 100
    if total > 0:
        score -= (out_of_stock / total) * 60
        score -= (low_stock / total) * 30
    score = max(0, int(score))

    grade = 'A' if score >= 85 else ('B' if score >= 70 else ('C' if score >= 50 else 'D'))

    alerts = []
    for part in parts.filter(stock_quantity=0):
        alerts.append({
            'type': 'out_of_stock',
            'severity': 'critical',
            'message': f'🚨 {part.name} is OUT OF STOCK',
            'part_id': part.id,
            'part_name': part.name,
        })
    for part in parts.filter(stock_quantity__gt=0).order_by('stock_quantity'):
        if part.needs_reorder:
            alerts.append({
                'type': 'low_stock',
                'severity': 'warning',
                'message': f'⚠️ {part.name} is LOW ({part.stock_quantity} left, reorder at {part.reorder_point})',
                'part_id': part.id,
                'part_name': part.name,
                'stock': part.stock_quantity,
                'reorder_qty': part.reorder_quantity,
            })

    return {
        'score': score,
        'grade': grade,
        'summary': f'{healthy} healthy, {low_stock} low stock, {out_of_stock} out of stock',
        'alerts': alerts,
        'stats': {
            'total': total,
            'healthy': healthy,
            'low_stock': low_stock,
            'out_of_stock': out_of_stock,
        }
    }


def models_reorder_point():
    """Helper — returns a Q object-compatible expression."""
    from django.db.models import F
    return F('reorder_point')


# ─── Reorder Recommendations ──────────────────────────────────────────────────

def get_reorder_recommendations():
    """
    Return parts that need reordering with EOQ-based quantities.
    """
    from ecommerceapp.models import SparePart, CartItem

    parts = SparePart.objects.filter(stock_quantity__lte=models_reorder_point())
    cutoff = timezone.now() - timedelta(days=90)
    recommendations = []

    for part in parts:
        demand_qs = CartItem.objects.filter(
            spare_part=part, added_on__gte=cutoff
        ).values_list('quantity', flat=True)
        total_demand = sum(demand_qs) if demand_qs else 1
        annual_demand = total_demand * 4

        eoq = calculate_eoq(
            annual_demand=annual_demand,
            unit_price=float(part.price)
        )
        suggested_qty = max(eoq, part.reorder_quantity)

        recommendations.append({
            'id': part.id,
            'name': part.name,
            'compatible': part.compatible_vehicle,
            'current_stock': part.stock_quantity,
            'reorder_point': part.reorder_point,
            'suggested_order_qty': suggested_qty,
            'eoq': eoq,
            'unit_price': float(part.price),
            'estimated_cost': round(suggested_qty * float(part.price), 2),
            'status': part.stock_status,
            'urgency': 'critical' if part.stock_quantity == 0 else 'warning',
        })

    recommendations.sort(key=lambda x: (x['urgency'] == 'warning', x['current_stock']))
    return recommendations


# ─── Full Inventory Report ────────────────────────────────────────────────────

def get_full_inventory_report():
    """Combine all inventory analysis into one response."""
    health = get_inventory_health()
    abc = abc_analysis()
    reorder = get_reorder_recommendations()

    return {
        'health': health,
        'abc_analysis': abc,
        'reorder_recommendations': reorder,
        'abc_summary': {
            'A': len([x for x in abc if x.get('abc_class') == 'A']),
            'B': len([x for x in abc if x.get('abc_class') == 'B']),
            'C': len([x for x in abc if x.get('abc_class') == 'C']),
        }
    }
