from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .models import Vehicle, SparePart, Mechanic, Booking , Service, Offer
from .forms import BookingForm  
from django.db.models import Q
from django.utils import timezone
from django.conf import settings



from django.utils import timezone
from django.shortcuts import render
from ecommerceapp.models import Service, Offer, HomePageContent  

def home(request):
    current_time = timezone.now()

    # ✨ Fetch homepage content (admin-controlled)
    home_content = HomePageContent.objects.filter(is_active=True).first()

    # 🌿 Fetch the latest 6 active services
    services = Service.objects.filter(is_active=True).order_by('-created_at')[:6]

    # 🎁 Fetch the latest 4 valid offers
    offers = Offer.objects.filter(
        is_visible=True,
        start_date__lte=current_time,
        end_date__gte=current_time
    ).order_by('-start_date')[:4]

    return render(request, 'home.html', {
        'home_content': home_content,  # 👈 Pass to template
        'services': services,
        'offers': offers,
    })



# ✅ About page
def about(request):
    return render(request, 'ecommerceapp/about.html')

# ✅ Login
def login_view(request):
    template = 'ecommerceapp/login.html'
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('home')
        else:
            return render(request, template, {'error': 'Invalid credentials'})
    return render(request, template)

# ✅ Logout
def logout_view(request):
    logout(request)
    return redirect('login')

# ✅ Register
def register_view(request):
    template = 'ecommerceapp/register.html'
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, template, {'form': form})

# ✅ Get Started page
def get_started(request):
    vehicles = Vehicle.objects.all()
    return render(request, 'ecommerceapp/get_started.html', {'vehicles': vehicles})

# ✅ Vehicle List with Search + Filter
def Vehicle_list(request):
    vehicles = Vehicle.objects.all()
    query = request.GET.get('q')
    if query:
        vehicles = vehicles.filter(
            brand__icontains=query
        ) | vehicles.filter(
            model__icontains=query
        )
    min_year = request.GET.get('min_year')
    max_year = request.GET.get('max_year')
    if min_year:
        vehicles = vehicles.filter(year__gte=min_year)
    if max_year:
        vehicles = vehicles.filter(year__lte=max_year)
    return render(request, 'ecommerceapp/vehicle_list.html', {'vehicles': vehicles})

# ✅ Spare Parts List
def spareparts_list(request):
    spareparts = SparePart.objects.all()
    query = request.GET.get('q')
    if query:
        spareparts = spareparts.filter(name__icontains=query)
    return render(request, 'ecommerceapp/spareparts_list.html', {'spareparts': spareparts})

def mechanics_list(request):
    mechanics = Mechanic.objects.all()
    query = request.GET.get('q')
    location = request.GET.get('location')

    if query:
        mechanics = mechanics.filter(
            name__icontains=query
        ) | mechanics.filter(
            specialization__icontains=query
        )
    if location:
        mechanics = mechanics.filter(location__icontains=location)

    return render(request, 'ecommerceapp/mechanics_list.html', {
        'mechanics': mechanics,
        'query': query,
        'location': location
    })
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import datetime
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from .models import Mechanic, Booking, Notification
from .forms import BookingForm
from .utilis import (
    send_booking_confirmation,
    send_payment_confirmation,
    send_raincheck_notification,
    send_cancellation_notice
)

@login_required
def book_mechanic(request, mechanic_id):
    mechanic = get_object_or_404(Mechanic, pk=mechanic_id)

    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking_date = form.cleaned_data['booking_date']
            time = form.cleaned_data['time']

            # Prevent double-booking
            conflict = Booking.objects.filter(
                mechanic=mechanic,
                booking_date=booking_date,
                time=time,
                status__in=['Pending', 'Approved']
            ).exists()

            if conflict:
                messages.warning(request, "⚠️ This mechanic is already booked at that time. Please choose another slot.")
            else:
                booking = form.save(commit=False)
                booking.user = request.user
                booking.mechanic = mechanic
                booking.status = 'Pending'
                booking.save()

                request.session['booking_id'] = booking.id

                # Notification
                Notification.objects.create(
                    user=request.user,
                    message=f"🛠️ Booking placed with {mechanic.name} for {booking_date} at {time}. Awaiting confirmation."
                )

                # Email confirmation only
                send_booking_confirmation(
                    user_email=request.user.email,
                    user_phone=getattr(request.user, 'phone', ''),
                    mechanic_name=mechanic.name,
                    booking_date=booking_date
                )

                messages.success(request, f"✅ Booking with {mechanic.name} on {booking_date} at {time} was successful.")
                messages.info(request, "💳 Proceeding to payment...")

                # ✅ CORRECTED REDIRECT TO STK PUSH
                return redirect('mechanic_payment')
    else:
        form = BookingForm(initial={'mechanic': mechanic})

    return render(request, 'ecommerceapp/book_mechanic.html', {
        'form': form,
        'mechanic': mechanic
    })


# ✅ Admin Panel: Booking Insights
@staff_member_required
def booking_insights(request):
    upcoming = Booking.objects.filter(date__gte=timezone.now()).order_by('date')
    mechanics = Mechanic.objects.all()
    return render(request, 'ecommerceapp/control_panel.html', {
        'view': 'booking_insights',
        'upcoming_bookings': upcoming,
        'mechanics': mechanics,
    })


# ✅ Cancel a Booking
@staff_member_required
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    send_cancellation_notice(request.user.email, request.user.phone)
    Notification.objects.create(
        user=request.user,
        message=f"❌ Your booking with {booking.mechanic.name} on {booking.booking_date} was cancelled."
    )
    booking.delete()
    messages.success(request, "Booking cancelled.")
    return redirect('control_panel_home')


# ✅ Reschedule Booking
@staff_member_required
def reschedule_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)

    if request.method == 'POST':
        new_date = request.POST.get('new_date')
        if new_date:
            booking.booking_date = new_date
            booking.save()
            send_raincheck_notification(request.user.email, request.user.phone, new_date)
            Notification.objects.create(
                user=request.user,
                message=f"📆 Your booking with {booking.mechanic.name} has been rescheduled to {new_date}."
            )
            messages.success(request, "Booking rescheduled.")
            return redirect('control_panel_home')

    return render(request, 'ecommerceapp/reschedule_booking.html', {'booking': booking})


# ✅ Inventory View
@staff_member_required
def manage_inventory(request):
    vehicles = Vehicle.objects.all()
    spare_parts = SparePart.objects.all()

    return render(request, 'ecommerceapp/manage_inventory.html', {
        'vehicles': vehicles,
        'spare_parts': spare_parts
    })


# ✅ Checkout View (With M-Pesa & Cash Option)
@login_required
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user)
    total = sum(item.total for item in cart_items)

    order, created = Order.objects.get_or_create(user=request.user, status='PENDING')

    if request.method == 'POST':
        method = request.POST.get('method')

        if method == 'MPESA':
            phone = request.POST.get('phone')
            order.status = 'PAID'
            order.save()

            send_payment_confirmation(
                request.user.email,
                request.user.phone,
                order.total_amount
            )

            Notification.objects.create(
                user=request.user,
                message="✅ M-Pesa payment confirmed. Your order is being processed."
            )

            return redirect('payment_success')

        elif method == 'CARD':
            # Stripe handles it
            pass

        elif method == 'PAYPAL':
            return redirect('paypal_redirect_url')

        elif method == 'CASH':
            order.status = 'PENDING_CASH'
            order.save()

            Notification.objects.create(
                user=request.user,
                message="💵 Order placed with Cash on Delivery. Please be available for confirmation."
            )

            return redirect('payment_success')

    return render(request, 'ecommerceapp/checkout.html', {
        'cart_items': cart_items,
        'total': total,
        'order': order,
    })



from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Vehicle, SparePart, CartItem, Order

from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Vehicle, SparePart, CartItem

@login_required
def add_to_cart(request, product_type, product_id):
    if product_type == 'vehicle':
        product = get_object_or_404(Vehicle, id=product_id)
        cart_item, created = CartItem.objects.get_or_create(
            user=request.user,
            product_type='vehicle',
            vehicle=product,
            spare_part=None
        )
    elif product_type == 'sparepart':
        product = get_object_or_404(SparePart, id=product_id)
        cart_item, created = CartItem.objects.get_or_create(
            user=request.user,
            product_type='sparepart',
            spare_part=product,
            vehicle=None
        )
    else:
        return redirect('home')  # You can redirect to an error page if needed
    
    if not created:
        cart_item.quantity += 1
        cart_item.save()

    return redirect('view_cart')  # Or wherever you want to show the updated cart


from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import CartItem

@login_required
def view_cart(request):
    # Get the cart items for the logged-in user
    cart_items = CartItem.objects.filter(user=request.user)
    
    # Calculate total price for all items
    total = sum(item.subtotal() for item in cart_items)
    
    return render(request, 'paymentapp/view_cart.html', {
        'cart_items': cart_items,
        'total': total
    })
from django.shortcuts import render, redirect
from .models import CartItem, Order
from django.contrib.auth.decorators import login_required
from .utilis import (
    send_payment_confirmation,
)

@login_required
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user)
    total = sum(item.total for item in cart_items)
    order, created = Order.objects.get_or_create(user=request.user, status='PENDING')

    if request.method == 'POST':
        method = request.POST.get('method')

        if method == 'MPESA':
            phone = request.POST.get('phone')
            # Simulate M-PESA payment success
            order.status = 'PAID'
            order.save()

            # 🔔 Send notification here
            send_payment_confirmation(
                request.user.email,
                getattr(request.user, 'phone', phone),  # fallback to POST phone
                order.total_amount
            )

            return redirect('payment_success')

        elif method == 'CARD':
            pass  # Stripe handles this

        elif method == 'PAYPAL':
            return redirect('paypal_redirect_url')

        elif method == 'CASH':
            order.status = 'PENDING_CASH'
            order.save()
            return redirect('payment_success')

    context = {
        'cart_items': cart_items,
        'total': total,
        'order': order,
    }
    return render(request, 'ecommerceapp/checkout.html', context)

@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, user=request.user)
    item.delete()
    return redirect('view_cart')
import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
def create_payment_intent(request, order_id):
    order = Order.objects.get(id=order_id, user=request.user)
    intent = stripe.PaymentIntent.create(
        amount=int(order.total * 100),  # amount in cents
        currency='usd',
        metadata={'order_id': order.id}
    )
    return JsonResponse({'clientSecret': intent.client_secret})
import stripe
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event['type'] == 'payment_intent.succeeded':
        intent = event['data']['object']
        order_id = intent['metadata']['order_id']
        order = Order.objects.get(id=order_id)
        order.payment_status = 'Paid'
        order.save()

    return HttpResponse(status=200)
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import stripe

stripe.api_key = 'your_stripe_secret_key'  # replace with your actual key

@csrf_exempt
def create_payment_intent(request, order_id):
    try:
        # Dummy total or fetch order by ID
        total_amount = 50000  # in cents, i.e., Ksh 500
        intent = stripe.PaymentIntent.create(
            amount=total_amount,
            currency='kes',
            metadata={'order_id': order_id},
        )
        return JsonResponse({'clientSecret': intent.client_secret})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
def paypal_redirect(request):
    
       return HttpResponse("Redirecting to PayPal...")
from django.shortcuts import render

def payment_success(request):
    return render(request, 'ecommerceapp/payment_success.html')


from django.shortcuts import render
from .models import Vehicle, SparePart, Mechanic
from .forms import UnifiedRecommendationForm
from django.db.models import Q

def recommend_anything(request):
    form = UnifiedRecommendationForm(request.GET or None)
    
    vehicles, spareparts, mechanics = [], [], []

    if form.is_valid():
        category = form.cleaned_data.get('category')
        
        if category == 'vehicle':
            filters = Q()
            brand = form.cleaned_data.get('brand')
            max_price = form.cleaned_data.get('max_price')
            min_year = form.cleaned_data.get('min_year')
            keywords = form.cleaned_data.get('keywords')
            
            if brand:
                filters &= Q(brand__icontains=brand)
            if max_price:
                filters &= Q(price__lte=max_price)
            if min_year:
                filters &= Q(year__gte=min_year)
            if keywords:
                filters &= Q(description__icontains=keywords)

            vehicles = Vehicle.objects.filter(filters).order_by('price')[:10]

        elif category == 'sparepart':
            filters = Q()
            part_keyword = form.cleaned_data.get('keywords')
            vehicle_compatibility = form.cleaned_data.get('compatible_vehicle')

            if part_keyword:
                filters &= Q(name__icontains=part_keyword) | Q(description__icontains=part_keyword)
            if vehicle_compatibility:
                filters &= Q(compatible_vehicle__icontains=vehicle_compatibility)

            spareparts = SparePart.objects.filter(filters).order_by('price')[:10]

        elif category == 'mechanic':
            filters = Q()
            location = form.cleaned_data.get('location')
            specialization = form.cleaned_data.get('specialization')

            if location:
                filters &= Q(location__icontains=location)
            if specialization:
                filters &= Q(specialization__icontains=specialization)

            mechanics = Mechanic.objects.filter(filters)[:10]

    return render(request, 'unified_recommendation.html', {
        'form': form,
        'vehicles': vehicles,
        'spareparts': spareparts,
      
        'mechanics': mechanics,
    })
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Sum, Count, Q
from ecommerceapp.models import Vehicle, SparePart, Mechanic, Order, Booking, CartItem, Notification
from django.contrib.auth.models import Group
from django.db.models.functions import TruncMonth, TruncDay
from django.utils.timezone import now
from collections import OrderedDict
from datetime import timedelta

@login_required
def dashboard_view(request):
    user = request.user
    context = {}

    query = request.GET.get('query', '')
    mechanics = Mechanic.objects.all()

    if query:
        mechanics = mechanics.filter(
            Q(name__icontains=query) | Q(specialization__icontains=query)
        )

    # Mechanics available now (no future bookings)
    booked_mechanic_ids = Booking.objects.filter(
        booking_date__gte=now()
    ).values_list('mechanic_id', flat=True)
    available_mechanics = mechanics.exclude(id__in=booked_mechanic_ids)

    if user.is_superuser or user.groups.filter(name="Employee").exists():
        # Core metrics
        context.update({
            'total_vehicles': Vehicle.objects.count(),
            'total_spareparts': SparePart.objects.count(),
            'total_mechanics': Mechanic.objects.count(),
            'total_orders': Order.objects.count(),
            'pending_orders': Order.objects.filter(status='PENDING').count(),
            'total_revenue': Order.objects.filter(is_paid=True)
                                .aggregate(Sum('items__cart_item__quantity'))['items__cart_item__quantity__sum'] or 0,
            'bookings_count': Booking.objects.count(),
        })

        # 📊 Monthly Orders (Last 6 months)
        months = [((now().replace(day=1) - timedelta(days=30 * i)).strftime('%B')) for i in reversed(range(6))]

        orders_monthly = (
            Order.objects
            .filter(created_at__year=now().year, is_paid=True)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )

        monthly_orders = OrderedDict((month, 0) for month in months)
        for o in orders_monthly:
            month_name = o['month'].strftime('%B')
            if month_name in monthly_orders:
                monthly_orders[month_name] = o['count']

        context['monthly_orders_labels'] = list(monthly_orders.keys())
        context['monthly_orders_data'] = list(monthly_orders.values())

        # 📈 Revenue Flow (last 7 days)
        past_7_days = [now().date() - timedelta(days=i) for i in reversed(range(7))]
        daily_orders = (
            Order.objects.filter(is_paid=True, created_at__date__gte=past_7_days[0])
            .annotate(day=TruncDay('created_at'))
            .values('day')
            .annotate(total=Count('id'))
        )

        daily_data = OrderedDict((day.strftime('%a'), 0) for day in past_7_days)
        for d in daily_orders:
            key = d['day'].strftime('%a')
            if key in daily_data:
                daily_data[key] = d['total']

        context['revenue_labels'] = list(daily_data.keys())
        context['revenue_data'] = list(daily_data.values())

        # 🧑‍🔧 Mechanic Load Chart (Weekly)
        current_week = now().date() - timedelta(days=now().weekday())
        mechanic_data = Booking.objects.filter(
            booking_date__gte=current_week
        ).values('mechanic__name').annotate(count=Count('id'))

        mechanic_chart = OrderedDict()
        for mech in Mechanic.objects.all():
            mechanic_chart[mech.name] = 0
        for entry in mechanic_data:
            mechanic_chart[entry['mechanic__name']] = entry['count']

        context['mechanic_names'] = list(mechanic_chart.keys())
        context['mechanic_booking_counts'] = list(mechanic_chart.values())

        

        # Weekly Summary (simple AI-lite)
        total_bookings = context['bookings_count']
        top_mechanic = max(mechanic_chart.items(), key=lambda x: x[1])[0] if mechanic_chart else 'N/A'
        top_day = max(daily_data.items(), key=lambda x: x[1])[0] if daily_data else 'N/A'
        total_orders = context['total_orders']
        context['weekly_summary'] = (
            f"This week saw {total_bookings} bookings. "
            f"The top-performing mechanic was **{top_mechanic}**, while peak activity occurred on **{top_day}**. "
            f"{total_orders} orders were processed, with steady revenue flow observed."
        )

    # Customer-specific data
    if user.groups.filter(name="Customer").exists():
        context.update({
            'my_orders': Order.objects.filter(user=user),
            'my_bookings': Booking.objects.filter(user=user),
        })

    # Shared context
    context['available_mechanics'] = available_mechanics
    context['mechanic_query'] = query
    context['unread_count'] = Notification.objects.filter(user=user, is_read=False).count()

    return render(request, 'dashboard.html', context)


from django.shortcuts import render
from django.contrib.auth.models import Group

def get_started_view(request):
    # Default role flags
    is_superuser = False
    is_employee = False
    is_customer = False

    # Check only if user is logged in
    if request.user.is_authenticated:
        is_superuser = request.user.is_superuser
        is_employee = request.user.groups.filter(name='Employee').exists()
        is_customer = request.user.groups.filter(name='Customer').exists()

    context = {
        'is_superuser': is_superuser,
        'is_employee': is_employee,
        'is_customer': is_customer,
    }

    return render(request, 'ecommerceapp/get-started.html', context)

# yourapp/context_processors.py
def user_roles(request):
    user = request.user
    return {
        'is_superuser': user.is_superuser if user.is_authenticated else False,
        'is_employee': hasattr(user, 'profile') and user.profile.role == 'employee',
        'is_customer': hasattr(user, 'profile') and user.profile.role == 'customer',
    }
@login_required
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    booking.status = 'CANCELLED'
    booking.save()

    # 🔔 Create a cancellation notification
    Notification.objects.create(
        user=request.user,
        message=f"❌ Your booking with {booking.mechanic.name} on {booking.date} has been cancelled."
    )

    messages.info(request, 'Booking cancelled successfully.')
    return redirect('dashboard')

@login_required
def request_raincheck(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if request.method == 'POST':
        reason = request.POST.get('reason')
        if reason:
            booking.status = 'RESCHEDULED'
            booking.details += f"\n\nRaincheck Requested: {reason}"
            booking.save()

            # 🔔 Create a raincheck notification
            Notification.objects.create(
                user=request.user,
                message=f"🌧️ Raincheck requested for booking with {booking.mechanic.name} on {booking.date}. Reason: {reason}"
            )

            messages.info(request, 'Raincheck submitted. We will follow up shortly.')

    return redirect('dashboard')


    from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Notification

@login_required
def notifications_view(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'ecommerceapp/notifications.html', {'notifications': notifications})


from django.views.decorators.http import require_POST
from django.shortcuts import redirect

@require_POST
@login_required
def mark_all_as_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('notifications')
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Notification

@login_required
def get_notifications(request):
    # Step 1: Fetch all notifications for user
    qs = Notification.objects.filter(user=request.user).order_by('-created_at')

    # Step 2: Get unread count from the full QuerySet
    unread_count = qs.filter(is_read=False).count()

    # Step 3: Slice to latest 10 for display
    latest_notifications = qs[:10]

    data = {
        'notifications': [
            {
                'message': n.message,
                'timestamp': n.created_at.strftime('%b %d, %H:%M'),
                'is_read': n.is_read
            } for n in latest_notifications
        ],
        'unread_count': unread_count
    }
    return JsonResponse(data)

from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required

from .models import Service, Offer, Vehicle, SparePart, Booking, Mechanic
from .forms import ServiceForm, OfferForm
from .utilis import (
    send_booking_confirmation,
    send_payment_confirmation,
    send_raincheck_notification,
    send_cancellation_notice
)

# 🌟 Add Service
@login_required
def add_service(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Service added successfully!")
            return redirect('home')
    else:
        form = ServiceForm()
    return render(request, 'ecommerceapp/add_service.html', {'form': form})

# 🌟 Edit Service
@login_required
def edit_service(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, "Service updated!")
            return redirect('home')
    else:
        form = ServiceForm(instance=service)
    return render(request, 'ecommerceapp/edit_service.html', {'form': form, 'object_id': pk})

# 🌟 Delete Service
@login_required
def delete_service(request, pk):
    service = get_object_or_404(Service, pk=pk)
    service.delete()
    messages.success(request, "Service deleted.")
    return redirect('home')

# 🌟 Add Offer
@login_required
def add_offer(request):
    if request.method == 'POST':
        form = OfferForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Offer created!")
            return redirect('home')
    else:
        form = OfferForm()
    return render(request, 'ecommerceapp/add_offer.html', {'form': form})

# 🌟 Edit Offer
@login_required
def edit_offer(request, pk):
    offer = get_object_or_404(Offer, pk=pk)
    if request.method == 'POST':
        form = OfferForm(request.POST, instance=offer)
        if form.is_valid():
            form.save()
            messages.success(request, "Offer updated!")
            return redirect('home')
    else:
        form = OfferForm(instance=offer)
    return render(request, 'ecommerceapp/edit_offer.html', {'form': form, 'object_id': pk})

# 🌟 Delete Offer
@login_required
def delete_offer(request, pk):
    offer = get_object_or_404(Offer, pk=pk)
    offer.delete()
    messages.success(request, "Offer removed.")
    return redirect('home')

# 🛠 Manage Inventory
@staff_member_required
def manage_inventory(request):
    vehicles = Vehicle.objects.all()
    spare_parts = SparePart.objects.all()
    return render(request, 'ecommerceapp/manage_inventory.html', {
        'vehicles': vehicles,
        'spare_parts': spare_parts,
    })

# 🗑 Delete Vehicle
@staff_member_required
def delete_vehicle(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    vehicle.delete()
    messages.success(request, "Vehicle deleted.")
    return redirect('manage_inventory')

# 🗑 Delete SparePart
@staff_member_required
def delete_spare(request, pk):
    spare = get_object_or_404(SparePart, pk=pk)
    spare.delete()
    messages.success(request, "Spare part deleted.")
    return redirect('manage_inventory')

# 📅 Booking Insights
@staff_member_required
def booking_insights(request):
    upcoming = Booking.objects.filter(date__gte=timezone.now()).order_by('date')
    mechanics = Mechanic.objects.all()
    return render(request, 'ecommerceapp/booking_insights.html', {
        'upcoming_bookings': upcoming,
        'mechanics': mechanics,
    })

# ❌ Cancel Booking
@staff_member_required
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    mechanic_name = booking.mechanic.name

    send_cancellation_notice(
        request.user.email,
        request.user.phone
    )

    booking.delete()
    messages.success(request, f"Booking with {mechanic_name} cancelled.")
    return redirect('booking_insights')

# 🔁 Reschedule Booking
@staff_member_required
def reschedule_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if request.method == 'POST':
        new_date = request.POST.get('new_date')
        if new_date:
            booking.date = new_date
            booking.save()

            send_raincheck_notification(
                request.user.email,
                request.user.phone,
                booking.date
            )

            messages.success(request, "Booking rescheduled.")
            return redirect('booking_insights')
    return render(request, 'ecommerceapp/reschedule_booking.html', {'booking': booking})



# 🔔 Reminder: After successful mechanic booking or payment,
# Call these functions in the relevant views (e.g. book_mechanic or checkout):
#
# send_booking_confirmation(request.user.email, request.user.phone, mechanic.name, booking.date)
# send_payment_confirmation(request.user.email, request.user.phone, order.total_amount)
from .notification import (
    send_booking_confirmation,
    send_payment_confirmation,
    send_raincheck_notification,
    send_cancellation_notice
)
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from .models import Notification

@login_required
def mark_notification_as_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()
    return redirect('notifications')  # Change if your notification view uses a different name

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from .models import Notification  # Ensure this import exists

@login_required
def delete_notification(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.delete()
    return redirect('notifications')
# views.py
from django.shortcuts import render
from .models import Offer

def offer_list(request):
    offers = Offer.objects.all()
    return render(request, 'ecommerceapp/offer_list.html', {'offers': offers})
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render

# Helper functions
def is_mechanic(user):
    return user.groups.filter(name='Mechanic').exists()

def is_employee(user):
    return user.groups.filter(name='Employee').exists()

def is_customer(user):
    return user.groups.filter(name='Customer').exists()

# Example dashboard views
@login_required
@user_passes_test(is_mechanic)
def mechanic_dashboard(request):
    user = request.user

    # Try to get mechanic profile
    try:
        mechanic = Mechanic.objects.get(user=user)
    except Mechanic.DoesNotExist:
        mechanic = None

    # Bookings for this mechanic
    if mechanic:
        bookings_qs = Booking.objects.filter(mechanic=mechanic).order_by('-booking_date')
        total_bookings     = bookings_qs.count()
        pending_bookings   = bookings_qs.filter(status='Pending').count()
        completed_bookings = bookings_qs.filter(status='Completed').count()
        recent_bookings    = bookings_qs.select_related('user')[:10]
        open_job_cards     = JobCard.objects.filter(mechanic=mechanic, status__in=['Open', 'In Progress']).count()
    else:
        total_bookings = pending_bookings = completed_bookings = open_job_cards = 0
        recent_bookings = []

    notifications = Notification.objects.filter(user=user).order_by('-created_at')[:8]

    return render(request, 'dashboards/mechanic_dashboard.html', {
        'mechanic':           mechanic,
        'total_bookings':     total_bookings,
        'pending_bookings':   pending_bookings,
        'completed_bookings': completed_bookings,
        'open_job_cards':     open_job_cards,
        'recent_bookings':    recent_bookings,
        'notifications':      notifications,
    })

@login_required
@user_passes_test(is_employee)
def employee_dashboard(request):
    return render(request, 'dashboards/employee_dashboard.html')

@login_required
@user_passes_test(is_customer)
def customer_dashboard(request):
    return render(request, 'dashboards/customer_dashboard.html')
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

@login_required
def role_based_redirect(request):
    user = request.user
    if user.groups.filter(name='Mechanic').exists():
        return redirect('mechanic_dashboard')
    elif user.groups.filter(name='Employee').exists():
        return redirect('employee_dashboard')
    elif user.groups.filter(name='Customer').exists():
        return redirect('customer_dashboard')
    else:
        return redirect('default_dashboard')  # Optional fallback
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Booking

@login_required
def customer_booking_history(request):
    bookings = Booking.objects.filter(user=request.user).order_by('-booking_date')
    return render(request, 'ecommerceapp/customer_booking_history.html', {'bookings': bookings})
from django.shortcuts import get_object_or_404

@login_required
def customer_booking_details(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    return render(request, 'ecommerceapp/customer_booking_details.html', {'booking': booking})
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Booking

@login_required
def customer_booking_details(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    return render(request, 'ecommerceapp/customer_booking_details.html', {'booking': booking})
from django.contrib import messages
from django.shortcuts import redirect

@login_required
def customer_cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if booking.status != 'Cancelled':
        booking.status = 'Cancelled'
        booking.save()
        messages.success(request, 'Your booking has been cancelled successfully.')
    else:
        messages.info(request, 'This booking was already cancelled.')

    return redirect('customer_booking_history')  # make sure this name exists in your URL patterns
from django.utils import timezone
from .forms import BookingForm

@login_required
def customer_reschedule_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if request.method == 'POST':
        form = BookingForm(request.POST, instance=booking)
        if form.is_valid():
            updated_booking = form.save(commit=False)
            updated_booking.status = 'Pending'  # Reset status on reschedule
            updated_booking.save()
            messages.success(request, 'Your booking has been rescheduled.')
            return redirect('customer_booking_history')
    else:
        form = BookingForm(instance=booking)

    return render(request, 'reschedule_booking.html', {'form': form, 'booking': booking})
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseServerError
from ecommerceapp.models import Booking, Mechanic
from paymentapp.models import Payment
from datetime import date, timedelta
from django.db.models import Sum

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Employee, Attendance, Shift
from datetime import datetime, date, time
from django.db.models import Count

@login_required
def employee_dashboard(request):
    today = emp_date.today()
    now_time = emp_tz.now()

    total_employees = Employee.objects.count()
    today_checkins  = Attendance.objects.filter(date=today).count()
    active_shifts   = Shift.objects.filter(status='active').count()

    # Check if the current user has checked in today
    checked_in = False
    try:
        emp = Employee.objects.get(user=request.user)
        checked_in = Attendance.objects.filter(employee=emp, date=today).exists()
    except Employee.DoesNotExist:
        pass

    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]

    context = {
        "total_employees": total_employees,
        "today_checkins":  today_checkins,
        "active_shifts":   active_shifts,
        "checked_in":      checked_in,
        "notifications":   notifications,
    }
    return render(request, "dashboards/employee_dashboard.html", context)
# ecommerceapp/views.py
from django.shortcuts import render, get_object_or_404
from .models import Vehicle

def vehicle_detail(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    return render(request, 'ecommerceapp/vehicle_detail.html', {'vehicle': vehicle})

# ─── Job Card Views ───────────────────────────────────────────────────────────

from .models import JobCard
from .forms import JobCardForm
from django.utils import timezone as tz

@login_required
def job_card_list(request):
    """Staff/mechanic see all job cards; customers get a 403."""
    user = request.user
    is_staff = user.is_superuser or user.groups.filter(name__in=['Employee', 'Mechanic']).exists()

    if not is_staff:
        messages.error(request, "You don't have permission to view job cards.")
        return redirect('dashboard')

    job_cards = JobCard.objects.select_related('mechanic', 'customer').all()

    status_filter = request.GET.get('status', '')
    if status_filter:
        job_cards = job_cards.filter(status=status_filter)

    return render(request, 'ecommerceapp/job_cards/list.html', {
        'job_cards': job_cards,
        'status_filter': status_filter,
        'status_choices': JobCard.STATUS_CHOICES,
    })


@login_required
def job_card_create(request):
    """Staff or admin can create a job card, optionally linked to a booking."""
    booking_id = request.GET.get('booking_id')
    booking = None
    initial = {}

    if booking_id:
        booking = get_object_or_404(Booking, id=booking_id)
        initial = {
            'mechanic': booking.mechanic,
            'title': f"{booking.service_type} – {booking.details[:60]}" if booking.details else booking.service_type,
            'description': booking.details,
        }

    if request.method == 'POST':
        form = JobCardForm(request.POST)
        if form.is_valid():
            job_card = form.save(commit=False)
            job_card.customer = booking.user if booking else request.user
            if booking:
                job_card.booking = booking
            job_card.save()
            Notification.objects.create(
                user=job_card.customer,
                message=f"🔧 Job Card JC-{job_card.id:04d} has been created for your vehicle "
                        f"({job_card.vehicle_make} {job_card.vehicle_model})."
            )
            messages.success(request, f"Job Card JC-{job_card.id:04d} created.")
            return redirect('job_card_detail', pk=job_card.id)
    else:
        form = JobCardForm(initial=initial)

    return render(request, 'ecommerceapp/job_cards/form.html', {
        'form': form,
        'booking': booking,
        'action': 'Create',
    })


@login_required
def job_card_detail(request, pk):
    job_card = get_object_or_404(JobCard, pk=pk)
    user = request.user
    is_staff = user.is_superuser or user.groups.filter(name__in=['Employee', 'Mechanic']).exists()

    if not is_staff:
        messages.error(request, "You don't have permission to view job cards.")
        return redirect('dashboard')

    return render(request, 'ecommerceapp/job_cards/detail.html', {'job_card': job_card})


@staff_member_required
def job_card_update(request, pk):
    job_card = get_object_or_404(JobCard, pk=pk)
    old_status = job_card.status

    if request.method == 'POST':
        form = JobCardForm(request.POST, instance=job_card)
        if form.is_valid():
            jc = form.save(commit=False)
            if jc.status == 'Completed' and old_status != 'Completed':
                jc.completed_at = tz.now()
            jc.save()
            # Notify customer on status change
            if jc.status != old_status:
                Notification.objects.create(
                    user=jc.customer,
                    message=f"🔧 Job Card JC-{jc.id:04d} status updated to '{jc.status}'."
                )
            messages.success(request, "Job card updated.")
            return redirect('job_card_detail', pk=jc.id)
    else:
        form = JobCardForm(instance=job_card)

    return render(request, 'ecommerceapp/job_cards/form.html', {
        'form': form,
        'job_card': job_card,
        'action': 'Update',
    })


@staff_member_required
def job_card_delete(request, pk):
    job_card = get_object_or_404(JobCard, pk=pk)
    if request.method == 'POST':
        job_card.delete()
        messages.success(request, "Job card deleted.")
        return redirect('job_card_list')
    return render(request, 'ecommerceapp/job_cards/confirm_delete.html', {'job_card': job_card})

# ─── Employee Management Views ────────────────────────────────────────────────

from .models import Employee, Attendance, Shift
from django.utils import timezone as emp_tz
from datetime import date as emp_date, datetime as emp_datetime

# ── Employee List (admin/superuser only) ──────────────────────────────────────
@staff_member_required
def employee_list(request):
    employees = Employee.objects.select_related('user').filter(is_active=True)
    return render(request, 'ecommerceapp/employees/list.html', {
        'employees': employees,
        'today': emp_date.today(),
    })


# ── Check-In ──────────────────────────────────────────────────────────────────
@login_required
def attendance_checkin(request):
    try:
        employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        messages.error(request, "No employee profile found for your account.")
        return redirect('home')

    today = emp_date.today()
    already = Attendance.objects.filter(employee=employee, date=today).first()

    if already:
        messages.warning(request, f"You already checked in today at {already.time_in.strftime('%H:%M')}.")
    else:
        Attendance.objects.create(
            employee=employee,
            date=today,
            time_in=emp_tz.now().time(),
        )
        Notification.objects.create(
            user=request.user,
            message=f"✅ Check-in recorded at {emp_tz.now().strftime('%H:%M')} on {today}."
        )
        messages.success(request, f"✅ Checked in at {emp_tz.now().strftime('%H:%M')}.")

    return redirect('employee_dashboard')


# ── Check-Out ─────────────────────────────────────────────────────────────────
@login_required
def attendance_checkout(request):
    try:
        employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        messages.error(request, "No employee profile found.")
        return redirect('home')

    today = emp_date.today()
    record = Attendance.objects.filter(employee=employee, date=today).first()

    if not record:
        messages.error(request, "You haven't checked in today.")
    elif record.time_out:
        messages.warning(request, f"You already checked out at {record.time_out.strftime('%H:%M')}.")
    else:
        record.time_out = emp_tz.now().time()
        record.save()
        Notification.objects.create(
            user=request.user,
            message=f"👋 Check-out recorded at {emp_tz.now().strftime('%H:%M')} on {today}."
        )
        messages.success(request, f"👋 Checked out at {emp_tz.now().strftime('%H:%M')}.")

    return redirect('employee_dashboard')


# ── Attendance History ────────────────────────────────────────────────────────
@login_required
def attendance_history(request):
    try:
        employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        messages.error(request, "No employee profile found.")
        return redirect('home')

    records = Attendance.objects.filter(employee=employee).order_by('-date')[:30]
    return render(request, 'ecommerceapp/employees/attendance.html', {
        'records': records,
        'employee': employee,
    })


# ── Shift List for Employee ───────────────────────────────────────────────────
@login_required
def my_shifts(request):
    try:
        employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        messages.error(request, "No employee profile found.")
        return redirect('home')

    shifts = Shift.objects.filter(employee=employee).order_by('-id')
    return render(request, 'ecommerceapp/employees/shifts.html', {
        'shifts': shifts,
        'employee': employee,
    })


# ── Admin: All Attendance Today ───────────────────────────────────────────────
@staff_member_required
def attendance_today(request):
    today = emp_date.today()
    records = Attendance.objects.filter(date=today).select_related('employee__user')
    all_employees = Employee.objects.filter(is_active=True)
    checked_in_ids = records.values_list('employee_id', flat=True)
    absent = all_employees.exclude(id__in=checked_in_ids)

    return render(request, 'ecommerceapp/employees/attendance_today.html', {
        'records': records,
        'absent': absent,
        'today': today,
    })

# ─── Mechanic Rating Views ────────────────────────────────────────────────────

from .models import MechanicRating
from django.db.models import Avg

@login_required
def rate_mechanic(request, booking_id):
    """Customer submits a star rating after a completed booking."""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if booking.status != 'Completed':
        messages.error(request, "You can only rate completed bookings.")
        return redirect('customer_booking_history')

    if hasattr(booking, 'rating'):
        messages.info(request, "You've already rated this booking.")
        return redirect('customer_booking_history')

    if request.method == 'POST':
        stars   = int(request.POST.get('stars', 0))
        comment = request.POST.get('comment', '').strip()

        if not 1 <= stars <= 5:
            messages.error(request, "Please select a rating between 1 and 5 stars.")
        else:
            MechanicRating.objects.create(
                booking=booking,
                mechanic=booking.mechanic,
                customer=request.user,
                stars=stars,
                comment=comment,
            )
            Notification.objects.create(
                user=request.user,
                message=f"⭐ Thank you for rating {booking.mechanic.name} ({stars} stars)!"
            )
            messages.success(request, f"Thank you for your {stars}★ rating!")
            return redirect('customer_booking_history')

    return render(request, 'ecommerceapp/rate_mechanic.html', {'booking': booking})


@staff_member_required
def mechanic_performance(request):
    """Admin view of mechanic performance metrics."""
    from django.db.models import Count, Avg
    mechanics = Mechanic.objects.annotate(
        total_bookings=Count('booking'),
        completed_bookings=Count('booking', filter=Q(booking__status='Completed')),
        avg_rating=Avg('ratings__stars'),
        total_ratings=Count('ratings'),
    ).order_by('-avg_rating')

    return render(request, 'ecommerceapp/mechanic_performance.html', {
        'mechanics': mechanics
    })
