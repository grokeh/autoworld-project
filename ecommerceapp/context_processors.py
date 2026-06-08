# yourapp/context_processors.py
def user_roles(request):
    user = request.user
    return {
        'is_superuser': user.is_superuser if user.is_authenticated else False,
        'is_employee': hasattr(user, 'profile') and user.profile.role == 'employee',
        'is_customer': hasattr(user, 'profile') and user.profile.role == 'customer',
    }
# context_processors.py

from ecommerceapp.models import Notification

def unread_notifications(request):
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    else:
        unread_count = 0
    return {'unread_notifications_count': unread_count}
