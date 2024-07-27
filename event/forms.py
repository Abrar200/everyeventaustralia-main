# forms.py
from django import forms
from .models import Quote, CustomUser, Venue, EventCategory, VenueOpeningHour
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

class QuoteForm(forms.ModelForm):
    class Meta:
        model = Quote
        fields = ['service', 'price']
        widgets = {
            'service': forms.Select(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }



class VenueVendorRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    venue_email = forms.EmailField(required=True)
    venue_contact_number = forms.CharField(max_length=20, required=True)
    venue_name = forms.CharField(max_length=100, required=True)
    venue_address = forms.CharField(max_length=255, required=True)
    description = forms.CharField(widget=forms.Textarea, required=True)
    price_per_event = forms.DecimalField(max_digits=10, decimal_places=2, required=True)
    profile_picture = forms.ImageField(required=False)
    cover_photo = forms.ImageField(required=False)
    venue_image = forms.ImageField(required=True)
    event_category = forms.ModelMultipleChoiceField(queryset=EventCategory.objects.all(), widget=forms.CheckboxSelectMultiple)
    
    # Adding opening hours fields
    opening_hours = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = CustomUser
        fields = ['username', 'password1', 'password2', 'first_name', 'last_name', 'venue_email', 'venue_contact_number', 'venue_name', 'venue_address', 'description', 'price_per_event', 'profile_picture', 'cover_photo', 'venue_image', 'event_category', 'opening_hours']

class VenueVendorLoginForm(AuthenticationForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'password']
