"""
AutoWorld PDF Report Generator
Uses ReportLab to generate downloadable PDF reports:
  - Bookings Report
  - Revenue Report
  - Inventory Report
  - Job Cards Report
"""

from io import BytesIO
from datetime import datetime, timedelta
from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


# ─── Colour Palette ───────────────────────────────────────────────────────────
DARK_PURPLE = colors.HexColor('#1e1153')
GREEN       = colors.HexColor('#11ba1f')
LIGHT_GREY  = colors.HexColor('#f4f3ff')
MID_GREY    = colors.HexColor('#888888')
WHITE       = colors.white


def _base_doc(buffer, title):
    return SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title=title
    )


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle('ReportTitle',
        fontSize=20, textColor=DARK_PURPLE, spaceAfter=4,
        fontName='Helvetica-Bold', alignment=TA_LEFT))
    s.add(ParagraphStyle('ReportSubtitle',
        fontSize=10, textColor=MID_GREY, spaceAfter=12,
        fontName='Helvetica', alignment=TA_LEFT))
    s.add(ParagraphStyle('SectionHead',
        fontSize=12, textColor=DARK_PURPLE, spaceBefore=14, spaceAfter=6,
        fontName='Helvetica-Bold'))
    s.add(ParagraphStyle('SmallText',
        fontSize=8, textColor=MID_GREY))
    return s


def _header_table(title, subtitle, generated_by='AutoWorld System'):
    now = timezone.now().strftime('%B %d, %Y %H:%M')
    data = [[
        Paragraph(f'<font color="#1e1153"><b>AutoWorld</b></font>', getSampleStyleSheet()['Normal']),
        Paragraph(f'<font color="#888">{generated_by} · {now}</font>',
                  ParagraphStyle('r', fontSize=8, alignment=TA_RIGHT))
    ]]
    t = Table(data, colWidths=['60%', '40%'])
    t.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    return t


def _table_style(header_bg=DARK_PURPLE):
    return TableStyle([
        ('BACKGROUND',   (0, 0), (-1, 0), header_bg),
        ('TEXTCOLOR',    (0, 0), (-1, 0), WHITE),
        ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, 0), 9),
        ('ALIGN',        (0, 0), (-1, 0), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_GREY]),
        ('FONTSIZE',     (0, 1), (-1, -1), 8),
        ('FONTNAME',     (0, 1), (-1, -1), 'Helvetica'),
        ('GRID',         (0, 0), (-1, -1), 0.3, colors.HexColor('#e0e0e0')),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',   (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
        ('LEFTPADDING',  (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ])


# ─── Bookings Report ──────────────────────────────────────────────────────────

def generate_bookings_report(days=30):
    from ecommerceapp.models import Booking
    buffer = BytesIO()
    doc = _base_doc(buffer, 'Bookings Report')
    s = _styles()
    story = []

    cutoff = timezone.now() - timedelta(days=days)
    bookings = Booking.objects.filter(
        created_at__gte=cutoff
    ).select_related('user', 'mechanic').order_by('-booking_date')

    story.append(_header_table('Bookings Report', ''))
    story.append(HRFlowable(width='100%', thickness=2, color=DARK_PURPLE, spaceAfter=12))
    story.append(Paragraph('Bookings Report', s['ReportTitle']))
    story.append(Paragraph(f'Last {days} days · {bookings.count()} bookings', s['ReportSubtitle']))

    # Summary stats
    pending   = bookings.filter(status='Pending').count()
    approved  = bookings.filter(status='Approved').count()
    completed = bookings.filter(status='Completed').count()
    cancelled = bookings.filter(status='Cancelled').count()
    paid      = bookings.filter(is_paid=True).count()

    summary_data = [
        ['Total', 'Pending', 'Approved', 'Completed', 'Cancelled', 'Paid'],
        [str(bookings.count()), str(pending), str(approved),
         str(completed), str(cancelled), str(paid)],
    ]
    st = Table(summary_data, colWidths=[2.5*cm]*6)
    st.setStyle(_table_style(GREEN))
    story.append(st)
    story.append(Spacer(1, 0.4*cm))

    # Bookings table
    story.append(Paragraph('Booking Details', s['SectionHead']))
    headers = ['#', 'Customer', 'Mechanic', 'Date', 'Time', 'Service', 'Status', 'Paid']
    rows = [headers]
    for b in bookings[:100]:  # cap at 100 rows
        rows.append([
            str(b.id),
            b.user.username[:15],
            b.mechanic.name[:15],
            str(b.booking_date),
            str(b.time)[:5],
            b.service_type[:12],
            b.status,
            '✓' if b.is_paid else '✗',
        ])

    col_w = [1*cm, 2.5*cm, 2.5*cm, 2.2*cm, 1.5*cm, 2.2*cm, 2*cm, 1.2*cm]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(_table_style())
    story.append(t)

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(
        f'Generated by AutoWorld · {timezone.now().strftime("%B %d, %Y")}',
        s['SmallText']
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer


# ─── Revenue Report ───────────────────────────────────────────────────────────

def generate_revenue_report(days=30):
    from ecommerceapp.models import Order, Booking
    buffer = BytesIO()
    doc = _base_doc(buffer, 'Revenue Report')
    s = _styles()
    story = []

    cutoff = timezone.now() - timedelta(days=days)
    orders = Order.objects.filter(
        created_at__gte=cutoff, is_paid=True
    ).select_related('user').order_by('-created_at')

    story.append(_header_table('Revenue Report', ''))
    story.append(HRFlowable(width='100%', thickness=2, color=GREEN, spaceAfter=12))
    story.append(Paragraph('Revenue Report', s['ReportTitle']))
    story.append(Paragraph(f'Last {days} days · {orders.count()} paid orders', s['ReportSubtitle']))

    total_revenue = sum(o.total_amount() for o in orders)
    paid_bookings = Booking.objects.filter(
        is_paid=True, created_at__gte=cutoff
    ).count()

    summary_data = [
        ['Paid Orders', 'Paid Bookings', 'Total Revenue (KES)'],
        [str(orders.count()), str(paid_bookings), f'KES {total_revenue:,.0f}'],
    ]
    st = Table(summary_data, colWidths=[5*cm, 5*cm, 7*cm])
    st.setStyle(_table_style(GREEN))
    story.append(st)
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph('Order Details', s['SectionHead']))
    headers = ['Order #', 'Customer', 'Date', 'Status', 'Amount (KES)']
    rows = [headers]
    for o in orders[:100]:
        rows.append([
            f'#{o.id}',
            o.user.username[:20],
            o.created_at.strftime('%Y-%m-%d') if o.created_at else '—',
            o.status,
            f'{o.total_amount():,.0f}',
        ])

    t = Table(rows, colWidths=[2*cm, 4*cm, 3*cm, 3*cm, 4*cm], repeatRows=1)
    t.setStyle(_table_style())
    story.append(t)

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(
        f'Generated by AutoWorld · {timezone.now().strftime("%B %d, %Y")}',
        s['SmallText']
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer


# ─── Inventory Report ─────────────────────────────────────────────────────────

def generate_inventory_report():
    from ecommerceapp.models import SparePart, Vehicle
    buffer = BytesIO()
    doc = _base_doc(buffer, 'Inventory Report')
    s = _styles()
    story = []

    parts = SparePart.objects.all().order_by('stock_quantity')
    vehicles = Vehicle.objects.all().order_by('brand')

    story.append(_header_table('Inventory Report', ''))
    story.append(HRFlowable(width='100%', thickness=2, color=DARK_PURPLE, spaceAfter=12))
    story.append(Paragraph('Inventory Report', s['ReportTitle']))
    story.append(Paragraph(
        f'{parts.count()} spare parts · {vehicles.count()} vehicles · '
        f'Generated {timezone.now().strftime("%B %d, %Y")}',
        s['ReportSubtitle']
    ))

    # Spare Parts
    story.append(Paragraph('Spare Parts Stock', s['SectionHead']))
    headers = ['Part Name', 'Compatible', 'Price (KES)', 'Stock', 'Reorder At', 'Status']
    rows = [headers]
    for p in parts:
        status_map = {
            'out_of_stock': 'OUT OF STOCK',
            'low_stock': 'LOW',
            'medium_stock': 'MEDIUM',
            'in_stock': 'OK',
        }
        rows.append([
            p.name[:25],
            p.compatible_vehicle[:20],
            f'{p.price:,.0f}',
            str(p.stock_quantity),
            str(p.reorder_point),
            status_map.get(p.stock_status, p.stock_status),
        ])

    t = Table(rows, colWidths=[4.5*cm, 3.5*cm, 2.5*cm, 1.5*cm, 2*cm, 2.5*cm], repeatRows=1)
    ts = _table_style()
    # Colour out-of-stock rows red
    for i, p in enumerate(parts, start=1):
        if p.stock_quantity == 0:
            ts.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fce4ec'))
        elif p.needs_reorder:
            ts.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fff8e1'))
    t.setStyle(ts)
    story.append(t)

    # Vehicles
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph('Vehicle Catalogue', s['SectionHead']))
    v_headers = ['Brand', 'Model', 'Year', 'Price (KES)']
    v_rows = [v_headers]
    for v in vehicles[:50]:
        v_rows.append([v.brand, v.model, str(v.year), f'{v.price:,.0f}'])

    vt = Table(v_rows, colWidths=[4*cm, 4*cm, 2.5*cm, 4*cm], repeatRows=1)
    vt.setStyle(_table_style())
    story.append(vt)

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(
        f'Generated by AutoWorld · {timezone.now().strftime("%B %d, %Y")}',
        s['SmallText']
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer


# ─── Job Cards Report ─────────────────────────────────────────────────────────

def generate_job_cards_report(days=30):
    from ecommerceapp.models import JobCard
    buffer = BytesIO()
    doc = _base_doc(buffer, 'Job Cards Report')
    s = _styles()
    story = []

    cutoff = timezone.now() - timedelta(days=days)
    job_cards = JobCard.objects.filter(
        created_at__gte=cutoff
    ).select_related('mechanic', 'customer').order_by('-created_at')

    story.append(_header_table('Job Cards Report', ''))
    story.append(HRFlowable(width='100%', thickness=2, color=DARK_PURPLE, spaceAfter=12))
    story.append(Paragraph('Job Cards Report', s['ReportTitle']))
    story.append(Paragraph(f'Last {days} days · {job_cards.count()} job cards', s['ReportSubtitle']))

    completed = job_cards.filter(status='Completed').count()
    in_progress = job_cards.filter(status='In Progress').count()
    total_revenue = sum(
        float(jc.total_cost) for jc in job_cards.filter(status='Completed')
    )

    summary_data = [
        ['Total', 'Completed', 'In Progress', 'Revenue (KES)'],
        [str(job_cards.count()), str(completed), str(in_progress), f'{total_revenue:,.0f}'],
    ]
    st = Table(summary_data, colWidths=[3.5*cm]*4)
    st.setStyle(_table_style(DARK_PURPLE))
    story.append(st)
    story.append(Spacer(1, 0.4*cm))

    headers = ['JC #', 'Customer', 'Mechanic', 'Vehicle', 'Status', 'Priority', 'Labour', 'Parts', 'Total']
    rows = [headers]
    for jc in job_cards[:100]:
        rows.append([
            f'JC-{jc.id:04d}',
            jc.customer.username[:12],
            jc.mechanic.name[:12] if jc.mechanic else '—',
            f'{jc.vehicle_make} {jc.vehicle_model}'[:15],
            jc.status[:10],
            jc.priority,
            f'{jc.labour_cost:,.0f}',
            f'{jc.parts_cost:,.0f}',
            f'{jc.total_cost:,.0f}',
        ])

    col_w = [1.5*cm, 2.2*cm, 2.2*cm, 2.5*cm, 2*cm, 1.5*cm, 1.8*cm, 1.5*cm, 1.8*cm]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(_table_style())
    story.append(t)

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(
        f'Generated by AutoWorld · {timezone.now().strftime("%B %d, %Y")}',
        s['SmallText']
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer
