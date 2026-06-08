from django import forms
from .models import Booking

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['booking_date', 'time', 'details']
        widgets = {
            'booking_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control', 'placeholder': 'Select booking date'}
            ),
            'time': forms.TimeInput(
                attrs={'type': 'time', 'class': 'form-control', 'placeholder': 'Select time'}
            ),
            'details': forms.Textarea(
                attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Describe the issue or service needed'}
            ),
        }
        labels = {
            'booking_date': 'Booking Date',
            'time': 'Preferred Time',
            'details': 'Service Details',
        }

        
from django import forms

CATEGORY_CHOICES = [
    ('vehicle', 'Vehicles'),
    ('sparepart', 'Spare Parts'),
    ('mechanic', 'Mechanics'),
]

class UnifiedRecommendationForm(forms.Form):
    category = forms.ChoiceField(choices=CATEGORY_CHOICES, label="What are you looking for?")
    
    # Vehicle-related
    brand = forms.CharField(required=False)
    max_price = forms.DecimalField(required=False)
    min_year = forms.IntegerField(required=False)
    keywords = forms.CharField(required=False)

    # Spare Part-related
    compatible_vehicle = forms.CharField(required=False)
    
    # Mechanic-related
    location = forms.CharField(required=False)
    specialization = forms.CharField(required=False)
# forms.py
from django import forms

class PaymentForm(forms.Form):
    phone_number = forms.CharField(label='M-Pesa Number', max_length=12, help_text="Enter in format 2547XXXXXXXX")

from django import forms
from .models import Service, Offer, JobCard

class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'description', 'price', 'image', 'is_active']


class OfferForm(forms.ModelForm):
    class Meta:
        model = Offer
        fields = ['service', 'title', 'description', 'discount_percentage', 'start_date', 'end_date', 'is_visible']
        widgets = {
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class JobCardForm(forms.ModelForm):
    class Meta:
        model = JobCard
        fields = [
            'vehicle_make', 'vehicle_model', 'vehicle_year', 'plate_number', 'mileage',
            'title', 'description', 'priority', 'mechanic',
            'parts_used', 'labour_cost', 'parts_cost', 'technician_notes', 'status',
        ]
        widgets = {
            'description':       forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'parts_used':        forms.Textarea(attrs={'rows': 3, 'class': 'form-control',
                                                       'placeholder': 'e.g.\nOil filter\nBrake pads'}),
            'technician_notes':  forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'vehicle_make':      forms.TextInput(attrs={'class': 'form-control'}),
            'vehicle_model':     forms.TextInput(attrs={'class': 'form-control'}),
            'vehicle_year':      forms.NumberInput(attrs={'class': 'form-control'}),
            'plate_number':      forms.TextInput(attrs={'class': 'form-control'}),
            'mileage':           forms.NumberInput(attrs={'class': 'form-control'}),
            'title':             forms.TextInput(attrs={'class': 'form-control'}),
            'priority':          forms.Select(attrs={'class': 'form-select'}),
            'status':            forms.Select(attrs={'class': 'form-select'}),
            'mechanic':          forms.Select(attrs={'class': 'form-select'}),
            'labour_cost':       forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'parts_cost':        forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
