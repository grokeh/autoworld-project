# paymentapp/forms.py

from django import forms

class MpesaPaymentForm(forms.Form):
    phone = forms.CharField(max_length=13, required=True)

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if not phone.startswith('2547'):
            raise forms.ValidationError("Phone must start with 2547.")
        return phone
