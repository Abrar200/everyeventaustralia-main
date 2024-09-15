from django.shortcuts import render
from .models import Product, Business, OpeningHour, Cart, Message, State, Variation, ProductVariation, CartItemVariation, ProductReview, Order, OrderItem, Refund, Service, ProductCategory, ServiceCategory, ServiceImage, ServiceReview, Quote, EventCategory, Award, ServiceVariation, ServiceVariationOption, Venue, VenueImage, VenueOpeningHour, Amenity, VenueReview, VenueView, VenueInquiry, OrderApproval, OrderTermsSignature, DeliveryByRadius, BlogPost
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.http import JsonResponse
import logging
import json
from django.core import serializers
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import itertools
from users.models import CustomUser
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect
from itertools import chain
from django.template import RequestContext
from django.template.context_processors import csrf
import stripe
from django.conf import settings
from collections import defaultdict
import string
import random
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.core.mail import EmailMultiAlternatives
from decimal import Decimal, InvalidOperation
from django.core.paginator import Paginator
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Subquery, OuterRef
from django.views.decorators.http import require_POST
from django.utils.safestring import mark_safe
from .forms import QuoteForm
from django.db import transaction
from itertools import chain
from operator import attrgetter
from .forms import VenueVendorRegistrationForm, VenueVendorLoginForm
from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError
from django.db.models import F
from geopy.distance import geodesic
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import ListView, DetailView
from django.utils import timezone
from django.contrib.sites.models import Site
from django.db import models
from django.utils.dateparse import parse_time
from django.utils.formats import time_format
from datetime import datetime
from django.core.files.storage import default_storage
import base64
from django.core.files.base import ContentFile
from dateutil.relativedelta import relativedelta
from celery import shared_task
from .tasks import send_email_task
from django.contrib.sites.shortcuts import get_current_site
import requests
from django.views.decorators.http import require_GET
from django.utils.html import strip_tags
from django.core.exceptions import ObjectDoesNotExist
import geopy
from io import BytesIO


stripe.api_key = settings.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)


def get_google_reviews(place_id):
    API_KEY = settings.GOOGLE_MAPS_API_KEY
    url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,rating,reviews&key={API_KEY}"
    
    print(f"Requesting Google Reviews for Place ID: {place_id}")
    response = requests.get(url)
    print(f"Google API Response Status Code: {response.status_code}")
    
    data = response.json()
    print(f"Google API Response Data: {data}")

    reviews = []
    if 'result' in data:
        reviews = data['result'].get('reviews', [])
        print(f"Number of reviews found: {len(reviews)}")
    else:
        print("No 'result' found in the API response.")

    return reviews

def home(request):
    best_selling_products = Product.objects.filter(is_best_seller=True)
    best_selling_services = Service.objects.filter(is_best_seller=True)
    blogs = BlogPost.objects.all()

    # Combine products and services, and add a 'type' attribute
    for product in best_selling_products:
        product.type = 'product'
    for service in best_selling_services:
        service.type = 'service'

    # Combine and sort the best sellers
    best_sellers = sorted(
        chain(best_selling_products, best_selling_services),
        key=lambda x: x.name  # Example: sort by name, adjust as needed
    )

    # Get all products and services for other parts of the template
    all_products = Product.objects.all()
    all_services = Service.objects.all()

    # Get Google reviews
    place_id = 'ChIJPZoiCZfs4E4R6qAOEetkbRY'  # Your actual Place ID
    google_reviews = get_google_reviews(place_id)

    print(f"Google Reviews passed to template: {google_reviews}")

    context = {
        'best_sellers': best_sellers,
        'products': all_products,
        'services': all_services,
        'google_reviews': google_reviews,
        'blogs': blogs,
    }
    return render(request, 'event/index.html', context)


def all_events(request):
    products = Product.objects.all()
    services = Service.objects.all()
    items = list(products) + list(services)

    # Apply filters
    type_filter = request.GET.getlist('type')
    if type_filter:
        if 'products' in type_filter:
            items = [item for item in items if isinstance(item, Product)]
        if 'services' in type_filter:
            items = [item for item in items if isinstance(item, Service)]
        if 'purchase' in type_filter:
            items = [item for item in items if getattr(item, 'for_purchase', False)]

    # New filters for Best Sellers and New Arrivals
    if 'best_sellers' in request.GET:
        items = [item for item in items if item.is_best_seller]
    if 'new_arrivals' in request.GET:
        items = [item for item in items if item.new_arrivals]

    price_sort = request.GET.get('price_sort')
    if price_sort == 'high_to_low':
        items.sort(key=lambda x: x.hire_price, reverse=True)
    elif price_sort == 'low_to_high':
        items.sort(key=lambda x: x.hire_price)

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        items = [item for item in items if item.hire_price >= float(min_price)]
    if max_price:
        items = [item for item in items if item.hire_price <= float(max_price)]

    state_filter = request.GET.getlist('state')
    if state_filter:
        items = [item for item in items if any(state in [s.name for s in item.business.states.all()] for state in state_filter)]

    event_category_filter = request.GET.getlist('event_category')
    if event_category_filter:
        items = [item for item in items if any(cat in [c.name for c in item.business.event_categories.all()] for cat in event_category_filter)]

    product_category_filter = request.GET.getlist('product_category')
    if product_category_filter:
        items = [item for item in items if isinstance(item, Product) and item.category.name in product_category_filter]

    service_category_filter = request.GET.getlist('service_category')
    if service_category_filter:
        items = [item for item in items if isinstance(item, Service) and item.category.name in service_category_filter]

    color_filter = request.GET.getlist('color')
    if color_filter:
        items = [item for item in items if isinstance(item, Product) and item.main_colour_theme in color_filter]

    # Pagination
    paginator = Paginator(items, 9)  # Show 9 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'states': State.objects.all(),
        'event_categories': EventCategory.objects.all(),
        'product_categories': ProductCategory.objects.all(),
        'service_categories': ServiceCategory.objects.all(),
        'get_params': request.GET,
        'type_filter': type_filter,
        'state_filter': state_filter,
        'event_category_filter': event_category_filter,
        'product_category_filter': product_category_filter,
        'service_category_filter': service_category_filter,
        'color_filter': color_filter,
        'color_choices': Product.COLOUR_CHOICES,
        'best_sellers_filter': 'best_sellers' in request.GET,
        'new_arrivals_filter': 'new_arrivals' in request.GET,
    }
    return render(request, 'event/all_events.html', context)

def privacy_policy(request):
    return render(request, 'event/privacy_policy.html')


def return_and_refund_policy(request):
    return render(request, 'event/return_and_refund_policy.html')


def terms_and_conditions(request):
    return render(request, 'event/terms_and_conditions.html')

def community(request):
    businesses = Business.objects.all().select_related('seller')

    states = State.objects.all()

    country_filter = request.GET.getlist('country')
    state_filter = request.GET.getlist('state')

    if country_filter and state_filter:
        businesses = businesses.filter(
            states__in=state_filter
        ).distinct()
    elif state_filter:
        businesses = businesses.filter(states__in=state_filter).distinct()

    if request.is_ajax():
        business_data = [
            {
                'business_name': business.business_name,
                'description': business.description,
                'business_slug': business.business_slug,
                'profile_picture': business.profile_picture.url,
                'seller_name': business.seller.get_full_name(),
                # Add more fields as needed
            }
            for business in businesses
        ]
        return JsonResponse({'businesses': business_data})

    context = {
        'businesses': businesses,
        'states': states,
        'selected_countries': country_filter,
        'selected_states': state_filter,
    }
    return render(request, 'event/community.html', context)


from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import default_token_generator as token_generator

class VerifyEmailView(View):
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = CustomUser.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
            user = None

        if user is not None and token_generator.check_token(user, token):
            user.is_active = True
            user.save()
            messages.success(request, 'Your email has been verified successfully. You can now log in.')
            return redirect('login')
        else:
            messages.error(request, 'The verification link is invalid or has expired.')
            return redirect('home')


from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes


class BusinessRegistrationView(View):
    def get(self, request):
        states = State.objects.all()
        day_choices = OpeningHour.DAY_CHOICES
        event_categories = EventCategory.objects.all()
        context = {
            'states': states,
            'day_choices': day_choices,
            'event_categories': event_categories,
            'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
        }
        return render(request, 'users/business_registration.html', context)

    def post(self, request):
        try:
            # Validate opening hours
            days = [day for day, _ in OpeningHour.DAY_CHOICES]
            invalid_days = []
            for day in days:
                is_closed = request.POST.get(f'opening_hours-{day}-is_closed') == 'on'
                opening_time = request.POST.get(f'opening_hours-{day}-opening_time')
                closing_time = request.POST.get(f'opening_hours-{day}-closing_time')

                if not is_closed and (not opening_time or not closing_time):
                    invalid_days.append(day)

            if invalid_days:
                error_message = f"For the following days, please provide both opening and closing times, or mark them as closed: {', '.join(invalid_days)}"
                messages.error(request, error_message)
                return redirect('business_registration')

            # User information
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            username = request.POST.get('email')
            email = request.POST.get('email')
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')

            if password != confirm_password:
                messages.error(request, "Passwords do not match.")
                return redirect('business_registration')
            
            # Check if the email already exists
            if CustomUser.objects.filter(email=email).exists():
                messages.error(request, "An account with this email address already exists. Please log in instead.")
                return redirect('business_registration')

            # Create user
            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_seller=True
            )
            user.is_active = False  # Deactivate account until email is verified
            user.save()

            # Send email verification
            self.send_verification_email(user, request)

            # Business information
            business_name = request.POST.get('business_name')
            description = request.POST.get('description')
            state_ids = request.POST.getlist('states')
            address = request.POST.get('address')
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            phone = request.POST.get('phone')
            terms_and_conditions = request.POST.get('terms_and_conditions')
            terms_and_conditions_pdf = request.FILES.get('terms_and_conditions_pdf')
            profile_picture = request.FILES.get('profile_picture')
            banner_image = request.FILES.get('banner_image')
            delivery_type = request.POST.get('delivery_type')

            business = Business.objects.create(
                seller=user,
                business_name=business_name,
                description=description,
                address=address,
                latitude=latitude if latitude else None,
                longitude=longitude if longitude else None,
                phone=phone,
                email=email,
                profile_picture=profile_picture,
                banner_image=banner_image,
                terms_and_conditions=terms_and_conditions,
                terms_and_conditions_pdf=terms_and_conditions_pdf,
                delivery_type=delivery_type,
            )

            if delivery_type == 'price_per_way':
                max_delivery_distance = request.POST.get('max_delivery_distance')
                delivery_price_per_way = request.POST.get('delivery_price_per_way')
                business.max_delivery_distance = max_delivery_distance
                business.delivery_price_per_way = delivery_price_per_way
            elif delivery_type == 'by_radius':
                radius_values = request.POST.getlist('delivery_radius')
                price_values = request.POST.getlist('delivery_radius_price')
                for radius, price in zip(radius_values, price_values):
                    DeliveryByRadius.objects.create(
                        business=business,
                        radius=radius,
                        price=price
                    )

            business.save()

            states = State.objects.filter(id__in=state_ids)
            business.states.set(states)
            event_category_ids = request.POST.getlist('event_categories')
            event_categories = EventCategory.objects.filter(id__in=event_category_ids)
            business.event_categories.set(event_categories)

            # Handle opening hours
            for day, day_display in OpeningHour.DAY_CHOICES:
                is_closed = request.POST.get(f'opening_hours-{day}-is_closed') == 'on'
                opening_time = request.POST.get(f'opening_hours-{day}-opening_time')
                closing_time = request.POST.get(f'opening_hours-{day}-closing_time')

                OpeningHour.objects.create(
                    business=business,
                    day=day,
                    is_closed=is_closed,
                    opening_time=opening_time if not is_closed else None,
                    closing_time=closing_time if not is_closed else None
                )

            # Handle awards
            for file in request.FILES.getlist('awards'):
                Award.objects.create(business=business, image=file)

            try:
                account = stripe.Account.create(
                    type='express',
                    country='AU',
                    email=email,
                    business_type='individual',
                )
                business.stripe_account_id = account.id
                business.save()

                account_link = stripe.AccountLink.create(
                    account=account.id,
                    refresh_url=request.build_absolute_uri(reverse('business_registration')),
                    return_url=request.build_absolute_uri(reverse('business_detail', args=[business.business_slug])),
                    type='account_onboarding',
                )
                messages.success(request, 'Registration successful! Please check your email to verify your account.')
                return redirect(account_link.url)
            except stripe.error.StripeError as e:
                messages.error(request, f"Stripe error: {e.user_message}")
                user.delete()
                business.delete()
                return redirect('business_registration')

        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            if 'user' in locals():
                user.delete()
            if 'business' in locals():
                business.delete()
            return redirect('business_registration')

    def send_verification_email(self, user, request):
        current_site = settings.SITE_URL
        mail_subject = 'Activate your account.'
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)
        verification_link = reverse('verify_email', kwargs={'uidb64': uid, 'token': token})
        verification_url = f"{current_site}{verification_link}"
        
        html_message = render_to_string('event/email_verification.html', {
            'user': user,
            'verification_url': verification_url,
            'domain': current_site,
        })
        plain_message = strip_tags(html_message)
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = user.email

        send_mail(
            mail_subject,
            plain_message,
            from_email,
            [to_email],
            html_message=html_message,
        )

@login_required
def edit_business(request, business_slug):
    business = get_object_or_404(Business, business_slug=business_slug)
    
    if request.user != business.seller:
        return redirect('business_detail', business_slug=business.business_slug)

    states = State.objects.all()
    event_categories = EventCategory.objects.all()

    if request.method == 'POST':
        business_name = request.POST.get('business_name')
        description = request.POST.get('description')
        state_ids = request.POST.getlist('states')
        event_category_ids = request.POST.getlist('event_categories')
        address = request.POST.get('address')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        terms_and_conditions = request.POST.get('terms_and_conditions')
        terms_and_conditions_pdf = request.FILES.get('terms_and_conditions_pdf')
        profile_picture = request.FILES.get('profile_picture')
        banner_image = request.FILES.get('banner_image')
        delivery_type = request.POST.get('delivery_type')

        # Check opening hours validity
        opening_hours_valid = True
        for day, _ in OpeningHour.DAY_CHOICES:
            is_closed = request.POST.get(f'opening_hours-{day}-is_closed') == 'on'
            opening_time = request.POST.get(f'opening_hours-{day}-opening_time')
            closing_time = request.POST.get(f'opening_hours-{day}-closing_time')

            if not is_closed and (not opening_time or not closing_time):
                opening_hours_valid = False
                break

        if not opening_hours_valid:
            messages.error(request, 'Please ensure all opening hours are filled out correctly for each day.')
            context = {
                'business': business,
                'states': states,
                'event_categories': event_categories,
                'day_choices': OpeningHour.DAY_CHOICES,
                'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
            }
            return render(request, 'event/edit_business.html', context)

        # Update business information
        business.business_name = business_name
        business.description = description
        business.address = address
        business.latitude = latitude if latitude else None
        business.longitude = longitude if longitude else None
        business.phone = phone
        business.email = email
        business.terms_and_conditions = terms_and_conditions
        business.delivery_type = delivery_type
        
        if terms_and_conditions_pdf:
            business.terms_and_conditions_pdf = terms_and_conditions_pdf
        if profile_picture:
            business.profile_picture = profile_picture
        if banner_image:
            business.banner_image = banner_image

        business.states.set(State.objects.filter(id__in=state_ids))
        business.event_categories.set(EventCategory.objects.filter(id__in=event_category_ids))

        # Handle delivery options
        if delivery_type == 'price_per_way':
            max_delivery_distance = request.POST.get('max_delivery_distance')
            delivery_price_per_way = request.POST.get('delivery_price_per_way')
            business.max_delivery_distance = max_delivery_distance
            business.delivery_price_per_way = delivery_price_per_way
            # Clear existing radius-based deliveries if any
            DeliveryByRadius.objects.filter(business=business).delete()
        elif delivery_type == 'by_radius':
            business.max_delivery_distance = None
            business.delivery_price_per_way = None
            # Clear existing radius entries
            DeliveryByRadius.objects.filter(business=business).delete()
            radius_values = request.POST.getlist('delivery_radius')
            price_values = request.POST.getlist('delivery_radius_price')
            for radius, price in zip(radius_values, price_values):
                if radius and price:  # Only create if both values are provided
                    DeliveryByRadius.objects.create(
                        business=business,
                        radius=radius,
                        price=price
                    )

        business.save()

        # Update opening hours
        for day, _ in OpeningHour.DAY_CHOICES:
            is_closed = request.POST.get(f'opening_hours-{day}-is_closed') == 'on'
            opening_time = request.POST.get(f'opening_hours-{day}-opening_time') or None
            closing_time = request.POST.get(f'opening_hours-{day}-closing_time') or None

            opening_hour, _ = OpeningHour.objects.get_or_create(business=business, day=day)
            opening_hour.is_closed = is_closed
            opening_hour.opening_time = None if is_closed else opening_time
            opening_hour.closing_time = None if is_closed else closing_time
            opening_hour.save()

        # Handle awards
        for file in request.FILES.getlist('awards'):
            Award.objects.create(business=business, image=file)

        business.refresh_from_db()  # Refresh the instance to ensure updated data is available

        messages.success(request, 'Business updated successfully.')
        return redirect('business_detail', business_slug=business.business_slug)

    # Ensure that the delivery radius options are included in the context
    context = {
        'business': business,
        'states': states,
        'event_categories': event_categories,
        'day_choices': OpeningHour.DAY_CHOICES,
        'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
        'delivery_radius_options': business.delivery_radius_options.all(),  # Add this to the context
    }
    return render(request, 'event/edit_business.html', context)

@csrf_exempt
@require_POST
def remove_award(request, award_id):
    try:
        award = Award.objects.get(id=award_id, business__seller=request.user)
        award.delete()
        return JsonResponse({'success': True})
    except Award.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Award not found or not authorized.'}, status=404)

class BusinessDetailView(View):
    def get(self, request, business_slug):
        business = get_object_or_404(Business, business_slug=business_slug)
        products = business.products.all()
        services = business.services.all()
        opening_hours = business.opening_hours.all()
        context = {
            'business': business, 
            'products': products, 
            'opening_hours': opening_hours, 
            'services': services,
            'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
        }
        return render(request, 'event/business_detail.html', context)
    

@method_decorator(login_required, name='dispatch')
class BusinessDeleteView(View):
    def post(self, request, business_slug):
        business = get_object_or_404(Business, business_slug=business_slug)

        if request.user != business.seller:
            messages.error(request, "You do not have permission to delete this business.")
            return redirect('business_detail', business_slug=business_slug)
        
        # Delete the business
        business.delete()
        
        # Set the user as not a seller
        request.user.is_seller = False
        request.user.save()
        
        messages.success(request, "Business has been successfully deleted.")
        return redirect('home')  # Redirect to the home page or any other page after deletion

class ProductDetailView(View):
    def get(self, request, business_slug=None, product_slug=None):
        business = get_object_or_404(Business, business_slug=business_slug)
        product = get_object_or_404(Product, product_slug=product_slug, business=business)
        
        variations = product.variations.all().prefetch_related('values')
        reviews = product.reviews.all()

        star_percentages = {
            5: product.star_rating_percentage(5),
            4: product.star_rating_percentage(4),
            3: product.star_rating_percentage(3),
            2: product.star_rating_percentage(2),
            1: product.star_rating_percentage(1),
        }

        # Fetch similar products based on category and main color theme
        similar_products = Product.objects.filter(
            category=product.category
        ).exclude(id=product.id)[:4]

        if not similar_products.exists():
            similar_products = Product.objects.filter(
                main_colour_theme=product.main_colour_theme
            ).exclude(id=product.id)[:4]

        context = {
            'product': product,
            'business': business,
            'variations': variations,
            'reviews': reviews,
            'star_percentages': star_percentages,
            'overall_review': product.overall_review,
            'similar_products': similar_products,
        }

        return render(request, 'event/product_detail.html', context)

    @method_decorator(login_required)
    def post(self, request, business_slug=None, product_slug=None):
        business = get_object_or_404(Business, business_slug=business_slug)
        product = get_object_or_404(Product, product_slug=product_slug, business=business)

        review_text = request.POST.get('message')
        rating = request.POST.get('rating')

        if review_text and rating:
            rating = int(rating)
            ProductReview.objects.create(
                product=product,
                user=request.user,
                review_text=review_text,
                rating=rating
            )
            return redirect('product_detail', business_slug=business_slug, product_slug=product_slug)
        
        reviews = product.reviews.all()

        star_percentages = {
            5: product.star_rating_percentage(5),
            4: product.star_rating_percentage(4),
            3: product.star_rating_percentage(3),
            2: product.star_rating_percentage(2),
            1: product.star_rating_percentage(1),
        }

        print("Form Data:", request.POST)
        
        # After processing the form data
        hire = request.POST.get('hire') == 'true'
        print("Hire value:", hire)

        context = {
            'product': product,
            'business': business,
            'reviews': reviews,
            'star_percentages': star_percentages,
        }

        return render(request, 'event/product_detail.html', context)


@method_decorator(login_required, name='dispatch')
class ProductDeleteView(View):
    def post(self, request, business_slug, product_slug):
        business = get_object_or_404(Business, business_slug=business_slug)
        product = get_object_or_404(Product, product_slug=product_slug, business=business)

        if request.user != business.seller:
            messages.error(request, "You do not have permission to delete this product.")
            return redirect('product_detail', business_slug=business_slug, product_slug=product_slug)
        
        product.delete()
        messages.success(request, "Product has been successfully deleted.")
        return redirect('business_detail', business_slug=business_slug)
    
@method_decorator(login_required, name='dispatch')
class ServiceDeleteView(View):
    def post(self, request, business_slug, service_slug):
        business = get_object_or_404(Business, business_slug=business_slug)
        service = get_object_or_404(Service, service_slug=service_slug, business=business)

        if request.user != business.seller:
            messages.error(request, "You do not have permission to delete this product.")
            return redirect('service_detail', business_slug=business_slug, service_slug=service_slug)
        
        service.delete()
        messages.success(request, "Service has been successfully deleted.")
        return redirect('business_detail', business_slug=business_slug)



class AjaxProductDetailView(View):
    def get(self, request, business_slug, product_slug):
        business = get_object_or_404(Business, business_slug=business_slug)
        product = get_object_or_404(Product, product_slug=product_slug, business=business)

        color_variations = Variation.objects.filter(product=product, name='color')
        size_variations = Variation.objects.filter(product=product, name='size')
        
        product_data = {
            'id': product.id,
            'name': product.name,
            'price': float(product.price),
            'description': product.description,
            'images': [product.image.url, product.image2.url] if product.image and product.image2 else [],
            'color_variations': list(color_variations.values('id', 'values__id', 'values__value', 'values__image')),
            'size_variations': list(size_variations.values('id', 'values__id', 'values__value')),
            'sku': product.product_slug,
            'categories': [product.business.business_name],
            'tags': [tag.name for tag in product.tags.all()] if hasattr(product, 'tags') else []
        }
        return JsonResponse(product_data)
    
class ProductCreateView(LoginRequiredMixin, View):
    def get(self, request, business_slug):
        business = get_object_or_404(Business, business_slug=business_slug, seller=request.user)
        categories = ProductCategory.objects.all()
        return render(request, 'event/product_create.html', {
            'business': business,
            'categories': categories,
            'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
        })

    def post(self, request, business_slug):
        business = get_object_or_404(Business, business_slug=business_slug, seller=request.user)
        if business.seller == request.user:
            def parse_decimal(value):
                if value in (None, ''):
                    return None
                try:
                    return Decimal(value)
                except InvalidOperation:
                    return None

            name = request.POST.get('name')
            description = request.POST.get('description')
            hire_price = parse_decimal(request.POST.get('hire_price'))
            purchase_price = parse_decimal(request.POST.get('purchase_price')) if request.POST.get('for_purchase') else None
            category_id = request.POST.get('category')
            category = get_object_or_404(ProductCategory, id=category_id)
            image = request.FILES.get('image')
            image2 = request.FILES.get('image2')
            image3 = request.FILES.get('image3')
            image4 = request.FILES.get('image4')
            in_stock = request.POST.get('in_stock') == 'on'
            stock_level = request.POST.get('stock_level')
            has_variations = request.POST.get('has_variations') == 'on'
            for_purchase = request.POST.get('for_purchase') == 'on'
            for_pickup = request.POST.get('for_pickup') == 'on'
            pickup_location = request.POST.get('pickup_location') if for_pickup else None
            can_deliver = request.POST.get('can_deliver') == 'on'
            main_colour_theme = request.POST.get('main_colour_theme')
            setup_packdown_fee = request.POST.get('setup_packdown_fee') == 'on'
            setup_packdown_fee_amount = parse_decimal(request.POST.get('setup_packdown_fee_amount')) if setup_packdown_fee else None

            product = Product.objects.create(
                name=name,
                description=description,
                hire_price=hire_price,
                purchase_price=purchase_price,
                category=category,
                image=image,
                image2=image2,
                image3=image3,
                image4=image4,
                business=business,
                in_stock=in_stock,
                stock_level=stock_level,
                has_variations=has_variations,
                for_purchase=for_purchase,
                for_pickup=for_pickup,
                pickup_location=pickup_location,
                can_deliver=can_deliver,
                main_colour_theme=main_colour_theme,
                setup_packdown_fee=setup_packdown_fee,
                setup_packdown_fee_amount=setup_packdown_fee_amount,
            )

            if has_variations:
                variation_names = [name for name in request.POST if name.startswith('variation_names_')]
                for var_name in variation_names:
                    var_index = var_name.split('_')[-1]
                    values = request.POST.getlist(f'variation_values_{var_index}[]')
                    price_varies = request.POST.getlist(f'price_varies_{var_index}[]')
                    prices = request.POST.getlist(f'variation_prices_{var_index}[]')

                    max_length = max(len(values), len(price_varies), len(prices))
                    values += [None] * (max_length - len(values))
                    price_varies += ['off'] * (max_length - len(price_varies))
                    prices += [''] * (max_length - len(prices))

                    variation = Variation.objects.create(
                        product=product,
                        name=request.POST[var_name]
                    )

                    for value, varies, price in zip(values, price_varies, prices):
                        if value is not None:
                            price_value = parse_decimal(price)
                            price_varies_bool = price_value is not None
                            ProductVariation.objects.create(
                                variation=variation,
                                value=value,
                                price=price_value,
                                price_varies=price_varies_bool
                            )

            return redirect('product_detail', business_slug=business.business_slug, product_slug=product.product_slug)
        else:
            return render(request, 'event/product_create.html', {
                'business': business,
                'error': 'You are not authorized to add products to this business.',
                'categories': ProductCategory.objects.all(),
            })

class ProductEditView(LoginRequiredMixin, View):
    def get(self, request, business_slug, product_slug):
        business = get_object_or_404(Business, business_slug=business_slug, seller=request.user)
        product = get_object_or_404(Product, product_slug=product_slug, business=business)
        categories = ProductCategory.objects.all()
        variations = product.variations.all()
        variations_with_values = {}
        for variation in variations:
            variation_values = ProductVariation.objects.filter(variation=variation)
            variations_with_values[variation.name] = list(variation_values.values('id', 'value', 'price', 'price_varies'))

        return render(request, 'event/product_edit.html', {
            'product': product,
            'business': business,
            'categories': categories,
            'variations_with_values': variations_with_values,
            'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
        })

    def post(self, request, business_slug, product_slug):
        business = get_object_or_404(Business, business_slug=business_slug, seller=request.user)
        product = get_object_or_404(Product, product_slug=product_slug, business=business)

        if request.user == business.seller:
            product.name = request.POST.get('name', product.name)
            product.description = request.POST.get('description', product.description)
            product.hire_price = request.POST.get('hire_price', product.hire_price)
            product.purchase_price = request.POST.get('purchase_price', product.purchase_price) if request.POST.get('for_purchase') == 'on' else None
            product.category_id = request.POST.get('category', product.category_id)
            
            if 'image' in request.FILES:
                product.image = request.FILES['image']
            if 'image2' in request.FILES:
                product.image2 = request.FILES['image2']
            if 'image3' in request.FILES:
                product.image3 = request.FILES['image3']
            if 'image4' in request.FILES:
                product.image4 = request.FILES['image4']

            product.in_stock = request.POST.get('in_stock') == 'on'
            product.stock_level = request.POST.get('stock_level', product.stock_level)
            product.has_variations = request.POST.get('has_variations') == 'on'
            product.for_hire = request.POST.get('for_hire') == 'on'
            product.for_purchase = request.POST.get('for_purchase') == 'on'
            product.for_pickup = request.POST.get('for_pickup') == 'on'
            product.pickup_location = request.POST.get('pickup_location') if product.for_pickup else None
            product.latitude = request.POST.get('latitude') if product.for_pickup else None
            product.longitude = request.POST.get('longitude') if product.for_pickup else None
            product.can_deliver = request.POST.get('can_deliver') == 'on'
            product.main_colour_theme = request.POST.get('main_colour_theme', product.main_colour_theme)
            product.setup_packdown_fee = request.POST.get('setup_packdown_fee') == 'on'
            product.setup_packdown_fee_amount = request.POST.get('setup_packdown_fee_amount') if product.setup_packdown_fee else None

            product.save()

            if product.has_variations:
                variation_names = [name for name in request.POST if name.startswith('variation_names_')]
                variation_values = [name for name in request.POST if name.startswith('variation_values_')]
                price_varies = [name for name in request.POST if name.startswith('price_varies_')]
                variation_prices = [name for name in request.POST if name.startswith('variation_prices_')]
                variation_value_ids = [name for name in request.POST if name.startswith('variation_value_ids_')]

                # Delete variations not in the request
                product.variations.exclude(name__in=[request.POST[name] for name in variation_names]).delete()

                variation_map = {}
                for var_name in variation_names:
                    var_index = var_name.split('_')[-1]
                    if var_index not in variation_map:
                        variation_map[var_index] = {
                            'name': request.POST[var_name],
                            'values': [],
                            'prices': [],
                            'price_varies': [],
                            'value_ids': []
                        }

                for var_value in variation_values:
                    var_index, val_index = var_value.split('_')[-2:]
                    variation_map[var_index]['values'].append(request.POST[var_value])
                    price_varies_key = f'price_varies_{var_index}_{val_index}'
                    variation_map[var_index]['price_varies'].append(price_varies_key in request.POST)
                    price_key = f'variation_prices_{var_index}_{val_index}'
                    variation_map[var_index]['prices'].append(request.POST.get(price_key) or None)
                    value_id_key = f'variation_value_ids_{var_index}_{val_index}'
                    variation_map[var_index]['value_ids'].append(request.POST.get(value_id_key) or None)

                for var_index, var_data in variation_map.items():
                    variation, created = Variation.objects.get_or_create(product=product, name=var_data['name'])
                    variation.values.exclude(id__in=[value_id for value_id in var_data['value_ids'] if value_id]).delete()

                    for value, price, price_varies, value_id in zip(var_data['values'], var_data['prices'], var_data['price_varies'], var_data['value_ids']):
                        if value is not None:
                            if value_id:
                                try:
                                    product_variation = ProductVariation.objects.get(id=value_id)
                                    product_variation.value = value
                                    product_variation.price_varies = price_varies
                                    product_variation.price = Decimal(price) if price_varies and price else None
                                    product_variation.save()
                                except ProductVariation.DoesNotExist:
                                    product_variation = ProductVariation.objects.create(
                                        variation=variation,
                                        value=value,
                                        price=Decimal(price) if price_varies and price else None,
                                        price_varies=price_varies
                                    )
                            else:
                                product_variation = ProductVariation.objects.create(
                                    variation=variation,
                                    value=value,
                                    price=Decimal(price) if price_varies and price else None,
                                    price_varies=price_varies
                                )
            messages.success(request, "Product has been updated successfully.")
            return redirect('product_detail', business_slug=business.business_slug, product_slug=product.product_slug)
        else:
            return redirect('product_detail', business_slug=business.business_slug, product_slug=product.product_slug)

@login_required
@require_POST
def delete_variation(request, variation_id):
    try:
        variation = ProductVariation.objects.get(id=variation_id)
        if variation.variation.product.business.seller == request.user:
            variation.delete()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)
    except ProductVariation.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Variation not found'}, status=404)


class ServiceCreateView(LoginRequiredMixin, View):
    def get(self, request, business_slug):
        business = get_object_or_404(Business, business_slug=business_slug, seller=request.user)
        categories = ServiceCategory.objects.all()
        return render(request, 'event/service_create.html', {'business': business, 'categories': categories})

    def post(self, request, business_slug):
        print("ServiceCreateView POST method called")
        business = get_object_or_404(Business, business_slug=business_slug, seller=request.user)
        if business.seller == request.user:
            print(f"POST data: {request.POST}")

            def parse_decimal(value):
                if value in (None, ''):
                    return None
                try:
                    return Decimal(value)
                except InvalidOperation:
                    print(f"Invalid decimal value: {value}")
                    return None

            name = request.POST.get('name')
            description = request.POST.get('description')
            hire_price = parse_decimal(request.POST.get('hire_price'))
            available_by_quotation_only = request.POST.get('available_by_quotation_only') == 'on'
            setup_packdown_fee = request.POST.get('setup_packdown_fee') == 'on'
            setup_packdown_fee_amount = parse_decimal(request.POST.get('setup_packdown_fee_amount'))
            has_variations = request.POST.get('has_variations') == 'on'
            category_id = request.POST.get('category')
            category = get_object_or_404(ServiceCategory, id=category_id)

            print(f"Parsed data: name={name}, hire_price={hire_price}, "
                  f"setup_packdown_fee={setup_packdown_fee}, "
                  f"setup_packdown_fee_amount={setup_packdown_fee_amount}, "
                  f"has_variations={has_variations}")

            try:
                service = Service.objects.create(
                    name=name,
                    description=description,
                    hire_price=hire_price,
                    available_by_quotation_only=available_by_quotation_only,
                    setup_packdown_fee=setup_packdown_fee,
                    setup_packdown_fee_amount=setup_packdown_fee_amount,
                    has_variations=has_variations,
                    business=business,
                    category=category
                )
                print(f"Service created: {service}")
            except Exception as e:
                print(f"Error creating service: {e}")
                raise

            images = request.FILES.getlist('images')
            print(f"Number of images: {len(images)}")
            for index, image in enumerate(images):
                service_image = ServiceImage.objects.create(service=service, image=image)
                print(f"Created ServiceImage: {service_image}")
                if index == 0:
                    service.image = service_image.image
                    service.save()
                    print("Set first image as main service image")

            if has_variations:
                variation_names = [name for name in request.POST if name.startswith('variation_names_')]
                print(f"Variation names: {variation_names}")

                for var_name in variation_names:
                    var_index = var_name.split('_')[-1]
                    print(f"Processing variation: {var_name}")
                    values = request.POST.getlist(f'variation_values_{var_index}[]')
                    price_varies = request.POST.getlist(f'price_varies_{var_index}[]')
                    prices = request.POST.getlist(f'variation_prices_{var_index}[]')

                    max_length = max(len(values), len(price_varies), len(prices))
                    values += [None] * (max_length - len(values))
                    price_varies += ['off'] * (max_length - len(price_varies))
                    prices += [''] * (max_length - len(prices))

                    print(f"Normalized Values: {values}")
                    print(f"Normalized Price varies: {price_varies}")
                    print(f"Normalized Prices: {prices}")

                    variation = ServiceVariation.objects.create(
                        service=service,
                        name=request.POST[var_name]
                    )
                    print(f"Created ServiceVariation: {variation}")

                    for value, varies, price in zip(values, price_varies, prices):
                        if value is not None:
                            price_value = parse_decimal(price)
                            price_varies_bool = price_value is not None
                            print(f"Creating ServiceVariationOption: value={value}, "
                                  f"price_varies={price_varies_bool}, price={price_value}")

                            try:
                                option = ServiceVariationOption.objects.create(
                                    variation=variation,
                                    value=value,
                                    price=price_value,
                                    price_varies=price_varies_bool
                                )
                                print(f"Created ServiceVariationOption: {option}")
                            except Exception as e:
                                print(f"Error creating ServiceVariationOption: {e}")
                                raise

            messages.success(request, "Service created successfully.")
            return redirect('service_detail', business_slug=business.business_slug, service_slug=service.service_slug)
        else:
            print("User not authorized to add services to this business")
            categories = ServiceCategory.objects.all()
            return render(request, 'event/service_create.html', {
                'business': business, 
                'categories': categories, 
                'error': 'You are not authorized to add services to this business.'
            })


class ServiceEditView(LoginRequiredMixin, View):
    def get(self, request, business_slug, service_slug):
        business = get_object_or_404(Business, business_slug=business_slug, seller=request.user)
        service = get_object_or_404(Service, service_slug=service_slug, business=business)
        categories = ServiceCategory.objects.all()
        variations = service.variations.all()
        service_variations_with_values = {}
        for variation in variations:
            variation_options = ServiceVariationOption.objects.filter(variation=variation)
            service_variations_with_values[variation.name] = list(variation_options.values('id', 'value', 'price', 'price_varies'))

        return render(request, 'event/service_edit.html', {
            'service': service,
            'business': business,
            'categories': categories,
            'service_variations_with_values': service_variations_with_values,
        })

    def post(self, request, business_slug, service_slug):
        business = get_object_or_404(Business, business_slug=business_slug, seller=request.user)
        service = get_object_or_404(Service, service_slug=service_slug, business=business)

        if request.user == business.seller:
            service.name = request.POST.get('name', service.name)
            service.description = request.POST.get('description', service.description)
            service.hire_price = request.POST.get('hire_price', service.hire_price)
            service.available_by_quotation_only = request.POST.get('available_by_quotation_only') == 'on'
            service.setup_packdown_fee = request.POST.get('setup_packdown_fee') == 'on'
            service.setup_packdown_fee_amount = request.POST.get('setup_packdown_fee_amount') if service.setup_packdown_fee else None
            service.category_id = request.POST.get('category', service.category_id)
            service.save()

            if service.has_variations:
                variation_names = [name for name in request.POST if name.startswith('variation_names_')]
                variation_values = [name for name in request.POST if name.startswith('variation_values_')]
                price_varies = [name for name in request.POST if name.startswith('price_varies_')]
                variation_prices = [name for name in request.POST if name.startswith('variation_prices_')]
                variation_value_ids = [name for name in request.POST if name.startswith('variation_value_ids_')]

                service.variations.exclude(name__in=[request.POST[name] for name in variation_names]).delete()

                variation_map = {}
                for var_name in variation_names:
                    var_index = var_name.split('_')[-1]
                    if var_index not in variation_map:
                        variation_map[var_index] = {
                            'name': request.POST[var_name],
                            'values': [],
                            'prices': [],
                            'price_varies': [],
                            'value_ids': []
                        }

                for var_value in variation_values:
                    var_index, val_index = var_value.split('_')[-2:]
                    variation_map[var_index]['values'].append(request.POST[var_value])
                    price_varies_key = f'price_varies_{var_index}_{val_index}'
                    variation_map[var_index]['price_varies'].append(price_varies_key in request.POST)
                    price_key = f'variation_prices_{var_index}_{val_index}'
                    variation_map[var_index]['prices'].append(request.POST.get(price_key) or None)
                    value_id_key = f'variation_value_ids_{var_index}_{val_index}'
                    variation_map[var_index]['value_ids'].append(request.POST.get(value_id_key) or None)

                for var_index, var_data in variation_map.items():
                    variation, created = ServiceVariation.objects.get_or_create(service=service, name=var_data['name'])
                    variation.options.exclude(id__in=[value_id for value_id in var_data['value_ids'] if value_id]).delete()

                    for value, price, price_varies, value_id in zip(var_data['values'], var_data['prices'], var_data['price_varies'], var_data['value_ids']):
                        if value is not None:
                            if value_id:
                                try:
                                    service_variation_option = ServiceVariationOption.objects.get(id=value_id)
                                    service_variation_option.value = value
                                    service_variation_option.price_varies = price_varies
                                    service_variation_option.price = Decimal(price) if price_varies and price else None
                                    service_variation_option.save()
                                except ServiceVariationOption.DoesNotExist:
                                    service_variation_option = ServiceVariationOption.objects.create(
                                        variation=variation,
                                        value=value,
                                        price=Decimal(price) if price_varies and price else None,
                                        price_varies=price_varies
                                    )
                            else:
                                service_variation_option = ServiceVariationOption.objects.create(
                                    variation=variation,
                                    value=value,
                                    price=Decimal(price) if price_varies and price else None,
                                    price_varies=price_varies
                                )

            images = request.FILES.getlist('images')
            for image in images:
                ServiceImage.objects.create(service=service, image=image)
            messages.success(request, "Service updated successfully.")
            return redirect('service_detail', business_slug=business.business_slug, service_slug=service.service_slug)
        else:
            return redirect('service_detail', business_slug=business.business_slug, service_slug=service.service_slug)


class ServiceDetailView(View):
    def get(self, request, business_slug=None, service_slug=None):
        business = get_object_or_404(Business, business_slug=business_slug)
        service = get_object_or_404(Service, service_slug=service_slug, business=business)
        
        reviews = service.reviews.all()

        star_percentages = {
            5: service.star_rating_percentage(5),
            4: service.star_rating_percentage(4),
            3: service.star_rating_percentage(3),
            2: service.star_rating_percentage(2),
            1: service.star_rating_percentage(1),
        }

        similar_services = Service.objects.filter(
            category=service.category
        ).exclude(id=service.id)[:4]

        context = {
            'service': service,
            'business': business,
            'reviews': reviews,
            'star_percentages': star_percentages,
            'overall_review': service.overall_review,
            'similar_services': similar_services,
        }

        return render(request, 'event/service_detail.html', context)

@require_POST
def delete_service_image(request, image_id):
    image = get_object_or_404(ServiceImage, id=image_id)
    service = image.service

    if request.user == service.business.seller and service.images.count() > 1:
        image_url = image.image.url
        image.delete()
        return JsonResponse({'success': True, 'image_url': image_url})
    else:
        return JsonResponse({'success': False})


class CartView(View):
    @method_decorator(require_POST)
    def validate_delivery(self, request):
        data = json.loads(request.body)
        customer_lat = data.get('lat')
        customer_lng = data.get('lng')
        
        cart_items = Cart.objects.filter(user=request.user).select_related(
            'product__business', 'service__business'
        ).prefetch_related(
            Prefetch('product__business__delivery_radius_options', 
                    queryset=DeliveryByRadius.objects.order_by('radius'))
        )
        
        invalid_items = []
        
        for item in cart_items:
            if item.product:
                # Skip products that are pickup-only
                if item.product.for_pickup and not item.product.can_deliver:
                    continue
                
                business = item.product.business
                item_name = item.product.name
            else:
                business = item.service.business
                item_name = item.service.name
            
            business_coords = (business.latitude, business.longitude)
            customer_coords = (customer_lat, customer_lng)
            distance = geodesic(business_coords, customer_coords).km

            if business.delivery_type == 'price_per_way':
                if distance > business.max_delivery_distance:
                    invalid_items.append(f"{item_name} by {business.business_name} exceeds the delivery distance limit.")
            elif business.delivery_type == 'by_radius':
                delivery_radius = business.delivery_radius_options.filter(radius__gte=distance).first()
                if not delivery_radius:
                    invalid_items.append(f"{item_name} by {business.business_name} exceeds the maximum delivery radius.")
        
        if invalid_items:
            message = "The following items exceed the delivery limit: " + ", ".join(invalid_items)
            return JsonResponse({'valid': False, 'message': message})
        else:
            return JsonResponse({'valid': True})

    def get(self, request):
        cart_items = Cart.objects.filter(user=request.user).select_related(
            'product__business', 'service__business'
        ).prefetch_related(
            'variations__product_variation', 
            'variations__service_variation'
        )
        
        cart_data = []
        total_price = Decimal('0.00')
        delivery_methods = {}
        
        for item in cart_items:
            item.calculate_total_price()
            item_data = {
                'id': item.id,
                'price': item.price,
                'quantity': item.quantity,
                'total_price': item.price * item.quantity,
                'hire': item.hire,
                'is_product': item.product is not None,
                'is_service': item.service is not None,
                'variations': [],
                'for_pickup': item.product.for_pickup if item.product else False,
                'can_deliver': item.product.can_deliver if item.product else True,
                'business_id': item.product.business.id if item.product else item.service.business.id,
                'price_per_way': item.product.business.delivery_price_per_way if item.product else item.service.business.delivery_price_per_way,
            }
            
            if item.product:
                item_data.update({
                    'name': item.product.name,
                    'image': item.product.image.url,
                    'business_name': item.product.business.business_name,
                    'base_price': item.product.hire_price if item.hire else item.product.purchase_price,
                    'pickup_location': item.product.pickup_location,
                })
            elif item.service:
                item_data.update({
                    'name': item.service.name,
                    'image': item.service.image.url,
                    'business_name': item.service.business.business_name,
                    'base_price': item.service.hire_price,
                })
            
            for variation in item.variations.all():
                if variation.product_variation:
                    item_data['variations'].append({
                        'name': variation.product_variation.variation.name,
                        'value': variation.product_variation.value,
                        'price': variation.product_variation.price or 0
                    })
                elif variation.service_variation:
                    item_data['variations'].append({
                        'name': variation.service_variation.variation.name,
                        'value': variation.service_variation.value,
                        'price': variation.service_variation.price or 0
                    })
            
            cart_data.append(item_data)
            total_price += item_data['total_price']

            if item.product:
                if item.product.for_pickup and item.product.can_deliver:
                    delivery_methods[str(item.id)] = 'both'
                elif item.product.can_deliver:
                    delivery_methods[str(item.id)] = 'delivery'
                elif item.product.for_pickup:
                    delivery_methods[str(item.id)] = 'pickup'
            else:
                delivery_methods[str(item.id)] = 'delivery'

        delivery_fee = calculate_delivery_fee(cart_items, delivery_methods)
        setup_packdown_fee = calculate_setup_packdown_fee(cart_items)

        context = {
            'cart_items': cart_data,
            'cart_total': total_price,
            'delivery_fee': delivery_fee,
            'setup_packdown_fee': setup_packdown_fee,
            'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
            'delivery_methods': delivery_methods,
        }
        return render(request, 'event/cart.html', context)

    @method_decorator(login_required)
    def post(self, request):
        if 'product_id' in request.POST:
            return self.add_product_to_cart(request)
        elif 'service_id' in request.POST:
            return self.add_service_to_cart(request)
        else:
            messages.error(request, "Invalid request.")
            return self.handle_response(request, False, "Invalid request")

    
    def add_product_to_cart(self, request):
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 1))
        selected_variations = request.POST.getlist('variations')
        hire = request.POST.get('hire') == 'true'

        if not product_id:
            messages.error(request, "No product selected.")
            return self.handle_response(request, False, "No product selected")

        product = get_object_or_404(Product, id=product_id)

        # Filter out empty strings from selected variations
        selected_variations = [var for var in selected_variations if var]

        variation_categories = product.variations.count()

        if product.has_variations and len(selected_variations) != variation_categories:
            messages.error(request, f"Please select all {variation_categories} variations.")
            return redirect('product_detail', business_slug=product.business.business_slug, product_slug=product.product_slug)

        variation_key = "-".join(sorted(selected_variations))

        base_price = product.hire_price if hire else product.purchase_price
        price = base_price
        for variation_id in selected_variations:
            variation = get_object_or_404(ProductVariation, id=variation_id)
            if variation.price:
                price += variation.price

        # Determine the appropriate delivery method
        if product.for_pickup and not product.can_deliver:
            delivery_method = 'pickup'
        elif not product.for_pickup and product.can_deliver:
            delivery_method = 'delivery'
        else:
            delivery_method = 'both'  # This will allow the user to choose in checkout

        cart_item, created = Cart.objects.get_or_create(
            user=request.user,
            product=product,
            variation_key=variation_key,
            defaults={
                'quantity': quantity, 
                'price': price, 
                'hire': hire,
                'delivery_method': delivery_method
            }
        )

        if not created:
            cart_item.quantity += quantity
            cart_item.price = price
            cart_item.hire = hire
            cart_item.delivery_method = delivery_method
            cart_item.save()

        CartItemVariation.objects.filter(cart=cart_item).delete()
        for variation_id in selected_variations:
            product_variation = get_object_or_404(ProductVariation, id=variation_id)
            CartItemVariation.objects.create(cart=cart_item, product_variation=product_variation)

        messages.success(request, f"{product.name} has been added to your cart.")
        return self.handle_response(request, True, f"{product.name} has been added to your cart.")

    
    def add_service_to_cart(self, request):
        service_id = request.POST.get('service_id')
        quantity = int(request.POST.get('quantity', 1))
        selected_options = request.POST.getlist('options')
        price = request.POST.get('price')

        if not service_id:
            messages.error(request, "No service selected.")
            return self.handle_response(request, False, "No service selected")

        service = get_object_or_404(Service, id=service_id)

        if service.available_by_quotation_only:
            if not price:
                messages.error(request, "Price is required for this service.")
                return self.handle_response(request, False, "Price is required")
            try:
                price = Decimal(price)
            except InvalidOperation:
                messages.error(request, "Invalid price format.")
                return self.handle_response(request, False, "Invalid price format")
        else:
            price = service.hire_price or Decimal('0')

        selected_options = [opt for opt in selected_options if opt]

        variation_categories = service.variations.count()

        if service.has_variations and len(selected_options) != variation_categories:
            messages.error(request, f"Please select all {variation_categories} variations.")
            return self.handle_response(request, False, f"Please select all {variation_categories} variations")

        variation_key = "-".join(sorted(selected_options))

        for option_id in selected_options:
            option = get_object_or_404(ServiceVariationOption, id=option_id)
            if option.price:
                price += option.price

        cart_item, created = Cart.objects.get_or_create(
            user=request.user,
            service=service,
            variation_key=variation_key,
            defaults={
                'quantity': quantity, 
                'price': price, 
                'hire': True,
                'delivery_method': 'delivery'  # Services always use delivery
            }
        )

        if not created:
            cart_item.quantity += quantity
            cart_item.price = price
            cart_item.hire = True
            cart_item.delivery_method = 'delivery'
            cart_item.save()

        CartItemVariation.objects.filter(cart=cart_item).delete()
        for option_id in selected_options:
            service_option = get_object_or_404(ServiceVariationOption, id=option_id)
            CartItemVariation.objects.create(cart=cart_item, service_variation=service_option)

        messages.success(request, f"{service.name} has been added to your cart.")
        return self.handle_response(request, True, f"{service.name} has been added to your cart.")


    def handle_response(self, request, success, message):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': success, 'message': message})
        else:
            return redirect(request.META.get('HTTP_REFERER', reverse('home')))

    def update_quantity(self, request):
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            action = data.get('action')
            quantity = int(data.get('quantity', 1))
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)

        cart_item = get_object_or_404(Cart, id=item_id)

        if action == 'update':
            cart_item.quantity = quantity
        elif action == 'increase':
            cart_item.quantity += 1
        elif action == 'decrease':
            if cart_item.quantity > 1:
                cart_item.quantity -= 1

        cart_item.save()

        cart_items = Cart.objects.filter(user=request.user).prefetch_related('variations__product_variation', 'variations__service_variation')
        cart_data = []
        total_price = 0

        for item in cart_items:
            item.calculate_total_price()
            item_data = {
                'id': item.id,
                'price': item.price,
                'quantity': item.quantity,
                'total_price': item.price * item.quantity,
                'variations': [],
            }

            if item.product:
                item_data['name'] = item.product.name
                item_data['image'] = item.product.image.url
            elif item.service:
                item_data['name'] = item.service.name
                item_data['image'] = item.service.image.url

            for variation in item.variations.all():
                if variation.product_variation:
                    item_data['variations'].append({
                        'name': variation.product_variation.variation.name,
                        'value': variation.product_variation.value,
                        'price': variation.product_variation.price or 0
                    })
                elif variation.service_variation:
                    item_data['variations'].append({
                        'name': variation.service_variation.variation.name,
                        'value': variation.service_variation.value,
                        'price': variation.service_variation.price or 0
                    })

            cart_data.append(item_data)
            total_price += item_data['total_price']

        return JsonResponse({'success': True, 'items': cart_data, 'subtotal': float(total_price)})

    def delete_cart_item(self, request, cart_item_id):
        cart_item = get_object_or_404(Cart, id=cart_item_id, user=request.user)
        cart_item.delete()
        messages.success(request, "Item removed from cart.")
        return JsonResponse({'success': True})

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST':
            if request.path == '/cart/update_quantity/':
                return self.update_quantity(request, *args, **kwargs)
            elif request.path == '/cart/validate-delivery/':
                return self.validate_delivery(request, *args, **kwargs)
            else:
                return self.post(request, *args, **kwargs)
        elif request.method == 'DELETE':
            return self.delete_cart_item(request, *args, **kwargs)
        elif request.method == 'GET':
            if request.path == '/cart/data/':
                return self.get_cart_data(request)
            else:
                return self.get(request, *args, **kwargs)

        return super().dispatch(request, *args, **kwargs)
    
@csrf_exempt
def update_cart_coordinates(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_lat = data.get('lat')
            customer_lng = data.get('lng')

            if customer_lat is None or customer_lng is None:
                return JsonResponse({'success': False, 'message': 'Invalid coordinates'}, status=400)

            Cart.objects.filter(user=request.user).update(customer_lat=customer_lat, customer_lng=customer_lng)

            return JsonResponse({'success': True})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)

from collections import defaultdict
from django.db.models import Prefetch
import traceback

def calculate_delivery_fee(cart_items, delivery_methods):
    total_delivery_fee = Decimal('0.00')
    business_fees = {}

    for item in cart_items:
        business = item.product.business if item.product else item.service.business
        business_id = business.id
        customer_coords = (item.customer_lat, item.customer_lng)
        business_coords = (business.latitude, business.longitude)
        distance = geodesic(business_coords, customer_coords).km

        requires_delivery = False

        if item.service:
            requires_delivery = True
        elif item.product:
            delivery_method = delivery_methods.get(str(item.id))

            if item.product.for_pickup and not item.product.can_deliver:
                requires_delivery = False
            elif not item.product.for_pickup and item.product.can_deliver:
                requires_delivery = True
            elif item.product.for_pickup and item.product.can_deliver:
                requires_delivery = delivery_method == 'delivery'

        if requires_delivery:
            if business.delivery_type == 'price_per_way':
                delivery_fee = business.delivery_price_per_way * 2
            elif business.delivery_type == 'by_radius':
                delivery_radius = DeliveryByRadius.objects.filter(
                    business_id=business_id, 
                    radius__gte=distance
                ).order_by('radius').first()
                
                if delivery_radius:
                    delivery_fee = delivery_radius.price
                else:
                    delivery_fee = Decimal('0.00')
            else:
                delivery_fee = Decimal('0.00')

            if business_id in business_fees:
                business_fees[business_id] = max(business_fees[business_id], delivery_fee)
            else:
                business_fees[business_id] = delivery_fee

    total_delivery_fee = sum(business_fees.values())
    return total_delivery_fee

def calculate_setup_packdown_fee(cart_items):
    businesses = {}
    for item in cart_items:
        if item.product:
            business = item.product.business
            if item.product.setup_packdown_fee:
                if business.id not in businesses or item.product.setup_packdown_fee_amount > businesses[business.id]:
                    businesses[business.id] = item.product.setup_packdown_fee_amount
        elif item.service:
            business = item.service.business
            if item.service.setup_packdown_fee:
                if business.id not in businesses or item.service.setup_packdown_fee_amount > businesses[business.id]:
                    businesses[business.id] = item.service.setup_packdown_fee_amount

    return sum(businesses.values())

import json
from decimal import Decimal
from django.core.serializers.json import DjangoJSONEncoder


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

class CreateCheckoutSessionView(LoginRequiredMixin, View):
    def get(self, request):
        try:
            print("Starting GET request for CreateCheckoutSessionView")
            
            cart_items = Cart.objects.filter(user=request.user).select_related(
                'product', 'service', 'product__business', 'service__business'
            ).prefetch_related(
                'variations__product_variation__variation',
                'variations__service_variation__variation'
            )

            print(f"Found {cart_items.count()} cart items")

            if not cart_items.exists():
                print("No items in cart")
                return JsonResponse({'error': 'No items in cart'}, status=400)

            cart_items_data = self.get_cart_items_data(cart_items)
            print("Cart items data:", json.dumps(cart_items_data, cls=DecimalEncoder))

            businesses_terms = self.get_businesses_terms(cart_items)
            print("Businesses terms:", businesses_terms)

            context = {
                'cart_items': cart_items_data,
                'cart_items_json': json.dumps(cart_items_data, cls=DecimalEncoder),
                'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
                'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
                'businesses_terms': businesses_terms,
            }
            print("Cart items being sent to template:", json.dumps(cart_items_data, cls=DecimalEncoder))
            print("Rendering checkout.html with context")
            return render(request, 'event/checkout.html', context)
        except Exception as e:
            print(f"Error in CreateCheckoutSessionView.get: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)

    def get_cart_items_data(self, cart_items):
        print("Starting get_cart_items_data")
        cart_items_data = []
        for item in cart_items:
            try:
                business = item.product.business if item.product else item.service.business
                item_data = {
                    'id': item.id,
                    'name': item.product.name if item.product else item.service.name,
                    'business_name': business.business_name,
                    'quantity': item.quantity,
                    'price': float(item.price),
                    'item_total_price': float(item.price * item.quantity),
                    'variations': [
                        {
                            'variation_name': cv.product_variation.variation.name if cv.product_variation else cv.service_variation.variation.name,
                            'variation_value': cv.product_variation.value if cv.product_variation else cv.service_variation.value
                        }
                        for cv in item.variations.all()
                    ],
                    'hire': item.hire,
                    'image': item.product.image.url if item.product and item.product.image else (item.service.image.url if item.service and item.service.image else None),
                    'delivery_method': 'both' if item.product and item.product.for_pickup and item.product.can_deliver else ('pickup' if item.product and item.product.for_pickup else 'delivery'),
                    'pickup_location': item.product.pickup_location if item.product and item.product.for_pickup else None,
                    'setup_packdown_fee': item.product.setup_packdown_fee if item.product else item.service.setup_packdown_fee,
                    'setup_packdown_fee_amount': float(item.product.setup_packdown_fee_amount) if item.product and item.product.setup_packdown_fee else (float(item.service.setup_packdown_fee_amount) if item.service and item.service.setup_packdown_fee else 0),
                    'business': {
                        'id': business.id,
                        'delivery_type': business.delivery_type,
                        'max_delivery_distance': business.max_delivery_distance,
                        'delivery_price_per_way': business.delivery_price_per_way,
                        'delivery_radius_options': [
                            {'radius': option.radius, 'price': float(option.price)}
                            for option in business.delivery_radius_options.all()
                        ],
                        'latitude': float(business.latitude) if business.latitude else None,
                        'longitude': float(business.longitude) if business.longitude else None,
                    },
                    'customer_lat': float(item.customer_lat) if item.customer_lat else None,
                    'customer_lng': float(item.customer_lng) if item.customer_lng else None,
                }
                cart_items_data.append(item_data)
                print(f"Added item data for item {item.id}")
            except Exception as e:
                print(f"Error processing item {item.id}: {str(e)}")
        print(f"Finished get_cart_items_data, processed {len(cart_items_data)} items")
        return cart_items_data

    def get_businesses_terms(self, cart_items):
        print("Starting get_businesses_terms")
        businesses_terms = {}
        for item in cart_items:
            try:
                business = item.product.business if item.product else item.service.business
                if business.id not in businesses_terms:
                    businesses_terms[business.id] = {
                        'name': business.business_name,
                        'terms': business.terms_and_conditions,
                        'terms_pdf': business.terms_and_conditions_pdf.url if business.terms_and_conditions_pdf else None
                    }
                    print(f"Added terms for business {business.id}")
            except Exception as e:
                print(f"Error processing terms for business {business.id}: {str(e)}")
        print(f"Finished get_businesses_terms, processed terms for {len(businesses_terms)} businesses")
        return businesses_terms

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            
            # Log the received data
            print("Received data:", data)
            
            cart_items = Cart.objects.filter(user=request.user).select_related(
                'product', 'service', 'product__business', 'service__business'
            ).prefetch_related('variations__product_variation', 'variations__service_variation')

            if not cart_items.exists():
                return JsonResponse({'error': 'No items in cart'}, status=400)

            # Log cart items
            print("Cart items:", list(cart_items.values()))

            subtotal = Decimal(str(data.get('subtotal', '0.00')))
            delivery_fee = Decimal(str(data.get('delivery_fee', '0.00')))
            setup_packdown_fee = Decimal(str(data.get('setup_packdown_fee', '0.00')))
            total_price = Decimal(str(data.get('total_price', '0.00')))
            business_delivery_fees = data.get('businessDeliveryFees', {})
            afterpay_fee = Decimal(str(data.get('afterpay_fee', '0.00')))

            # Log the calculated fees
            print(f"Subtotal: {subtotal}, Delivery fee: {delivery_fee}, Setup/Packdown fee: {setup_packdown_fee}, Total price: {total_price}, Afterpay fee: {afterpay_fee}")

            current_domain = request.get_host()
            protocol = 'https' if request.is_secure() else 'http'
            YOUR_DOMAIN = f"{protocol}://{current_domain}"

            delivery_methods = data.get('delivery_methods', {})
            payment_method = data.get('payment_method', 'card')
            signatures = data.get('signatures', {})

            # Log delivery methods and payment method
            print(f"Delivery methods: {delivery_methods}, Payment method: {payment_method}")

            line_items = self.create_line_items(cart_items, delivery_fee, setup_packdown_fee, afterpay_fee, YOUR_DOMAIN)

            # Log line items
            print("Line items:", line_items)

            checkout_session = stripe.checkout.Session.create(
                payment_method_types=[payment_method],
                line_items=line_items,
                mode='payment',
                success_url=YOUR_DOMAIN + reverse('success'),
                cancel_url=YOUR_DOMAIN + reverse('cancel'),
                payment_intent_data={
                    'shipping': {
                        'name': request.user.username,
                        'address': {
                            'line1': data.get('billing_address', ''),
                            'city': data.get('city', ''),
                            'state': data.get('state', ''),
                            'postal_code': data.get('postal_code', ''),
                            'country': 'AU',
                        },
                    },
                },
            )

            self.save_session_data(request, checkout_session, data, cart_items, delivery_methods, 
                               subtotal, delivery_fee, setup_packdown_fee, total_price, afterpay_fee,
                               business_delivery_fees)

            return JsonResponse({'id': checkout_session.id})
        except Exception as e:
            print(f"Error in CreateCheckoutSessionView.post: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)

    def create_line_items(self, cart_items, delivery_fee, setup_packdown_fee, afterpay_fee, domain):
        line_items = []
        for item in cart_items:
            if item.product:
                name = item.product.name
                image = item.product.image.url if item.product.image else None
            else:
                name = item.service.name
                image = item.service.image.url if item.service and item.service.image else None

            line_items.append({
                'price_data': {
                    'currency': 'aud',
                    'product_data': {
                        'name': name,
                        'images': [f"{domain}{image}"] if image else [],
                    },
                    'unit_amount': int(float(item.price) * 100),
                },
                'quantity': item.quantity,
            })

        if delivery_fee > 0:
            line_items.append({
                'price_data': {
                    'currency': 'aud',
                    'product_data': {
                        'name': 'Delivery Fee',
                    },
                    'unit_amount': int(delivery_fee * 100),
                },
                'quantity': 1,
            })

        if setup_packdown_fee > 0:
            line_items.append({
                'price_data': {
                    'currency': 'aud',
                    'product_data': {
                        'name': 'Setup/Packdown Fee',
                    },
                    'unit_amount': int(setup_packdown_fee * 100),
                },
                'quantity': 1,
            })

        if afterpay_fee > 0:
            line_items.append({
                'price_data': {
                    'currency': 'aud',
                    'product_data': {
                        'name': 'Afterpay Fee',
                    },
                    'unit_amount': int(afterpay_fee * 100),
                },
                'quantity': 1,
            })

        return line_items

    def save_session_data(self, request, checkout_session, data, cart_items, delivery_methods, 
                      subtotal, delivery_fee, setup_packdown_fee, total_price, afterpay_fee,
                      business_delivery_fees):
        request.session['checkout_session_id'] = checkout_session.id
        request.session['business_items'] = self.get_business_items(cart_items, delivery_methods)
        request.session['address'] = data.get('address')
        request.session['billing_address'] = data.get('billing_address')
        request.session['city'] = data.get('city')
        request.session['state'] = data.get('state')
        request.session['postal_code'] = data.get('postal_code')
        request.session['note'] = data.get('note')
        request.session['event_date'] = data.get('event_date')
        request.session['event_time'] = data.get('event_time')
        request.session['cart_items'] = self.get_cart_items(cart_items, delivery_methods)
        request.session['delivery_fee'] = float(delivery_fee)
        request.session['setup_packdown_fee'] = float(setup_packdown_fee)
        request.session['subtotal'] = float(subtotal)
        request.session['total_price'] = float(total_price)
        request.session['afterpay_fee'] = float(afterpay_fee)
        request.session['delivery_methods'] = delivery_methods
        request.session['payment_method'] = data.get('payment_method')
        request.session['signatures'] = data.get('signatures')
        request.session['payment_intent_id'] = checkout_session.payment_intent
        request.session['business_delivery_fees'] = business_delivery_fees
    
    def get_business_items(self, cart_items, delivery_methods):
        business_items = {}
        for item in cart_items:
            business = item.product.business if item.product else item.service.business
            if str(business.id) not in business_items:
                business_items[str(business.id)] = []
            
            business_items[str(business.id)].append({
                'amount': int(float(item.price) * 100 * item.quantity),
                'business': business.stripe_account_id,
                'item_id': item.product.id if item.product else item.service.id,
                'item_type': 'product' if item.product else 'service',
                'quantity': item.quantity,
                'total_price': float(item.price * item.quantity),
                'variations': [
                    {
                        'variation_name': cv.product_variation.variation.name if cv.product_variation else cv.service_variation.variation.name,
                        'variation_value': cv.product_variation.value if cv.product_variation else cv.service_variation.value
                    }
                    for cv in item.variations.all()
                ],
                'price': float(item.price),
                'hire': item.hire,
                'delivery_method': delivery_methods.get(str(item.id), 'delivery'),
                'image': item.product.image.url if item.product and item.product.image else (item.service.image.url if item.service and item.service.image else None)
            })
        return business_items

    def get_cart_items(self, cart_items, delivery_methods):
        cart_items_data = []
        for item in cart_items:
            item_data = {
                'id': item.id,
                'name': item.product.name if item.product else item.service.name,
                'business_name': item.product.business.business_name if item.product else item.service.business.business_name,
                'quantity': item.quantity,
                'price': float(item.price),
                'item_total_price': float(item.price * item.quantity),
                'variations': [
                    {
                        'variation_name': cv.product_variation.variation.name if cv.product_variation else cv.service_variation.variation.name,
                        'variation_value': cv.product_variation.value if cv.product_variation else cv.service_variation.value
                    }
                    for cv in item.variations.all()
                ],
                'hire': item.hire,
                'image': item.product.image.url if item.product and item.product.image else (item.service.image.url if item.service and item.service.image else None),
                'delivery_method': delivery_methods.get(str(item.id), 'delivery'),
                'item_type': 'product' if item.product else 'service',
                'pickup_location': item.product.pickup_location if item.product and item.product.for_pickup else None,
                'setup_packdown_fee': item.product.setup_packdown_fee if item.product else item.service.setup_packdown_fee,
                'setup_packdown_fee_amount': float(item.product.setup_packdown_fee_amount) if item.product and item.product.setup_packdown_fee else (float(item.service.setup_packdown_fee_amount) if item.service and item.service.setup_packdown_fee else 0),
            }
            cart_items_data.append(item_data)
        return cart_items_data


class PaymentSuccessView(LoginRequiredMixin, View):
    def get(self, request):
        print("PaymentSuccessView: Starting get method")
        business_delivery_fees = request.session.get('business_delivery_fees', {})
        checkout_session_id = request.session.get('checkout_session_id')
        signatures = request.session.get('signatures', {})
        print(f"PaymentSuccessView: Checkout session ID: {checkout_session_id}")

        try:
            session = stripe.checkout.Session.retrieve(checkout_session_id)
            payment_intent_id = session.payment_intent
            print(f"PaymentSuccessView: Retrieved Stripe session. Payment intent ID: {payment_intent_id}")

            ref_code = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
            print(f"PaymentSuccessView: Generated ref_code: {ref_code}")

            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user,
                    ref_code=ref_code,
                    total_amount=request.session.get('total_price'),
                    address=request.session.get('address'),
                    billing_address=request.session.get('billing_address'),
                    city=request.session.get('city'),
                    state=request.session.get('state'),
                    postal_code=request.session.get('postal_code'),
                    note=request.session.get('note'),
                    event_date=request.session.get('event_date'),
                    event_time=datetime.strptime(request.session.get('event_time'), '%H:%M').time() if request.session.get('event_time') else None,
                    status='pending',
                    delivery_fee=request.session.get('delivery_fee'),
                    setup_packdown_fee=request.session.get('setup_packdown_fee'),
                    payment_method=request.session.get('payment_method'),
                    payment_intent=payment_intent_id,
                    afterpay_fee=request.session.get('afterpay_fee'),
                    business_delivery_fees=request.session.get('business_delivery_fees'),
                )
                print(f"PaymentSuccessView: Created Order with ID: {order.id}")


                # Save signatures
                for business_id, signature_data in signatures.items():
                    business = Business.objects.get(id=business_id)
                    signature_image = self.base64_to_image(signature_data)
                    OrderTermsSignature.objects.create(
                        order=order,
                        business=business,
                        signature=signature_image
                    )
                print(f"PaymentSuccessView: Saved {len(signatures)} signatures")

                # Fetch the cart items for the user
                cart_items = Cart.objects.filter(user=request.user)
                business_items = {}

                for cart_item in cart_items:
                    item_type = 'product' if cart_item.product else 'service'
                    print(f"PaymentSuccessView: Processing {item_type} in cart with ID: {cart_item.id}")

                    if item_type == 'product':
                        product = cart_item.product
                        service = None
                        business = product.business
                        print(f"PaymentSuccessView: Found Product with ID: {product.id}")
                    elif item_type == 'service':
                        service = cart_item.service
                        product = None
                        business = service.business
                        print(f"PaymentSuccessView: Found Service with ID: {service.id}")
                    else:
                        print(f"PaymentSuccessView: Unknown item type for cart item ID: {cart_item.id}")
                        continue

                    # Creating the order item
                    order_item = OrderItem.objects.create(
                        order=order,
                        product=product,
                        service=service,
                        quantity=cart_item.quantity,
                        price=cart_item.price,
                        variations=self.get_variations(cart_item),
                        hire=cart_item.hire,
                        delivery_method=cart_item.delivery_method,
                    )
                    print(f"PaymentSuccessView: Created OrderItem with ID: {order_item.id}")

                    OrderApproval.objects.get_or_create(order=order, business=business)
                    print(f"PaymentSuccessView: Created OrderApproval for business: {business.id}")

                    # Group items by business
                    business_id = business.id
                    if business_id not in business_items:
                        business_items[business_id] = []
                    business_items[business_id].append({
                        'id': cart_item.id,
                        'name': product.name if product else service.name,
                        'business_name': business.business_name,
                        'quantity': cart_item.quantity,
                        'price': cart_item.price,
                        'item_total_price': cart_item.price * cart_item.quantity,
                        'variations': self.get_variations(cart_item),
                        'hire': cart_item.hire,
                        'image': product.image.url if product else service.image.url,
                        'delivery_method': cart_item.delivery_method,
                        'pickup_location': product.pickup_location if product and product.for_pickup else None,
                        'setup_packdown_fee': cart_item.service.setup_packdown_fee if service else product.setup_packdown_fee,
                        'setup_packdown_fee_amount': cart_item.service.setup_packdown_fee_amount if service else product.setup_packdown_fee_amount,
                    })

                # Clear the cart after creating the order
                cart_items.delete()

                self.send_order_emails(order, business_items, list(business_items.values()), business_delivery_fees)

                # Clear session data related to the checkout process
                for key in [
                    'checkout_session_id', 'cart_items', 'address', 'city', 'state', 
                    'postal_code', 'note', 'event_date', 'event_time', 'delivery_methods', 'signatures', 
                    'subtotal', 'total_price', 'delivery_fee', 'setup_packdown_fee', 'afterpay_fee'
                ]:
                    if key in request.session:
                        del request.session[key]

                print("PaymentSuccessView: Completed processing order")
                return render(request, 'event/success.html', {'order': order, 'total_price': request.session.get('total_price')})

        except Exception as e:
            print(f"PaymentSuccessView: Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)
        
    def base64_to_image(self, base64_string):
        # Remove the data URL prefix if present
        if 'data:' in base64_string and ';base64,' in base64_string:
            header, base64_string = base64_string.split(';base64,')

        # Decode the base64 string
        image_data = base64.b64decode(base64_string)

        # Create a BytesIO object
        image_file = BytesIO(image_data)

        # Create a Django ContentFile
        return ContentFile(image_file.getvalue(), name='signature.png')

    def get_variations(self, cart_item):
        """Helper method to get variations for the cart item."""
        variations = []
        for variation in cart_item.variations.all():
            if variation.product_variation:
                variations.append({
                    'variation_name': variation.product_variation.variation.name,
                    'variation_value': variation.product_variation.value
                })
            elif variation.service_variation:
                variations.append({
                    'variation_name': variation.service_variation.variation.name,
                    'variation_value': variation.service_variation.value
                })
        return variations

    def send_order_emails(self, order, business_items, cart_items, business_delivery_fees):
        try:
            domain = settings.SITE_URL
            
            # Flatten the list of cart items
            flat_cart_items = [item for sublist in cart_items for item in sublist]
            
            # Calculate subtotal
            subtotal = sum(Decimal(str(item['item_total_price'])) for item in flat_cart_items)
            total_price = order.total_amount
            
            customer_subject = f"Order Received - Pending Approval - {order.ref_code}"
            customer_message = render_to_string('event/customer_checkout_email.html', {
                'order': order,
                'cart_items': flat_cart_items,
                'total_price': total_price,
                'delivery_fee': order.delivery_fee,
                'setup_packdown_fee': order.setup_packdown_fee,
                'subtotal': subtotal,
                'afterpay_fee': order.afterpay_fee,
                'domain': domain
            })

            customer_email = EmailMultiAlternatives(
                subject=customer_subject,
                body="Your order has been placed.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[order.user.email]
            )
            customer_email.attach_alternative(customer_message, "text/html")
            customer_email.send()

            for business_id, items in business_items.items():
                business = Business.objects.get(id=business_id)
                business_cart_items = [item for item in flat_cart_items if item['business_name'] == business.business_name]
                business_subtotal = sum(Decimal(str(item['item_total_price'])) for item in business_cart_items)
                
                business_setup_packdown_fee = sum(
                    Decimal(str(item['setup_packdown_fee_amount'])) if item['setup_packdown_fee_amount'] else Decimal('0') 
                    for item in business_cart_items
                )
                
                business_delivery_fee = Decimal(str(business_delivery_fees.get(str(business_id), '0.00')))
                
                business_total = business_subtotal + business_setup_packdown_fee + business_delivery_fee
                
                review_url = f'{settings.SITE_URL}{reverse("review_order", args=[order.id, business.id])}'
                
                business_subject = f"New Order Received - Approval Required - {order.ref_code}"
                business_message = render_to_string('event/business_checkout_email.html', {
                    'order': order,
                    'business': business,
                    'cart_items': business_cart_items,
                    'business_subtotal': business_subtotal,
                    'business_setup_packdown_fee': business_setup_packdown_fee,
                    'business_delivery_fee': business_delivery_fee,
                    'business_total': business_total,
                    'review_url': review_url,
                    'domain': domain
                })
                
                business_email = EmailMultiAlternatives(
                    subject=business_subject,
                    body="You have received a new order.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[business.email]
                )
                business_email.attach_alternative(business_message, "text/html")
                business_email.send()

        except Exception as e:
            print(f"Error in send_order_emails: {str(e)}")
            import traceback
            traceback.print_exc()
            raise


class ReviewOrderView(UserPassesTestMixin, View):
    def test_func(self):
        order = get_object_or_404(Order, id=self.kwargs['order_id'])
        business = get_object_or_404(Business, id=self.kwargs['business_id'])
        return self.request.user == business.seller

    def get(self, request, order_id, business_id):
        print(f"ReviewOrderView: Starting get method for order {order_id} and business {business_id}")
        order = get_object_or_404(Order, id=order_id)
        business = get_object_or_404(Business, id=business_id)
        order_items = order.items.filter(
            models.Q(product__business=business) |
            models.Q(service__business=business)
        )
        print(f"ReviewOrderView: Found {order_items.count()} order items")

        context = {
            'order': order,
            'business': business,
            'order_items': order_items,
            'business_subtotal': sum(item.price * item.quantity for item in order_items),
            'business_setup_packdown_fee': sum(
                item.product.setup_packdown_fee_amount if item.product and item.product.setup_packdown_fee else
                item.service.setup_packdown_fee_amount if item.service and item.service.setup_packdown_fee else Decimal('0')
                for item in order_items
            ),
            'business_delivery_fee': Decimal(str(order.business_delivery_fees.get(str(business.id), '0.00'))),
        }
        context['business_total'] = context['business_subtotal'] + context['business_setup_packdown_fee'] + context['business_delivery_fee']
        print(f"ReviewOrderView: Context prepared with business_total: {context['business_total']}")
        return render(request, 'event/review_order.html', context)

    def post(self, request, order_id, business_id):
        order = get_object_or_404(Order, id=order_id)
        business = get_object_or_404(Business, id=business_id)

        with transaction.atomic():
            for item in order.items.filter(models.Q(product__business=business) | models.Q(service__business=business)):
                action = request.POST.get(f'item_{item.id}')
                if action == 'approve':
                    item.status = 'approved'
                    item.save()
                    self.process_payment(order, item)
                elif action == 'reject':
                    item.status = 'rejected'
                    item.save()
                    self.process_refund(order, item)

            order.update_status()
        
        if order.status in ['approved', 'partially_approved', 'partially_rejected', 'rejected']:
            self.send_consolidated_email(order)

        messages.success(request, "Your review has been submitted successfully.")
        return redirect('business_orders')

    def process_payment(self, order, item):
        # Calculate the business total
        business = item.product.business if item.product else item.service.business
        business_items = order.items.filter(
            models.Q(product__business=business) |
            models.Q(service__business=business)
        )
        
        business_subtotal = sum(i.price * i.quantity for i in business_items)
        
        business_setup_packdown_fee = sum(
            (i.product.setup_packdown_fee_amount if i.product and i.product.setup_packdown_fee else 0) or
            (i.service.setup_packdown_fee_amount if i.service and i.service.setup_packdown_fee else 0)
            for i in business_items
        )
        
        business_delivery_fee = Decimal(str(order.business_delivery_fees.get(str(business.id), '0.00')))
        business_total = business_subtotal + business_setup_packdown_fee + business_delivery_fee

        # Transfer 86% of the business total
        amount = int(business_total * Decimal('100') * Decimal('0.86'))
        
        # Create the transfer
        stripe.Transfer.create(
            amount=amount,
            currency='aud',
            destination=business.stripe_account_id,
            transfer_group=order.ref_code,
        )

    def process_refund(self, order, item):
        # Calculate the business total
        business = item.product.business if item.product else item.service.business
        business_items = order.items.filter(
            models.Q(product__business=business) |
            models.Q(service__business=business)
        )
        
        business_subtotal = sum(i.price * i.quantity for i in business_items)
        
        business_setup_packdown_fee = sum(
            (i.product.setup_packdown_fee_amount if i.product and i.product.setup_packdown_fee else 0) or
            (i.service.setup_packdown_fee_amount if i.service and i.service.setup_packdown_fee else 0)
            for i in business_items
        )
        
        business_delivery_fee = Decimal(str(order.business_delivery_fees.get(str(business.id), '0.00')))
        business_total = business_subtotal + business_setup_packdown_fee + business_delivery_fee

        # Refund the full business total
        amount = int(business_total * Decimal('100'))
        
        # Create the refund
        stripe.Refund.create(
            payment_intent=order.payment_intent,
            amount=amount,
        )
    
    def send_consolidated_email(self, order):
        approved_items = order.items.filter(status='approved')
        rejected_items = order.items.filter(status='rejected')
        pending_items = order.items.filter(status='pending')

        business_totals = {}
        for business_id, fee in order.business_delivery_fees.items():
            business_totals[business_id] = {
                'subtotal': Decimal('0'),
                'setup_packdown_fee': Decimal('0'),
                'delivery_fee': Decimal(str(fee)),
            }

        for item in order.items.all():
            business = item.product.business if item.product else item.service.business
            business_id = str(business.id)
            
            if business_id not in business_totals:
                business_totals[business_id] = {
                    'subtotal': Decimal('0'),
                    'setup_packdown_fee': Decimal('0'),
                    'delivery_fee': Decimal('0'),
                }
            
            business_totals[business_id]['subtotal'] += item.price * item.quantity
            
            if item.product and item.product.setup_packdown_fee:
                business_totals[business_id]['setup_packdown_fee'] += item.product.setup_packdown_fee_amount
            elif item.service and item.service.setup_packdown_fee:
                business_totals[business_id]['setup_packdown_fee'] += item.service.setup_packdown_fee_amount

        total_approved = sum(
            business_totals[str(item.product.business.id if item.product else item.service.business.id)]['subtotal'] +
            business_totals[str(item.product.business.id if item.product else item.service.business.id)]['setup_packdown_fee'] +
            business_totals[str(item.product.business.id if item.product else item.service.business.id)]['delivery_fee']
            for item in approved_items
        )

        total_rejected = sum(
            business_totals[str(item.product.business.id if item.product else item.service.business.id)]['subtotal'] +
            business_totals[str(item.product.business.id if item.product else item.service.business.id)]['setup_packdown_fee'] +
            business_totals[str(item.product.business.id if item.product else item.service.business.id)]['delivery_fee']
            for item in rejected_items
        )

        total_pending = sum(
            business_totals[str(item.product.business.id if item.product else item.service.business.id)]['subtotal'] +
            business_totals[str(item.product.business.id if item.product else item.service.business.id)]['setup_packdown_fee'] +
            business_totals[str(item.product.business.id if item.product else item.service.business.id)]['delivery_fee']
            for item in pending_items
        )

        context = {
            'order': order,
            'approved_items': approved_items,
            'rejected_items': rejected_items,
            'pending_items': pending_items,
            'business_totals': business_totals,
            'total_approved': total_approved,
            'total_rejected': total_rejected,
            'total_pending': total_pending,
            'afterpay_fee': order.afterpay_fee,
            'total_charged': total_approved + order.afterpay_fee,
            'total_refunded': total_rejected,
            'final_total': total_approved + order.afterpay_fee,
        }

        customer_subject = f"Order Status Update - {order.ref_code}"
        customer_message = render_to_string('event/customer_order_status_email.html', context)

        customer_email = EmailMultiAlternatives(
            subject=customer_subject,
            body="Your order status has been updated.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.user.email]
        )
        customer_email.attach_alternative(customer_message, "text/html")
        customer_email.send()


    def send_business_confirmation_email(self, order, business, approved_items):
        context = self.get_business_email_context(order, business, approved_items)
        subject = f"Order Confirmed - {order.ref_code}"
        message = render_to_string('event/business_order_confirmed.html', context)
        
        self.send_business_email(subject, message, business.email)

    def send_business_rejection_email(self, order, business, rejected_items):
        context = self.get_business_email_context(order, business, rejected_items)
        subject = f"Order Rejected - {order.ref_code}"
        message = render_to_string('event/business_order_rejected.html', context)
        
        self.send_business_email(subject, message, business.email)

    def get_business_email_context(self, order, business, items):
        business_subtotal = sum(item.price * item.quantity for item in items)
        business_setup_packdown_fee = sum(
            item.product.setup_packdown_fee_amount if item.product and item.product.setup_packdown_fee else
            (item.service.setup_packdown_fee_amount if item.service and item.service.setup_packdown_fee else Decimal('0'))
            for item in items
        )
        business_delivery_fee = Decimal(str(order.business_delivery_fees.get(str(business.id), '0.00')))
        business_total = business_subtotal + business_setup_packdown_fee + business_delivery_fee

        return {
            'order': order,
            'business': business,
            'cart_items': items,
            'business_subtotal': business_subtotal,
            'business_setup_packdown_fee': business_setup_packdown_fee,
            'business_delivery_fee': business_delivery_fee,
            'business_total': business_total,
        }

    def send_business_email(self, subject, message, to_email):
        email = EmailMultiAlternatives(
            subject=subject,
            body="Your order status has been updated.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email]
        )
        email.attach_alternative(message, "text/html")
        email.send()

class BusinessOrdersView(UserPassesTestMixin, ListView):
    model = Order
    template_name = 'event/business_orders.html'
    context_object_name = 'orders'
    paginate_by = 9

    def test_func(self):
        return hasattr(self.request.user, 'business')

    def get_queryset(self):
        print("BusinessOrdersView: Starting get_queryset method")
        status_filter = self.request.GET.get('status', '')
        print(f"BusinessOrdersView: Status filter: {status_filter}")
        
        queryset = Order.objects.filter(
            items__in=OrderItem.objects.filter(
                models.Q(product__business=self.request.user.business) |
                models.Q(service__business=self.request.user.business)
            )
        ).distinct().prefetch_related(
            'items__product', 'items__service', 'items__product__business', 'items__service__business'
        ).order_by('-created_at')
        
        print(f"BusinessOrdersView: Found {queryset.count()} orders before filtering")
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            print(f"BusinessOrdersView: Found {queryset.count()} orders after filtering by status")
        
        return queryset

    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        orders_with_totals = []
        business = self.request.user.business
        for order in context['orders']:
            business_total = self.calculate_total_for_business(order, business)
            business_delivery_fee = Decimal(str(order.business_delivery_fees.get(str(business.id), '0.00')))
            
            setup_packdown_fee = sum(
                item.product.setup_packdown_fee_amount if item.product and item.product.setup_packdown_fee else
                item.service.setup_packdown_fee_amount if item.service and item.service.setup_packdown_fee else Decimal('0')
                for item in order.items.filter(
                    models.Q(product__business=business) |
                    models.Q(service__business=business)
                )
            )

            business_total += business_delivery_fee + setup_packdown_fee
            orders_with_totals.append((order, business_total))

        context['orders_with_totals'] = orders_with_totals
        context['business'] = business
        context['status_choices'] = Order.STATUS_CHOICES
        context['current_status'] = self.request.GET.get('status', '')
        return context

    def calculate_total_for_business(self, order, business):
        total = Decimal('0.00')
        for item in order.items.filter(
                models.Q(product__business=business) |
                models.Q(service__business=business)):
            total += item.price * item.quantity
        print(f"BusinessOrdersView: Calculated total {total} for order {order.id} and business {business.id}")
        return total


class UserOrdersView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        orders = Order.objects.filter(user=request.user).order_by('-created_at')
        paginator = Paginator(orders, 9)

        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        orders_with_status = []
        for order in page_obj:
            approved_items = order.items.filter(status='approved')
            rejected_items = order.items.filter(status='rejected')
            pending_items = order.items.filter(status='pending')

            if pending_items.exists():
                status = 'Partially Approved' if approved_items.exists() else 'Pending'
            elif rejected_items.exists():
                status = 'Partially Rejected' if approved_items.exists() else 'Rejected'
            else:
                status = 'Approved'

            orders_with_status.append((order, status))

        return render(request, 'event/user_orders.html', {
            'orders_with_status': orders_with_status,
            'page_obj': page_obj
        })


class UserOrderDetailsView(LoginRequiredMixin, View):
    def get(self, request, order_id, *args, **kwargs):
        order = get_object_or_404(Order, id=order_id, user=request.user)
        approved_items = order.items.filter(status='approved')
        rejected_items = order.items.filter(status='rejected')
        pending_items = order.items.filter(status='pending')
        signatures = order.signatures.all()

        business_totals = {}
        flattened_business_terms = {}
        for business_id, fee in order.business_delivery_fees.items():
            business = Business.objects.get(id=business_id)
            print(f"Business ID: {business_id} - {business.business_name}")
            business_totals[business_id] = {
                'name': business.business_name,
                'subtotal': Decimal('0'),
                'setup_packdown_fee': Decimal('0'),
                'delivery_fee': Decimal(str(fee)),
                'status': 'pending'  # Add a status field
            }

        for item in order.items.all():
            business = item.product.business if item.product else item.service.business
            business_id = str(business.id)
            
            if business_id not in business_totals:
                business_totals[business_id] = {
                    'name': business.business_name,
                    'subtotal': Decimal('0'),
                    'setup_packdown_fee': Decimal('0'),
                    'delivery_fee': Decimal('0'),
                    'status': 'pending'  # Add a status field
                }

            # Flatten the terms data for easier access in the template
            flattened_business_terms[business_id] = {
                'terms': business.terms_and_conditions,
                'terms_pdf': business.terms_and_conditions_pdf.url if business.terms_and_conditions_pdf else None,
            }

            # Debugging output for terms and conditions
            print(f"Terms for Business {business.business_name}: {flattened_business_terms[business_id]['terms']}")
            print(f"PDF for Business {business.business_name}: {flattened_business_terms[business_id]['terms_pdf']}")
            
            business_totals[business_id]['subtotal'] += item.price * item.quantity
            
            if item.product and item.product.setup_packdown_fee:
                business_totals[business_id]['setup_packdown_fee'] += item.product.setup_packdown_fee_amount
            elif item.service and item.service.setup_packdown_fee:
                business_totals[business_id]['setup_packdown_fee'] += item.service.setup_packdown_fee_amount
            
            # Update the status based on the item's status
            if item.status == 'approved':
                business_totals[business_id]['status'] = 'approved'
            elif item.status == 'rejected' and business_totals[business_id]['status'] != 'approved':
                business_totals[business_id]['status'] = 'rejected'

        for business_id, totals in business_totals.items():
            totals['total'] = totals['subtotal'] + totals['setup_packdown_fee'] + totals['delivery_fee']

        total_approved = sum(
            totals['total'] for totals in business_totals.values() if totals['status'] == 'approved'
        )

        total_rejected = sum(
            totals['total'] for totals in business_totals.values() if totals['status'] == 'rejected'
        )

        total_pending = sum(
            totals['total'] for totals in business_totals.values() if totals['status'] == 'pending'
        )

        context = {
            'order': order,
            'approved_items': approved_items,
            'rejected_items': rejected_items,
            'pending_items': pending_items,
            'total_approved': total_approved,
            'total_rejected': total_rejected,
            'total_pending': total_pending,
            'afterpay_fee': order.afterpay_fee,
            'total_price': total_approved + order.afterpay_fee,
            'business_totals': business_totals,
            'signatures': signatures,
            'business_terms': flattened_business_terms,
        }
        return render(request, 'event/user_order_detail.html', context)


class RequestRefundView(LoginRequiredMixin, View):
    def get(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, user=request.user)
        return render(request, 'event/request_refund.html', {'order': order})

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, user=request.user)
        
        if order.refund_requested:
            return redirect('user_orders')
        
        email = request.POST.get('email')
        reason = request.POST.get('reason')
        
        refund = Refund.objects.create(
            order=order,
            reason=reason,
            email=email
        )
        
        order.refund_requested = True
        order.save()

        # Get unique business emails associated with this order
        business_emails = OrderItem.objects.filter(order=order).select_related('product__business').values_list('product__business__email', flat=True).distinct()

        # Send email to each business
        for business_email in business_emails:
            # Get items for this specific business in this order
            business_items = OrderItem.objects.filter(
                order=order,
                product__business__email=business_email
            ).select_related('product')

            items_details = "\n".join([
                f"- {item.quantity} x {item.product.name} - ${item.price}"
                for item in business_items
            ])

            message = f"""
A refund has been requested for Order #{order.ref_code}.

Items from your business in this order:
{items_details}

Reason: {reason}

Customer Email: {email}
            """

            send_mail(
                f'Refund Request for Order #{order.ref_code}',
                message,
                settings.DEFAULT_FROM_EMAIL,
                [business_email],
                fail_silently=False,
            )

        return redirect('user_orders')

@login_required
def create_quote(request, username):
    print(f"[DEBUG] Entering create_quote view. Username: {username}")
    print(f"[DEBUG] Request method: {request.method}")
    
    recipient = get_object_or_404(CustomUser, username=username)
    business = Business.objects.filter(seller=request.user).first()

    if not business:
        print("[DEBUG] No business found for this user")
        return JsonResponse({'success': False, 'error': 'No business found for this user'})

    if request.method == 'POST':
        print("[DEBUG] Processing POST request")
        print(f"[DEBUG] POST data: {request.POST}")
        
        form = QuoteForm(request.POST)
        if form.is_valid():
            print("[DEBUG] Form is valid")
            service = form.cleaned_data['service']
            
            # Check if the service is available by quotation only
            if not service.available_by_quotation_only:
                return JsonResponse({'success': False, 'error': 'This service is not available for quotation'})
            
            price = form.cleaned_data['price']
            
            # Create the message
            message = Message.objects.create(
                sender=request.user,
                recipient=recipient,
                business=business,
                content=f"Quote for {service.name} at ${price}"
            )
            print(f"[DEBUG] Message created: {message}")
            
            # Create the quote
            quote = Quote.objects.create(
                sender=request.user,
                recipient=recipient,
                service=service,
                price=price,
                message=message
            )
            print(f"[DEBUG] Quote created: {quote}")
            
            return JsonResponse({'success': True})
        else:
            print(f"[DEBUG] Form is invalid. Errors: {form.errors}")
            return JsonResponse({'success': False, 'errors': form.errors})

    print("[DEBUG] Invalid request method")
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def accept_quote(request, quote_id):
    quote = get_object_or_404(Quote, id=quote_id, recipient=request.user)
    quote.is_accepted = True
    quote.save()
    return JsonResponse({'success': True})


@login_required
def add_quote_to_cart(request, quote_id):
    quote = get_object_or_404(Quote, id=quote_id)
    
    # Check if the quote is for the current user
    if quote.recipient != request.user:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    # Add the service to the cart with the quoted price
    cart_item, created = Cart.objects.get_or_create(
        user=request.user,
        service=quote.service,
        defaults={'price': quote.price, 'hire': True}
    )
    
    if not created:
        cart_item.price = quote.price
        cart_item.hire = True
        cart_item.save()

    return JsonResponse({'success': True})

@login_required
def message_seller(request, business_slug):
    business = get_object_or_404(Business, business_slug=business_slug)
    
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            # Create the message
            Message.objects.create(
                sender=request.user,
                recipient=business.seller,
                business=business,
                content=content
            )
            
            # Get the current site
            current_site = get_current_site(request)
            domain = 'everyeventaustralia.pythonanywhere.com'
            
            # Prepare email content
            subject = f"New message from {request.user.username}"
            email_body = render_to_string('event/message_notification.html', {
                'sender': request.user,
                'recipient': business.seller,
                'message_content': content,
                'business': business,
                'domain': f'http://{domain}'  # Use https if your site uses SSL
            })
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [business.email]
            
            # Send email asynchronously
            print(f"About to create email task: subject='{subject}', from='{from_email}', to={recipient_list}")
            send_email_task(subject, email_body, from_email, recipient_list)
            print("Email task created")
            
            return redirect('message_seller', business_slug=business.business_slug)

    # Mark messages as read for the current user and business
    Message.objects.filter(recipient=request.user, business=business).update(is_read=True)

    conversation_messages = Message.objects.filter(
        Q(sender=request.user, recipient=business.seller) |
        Q(sender=business.seller, recipient=request.user)
    ).filter(business=business).order_by('timestamp')

    individual_business_message_counter = Message.objects.filter(recipient=request.user, business=business, is_read=False).count()
    
    context = {
        'business': business,
        'conversation_messages': conversation_messages,
        'individual_business_message_counter': individual_business_message_counter,
    }
    return render(request, 'event/message.html', context)

@login_required
def message_buyer(request, username):
    user = get_object_or_404(CustomUser, username=username)
    business = Business.objects.filter(seller=request.user).first()

    if not business:
        return redirect('user_messages')

    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            # Create the message
            Message.objects.create(
                sender=request.user,
                recipient=user,
                business=business,
                content=content
            )
            
            # Get the current site
            current_site = get_current_site(request)
            domain = 'everyeventaustralia.pythonanywhere.com'
            
            # Prepare email content
            subject = f"New message from {business.business_name}"
            email_body = render_to_string('event/message_notification.html', {
                'sender': request.user,
                'recipient': user,
                'message_content': content,
                'business': business,
                'domain': f'http://{domain}'  # Use https if your site uses SSL
            })
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [user.email]
            
            # Send email asynchronously
            print(f"About to create email task: subject='{subject}', from='{from_email}', to={recipient_list}")
            send_email_task(subject, email_body, from_email, recipient_list)
            print("Email task created")
            
            return redirect('message_buyer', username=user.username)

    # Mark messages as read
    Message.objects.filter(recipient=request.user, sender=user).update(is_read=True)

    conversation_messages = Message.objects.filter(
        Q(sender=request.user, recipient=user) |
        Q(sender=user, recipient=request.user)
    ).filter(business=business).order_by('timestamp')

    can_create_quote = bool(request.user.business)
    business_services = business.services.filter(available_by_quotation_only=True) if business else []

    context = {
        'user': user,
        'conversation_messages': conversation_messages,
        'business': business,
        'can_create_quote': can_create_quote,
        'business_services': business_services,
    }
    return render(request, 'event/message_buyer.html', context)

@login_required
def user_messages_view(request):
    businesses = Business.objects.filter(
        Q(messages__sender=request.user) | Q(messages__recipient=request.user)
    ).distinct()

    user_messages = []
    latest_messages = []

    for business in businesses:
        if request.user == business.seller:
            # Query messages for business with other users
            messages = Message.objects.filter(
                Q(sender=business.seller) | Q(recipient=business.seller)
            ).filter(business=business).order_by('-timestamp')
            for user, chat in itertools.groupby(messages, lambda m: m.recipient if m.sender == request.user else m.sender):
                last_message = next(chat)
                unread_count = Message.objects.filter(recipient=business.seller, sender=user, business=business, is_read=False).count()
                user_messages.append({
                    'business': business,
                    'last_message': last_message,
                    'user': user,
                    'unread_count': unread_count,
                })
                latest_messages.append(last_message)
        else:
            last_message = Message.objects.filter(
                Q(sender=request.user, recipient=business.seller) |
                Q(sender=business.seller, recipient=request.user)
            ).filter(business=business).order_by('-timestamp').first()
            unread_count = Message.objects.filter(recipient=request.user, sender=business.seller, business=business, is_read=False).count()
            user_messages.append({
                'business': business,
                'last_message': last_message,
                'unread_count': unread_count,
            })
            latest_messages.append(last_message)

    # Sort user_messages by the latest message timestamp
    user_messages = sorted(user_messages, key=lambda um: um['last_message'].timestamp, reverse=True)
    
    unread_message_counter = sum(msg['unread_count'] for msg in user_messages)

    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            if 'business_slug' in request.POST:
                business_slug = request.POST.get('business_slug')
                business = get_object_or_404(Business, business_slug=business_slug)
                if request.user == business.seller:
                    username = request.POST.get('username')
                    if username:
                        recipient = get_object_or_404(CustomUser, username=username)
                        Message.objects.create(
                            sender=request.user,
                            recipient=recipient,
                            business=business,
                            content=content
                        )
                        
                        # Get the current site
                        current_site = get_current_site(request)
                        domain = 'everyeventaustralia.pythonanywhere.com'
                        
                        subject = f"New message from {business.business_name}"
                        email_body = render_to_string('event/message_notification.html', {
                            'sender': request.user,
                            'recipient': recipient,
                            'message_content': content,
                            'business': business,
                            'domain': f'http://{domain}'  # Use https if your site uses SSL
                        })
                        from_email = settings.DEFAULT_FROM_EMAIL
                        recipient_list = [recipient.email]
                        
                        print(f"About to create email task: subject='{subject}', from='{from_email}', to={recipient_list}")
                        send_email_task(subject, email_body, from_email, recipient_list)
                        print("Email task created")
                        
                        return redirect(f'{request.path}?business_slug={business_slug}&username={username}')
                else:
                    Message.objects.create(
                        sender=request.user,
                        recipient=business.seller,
                        business=business,
                        content=content
                    )
                    
                    # Get the current site
                    current_site = get_current_site(request)
                    domain = 'everyeventaustralia.pythonanywhere.com'
                    
                    subject = f"New message from {request.user.username}"
                    email_body = render_to_string('event/message_notification.html', {
                        'sender': request.user,
                        'recipient': business.seller,
                        'message_content': content,
                        'business': business,
                        'domain': f'http://{domain}'  # Use https if your site uses SSL
                    })
                    from_email = settings.DEFAULT_FROM_EMAIL
                    recipient_list = [business.email]
                    
                    print(f"About to create email task: subject='{subject}', from='{from_email}', to={recipient_list}")
                    send_email_task(subject, email_body, from_email, recipient_list)
                    print("Email task created")
                    
                    return redirect(f'{request.path}?business_slug={business_slug}')
            elif 'username' in request.POST:
                username = request.POST.get('username')
                recipient = get_object_or_404(CustomUser, username=username)
                business = Business.objects.filter(seller=request.user).first()
                Message.objects.create(
                    sender=request.user,
                    recipient=recipient,
                    business=business,
                    content=content
                )
                
                # Get the current site
                current_site = get_current_site(request)
                domain = current_site.domain
                
                subject = f"New message from {business.business_name}"
                email_body = render_to_string('event/message_notification.html', {
                    'sender': request.user,
                    'recipient': recipient,
                    'message_content': content,
                    'business': business,
                    'domain': f'http://{domain}'  # Use https if your site uses SSL
                })
                from_email = settings.DEFAULT_FROM_EMAIL
                recipient_list = [recipient.email]
                
                print(f"About to create email task: subject='{subject}', from='{from_email}', to={recipient_list}")
                send_email_task(subject, email_body, from_email, recipient_list)
                print("Email task created")
                
                return redirect(f'{request.path}?username={username}')

    selected_business = None
    selected_user = None
    can_create_quote = False
    conversation_messages = []
    business_services = []

    if 'business_slug' in request.GET:
        business_slug = request.GET.get('business_slug')
        selected_business = get_object_or_404(Business, business_slug=business_slug)
        if request.user == selected_business.seller:
            username = request.GET.get('username')
            selected_user = get_object_or_404(CustomUser, username=username)
            conversation_messages = Message.objects.filter(
                Q(sender=selected_user, recipient=selected_business.seller) |
                Q(sender=selected_business.seller, recipient=selected_user)
            ).filter(business=selected_business).order_by('timestamp')
            can_create_quote = True
            business_services = selected_business.services.filter(available_by_quotation_only=True)
        else:
            can_create_quote = False
            business_services = []
            conversation_messages = Message.objects.filter(
                Q(sender=request.user, recipient=selected_business.seller) |
                Q(sender=selected_business.seller, recipient=request.user)
            ).filter(business=selected_business).order_by('timestamp')
        Message.objects.filter(recipient=request.user, business=selected_business).update(is_read=True)
    elif 'username' in request.GET:
        username = request.GET.get('username')
        selected_user = get_object_or_404(CustomUser, username=username)
        business = Business.objects.filter(seller=request.user).first()
        if request.user.business:
            can_create_quote = True
            business_services = business.services.filter(available_by_quotation_only=True)
        conversation_messages = Message.objects.filter(
            Q(sender=request.user, recipient=selected_user) |
            Q(sender=selected_user, recipient=request.user)
        ).filter(business=business).order_by('timestamp')
        Message.objects.filter(recipient=request.user, sender=selected_user).update(is_read=True)

    context = {
        'user_messages': user_messages,
        'selected_business': selected_business,
        'selected_user': selected_user,
        'conversation_messages': conversation_messages,
        'unread_message_counter': unread_message_counter,
        'can_create_quote': can_create_quote,
        'business_services': business_services,
    }
    return render(request, 'event/user_messages.html', context)

def products(request):
    products = Product.objects.all()
    
    # Category filter
    category = request.GET.get('category')
    if category:
        products = products.filter(category=category)
    
    # Sorting
    sort = request.GET.get('sort')
    if sort == 'price_high_low':
        products = products.order_by('-price')
    elif sort == 'price_low_high':
        products = products.order_by('price')
    elif sort == 'best_selling':
        products = products.filter(is_best_seller=True)
    elif sort == 'popular':
        products = products.filter(is_popular=True)
    elif sort == 'trending':
        products = products.filter(trending=True)
    elif sort == 'new_releases':
        products = products.filter(new_releases=True)
    
    # Pagination
    paginator = Paginator(products, 9)  # Show 9 products per page
    page = request.GET.get('page', 1)
    
    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)
    
    # Get all categories for the filter
    categories = Product.Category.choices
    
    context = {
        "products": products,
        "categories": categories,
    }
    
    return render(request, "event/products.html", context)



def services(request):
    services = Service.objects.all()
    
    # Get countries and states with their service counts
    states = State.objects.annotate(
        service_count=Count('business__services', distinct=True)
    )

    # Filtering
    selected_countries = request.GET.getlist('country')
    selected_states = request.GET.getlist('state')

    if selected_countries:
        services = services.filter(business__countries__id__in=selected_countries)
    if selected_states:
        services = services.filter(business__states__id__in=selected_states)

    # Pagination
    paginator = Paginator(services, 10)  # Show 10 services per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        "services": page_obj,
        "states": states,
        "selected_countries": selected_countries,
        "selected_states": selected_states,
    }
    return render(request, "event/services.html", context)



def search_view(request):
    query = request.GET.get('q', '')
    products = Product.objects.filter(
        Q(name__icontains=query) | 
        Q(description__icontains=query) |
        Q(business__business_name__icontains=query)
    )
    services = Service.objects.filter(
        Q(name__icontains=query) | 
        Q(description__icontains=query) |
        Q(business__business_name__icontains=query)
    )
    
    results = list(products) + list(services)
    results.sort(key=lambda x: x.name.lower())

    context = {
        'query': query,
        'results': results,
    }
    return render(request, 'event/search_results.html', context)

@login_required
def quick_shop_view(request, product_slug):
    # Get the product based on the slug
    product = get_object_or_404(Product, product_slug=product_slug)

    # Check if the product has variations
    if product.has_variations:
        # Redirect to the product detail page
        product_detail_url = reverse('product_detail', args=[product.business.business_slug, product.product_slug])
        messages.info(request, f"Please select your variations.")
        return redirect(product_detail_url)
    else:
        # Get the current user
        user = request.user

        # Create a new cart item
        cart_item, created = Cart.objects.get_or_create(
            user=user,
            product=product,
            defaults={'quantity': 1, 'variation_key': None}
        )

        # If the cart item already exists, increment the quantity
        if not created:
            cart_item.quantity += 1
            cart_item.save()

        # Display a success message
        messages.success(request, f"{product.name} has been added to your cart.")

        # Redirect to the checkout page
        return redirect('checkout')
    

def delete_cart_item(request, cart_item_id):
    if request.method == 'POST':
        cart_item = get_object_or_404(Cart, id=cart_item_id, user=request.user)
        item_name = cart_item.product.name if cart_item.product else cart_item.service.name
        cart_item.delete()
        messages.success(request, f"{item_name} has been removed from your cart.")
    return redirect('cart')  # Assuming 'cart' is the name of your cart view

class VenueVendorRegistrationView(View):
    def get(self, request):
        day_choices = VenueOpeningHour.DAY_CHOICES
        event_categories = EventCategory.objects.all()
        amenities = Amenity.objects.all()
        states = State.objects.all()
        context = {
            'day_choices': day_choices,
            'event_categories': event_categories,
            'amenities': amenities,
            'states': states,
            'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
        }
        return render(request, 'event/venue_vendor_registration.html', context)

    def post(self, request):
        try:
            with transaction.atomic():
                # Create user and venue
                user = CustomUser.objects.create_user(
                    username=request.POST['venue_email'],
                    password=request.POST['password1'],
                    email=request.POST['venue_email'],
                    first_name=request.POST['first_name'],
                    last_name=request.POST['last_name'],
                    is_venue_vendor=True
                )

                user.is_active = False  # Deactivate account until email is verified
                user.save()

                # Send email verification
                self.send_verification_email(user, request)

                venue = Venue.objects.create(
                    user=user,
                    first_name=request.POST['first_name'],
                    last_name=request.POST['last_name'],
                    venue_email=request.POST['venue_email'],
                    venue_contact_number=request.POST['venue_contact_number'],
                    venue_name=request.POST['venue_name'],
                    venue_address=request.POST['venue_address'],
                    description=request.POST['description'],
                    price_per_event=request.POST['price_per_event'],
                    min_reception_guests=request.POST['min_reception_guests'],
                    max_reception_guests=request.POST['max_reception_guests'],
                    low_price_per_head=request.POST['low_price_per_head'],
                    high_price_per_head=request.POST['high_price_per_head'],
                    ceremony_indoors=request.POST.get('ceremony_indoors') == 'on',
                    ceremony_outdoors=request.POST.get('ceremony_outdoors') == 'on',
                    in_house_catering=request.POST.get('in_house_catering') == 'on',
                    profile_picture=request.FILES.get('profile_picture'),
                    cover_photo=request.FILES.get('cover_photo'),
                    venue_image=request.FILES['venue_image'],
                    video_url=request.POST.get('video_url'),
                )

                venue.states.set(request.POST.getlist('states'))
                venue.event_category.set(request.POST.getlist('event_category'))
                venue.amenities.set(request.POST.getlist('amenities'))

                # Create opening hours
                for day, _ in VenueOpeningHour.DAY_CHOICES:
                    is_closed = request.POST.get(f'opening_hours-{day}-is_closed') == 'on'
                    opening_time = request.POST.get(f'opening_hours-{day}-opening_time')
                    closing_time = request.POST.get(f'opening_hours-{day}-closing_time')

                    VenueOpeningHour.objects.create(
                        venue=venue,
                        day=day,
                        is_closed=is_closed,
                        opening_time=opening_time if not is_closed else None,
                        closing_time=closing_time if not is_closed else None
                    )

                # Create venue images
                for image in request.FILES.getlist('venue_images'):
                    VenueImage.objects.create(venue=venue, image=image)

                # Create a Stripe customer
                customer = stripe.Customer.create(
                    email=user.email,
                    name=f"{user.first_name} {user.last_name}",
                )

                # Create a Stripe Checkout Session
                checkout_session = stripe.checkout.Session.create(
                    customer=customer.id,
                    payment_method_types=['card'],
                    line_items=[
                        {
                            'price': settings.STRIPE_ANNUAL_SUBSCRIPTION_PRICE_ID,
                            'quantity': 1,
                        },
                    ],
                    mode='subscription',
                    subscription_data={
                        'trial_period_days': 365,
                    },
                    success_url=request.build_absolute_uri(reverse('venue_detail', kwargs={'venue_slug': venue.venue_slug})),
                    cancel_url=request.build_absolute_uri(reverse('venue_vendor_register')),
                )

                # Save the subscription ID and redirect to Stripe checkout
                venue.stripe_subscription_id = checkout_session.subscription
                venue.save()
                messages.success(request, f"Your Venue Profile has now been created. Please check your email to verify your account.")
                return redirect(checkout_session.url)

        except Exception as e:
            print(f"Error occurred: {str(e)}")
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('venue_vendor_register')
        
    def send_verification_email(self, user, request):
        current_site = settings.SITE_URL
        mail_subject = 'Activate your account.'
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)
        verification_link = reverse('verify_email', kwargs={'uidb64': uid, 'token': token})
        verification_url = f"{current_site}{verification_link}"
        
        html_message = render_to_string('event/email_verification.html', {
            'user': user,
            'verification_url': verification_url,
            'domain': current_site,  # Use the SITE_URL as the domain in the template
        })
        plain_message = strip_tags(html_message)
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = user.email

        send_mail(
            mail_subject,
            plain_message,
            from_email,
            [to_email],
            html_message=html_message,
        )

class VenueDetailView(View):
    def get(self, request, venue_slug):
        venue = get_object_or_404(Venue, venue_slug=venue_slug)
        venue.views_count = F('views_count') + 1
        venue.save(update_fields=['views_count'])

        opening_hours = venue.venue_opening_hours.all()
        reviews = venue.reviews.all()

        context = {
            'venue': venue,
            'opening_hours': opening_hours,
            'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
            'overall_review': venue.overall_review,
        }
        return render(request, 'event/venue_detail.html', context)

    @method_decorator(login_required)
    def post(self, request, venue_slug):
        venue = get_object_or_404(Venue, venue_slug=venue_slug)

        # Handle review submission
        if 'rating' in request.POST:
            review_text = request.POST.get('message')
            rating = request.POST.get('rating')

            if review_text and rating:
                VenueReview.objects.create(
                    venue=venue,
                    user=request.user,
                    review_text=review_text,
                    rating=int(rating)
                )
                messages.success(request, 'Thank you for your review!')
                return redirect('venue_detail', venue_slug=venue_slug)

        # Handle inquiry form submission
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        event_date = request.POST.get('event_date')
        guests = request.POST.get('guests')
        comments = request.POST.get('comments')

        if name and email and phone and event_date and guests:
            VenueInquiry.objects.create(
                venue=venue,
                name=name,
                email=email,
                phone=phone,
                event_date=event_date,
                guests=guests,
                comments=comments
            )
            messages.success(request, 'Your inquiry has been sent successfully!')
            return redirect('venue_detail', venue_slug=venue_slug)

        messages.error(request, 'All fields are required for inquiry.')
        return render(request, 'event/venue_detail.html', {'venue': venue})

@method_decorator(login_required, name='dispatch')
class SubscriptionCancelView(View):
    def get(self, request, venue_slug):
        venue = get_object_or_404(Venue, venue_slug=venue_slug, user=request.user)
        return render(request, 'event/cancel_subscription_confirm.html', {'venue': venue})

    def post(self, request, venue_slug):
        venue = get_object_or_404(Venue, venue_slug=venue_slug, user=request.user)
        try:
            # Cancel the Stripe subscription if it exists
            if venue.stripe_subscription_id:
                stripe.Subscription.delete(venue.stripe_subscription_id)

            # Set is_venue_vendor to False
            user = venue.user
            user.is_venue_vendor = False
            user.save()

            # Delete the venue and related data
            venue.delete()

            messages.success(request, 'Your subscription has been cancelled, your venue has been removed, and your vendor status has been updated.')
            return redirect('home')
        except Exception as e:
            messages.error(request, f"An error occurred while cancelling your subscription: {str(e)}")
            return redirect('venue_detail', venue_slug=venue_slug)


def charge_annual_subscription(venue):
    try:
        # Create a payment intent for the annual subscription
        payment_intent = stripe.PaymentIntent.create(
            amount=27500,  # $275 in cents
            currency='aud',
            customer=venue.stripe_account_id,
            description=f"Annual subscription for {venue.venue_name}",
            confirm=True,
        )

        if payment_intent.status == 'succeeded':
            venue.subscription_start_date = timezone.now()
            venue.save()

            # Notify the venue via email
            subject = "Subscription Charge Successful"
            message = render_to_string('business/subscription_successful_email.html', {'venue': venue})
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [venue.venue_email])
            return True
        else:
            return False
    except stripe.error.StripeError as e:
        # Log or notify about the error
        print(f"Stripe error for venue {venue.id}: {str(e)}")
        return False


def check_and_charge_subscriptions():
    today = timezone.now().date()
    venues_to_charge = Venue.objects.filter(
        subscription_start_date__lte=today - relativedelta(years=1),
        stripe_account_id__isnull=False
    )

    for venue in venues_to_charge:
        success = charge_annual_subscription(venue)
        if success:
            print(f"Successfully charged annual subscription for venue {venue.id}")
        else:
            print(f"Failed to charge annual subscription for venue {venue.id}")


@shared_task
def daily_subscription_check():
    check_and_charge_subscriptions()

@login_required
def edit_venue(request, venue_slug):
    venue = get_object_or_404(Venue, venue_slug=venue_slug)

    if request.user != venue.user:
        return redirect('venue_detail', venue_slug=venue.venue_slug)

    event_categories = EventCategory.objects.all()
    amenities = Amenity.objects.all()
    states = State.objects.all()
    day_choices = VenueOpeningHour.DAY_CHOICES

    if request.method == 'POST':
        venue.venue_email = request.POST.get('venue_email')
        venue.venue_contact_number = request.POST.get('venue_contact_number')
        venue.venue_name = request.POST.get('venue_name')
        venue.venue_address = request.POST.get('venue_address')
        venue.description = request.POST.get('description')
        venue.price_per_event = request.POST.get('price_per_event')
        venue.min_reception_guests = request.POST.get('min_reception_guests')
        venue.max_reception_guests = request.POST.get('max_reception_guests')
        venue.low_price_per_head = request.POST.get('low_price_per_head')
        venue.high_price_per_head = request.POST.get('high_price_per_head')
        venue.ceremony_indoors = request.POST.get('ceremony_indoors') == 'on'
        venue.ceremony_outdoors = request.POST.get('ceremony_outdoors') == 'on'
        venue.in_house_catering = request.POST.get('in_house_catering') == 'on'
        venue.video_url = request.POST.get('video_url')
        states_ids = request.POST.getlist('states')

        if request.FILES.get('profile_picture'):
            venue.profile_picture = request.FILES.get('profile_picture')
        if request.FILES.get('cover_photo'):
            venue.cover_photo = request.FILES.get('cover_photo')
        if request.FILES.get('venue_image'):
            venue.venue_image = request.FILES.get('venue_image')

        venue.event_category.set(request.POST.getlist('event_categories'))
        venue.amenities.set(request.POST.getlist('amenities'))
        venue.states.set(states_ids)

        for day, _ in VenueOpeningHour.DAY_CHOICES:
            is_closed = request.POST.get(f'opening_hours-{day}-is_closed') == 'on'
            opening_time = request.POST.get(f'opening_hours-{day}-opening_time')
            closing_time = request.POST.get(f'opening_hours-{day}-closing_time')

            opening_hour, created = VenueOpeningHour.objects.get_or_create(venue=venue, day=day)
            opening_hour.is_closed = is_closed
            opening_hour.opening_time = None if is_closed else opening_time
            opening_hour.closing_time = None if is_closed else closing_time
            opening_hour.save()

        for image in request.FILES.getlist('venue_images'):
            VenueImage.objects.create(venue=venue, image=image)

        if 'delete_images' in request.POST:
            delete_images_ids = request.POST.getlist('delete_images')
            VenueImage.objects.filter(id__in=delete_images_ids).delete()

        venue.save()

        messages.success(request, 'Venue updated successfully.')
        return redirect('venue_detail', venue_slug=venue.venue_slug)

    context = {
        'venue': venue,
        'event_categories': event_categories,
        'amenities': amenities,
        'states': states,
        'day_choices': VenueOpeningHour.DAY_CHOICES,
        'opening_hours': venue.venue_opening_hours.all(),
        'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
    }
    return render(request, 'event/venue_edit.html', context)



@require_POST
def delete_venue_image(request, image_id):
    image = get_object_or_404(VenueImage, id=image_id)
    venue = image.venue

    if request.user == venue.user and venue.images.count() > 1:
        image_url = image.image.url
        image.delete()
        return JsonResponse({'success': True, 'image_url': image_url})
    else:
        return JsonResponse({'success': False})
    


def venues(request):
    venues = Venue.objects.all()
    
    # Get states with their venue counts
    states = State.objects.annotate(
        venue_count=Count('venue', distinct=True)
    )

    # Filtering
    selected_states = request.GET.getlist('state')

    if selected_states:
        venues = venues.filter(states__id__in=selected_states)

    # Pagination
    paginator = Paginator(venues, 10)  # Show 10 venues per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        "venues": page_obj,
        "states": states,
        "selected_states": selected_states,
    }
    return render(request, "event/venues.html", context)


@method_decorator(login_required, name='dispatch')
class VenueAnalyticsView(View):
    def get(self, request, venue_slug):
        venue = get_object_or_404(Venue, venue_slug=venue_slug, user=request.user)
        
        # Venue views analytics
        views = VenueView.objects.filter(venue=venue).values('viewed_at__date').annotate(count=Count('id'))
        view_data = {str(entry['viewed_at__date']): entry['count'] for entry in views}

        # Venue inquiries analytics
        inquiries = VenueInquiry.objects.filter(venue=venue).values('submitted_at__date').annotate(count=Count('id'))
        inquiry_data = {str(entry['submitted_at__date']): entry['count'] for entry in inquiries}

        context = {
            'venue': venue,
            'view_data': view_data,
            'inquiry_data': inquiry_data,
        }
        return render(request, 'event/venue_analytics.html', context)
    


def about_us(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        comment = request.POST.get('comment')
        
        subject = f"New contact from {name}"
        message = f"Name: {name}\nEmail: {email}\nPhone: {phone}\n\nMessage:\n{comment}"
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.DEFAULT_FROM_EMAIL],
                fail_silently=False,
            )
            messages.success(request, 'Your message has been sent successfully!')
        except Exception as e:
            messages.error(request, 'An error occurred while sending your message. Please try again later.')
    
    return render(request, 'event/about_us.html')

class BlogPostListView(ListView):
    model = BlogPost
    template_name = 'event/blog_list.html'

class BlogPostDetailView(DetailView):
    model = BlogPost
    template_name = 'event/blog_detail.html'