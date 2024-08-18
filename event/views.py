from django.shortcuts import render
from .models import Product, Business, OpeningHour, Cart, Message, State, Variation, ProductVariation, CartItemVariation, ProductReview, Order, OrderItem, Refund, Service, ProductCategory, ServiceCategory, ServiceImage, ServiceReview, Quote, EventCategory, Award, ServiceVariation, ServiceVariationOption, Venue, VenueImage, VenueOpeningHour, Amenity, VenueReview, VenueView, VenueInquiry, OrderApproval, OrderTermsSignature
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
from django.views.generic import ListView
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


stripe.api_key = settings.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)



def home(request):
    best_selling_products = Product.objects.filter(is_best_seller=True)
    best_selling_services = Service.objects.filter(is_best_seller=True)

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

    context = {
        'best_sellers': best_sellers,
        'products': all_products,
        'services': all_services,
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
        if 'hire' in type_filter:
            items = [item for item in items if getattr(item, 'for_hire', False)]

    price_sort = request.GET.get('price_sort')
    if price_sort == 'high_to_low':
        items.sort(key=lambda x: x.price, reverse=True)
    elif price_sort == 'low_to_high':
        items.sort(key=lambda x: x.price)

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        items = [item for item in items if item.price >= float(min_price)]
    if max_price:
        items = [item for item in items if item.price <= float(max_price)]

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

    # New color filter
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

            # Create user
            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_seller=True
            )

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
            delivery_radius = request.POST.get('delivery_radius')
            price_per_way = request.POST.get('price_per_way')
            profile_picture = request.FILES.get('profile_picture')
            banner_image = request.FILES.get('banner_image')

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
                delivery_radius=delivery_radius if delivery_radius else None,
                price_per_way=price_per_way if price_per_way else None,
            )

            states = State.objects.filter(id__in=state_ids)
            business.states.set(states)
            event_category_ids = request.POST.getlist('event_categories')
            event_categories = EventCategory.objects.filter(id__in=event_category_ids)
            business.event_categories.set(event_categories)
            business.save()

            for day, day_display in OpeningHour.DAY_CHOICES:
                is_closed = request.POST.get(f'opening_hours-{day}-is_closed', False)
                opening_time = request.POST.get(f'opening_hours-{day}-opening_time')
                closing_time = request.POST.get(f'opening_hours-{day}-closing_time')

                if is_closed:
                    OpeningHour.objects.create(
                        business=business,
                        day=day,
                        is_closed=True
                    )
                elif opening_time and closing_time:
                    OpeningHour.objects.create(
                        business=business,
                        day=day,
                        opening_time=opening_time,
                        closing_time=closing_time
                    )

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

                login(request, user)
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
        terms_and_conditions = request.POST.get('terms_and_conditions')
        terms_and_conditions_pdf = request.FILES.get('terms_and_conditions_pdf')
        delivery_radius = request.POST.get('delivery_radius')
        email = request.POST.get('email')
        profile_picture = request.FILES.get('profile_picture')
        banner_image = request.FILES.get('banner_image')

        business.business_name = business_name
        business.description = description
        business.address = address
        business.latitude = latitude if latitude else None
        business.longitude = longitude if longitude else None
        business.phone = phone
        business.email = email
        business.terms_and_conditions = terms_and_conditions
        business.terms_and_conditions_pdf = terms_and_conditions_pdf
        business.delivery_radius = delivery_radius if delivery_radius else None
        if profile_picture:
            business.profile_picture = profile_picture
        if banner_image:
            business.banner_image = banner_image

        business.states.set(State.objects.filter(id__in=state_ids))
        business.event_categories.set(EventCategory.objects.filter(id__in=event_category_ids))

        business.save()

        # Update opening hours
        for day, _ in OpeningHour.DAY_CHOICES:
            is_closed = request.POST.get(f'opening_hours-{day}-is_closed') == 'on'
            opening_time = request.POST.get(f'opening_hours-{day}-opening_time')
            closing_time = request.POST.get(f'opening_hours-{day}-closing_time')

            opening_hour, _ = OpeningHour.objects.get_or_create(business=business, day=day)
            opening_hour.is_closed = is_closed
            opening_hour.opening_time = None if is_closed else opening_time
            opening_hour.closing_time = None if is_closed else closing_time
            opening_hour.save()

        # Handle awards
        for file in request.FILES.getlist('awards'):
            Award.objects.create(business=business, image=file)

        messages.success(request, 'Business updated successfully.')
        return redirect('business_detail', business_slug=business.business_slug)

    context = {
        'business': business,
        'states': states,
        'event_categories': event_categories,
        'day_choices': OpeningHour.DAY_CHOICES,
        'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
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
        })

    def post(self, request, business_slug):
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
            price = parse_decimal(request.POST.get('price'))
            category_id = request.POST.get('category')
            category = get_object_or_404(ProductCategory, id=category_id)
            image = request.FILES.get('image')
            image2 = request.FILES.get('image2')
            image3 = request.FILES.get('image3')
            image4 = request.FILES.get('image4')
            in_stock = request.POST.get('in_stock') == 'on'
            stock_level = request.POST.get('stock_level')
            has_variations = request.POST.get('has_variations') == 'on'
            for_hire = request.POST.get('for_hire') == 'on'
            hire_price = parse_decimal(request.POST.get('hire_price')) if for_hire else None
            hire_duration = request.POST.get('hire_duration') if for_hire else None
            for_pickup = request.POST.get('for_pickup') == 'on'
            pickup_location = request.POST.get('pickup_location') if for_pickup else None
            can_deliver = request.POST.get('can_deliver') == 'on'
            delivery_radius = request.POST.get('delivery_radius') if can_deliver else None
            main_colour_theme = request.POST.get('main_colour_theme')
            setup_packdown_fee = request.POST.get('setup_packdown_fee') == 'on'
            setup_packdown_fee_amount = parse_decimal(request.POST.get('setup_packdown_fee_amount')) if setup_packdown_fee else None

            product = Product.objects.create(
                name=name,
                description=description,
                price=price,
                category=category,
                image=image,
                image2=image2,
                image3=image3,
                image4=image4,
                business=business,
                in_stock=in_stock,
                stock_level=stock_level,
                has_variations=has_variations,
                for_hire=for_hire,
                hire_price=hire_price,
                hire_duration=hire_duration,
                for_pickup=for_pickup,
                pickup_location=pickup_location,
                can_deliver=can_deliver,
                delivery_radius=delivery_radius,
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
        })

    def post(self, request, business_slug, product_slug):
        business = get_object_or_404(Business, business_slug=business_slug, seller=request.user)
        product = get_object_or_404(Product, product_slug=product_slug, business=business)

        if request.user == business.seller:
            product.name = request.POST.get('name', product.name)
            product.description = request.POST.get('description', product.description)
            product.price = request.POST.get('price', product.price)
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
            product.hire_price = request.POST.get('hire_price') if product.for_hire else None
            product.hire_duration = request.POST.get('hire_duration') if product.for_hire else None
            product.for_pickup = request.POST.get('for_pickup') == 'on'
            product.pickup_location = request.POST.get('pickup_location') if product.for_pickup else None
            product.can_deliver = request.POST.get('can_deliver') == 'on'
            product.delivery_radius = request.POST.get('delivery_radius') if product.can_deliver else None
            product.main_colour_theme = request.POST.get('main_colour_theme', product.main_colour_theme)
            product.setup_packdown_fee = request.POST.get('setup_packdown_fee') == 'on'
            product.setup_packdown_fee_amount = request.POST.get('setup_packdown_fee_amount') if product.setup_packdown_fee else None
            product.save()

            if product.has_variations:
                print(f"POST data: {request.POST}")
                variation_names = [name for name in request.POST if name.startswith('variation_names_')]
                variation_values = [name for name in request.POST if name.startswith('variation_values_')]
                price_varies = [name for name in request.POST if name.startswith('price_varies_')]
                variation_prices = [name for name in request.POST if name.startswith('variation_prices_')]
                variation_value_ids = [name for name in request.POST if name.startswith('variation_value_ids_')]

                print(f"Variation names: {variation_names}")
                print(f"Variation values: {variation_values}")
                print(f"Price varies: {price_varies}")
                print(f"Variation prices: {variation_prices}")
                print(f"Variation value ids: {variation_value_ids}")

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
                    print(f"Processing variation {var_data['name']} with values {var_data['values']}, prices {var_data['prices']}, price varies {var_data['price_varies']}")
                    variation, created = Variation.objects.get_or_create(product=product, name=var_data['name'])
                    variation.values.exclude(id__in=[value_id for value_id in var_data['value_ids'] if value_id]).delete()

                    for value, price, price_varies, value_id in zip(var_data['values'], var_data['prices'], var_data['price_varies'], var_data['value_ids']):
                        if value is not None:
                            print(f"Updating/Creating ProductVariation with value: {value}, price varies: {price_varies}, price: {price}, value_id: {value_id}")
                            if value_id:
                                try:
                                    product_variation = ProductVariation.objects.get(id=value_id)
                                    product_variation.value = value
                                    product_variation.price_varies = price_varies
                                    product_variation.price = Decimal(price) if price_varies and price else None
                                    product_variation.save()
                                    print(f"Updated ProductVariation {product_variation.id} with value: {value}, price: {product_variation.price}, price varies: {price_varies}")
                                except ProductVariation.DoesNotExist:
                                    product_variation = ProductVariation.objects.create(
                                        variation=variation,
                                        value=value,
                                        price=Decimal(price) if price_varies and price else None,
                                        price_varies=price_varies
                                    )
                                    print(f"Created ProductVariation {product_variation.id} with value: {value}, price: {product_variation.price}, price varies: {price_varies}")
                            else:
                                product_variation = ProductVariation.objects.create(
                                    variation=variation,
                                    value=value,
                                    price=Decimal(price) if price_varies and price else None,
                                    price_varies=price_varies
                                )
                                print(f"Created ProductVariation {product_variation.id} with value: {value}, price: {product_variation.price}, price varies: {price_varies}")

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
            hire_duration = request.POST.get('hire_duration')
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
                    hire_duration=hire_duration,
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

                    # Ensure all lists have the same length
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

            print("Service creation completed successfully")
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
            service.hire_duration = request.POST.get('hire_duration', service.hire_duration)
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

        # Fetch similar services based on category
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

    @method_decorator(login_required)
    def post(self, request, business_slug=None, service_slug=None):
        business = get_object_or_404(Business, business_slug=business_slug)
        service = get_object_or_404(Service, service_slug=service_slug, business=business)

        review_text = request.POST.get('message')
        rating = request.POST.get('rating')

        if review_text and rating:
            rating = int(rating)
            ServiceReview.objects.create(
                service=service,
                user=request.user,
                review_text=review_text,
                rating=rating
            )
            return redirect('service_detail', business_slug=business_slug, service_slug=service_slug)
        
        reviews = service.reviews.all()

        star_percentages = {
            5: service.star_rating_percentage(5),
            4: service.star_rating_percentage(4),
            3: service.star_rating_percentage(3),
            2: service.star_rating_percentage(2),
            1: service.star_rating_percentage(1),
        }

        context = {
            'service': service,
            'business': business,
            'reviews': reviews,
            'star_percentages': star_percentages,
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
    def get(self, request):
        cart_items = Cart.objects.filter(user=request.user).prefetch_related(
            'variations__product_variation', 
            'variations__service_variation',
            'product',
            'service'
        )
        
        cart_data = []
        total_price = 0
        
        for item in cart_items:
            item.calculate_total_price()  # This ensures the price is up-to-date
            item_data = {
                'id': item.id,
                'price': item.price,
                'quantity': item.quantity,
                'total_price': item.price * item.quantity,
                'hire': item.hire,
                'is_product': item.product is not None,
                'is_service': item.service is not None,
                'variations': [],
            }
            
            if item.product:
                item_data['name'] = item.product.name
                item_data['image'] = item.product.image.url
                item_data['business_name'] = item.product.business.business_name
                item_data['hire_duration'] = item.product.hire_duration
                item_data['base_price'] = item.product.hire_price if item.hire else item.product.price
            elif item.service:
                item_data['name'] = item.service.name
                item_data['image'] = item.service.image.url
                item_data['business_name'] = item.service.business.business_name
                item_data['hire_duration'] = item.service.hire_duration
                item_data['base_price'] = item.service.hire_price
            
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

        context = {
            'cart_items': cart_data,
            'cart_total': total_price,
            'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
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

        base_price = product.hire_price if hire and product.for_hire else product.price
        price = base_price
        for variation_id in selected_variations:
            variation = get_object_or_404(ProductVariation, id=variation_id)
            if variation.price:
                price += variation.price

        cart_item, created = Cart.objects.get_or_create(
            user=request.user,
            product=product,
            variation_key=variation_key,
            defaults={'quantity': quantity, 'price': price, 'hire': hire}
        )

        if not created:
            cart_item.quantity += quantity
            cart_item.price = price
            cart_item.hire = hire
            cart_item.save()

        CartItemVariation.objects.filter(cart=cart_item).delete()
        for variation_id in selected_variations:
            product_variation = get_object_or_404(ProductVariation, id=variation_id)
            CartItemVariation.objects.create(cart=cart_item, product_variation=product_variation)

        messages.success(request, f"{product.name} has been added to your cart.")
        return self.handle_response(request, True, f"{product.name} has been added to your cart.")

    def add_service_to_cart(self, request):
        service_id = request.POST.get('service_id')
        duration = int(request.POST.get('duration', 1))
        selected_options = request.POST.getlist('options')
        price = request.POST.get('price')

        if not service_id:
            messages.error(request, "No service selected.")
            return self.handle_response(request, False, "No service selected")

        service = get_object_or_404(Service, id=service_id)

        # If the service is available by quotation only, use the provided price
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

        # Filter out empty strings from selected options
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
            defaults={'quantity': duration, 'price': price, 'hire': True}  # Set hire=True here
        )

        if not created:
            cart_item.quantity += duration
            cart_item.price = price
            cart_item.hire = True  # Ensure hire is always True
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
    
    
    @method_decorator(require_POST)
    def validate_delivery(self, request):
        data = json.loads(request.body)
        customer_lat = data.get('lat')
        customer_lng = data.get('lng')
        
        print(f"Validating delivery for coordinates: Lat {customer_lat}, Lng {customer_lng}")
        
        cart_items = Cart.objects.filter(user=request.user).select_related('product__business', 'service__business')
        
        print(f"Number of items in cart: {cart_items.count()}")
        
        invalid_items = []
        
        for item in cart_items:
            if item.product:
                business = item.product.business
                item_name = item.product.name
                can_deliver = item.product.can_deliver
            else:  # It's a service
                business = item.service.business
                item_name = item.service.name
                can_deliver = True  # Assuming all services can be delivered
            
            print(f"\nChecking item: {item_name}")
            print(f"Business: {business.business_name}")
            print(f"Can deliver: {can_deliver}")
            print(f"Delivery radius: {business.delivery_radius} km")
            print(f"Business coordinates: Lat {business.latitude}, Lng {business.longitude}")
            
            if can_deliver and business.delivery_radius:
                business_coords = (business.latitude, business.longitude)
                customer_coords = (customer_lat, customer_lng)
                distance = geodesic(business_coords, customer_coords).km
                
                print(f"Distance to customer: {distance:.2f} km")
                print(f"Within radius: {distance <= business.delivery_radius}")
                
                if distance > business.delivery_radius:
                    invalid_items.append(f"{item_name} by {business.business_name}")
            else:
                print("Distance: N/A (delivery not available)")
        
        if invalid_items:
            message = "The following items exceed the delivery radius limit: " + ", ".join(invalid_items)
            print(f"\nValidation result: Invalid")
            print(f"Message: {message}")
            return JsonResponse({'valid': False, 'message': message})
        else:
            print(f"\nValidation result: Valid")
            print("Message: All items are within delivery radius")
            return JsonResponse({'valid': True})
        

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



from collections import defaultdict
from django.db.models import Prefetch
import traceback

def calculate_delivery_fee(order_items):
    businesses = {}
    total_delivery_fee = Decimal('0.00')
    
    print("\n--- Calculating Delivery Fee ---")
    
    for item in order_items:
        business = item.product.business if item.product else item.service.business
        business_id = business.id
        
        if business_id not in businesses:
            businesses[business_id] = {
                'delivery_required': False,
                'price_per_way': business.price_per_way,
                'name': business.business_name
            }
        
        if item.service:
            businesses[business_id]['delivery_required'] = True
            print(f"Service '{item.service.name}' from {business.business_name} requires delivery.")
        elif item.product:
            if item.delivery_method == 'delivery':
                businesses[business_id]['delivery_required'] = True
                print(f"Product '{item.product.name}' from {business.business_name} has delivery method: {item.delivery_method}")
            else:
                print(f"Product '{item.product.name}' from {business.business_name} has pickup method: {item.delivery_method}")

    for business_id, business_data in businesses.items():
        if business_data['delivery_required']:
            business_fee = business_data['price_per_way'] * 2
            total_delivery_fee += business_fee
            print(f"Delivery fee for {business_data['name']}: ${business_fee}")
        else:
            print(f"No delivery fee for {business_data['name']}")

    print(f"Total delivery fee: ${total_delivery_fee}")
    print("--- End of Delivery Fee Calculation ---\n")
    
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

class CreateCheckoutSessionView(LoginRequiredMixin, View):
    def get(self, request):
        print("CreateCheckoutSessionView GET: Entered get method")
        cart_items = Cart.objects.filter(user=request.user).select_related(
            'product', 'service', 'product__business', 'service__business'
        ).prefetch_related(
            'variations__product_variation__variation',
            'variations__service_variation__variation'
        )

        total_price = Decimal('0.00')
        domain = settings.SITE_URL  # Get the site URL

        delivery_fee = calculate_delivery_fee(cart_items)
        setup_packdown_fee = calculate_setup_packdown_fee(cart_items)

        cart_items_data = []
        delivery_methods = []

        businesses_terms = {}

        for item in cart_items:
            item_total_price = item.price * item.quantity
            total_price += item_total_price

            if item.product:
                product = item.product
                business = product.business
                if product.can_deliver and product.for_pickup:
                    delivery_methods.append({
                        'id': item.id,
                        'name': product.name,
                        'business_name': business.business_name,
                        'method': 'both',
                        'pickup_location': product.pickup_location,
                        'delivery_radius': business.delivery_radius,
                        'business_id': business.id,
                        'price_per_way': business.price_per_way,
                        'item_type': 'product',
                    })
                elif product.can_deliver:
                    delivery_methods.append({
                        'id': item.id,
                        'name': product.name,
                        'business_name': business.business_name,
                        'method': 'delivery',
                        'pickup_location': None,
                        'delivery_radius': business.delivery_radius,
                        'business_id': business.id,
                        'price_per_way': business.price_per_way,
                        'item_type': 'product',
                    })
                elif product.for_pickup:
                    delivery_methods.append({
                        'id': item.id,
                        'name': product.name,
                        'business_name': business.business_name,
                        'method': 'pickup',
                        'pickup_location': product.pickup_location,
                        'delivery_radius': None,
                        'business_id': business.id,
                        'price_per_way': business.price_per_way,
                        'item_type': 'product',
                    })
            elif item.service:
                service = item.service
                business = service.business
                delivery_methods.append({
                    'id': item.id,
                    'name': service.name,
                    'business_name': business.business_name,
                    'method': 'delivery',
                    'pickup_location': None,
                    'delivery_radius': business.delivery_radius,
                    'business_id': business.id,
                    'price_per_way': business.price_per_way,
                    'item_type': 'service',
                })

            if business.id not in businesses_terms:
                businesses_terms[business.id] = {
                    'name': business.business_name,
                    'terms': business.terms_and_conditions,
                    'terms_pdf': business.terms_and_conditions_pdf.url if business.terms_and_conditions_pdf else None
                }

            variations = []
            for variation in item.variations.all():
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

            cart_items_data.append({
                'id': item.id,
                'name': item.product.name if item.product else item.service.name,
                'business_name': item.product.business.business_name if item.product else item.service.business.business_name,
                'quantity': item.quantity,
                'price': float(item.price),
                'item_total_price': float(item_total_price),
                'variations': variations,
                'hire': item.hire,
                'hire_duration': item.product.hire_duration if item.product and item.hire else (item.service.hire_duration if item.service else None),
                'image': f"{domain}{item.product.image.url}" if item.product and item.product.image else (f"{domain}{item.service.image.url}" if item.service and item.service.image else None),
                'item_type': 'product' if item.product else 'service',
                'delivery_method': item.delivery_method,
            })

            print(f"Cart item: {cart_items_data[-1]}")  # Debug: Cart item data

        total_price += delivery_fee + setup_packdown_fee

        return render(request, 'event/checkout.html', {
            'cart_items': cart_items_data,
            'total_price': float(total_price),
            'delivery_fee': float(delivery_fee),
            'setup_packdown_fee': float(setup_packdown_fee),
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
            'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
            'delivery_methods': delivery_methods,
            'businesses_terms': businesses_terms,
        })

    def post(self, request, *args, **kwargs):
        print("CreateCheckoutSessionView POST: Entered post method")
        cart_items = Cart.objects.filter(user=request.user).prefetch_related('variations__product_variation')
        current_domain = request.get_host()
        protocol = 'https' if request.is_secure() else 'http'
        YOUR_DOMAIN = f"{protocol}://{current_domain}"

        line_items = []
        total_amount = Decimal('0.00')
        setup_packdown_fee = Decimal('0.00')

        request_data = json.loads(request.body)
        delivery_methods = request_data.get('delivery_methods', {})
        payment_method = request_data.get('payment_method', 'card')
        signatures = request_data.get('signatures', {})

        print(f"Received delivery methods: {delivery_methods}")  # Debug: Delivery methods
        print(f"Received signatures: {signatures}")  # Debug: Signatures

        businesses = {}

        if len(signatures) != len(set(item.product.business.id if item.product else item.service.business.id for item in cart_items)):
            return JsonResponse({'error': 'Please sign all terms and conditions before proceeding.'}, status=400)

        for item in cart_items:
            if item.product:
                business = item.product.business
                name = item.product.name
                image = item.product.image.url if item.product.image else None
                price = item.price
                if item.product.setup_packdown_fee:
                    setup_packdown_fee += item.product.setup_packdown_fee_amount
            else:
                business = item.service.business
                name = item.service.name
                image = item.service.image.url if item.service.image else None
                price = item.price
                if item.service.setup_packdown_fee:
                    setup_packdown_fee += item.service.setup_packdown_fee_amount

            delivery_method = delivery_methods.get(str(item.id))
            if delivery_method == 'delivery' or item.service:
                if business.id not in businesses:
                    businesses[business.id] = {
                        'business': business,
                        'delivery_required': True,
                        'price_per_way': business.price_per_way
                    }
                else:
                    businesses[business.id]['delivery_required'] = True

            amount = int(float(price) * 100)
            total_amount += amount * item.quantity

            line_items.append({
                'price_data': {
                    'currency': 'aud',
                    'product_data': {
                        'name': name,
                        'images': [f"{YOUR_DOMAIN}{image}"] if image else [],
                    },
                    'unit_amount': amount,
                },
                'quantity': item.quantity,
            })

            print(f"Line item added: {line_items[-1]}")  # Debug: Line item data

        delivery_fee = sum(business['price_per_way'] * 2 for business in businesses.values() if business['delivery_required'])

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
            total_amount += int(delivery_fee * 100)

            print(f"Delivery fee added: {delivery_fee}")  # Debug: Delivery fee

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
            total_amount += int(setup_packdown_fee * 100)

            print(f"Setup/Packdown fee added: {setup_packdown_fee}")  # Debug: Setup/Packdown fee

        address = request_data.get('address', '')
        city = request_data.get('city', '')
        state = request_data.get('state', '')
        postal_code = request_data.get('postal_code', '')
        note = request_data.get('note', '')
        event_date = request_data.get('event_date', '')
        event_time = request_data.get('event_time', '')
        formatted_event_time = datetime.strptime(event_time, '%H:%M').strftime('%I:%M %p') if event_time else ''
        name = request_data.get('name', 'Customer')
        payment_method = request_data.get('payment_method', 'card')

        print(f"Final total amount: {total_amount}")  # Debug: Final total amount

        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=[payment_method],
                line_items=line_items,
                mode='payment',
                success_url=YOUR_DOMAIN + reverse('success'),
                cancel_url=YOUR_DOMAIN + reverse('cancel'),
                payment_intent_data={
                    'shipping': {
                        'name': name,
                        'address': {
                            'line1': address,
                            'city': city,
                            'state': state,
                            'postal_code': postal_code,
                            'country': 'AU',
                        },
                    },
                },
            )

            request.session['checkout_session_id'] = checkout_session.id
            request.session['business_items'] = self.get_business_items(cart_items, delivery_methods)
            request.session['address'] = request_data.get('address')
            request.session['city'] = request_data.get('city')
            request.session['state'] = request_data.get('state')
            request.session['postal_code'] = request_data.get('postal_code')
            request.session['note'] = request_data.get('note')
            request.session['event_date'] = request_data.get('event_date')
            request.session['event_time'] = request_data.get('event_time')
            request.session['cart_items'] = self.get_cart_items(cart_items, delivery_methods)
            request.session['delivery_fee'] = float(delivery_fee)
            request.session['setup_packdown_fee'] = float(setup_packdown_fee)
            request.session['delivery_methods'] = delivery_methods
            request.session['payment_method'] = payment_method
            request.session['signatures'] = signatures
            request.session['payment_intent_id'] = checkout_session.payment_intent

            print(f"Checkout session created: {checkout_session.id}")  # Debug: Checkout session ID

            return JsonResponse({'id': checkout_session.id})
        except Exception as e:
            print(f"Error in creating checkout session: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    def get_business_items(self, cart_items, delivery_methods):
        print("CreateCheckoutSessionView: Entered get_business_items method")
        business_items = defaultdict(list)
        domain = settings.SITE_URL  # Get the site URL

        for item in cart_items:
            business = item.product.business if item.product else item.service.business
            total_price = float(item.price * item.quantity)
            variations = [
                {
                    'variation_name': cv.product_variation.variation.name if cv.product_variation else cv.service_variation.variation.name,
                    'variation_value': cv.product_variation.value if cv.product_variation else cv.service_variation.value
                }
                for cv in item.variations.all()
            ]
            business_items[str(business.id)].append({
                'amount': int(float(item.price) * 100 * item.quantity),
                'business': business.stripe_account_id,
                'item_id': item.product.id if item.product else item.service.id,
                'item_type': 'product' if item.product else 'service',
                'quantity': item.quantity,
                'total_price': total_price,
                'variations': variations,
                'price': float(item.price),
                'hire': item.hire,
                'hire_duration': item.product.hire_duration if item.product and item.hire else (item.service.hire_duration if item.service else None),
                'delivery_method': delivery_methods.get(str(item.id), 'delivery'),
                'image': f"{domain}{item.product.image.url}" if item.product and item.product.image else (f"{domain}{item.service.image.url}" if item.service and item.service.image else None)
            })

            print(f"Business item: {business_items[str(business.id)]}")  # Debug: Business item data
        return dict(business_items)

    def get_cart_items(self, cart_items, delivery_methods):
        print("CreateCheckoutSessionView: Entered get_cart_items method")
        cart_items_data = []
        domain = settings.SITE_URL  # Get the site URL

        for item in cart_items:
            is_product = bool(item.product)
            is_service = bool(item.service)

            item_data = {
                'id': item.id,
                'item_id': item.product.id if is_product else item.service.id,
                'item_type': 'product' if is_product else 'service',
                'hire': item.hire if is_product else True,
                'hire_duration': item.product.hire_duration if is_product and item.hire else (item.service.hire_duration if is_service else None),
                'name': item.product.name if is_product else item.service.name,
                'business_name': item.product.business.business_name if is_product else item.service.business.business_name,
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
                'delivery_method': delivery_methods.get(str(item.id), 'delivery'),
                'pickup_location': item.product.pickup_location if is_product and item.product.for_pickup else None,
                'image': f"{domain}{item.product.image.url}" if is_product and item.product.image else (f"{domain}{item.service.image.url}" if is_service and item.service.image else None),
            }
            cart_items_data.append(item_data)

            print(f"Cart item data: {cart_items_data[-1]}")  # Debug: Cart item data
        return cart_items_data

class PaymentSuccessView(LoginRequiredMixin, View):
    def get(self, request):
        print("PaymentSuccessView GET: Entered get method")
        checkout_session_id = request.session.get('checkout_session_id')
        payment_intent_id = request.session.get('payment_intent_id')
        business_items = request.session.get('business_items')
        cart_items = request.session.get('cart_items')
        address = request.session.get('address')
        city = request.session.get('city')
        state = request.session.get('state')
        postal_code = request.session.get('postal_code')
        note = request.session.get('note')
        event_date = request.session.get('event_date')
        event_time = request.session.get('event_time')
        delivery_fee = request.session.get('delivery_fee')
        setup_packdown_fee = request.session.get('setup_packdown_fee')
        payment_method = request.session.get('payment_method', 'card')
        delivery_methods = request.session.get('delivery_methods', {})
        signatures = request.session.get('signatures', {})

        print(f"Session data: checkout_session_id={checkout_session_id}, payment_intent_id={payment_intent_id}, business_items={business_items}, cart_items={cart_items}")  # Debug: Session data

        try:
            session = stripe.checkout.Session.retrieve(checkout_session_id)
            payment_intent_id = session.payment_intent

            characters = string.ascii_letters + string.digits
            ref_code = ''.join(random.choice(characters) for _ in range(10))

            total_price = sum(item['quantity'] * item['price'] for item in cart_items)

            formatted_event_time = datetime.strptime(event_time, '%H:%M').time() if event_time else None

            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user,
                    ref_code=ref_code,
                    total_amount=total_price,
                    address=address,
                    city=city,
                    state=state,
                    postal_code=postal_code,
                    note=note,
                    event_date=event_date,
                    event_time=formatted_event_time,
                    status='pending',
                    delivery_fee=delivery_fee,
                    setup_packdown_fee=setup_packdown_fee,
                    payment_method=payment_method,
                    payment_intent=payment_intent_id,
                )

                print(f"Order created: {order}")  # Debug: Order created

                for item in cart_items:
                    try:
                        if item['item_type'] == 'product':
                            try:
                                product = Product.objects.get(id=item['item_id'])
                                service = None
                                business = product.business
                            except Product.DoesNotExist:
                                service = Service.objects.get(id=item['item_id'])
                                product = None
                                business = service.business
                        else:
                            service = Service.objects.get(id=item['item_id'])
                            product = None
                            business = service.business

                        order_item = OrderItem.objects.create(
                            order=order,
                            product=product,
                            service=service,
                            quantity=item['quantity'],
                            price=item['price'],
                            variations=item['variations'],
                            hire=item['hire'],
                            hire_duration=item['hire_duration'],
                            delivery_method=delivery_methods.get(str(item['id']), 'delivery')
                        )

                        OrderApproval.objects.get_or_create(order=order, business=business)

                        print(f"Order item created: {order_item}")  # Debug: Order item created
                    except (Product.DoesNotExist, Service.DoesNotExist) as e:
                        print(f"Error processing item: {item}. Error: {str(e)}")
                        continue

                # Save signatures
                for business_id, signature_data in signatures.items():
                    OrderTermsSignature.objects.create(
                        order=order,
                        business_id=business_id,
                        signature=self.base64_to_image(signature_data)
                    )
                    print(f"Signature saved for business {business_id}")  # Debug: Signature saved

            cart_items = self.get_cart_items(order.items.all())

            Cart.objects.filter(user=request.user).delete()

            self.send_order_emails(order, business_items, cart_items)

            for key in ['checkout_session_id', 'business_items', 'cart_items', 'address', 'city', 'state', 'postal_code', 'note', 'event_date', 'event_time', 'delivery_methods', 'signatures']:
                if key in request.session:
                    del request.session[key]

            
            cart_items = self.get_cart_items(order.items.all())
            domain = settings.SITE_URL  # Get the site URL
            
            subtotal = sum(item['item_total_price'] for item in cart_items)
            total_price = subtotal + order.delivery_fee + order.setup_packdown_fee

            print(f"Order processed successfully: {order.ref_code}")  # Debug: Order processed
            return render(request, 'event/success.html', {'order': order, 'total_price': total_price})
        except Exception as e:
            print(f"Error in PaymentSuccessView: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)

    def base64_to_image(self, base64_string):
        format, imgstr = base64_string.split(';base64,')
        ext = format.split('/')[-1]
        print(f"Converting base64 to image: format={format}, ext={ext}")  # Debug: base64 conversion
        return ContentFile(base64.b64decode(imgstr), name=f'signature.{ext}')
    
    def send_order_emails(self, order, business_items, cart_items):
        print("PaymentSuccessView: Entered send_order_emails method")
        try:
            cart_items = self.get_cart_items(order.items.all())
            domain = settings.SITE_URL  # Get the site URL
            
            subtotal = sum(item['item_total_price'] for item in cart_items)
            total_price = subtotal + order.delivery_fee + order.setup_packdown_fee
            
            customer_subject = f"Order Received - Pending Approval - {order.ref_code}"
            customer_message = render_to_string('event/customer_checkout_email.html', {
                'order': order,
                'cart_items': cart_items,
                'total_price': total_price,
                'delivery_fee': order.delivery_fee,
                'setup_packdown_fee': order.setup_packdown_fee,
                'subtotal': subtotal,
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

            print(f"Customer email sent to {order.user.email}")  # Debug: Customer email sent

            for business_id, items in business_items.items():
                business = Business.objects.get(id=business_id)
                business_cart_items = [item for item in cart_items if item['business_name'] == business.business_name]
                business_subtotal = sum(item['item_total_price'] for item in business_cart_items)
                
                business_setup_packdown_fee = sum(
                    item['setup_packdown_fee_amount'] if item.get('setup_packdown_fee', False) else 0
                    for item in business_cart_items
                )
                
                business_delivery_fee = business.price_per_way * 2 if any(item['delivery_method'] == 'delivery' for item in business_cart_items) else 0
                
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

                print(f"Business email sent to {business.email}")  # Debug: Business email sent
        except Exception as e:
            print(f"Error in send_order_emails: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    def get_cart_items(self, order_items):
        print("PaymentSuccessView: Entered get_cart_items method")
        cart_items_data = []
        domain = settings.SITE_URL  # Get the site URL

        for item in order_items:
            is_product = bool(item.product)
            is_service = bool(item.service)

            if is_product:
                setup_packdown_fee = item.product.setup_packdown_fee
                setup_packdown_fee_amount = item.product.setup_packdown_fee_amount if setup_packdown_fee else 0
            elif is_service:
                setup_packdown_fee = item.service.setup_packdown_fee
                setup_packdown_fee_amount = item.service.setup_packdown_fee_amount if setup_packdown_fee else 0
            else:
                setup_packdown_fee = False
                setup_packdown_fee_amount = 0

            item_data = {
                'id': item.id,
                'item_id': item.product.id if is_product else item.service.id,
                'name': item.product.name if is_product else item.service.name,
                'business_name': item.product.business.business_name if is_product else item.service.business.business_name,
                'quantity': item.quantity,
                'price': float(item.price),
                'item_total_price': float(item.price * item.quantity),
                'variations': item.variations or [],
                'item_type': 'product' if is_product else 'service',
                'hire': item.hire,
                'hire_duration': item.hire_duration,
                'delivery_method': item.delivery_method,
                'pickup_location': item.product.pickup_location if is_product and item.product.for_pickup else None,
                'image': f"{domain}{item.product.image.url}" if is_product and item.product.image else (f"{domain}{item.service.image.url}" if is_service and item.service.image else None),
                'setup_packdown_fee': setup_packdown_fee,
                'setup_packdown_fee_amount': float(setup_packdown_fee_amount),
                'payment_method': item.order.payment_method,
            }

            cart_items_data.append(item_data)
            print(f"Order item data: {cart_items_data[-1]}")  # Debug: Order item data
        return cart_items_data



class ReviewOrderView(UserPassesTestMixin, View):
    def test_func(self):
        order = get_object_or_404(Order, id=self.kwargs['order_id'])
        business = get_object_or_404(Business, id=self.kwargs['business_id'])
        return self.request.user == business.seller

    def get(self, request, order_id, business_id):
        order = get_object_or_404(Order, id=order_id)
        business = get_object_or_404(Business, id=business_id)
        order_items = order.items.filter(
            models.Q(product__business=business) |
            models.Q(service__business=business)
        )

        # Calculate business subtotal
        business_subtotal = sum(item.price * item.quantity for item in order_items)
        
        # Calculate setup/packdown fee for the business
        business_setup_packdown_fee = sum(
            item.product.setup_packdown_fee_amount if item.product and item.product.setup_packdown_fee else
            item.service.setup_packdown_fee_amount if item.service and item.service.setup_packdown_fee else 0
            for item in order_items
        )
        
        # Calculate delivery fee for the business
        business_delivery_fee = business.price_per_way * 2 if any(item.delivery_method == 'delivery' for item in order_items) else 0
        
        # Calculate total for the business
        business_total = business_subtotal + business_setup_packdown_fee + business_delivery_fee

        items_data = []
        for item in order_items:
            item_data = {
                'product': item.product,
                'service': item.service,
                'quantity': item.quantity,
                'price': item.price,
                'variations': item.variations,
                'hire': item.product.for_hire if item.product else True,
                'hire_duration': item.product.hire_duration if item.product and item.product.for_hire else (item.service.hire_duration if item.service else None),
            }
            items_data.append(item_data)

        return render(request, 'event/review_order.html', {
            'order': order,
            'business': business,
            'order_items': items_data,
            'business_subtotal': business_subtotal,
            'business_setup_packdown_fee': business_setup_packdown_fee,
            'business_delivery_fee': business_delivery_fee,
            'business_total': business_total,
        })


    def post(self, request, order_id, business_id):
        order = get_object_or_404(Order, id=order_id)
        business = get_object_or_404(Business, id=business_id)
        action = request.POST.get('action')

        if action == 'approve':
            approval, created = OrderApproval.objects.get_or_create(order=order, business=business)
            if not approval.approved:
                approval.approved = True
                approval.approval_date = timezone.now()
                approval.save()

                if order.all_businesses_approved():
                    order.status = 'approved'
                    order.save()

                    self.process_payment(order)
                    self.send_confirmation_emails(order)

                    messages.success(request, "Order has been approved. Payments have been processed.")
                else:
                    messages.success(request, "Order has been approved by you, waiting for other businesses in the order to approve to process payment.")
            else:
                messages.info(request, "Order was already approved by you.")

        elif action == 'reject':
            approval, created = OrderApproval.objects.get_or_create(order=order, business=business)
            approval.approved = False
            approval.approval_date = timezone.now()
            approval.save()
            order.status = 'rejected'
            order.save()
            self.process_refund(order)
            self.send_rejection_emails(order)
            messages.success(request, "Order has been rejected and payment has been refunded.")

        return redirect('business_orders')

    def process_payment(self, order):
        for item in order.items.all():
            business = item.product.business if item.product else item.service.business
            amount = int(item.price * item.quantity * Decimal('100') * Decimal('0.85'))
            stripe.Transfer.create(
                amount=amount,
                currency='aud',
                destination=business.stripe_account_id,
                transfer_group=order.ref_code,
            )

    def process_refund(self, order):
        if not order.payment_intent:
            raise ValueError("No payment intent found for this order.")
        
        stripe.Refund.create(payment_intent=order.payment_intent)

    def send_confirmation_emails(self, order):
        # Collect delivery methods from each order item
        delivery_methods = {str(item.id): item.delivery_method for item in order.items.all()}
        cart_items = self.get_cart_items(order.items.all(), delivery_methods)
        subtotal = sum(item['item_total_price'] for item in cart_items)

        subtotal = Decimal(str(subtotal))
        delivery_fee = order.delivery_fee or Decimal('0')
        setup_packdown_fee = order.setup_packdown_fee or Decimal('0')

        total_price = subtotal + delivery_fee + setup_packdown_fee
        
        customer_subject = f"Order Confirmed - {order.ref_code}"
        customer_message = render_to_string('event/customer_order_confirmed_email.html', {
            'order': order,
            'cart_items': cart_items,
            'subtotal': subtotal,
            'delivery_fee': delivery_fee,
            'setup_packdown_fee': setup_packdown_fee,
            'total_price': total_price
        })
        customer_email = EmailMultiAlternatives(
            subject=customer_subject,
            body="Your order has been confirmed.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.user.email]
        )
        customer_email.attach_alternative(customer_message, "text/html")
        customer_email.send()

        for item in order.items.all():
            business = item.product.business if item.product else item.service.business
            business_cart_items = [item for item in cart_items if item['business_name'] == business.business_name]
            business_subtotal = sum(item['item_total_price'] for item in business_cart_items)
            
            business_setup_packdown_fee = sum(
                item['setup_packdown_fee_amount'] if item.get('setup_packdown_fee', False) else 0
                for item in business_cart_items
            )
            
            business_delivery_fee = business.price_per_way * 2 if any(item['delivery_method'] == 'delivery' for item in business_cart_items) else 0
            
            business_total = business_subtotal + business_setup_packdown_fee + business_delivery_fee
            
            business_subject = f"Order Confirmed - {order.ref_code}"
            business_message = render_to_string('event/business_order_confirmed_email.html', {
                'order': order,
                'business': business,
                'cart_items': business_cart_items,
                'business_subtotal': business_subtotal,
                'business_setup_packdown_fee': business_setup_packdown_fee,
                'business_delivery_fee': business_delivery_fee,
                'business_total': business_total
            })
            business_email = EmailMultiAlternatives(
                subject=business_subject,
                body="An order has been confirmed.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[business.email]
            )
            business_email.attach_alternative(business_message, "text/html")
            business_email.send()

    def send_rejection_emails(self, order):
        # Collect delivery methods from each order item
        delivery_methods = {str(item.id): item.delivery_method for item in order.items.all()}
        cart_items = self.get_cart_items(order.items.all(), delivery_methods)
        subtotal = sum(item['item_total_price'] for item in cart_items)

        subtotal = Decimal(str(subtotal))
        delivery_fee = order.delivery_fee or Decimal('0')
        setup_packdown_fee = order.setup_packdown_fee or Decimal('0')

        total_price = subtotal + delivery_fee + setup_packdown_fee
        
        customer_subject = f"Order Rejected - {order.ref_code}"
        customer_message = render_to_string('event/customer_order_rejected_email.html', {
            'order': order,
            'cart_items': cart_items,
            'subtotal': subtotal,
            'delivery_fee': delivery_fee,
            'setup_packdown_fee': setup_packdown_fee,
            'total_price': total_price
        })
        customer_email = EmailMultiAlternatives(
            subject=customer_subject,
            body="Your order has been rejected.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.user.email]
        )
        customer_email.attach_alternative(customer_message, "text/html")
        customer_email.send()

        for item in order.items.all():
            business = item.product.business if item.product else item.service.business
            business_cart_items = [item for item in cart_items if item['business_name'] == business.business_name]
            business_subtotal = sum(item['item_total_price'] for item in business_cart_items)
            
            business_setup_packdown_fee = sum(
                item['setup_packdown_fee_amount'] if item.get('setup_packdown_fee', False) else 0
                for item in business_cart_items
            )
            
            business_delivery_fee = business.price_per_way * 2 if any(item['delivery_method'] == 'delivery' for item in business_cart_items) else 0
            
            business_total = business_subtotal + business_setup_packdown_fee + business_delivery_fee
            
            business_subject = f"Order Rejected - {order.ref_code}"
            business_message = render_to_string('event/business_order_rejected_email.html', {
                'order': order,
                'business': business,
                'cart_items': business_cart_items,
                'business_subtotal': business_subtotal,
                'business_setup_packdown_fee': business_setup_packdown_fee,
                'business_delivery_fee': business_delivery_fee,
                'business_total': business_total
            })
            business_email = EmailMultiAlternatives(
                subject=business_subject,
                body="An order has been rejected.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[business.email]
            )
            business_email.attach_alternative(business_message, "text/html")
            business_email.send()

    def calculate_total_for_business(self, order, business):
        total = Decimal('0.00')
        for item in order.items.filter(
                models.Q(product__business=business) |
                models.Q(service__business=business)):
            total += item.price * item.quantity
        return total

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['business'] = self.request.user.business
        return context
    
    
    def get_cart_items(self, cart_items, delivery_methods):
        print("CreateCheckoutSessionView: Entered get_cart_items method")
        cart_items_data = []
        domain = settings.SITE_URL  # Get the site URL

        for item in cart_items:
            is_product = bool(item.product)
            is_service = bool(item.service)

            # Check if item.variations is a list and extract variations accordingly
            if isinstance(item.variations, list):
                variations = [
                    {
                        'variation_name': cv.get('variation_name'),
                        'variation_value': cv.get('variation_value')
                    }
                    for cv in item.variations
                ]
            else:
                variations = []

            item_data = {
                'id': item.id,
                'item_id': item.product.id if is_product else item.service.id,
                'item_type': 'product' if is_product else 'service',
                'hire': item.hire if is_product else True,
                'hire_duration': item.product.hire_duration if is_product and item.hire else (item.service.hire_duration if is_service else None),
                'name': item.product.name if is_product else item.service.name,
                'business_name': item.product.business.business_name if is_product else item.service.business.business_name,
                'quantity': item.quantity,
                'price': float(item.price),
                'item_total_price': float(item.price * item.quantity),
                'variations': variations,
                'delivery_method': delivery_methods.get(str(item.id), 'delivery'),
                'pickup_location': item.product.pickup_location if is_product and item.product.for_pickup else None,
                'image': f"{domain}{item.product.image.url}" if is_product and item.product.image else (f"{domain}{item.service.image.url}" if is_service and item.service.image else None),
            }
            cart_items_data.append(item_data)

            print(f"Cart item data: {cart_items_data[-1]}")  # Debug: Cart item data
        return cart_items_data


class BusinessOrdersView(UserPassesTestMixin, ListView):
    model = Order
    template_name = 'event/business_orders.html'
    context_object_name = 'orders'
    paginate_by = 9

    def test_func(self):
        return hasattr(self.request.user, 'business')

    def get_queryset(self):
        status_filter = self.request.GET.get('status', '')
        queryset = Order.objects.filter(approvals__business=self.request.user.business).prefetch_related(
            'items__product', 'items__service', 'items__product__business', 'items__service__business'
        ).order_by('-created_at')  # Ordering by most recent
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        orders_with_totals = []
        for order in context['orders']:
            business = self.request.user.business
            business_total = self.calculate_total_for_business(order, business)
            delivery_fee = business.price_per_way * 2 if any(item.delivery_method == 'delivery' for item in order.items.filter(
                models.Q(product__business=business) |
                models.Q(service__business=business)
            )) else 0
            
            # Correctly access setup_packdown_fee from the related Product or Service
            setup_packdown_fee = sum(
                item.product.setup_packdown_fee_amount if item.product and item.product.setup_packdown_fee else
                item.service.setup_packdown_fee_amount if item.service and item.service.setup_packdown_fee else 0
                for item in order.items.filter(
                    models.Q(product__business=business) |
                    models.Q(service__business=business)
                )
            )

            business_total += delivery_fee + setup_packdown_fee
            orders_with_totals.append((order, business_total))

        context['orders_with_totals'] = orders_with_totals
        context['business'] = self.request.user.business
        context['status_choices'] = Order.STATUS_CHOICES
        context['current_status'] = self.request.GET.get('status', '')
        return context

    def calculate_total_for_business(self, order, business):
        total = Decimal('0.00')
        for item in order.items.filter(
                models.Q(product__business=business) |
                models.Q(service__business=business)):
            total += item.price * item.quantity
        return total


class UserOrdersView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        orders = Order.objects.filter(user=request.user).order_by('-created_at')
        paginator = Paginator(orders, 9)  # 10 orders per page

        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        return render(request, 'event/user_orders.html', {'orders': page_obj})

class UserOrderDetailsView(LoginRequiredMixin, View):
    def get(self, request, order_id, *args, **kwargs):
        order = get_object_or_404(Order, id=order_id, user=request.user)
        order_items = order.items.all()
        return render(request, 'event/user_order_detail.html', {
            'order': order,
            'order_items': order_items,
        })


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
            domain = '127.0.0.1:8000'
            
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
            send_email_task.delay(subject, email_body, from_email, recipient_list)
            
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
            domain = '127.0.0.1:8000'
            
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
            send_email_task.delay(subject, email_body, from_email, recipient_list)
            
            return redirect('message_buyer', username=user.username)

    # Mark messages as read
    Message.objects.filter(recipient=request.user, sender=user).update(is_read=True)

    conversation_messages = Message.objects.filter(
        Q(sender=request.user, recipient=user) |
        Q(sender=user, recipient=request.user)
    ).filter(business=business).order_by('timestamp')

    can_create_quote = bool(request.user.business)
    business_services = business.services.all() if business else []

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
                        domain = '127.0.0.1:8000'
                        
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
                        
                        send_email_task.delay(subject, email_body, from_email, recipient_list)
                        
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
                    domain = '127.0.0.1:8000'
                    
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
                    
                    send_email_task.delay(subject, email_body, from_email, recipient_list)
                    
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
                
                send_email_task.delay(subject, email_body, from_email, recipient_list)
                
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
            business_services = selected_business.services.all()
        else:
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
            business_services = business.services.all()
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
                    subscription_start_date=timezone.now()
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

                # Create Stripe Connect account for the venue
                print("Creating Stripe Connect account...")
                print(f"Venue email: {venue.venue_email}")
                print(f"Business profile URL: {settings.DEFAULT_VENUE_URL}")

                account = stripe.Account.create(
                    type='express',
                    country='AU',
                    email=venue.venue_email,
                    business_type='individual',
                    capabilities={
                        'card_payments': {'requested': True},
                        'transfers': {'requested': True},
                    },
                    business_profile={
                        'name': venue.venue_name,
                        'url': settings.DEFAULT_VENUE_URL,
                    },
                )
                venue.stripe_account_id = account.id
                venue.save()

                # Redirect to Stripe's onboarding flow
                refresh_url = request.build_absolute_uri(reverse('venue_vendor_register'))
                return_url = request.build_absolute_uri(reverse('venue_detail', kwargs={'venue_slug': venue.venue_slug}))

                print(f"Refresh URL: {refresh_url}")
                print(f"Return URL: {return_url}")

                account_link = stripe.AccountLink.create(
                    account=venue.stripe_account_id,
                    refresh_url=refresh_url,
                    return_url=return_url,
                    type='account_onboarding',
                )

                print(f"Account link URL: {account_link.url}")

                return redirect(account_link.url)

        except Exception as e:
            print(f"Error occurred: {str(e)}")  # Log the actual exception message
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('venue_vendor_register')


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
            messages.success(request, 'Your enquiry has been sent successfully!')
            return redirect('venue_detail', venue_slug=venue_slug)

        messages.error(request, 'All fields are required for enquiry.')
        return render(request, 'event/venue_detail.html', {'venue': venue})


@method_decorator(login_required, name='dispatch')
class SubscriptionCancelView(View):
    def get(self, request, venue_slug):
        venue = get_object_or_404(Venue, venue_slug=venue_slug, user=request.user)
        return render(request, 'event/cancel_subscription_confirm.html', {'venue': venue})

    def post(self, request, venue_slug):
        venue = get_object_or_404(Venue, venue_slug=venue_slug, user=request.user)
        try:
            # Cancel the Stripe account if it exists
            if venue.stripe_account_id:
                stripe.Account.delete(venue.stripe_account_id)

            # Delete the venue and related data
            venue.delete()
            messages.success(request, 'Your subscription has been cancelled and your venue has been removed.')
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