from django.shortcuts import render
from .models import Product, Business, OpeningHour, Cart, Message, State, Variation, ProductVariation, CartItemVariation, ProductReview, Order, OrderItem, Refund, Service, ProductCategory, ServiceCategory, ServiceImage, ServiceReview, Quote, EventCategory, Award, ServiceVariation, ServiceVariationOption, Venue, VenueImage, VenueOpeningHour, Amenity, VenueReview, VenueView, VenueInquiry
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
    paginator = Paginator(items, 8)  # Show 8 items per page
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




class BusinessRegistrationView(LoginRequiredMixin, View):
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
            email = request.POST.get('email')
            profile_picture = request.FILES.get('profile_picture')
            banner_image = request.FILES.get('banner_image')

            user = request.user
            user.is_seller = True
            user.save()

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

                return redirect(account_link.url)
            except stripe.error.StripeError as e:
                messages.error(request, f"Stripe error: {e.user_message}")
                business.delete()
                return redirect('business_registration')

        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
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



class BusinessOrdersView(LoginRequiredMixin, View):
    def get(self, request, business_slug):
        business = Business.objects.get(business_slug=business_slug)
        if request.user != business.seller:
            return JsonResponse({'error': 'Unauthorized access'}, status=403)

        # Fetch orders related to this business
        orders = Order.objects.filter(items__product__business=business).distinct().order_by('-created_at')
        order_data = []
        for order in orders:
            items = order.items.filter(product__business=business)
            order_data.append({
                'order': order,
                'items': items
            })

        return render(request, 'event/business_orders.html', {'business': business, 'orders': order_data})

    def post(self, request, business_slug):
        business = Business.objects.get(business_slug=business_slug)
        if request.user != business.seller:
            return JsonResponse({'error': 'Unauthorized access'}, status=403)

        order_id = request.POST.get('order_id')
        new_status = request.POST.get('status')
        order = Order.objects.get(id=order_id)

        # Update the order status
        order.order_status = new_status
        order.save()

        # Send email to the user based on the new status
        self.send_status_update_email(order, business, new_status)

        # Add a success message
        messages.success(request, f'Order status updated to {new_status} and email sent to the customer.')

        return redirect('business_orders', business_slug=business_slug)

    def send_status_update_email(self, order, business, status):
        user = order.user
        item_details = [
            f"{item.quantity} x {item.product.name} ({', '.join([f'{k}: {v}' for k, v in item.variations.items()]) if item.variations else ''})"
            for item in order.items.filter(product__business=business)
        ]

        if status == 'shipped':
            email_subject = f"Your order {order.ref_code} has been shipped"
            email_template = 'event/order_shipped_email.html'
        elif status == 'delivered':
            email_subject = f"Your order {order.ref_code} has been delivered"
            email_template = 'event/order_delivered_email.html'
        else:
            return

        email_body = render_to_string(email_template, {
            'user': user,
            'business': business,
            'order': order,
            'item_details': item_details
        })

        email = EmailMultiAlternatives(
            subject=email_subject,
            body=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.attach_alternative(email_body, "text/html")
        email.send(fail_silently=False)



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


class CartView(LoginRequiredMixin, View):
    def get(self, request):
        cart_items = Cart.objects.filter(user=request.user).prefetch_related('variations__product_variation')
        total_price = 0
        
        for item in cart_items:
            if item.product:
                item_price = item.product.price
                for variation in item.variations.all():
                    if variation.product_variation.price:
                        item_price = variation.product_variation.price
            else:  # It's a service
                item_price = item.price
            
            item.price = item_price
            item.total_price = item_price * item.quantity
            total_price += item.total_price

        context = {
            'cart_items': cart_items,
            'cart_total': total_price
        }
        return render(request, 'event/cart.html', context)

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
        color = request.POST.get('color')
        size = request.POST.get('size')

        if not product_id:
            messages.error(request, "No product selected.")
            return self.handle_response(request, False, "No product selected")

        product = get_object_or_404(Product, id=product_id)

        selected_variations = []
        if color:
            selected_variations.append(color)
        if size:
            selected_variations.append(size)

        variation_categories = product.variations.count()

        if product.has_variations and len(selected_variations) != variation_categories:
            messages.error(request, f"Please select all {variation_categories} variations.")
            return self.handle_response(request, False, f"Please select all {variation_categories} variations")

        variation_key = "-".join(sorted(selected_variations))

        # Calculate the price based on variations
        price = product.price
        if selected_variations:
            for variation_id in selected_variations:
                variation = get_object_or_404(ProductVariation, id=variation_id)
                if variation.price:
                    price = variation.price
                    break

        cart_item, created = Cart.objects.get_or_create(
            user=request.user,
            product=product,
            variation_key=variation_key,
            defaults={'quantity': quantity, 'price': price}
        )

        if not created:
            cart_item.quantity += quantity
            cart_item.price = price  # Update price even if the item already exists
            cart_item.save()

        if color:
            color_variation = get_object_or_404(ProductVariation, id=color)
            CartItemVariation.objects.get_or_create(cart=cart_item, product_variation=color_variation)
        if size:
            size_variation = get_object_or_404(ProductVariation, id=size)
            CartItemVariation.objects.get_or_create(cart=cart_item, product_variation=size_variation)

        messages.success(request, f"{product.name} has been added to your cart.")
        return self.handle_response(request, True, f"{product.name} has been added to your cart.")

    def add_service_to_cart(self, request):
        service_id = request.POST.get('service_id')
        price = float(request.POST.get('price', 0))
        quantity = int(request.POST.get('quantity', 1))

        if not service_id:
            messages.error(request, "No service selected.")
            return self.handle_response(request, False, "No service selected")

        service = get_object_or_404(Service, id=service_id)

        cart_item, created = Cart.objects.get_or_create(
            user=request.user,
            service=service,
            defaults={'quantity': quantity, 'price': price}
        )

        if not created:
            cart_item.quantity += quantity
            cart_item.price = price  # Update price even if the item already exists
            cart_item.save()

        messages.success(request, f"{service.name} has been added to your cart.")
        return self.handle_response(request, True, f"{service.name} has been added to your cart.")

    def handle_response(self, request, success, message):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': success, 'message': message})
        else:
            return redirect(request.META.get('HTTP_REFERER', reverse('home')))

    def get_cart_data(self, request):
        cart_items = Cart.objects.filter(user=request.user)
        cart_data = []
        for item in cart_items:
            if item.product:
                item_variations = [v.product_variation.value for v in item.variations.all()]
                cart_data.append({
                    'id': item.id,
                    'product': {
                        'id': item.product.id,
                        'name': item.product.name,
                        'price': float(item.product.price),
                        'image': str(item.product.image.url) if item.product.image else None,
                    },
                    'variations': item_variations,
                    'quantity': item.quantity,
                })
            else:  # It's a service
                cart_data.append({
                    'id': item.id,
                    'service': {
                        'id': item.service.id,
                        'name': item.service.name,
                        'price': float(item.price),
                        'image': str(item.service.image.url) if item.service.image else None,
                    },
                    'quantity': item.quantity,
                })
        total_price = sum(item.price * item.quantity for item in cart_items)
        return JsonResponse({'items': cart_data, 'subtotal': total_price})

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

        cart_items = Cart.objects.filter(user=request.user).prefetch_related('variations__product_variation')
        cart_data = []
        total_price = 0

        for item in cart_items:
            if item.product:
                item_price = item.product.price
                for variation in item.variations.all():
                    if variation.product_variation.price:
                        item_price = variation.product_variation.price
                item_total = item_price * item.quantity
                total_price += item_total

                cart_data.append({
                    'id': item.id,
                    'product': {
                        'id': item.product.id,
                        'name': item.product.name,
                        'price': float(item_price),
                        'image': item.product.image.url if item.product.image else None,
                    },
                    'variations': [{'category': v.product_variation.variation.get_name_display(), 'value': v.product_variation.value} for v in item.variations.all()],
                    'quantity': item.quantity,
                    'total': float(item_total),
                })
            else:  # It's a service
                item_total = item.price * item.quantity
                total_price += item_total

                cart_data.append({
                    'id': item.id,
                    'service': {
                        'id': item.service.id,
                        'name': item.service.name,
                        'price': float(item.price),
                        'image': item.service.image.url if item.service.image else None,
                    },
                    'quantity': item.quantity,
                    'total': float(item_total),
                })

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


class CreateCheckoutSessionView(LoginRequiredMixin, View):
    def get(self, request):
        cart_items = Cart.objects.filter(user=request.user).prefetch_related('variations__product_variation')
        total_price = sum(item.price * item.quantity for item in cart_items)
        return render(request, 'event/checkout.html', {
            'cart_items': cart_items,
            'total_price': total_price,
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY
        })

    def post(self, request, *args, **kwargs):
        cart_items = Cart.objects.filter(user=request.user).prefetch_related('variations__product_variation')
        current_domain = request.get_host()
        protocol = 'https' if request.is_secure() else 'http'
        YOUR_DOMAIN = f"{protocol}://{current_domain}"

        line_items = []
        total_amount = 0
        for item in cart_items:
            if item.product:
                name = item.product.name
                image = item.product.image.url if item.product.image else None
                price = item.price
            else:
                name = item.service.name
                image = item.service.image.url if item.service.image else None
                price = item.price

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

        # Collect user address details from the request body
        request_data = json.loads(request.body)
        address = request_data.get('address', '')
        city = request_data.get('city', '')
        state = request_data.get('state', '')
        postal_code = request_data.get('postal_code', '')
        note = request_data.get('note', '')
        name = request_data.get('name', 'Customer')
        payment_method = request_data.get('payment_method', 'card')

        try:
            # Create a Checkout Session
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
                            'country': 'AU',  # assuming country as AU
                        },
                    },
                },
            )

            # Save the session ID and other relevant details
            request.session['checkout_session_id'] = checkout_session.id
            request.session['business_items'] = self.get_business_items(cart_items)
            request.session['address'] = address
            request.session['city'] = city
            request.session['state'] = state
            request.session['postal_code'] = postal_code
            request.session['note'] = note
            request.session['cart_items'] = self.get_cart_items(cart_items)

            return JsonResponse({'id': checkout_session.id})
        except Exception as e:
            return JsonResponse({'error': str(e)})

    def get_business_items(self, cart_items):
        business_items = defaultdict(list)
        for item in cart_items:
            business = item.product.business if item.product else item.service.business
            business_items[str(business.id)].append({
                'amount': int(float(item.price) * 100 * item.quantity),
                'business': business.stripe_account_id,
                'item_id': item.product.id if item.product else item.service.id,
                'item_type': 'product' if item.product else 'service',
                'quantity': item.quantity,
                'variations': [
                    {
                        'variation_name': cv.product_variation.variation.name,
                        'variation_value': cv.product_variation.value
                    }
                    for cv in item.variations.all()
                ] if item.product else []
            })
        return dict(business_items)

    def get_cart_items(self, cart_items):
        return [
            {
                'item_id': item.product.id if item.product else item.service.id,
                'item_type': 'product' if item.product else 'service',
                'quantity': item.quantity,
                'price': float(item.price),
                'variations': [
                    {
                        'variation_name': cv.product_variation.variation.name,
                        'variation_value': cv.product_variation.value
                    }
                    for cv in item.variations.all()
                ] if item.product else []
            }
            for item in cart_items
        ]

    def group_items_by_business(self, cart_items):
        business_items = defaultdict(list)
        for item in cart_items:
            business = item.product.business if item.product else item.service.business
            business_items[business].append(item)
        return business_items

class PaymentSuccessView(LoginRequiredMixin, View):
    def get(self, request):
        checkout_session_id = request.session.get('checkout_session_id')
        business_items = request.session.get('business_items')
        cart_items = request.session.get('cart_items')
        address = request.session.get('address')
        city = request.session.get('city')
        state = request.session.get('state')
        postal_code = request.session.get('postal_code')
        note = request.session.get('note')

        if not checkout_session_id or not business_items or not cart_items:
            return JsonResponse({'error': 'Session data not found'}, status=400)

        try:
            # Retrieve the checkout session
            session = stripe.checkout.Session.retrieve(checkout_session_id)
            payment_intent_id = session.payment_intent

            # Create transfers for each business
            for business_id, items in business_items.items():
                total_amount = sum(item['amount'] for item in items)
                stripe.Transfer.create(
                    amount=int(total_amount * 0.86),  # 86% of the total amount
                    currency='aud',
                    destination=items[0]['business'],
                    transfer_group=payment_intent_id,
                )

            # Generate a unique reference code with strings and digits
            characters = string.ascii_letters + string.digits
            ref_code = ''.join(random.choice(characters) for _ in range(10))

            total_price = sum(item['quantity'] * item['price'] for item in cart_items)
            
            with transaction.atomic():
                order = Order.objects.create(
                    user=request.user,
                    ref_code=ref_code,
                    total_amount=total_price,
                    address=address,
                    city=city,
                    state=state,
                    postal_code=postal_code,
                    note=note
                )

                for item in cart_items:
                    if item['item_type'] == 'product':
                        product = Product.objects.get(id=item['item_id'])
                        service = None
                    else:
                        service = Service.objects.get(id=item['item_id'])
                        product = None

                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        service=service,
                        quantity=item['quantity'],
                        price=item['price'],
                        variations=item['variations']
                    )

            # Clear the cart
            Cart.objects.filter(user=request.user).delete()

            # Send email to businesses
            self.send_order_emails(order, business_items)

            # Clear the session data
            del request.session['checkout_session_id']
            del request.session['business_items']
            del request.session['cart_items']
            del request.session['address']
            del request.session['city']
            del request.session['state']
            del request.session['postal_code']
            del request.session['note']

            return render(request, 'event/success.html')
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def send_order_emails(self, order, business_items):
        for business_id, items in business_items.items():
            business = Business.objects.get(id=business_id)
            business_total = sum(item['amount'] for item in items) / 100  # Convert cents to dollars

            item_details = []
            for item in items:
                if item['item_type'] == 'product':
                    product = Product.objects.get(id=item['item_id'])
                    name = product.name
                else:
                    service = Service.objects.get(id=item['item_id'])
                    name = service.name

                variations_str = ', '.join([f"{v['variation_name']}: {v['variation_value']}" for v in item['variations']])
                item_detail = (
                    f"{item['quantity']} x {name} "
                    f"({variations_str}) - "
                    f"${item['amount'] / 100}"  # Convert cents to dollars
                )
                item_details.append(item_detail)

            email_subject = f"New Order Received - {order.ref_code}"
            email_body = render_to_string('event/new_order_email.html', {
                'business': business,
                'order': order,
                'business_total': business_total,
                'item_details': item_details
            })

            email = EmailMultiAlternatives(
                subject=email_subject,
                body=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[business.email],
            )
            email.attach_alternative(email_body, "text/html")
            email.send(fail_silently=False)


class UserOrdersView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        orders = Order.objects.filter(user=request.user).order_by('-created_at')
        return render(request, 'event/user_orders.html', {'orders': orders})
    


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
def message_seller(request, business_slug):
    business = get_object_or_404(Business, business_slug=business_slug)
    
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            Message.objects.create(
                sender=request.user,
                recipient=business.seller,
                business=business,
                content=content
            )
            
            # Send email to the business
            subject = f"New message from {request.user.username}"
            message = f"{request.user.username} has messaged {business.business_name}"
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [business.email]
            
            send_mail(subject, message, from_email, recipient_list)
            
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
            Message.objects.create(
                sender=request.user,
                recipient=user,
                business=business,
                content=content
            )
            
            # Send email to the user
            subject = f"New message from {business.business_name}"
            message = f"{business.business_name} has messaged you"
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [user.email]
            
            send_mail(subject, message, from_email, recipient_list)
            
            return redirect('message_buyer', username=user.username)

    # Mark messages as read for the current user and buyer
    Message.objects.filter(recipient=request.user, sender=user).update(is_read=True)

    conversation_messages = Message.objects.filter(
        Q(sender=request.user, recipient=user) |
        Q(sender=user, recipient=request.user)
    ).filter(business=business).order_by('timestamp')

    context = {
        'user': user,
        'conversation_messages': conversation_messages,
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
                    # Business sending message to user
                    username = request.POST.get('username')
                    if username:
                        recipient = get_object_or_404(CustomUser, username=username)
                        Message.objects.create(
                            sender=request.user,
                            recipient=recipient,
                            business=business,
                            content=content
                        )
                        
                        # Send email to the user
                        subject = f"New message from {business.business_name}"
                        message = f"{business.business_name} has messaged you"
                        from_email = settings.DEFAULT_FROM_EMAIL
                        recipient_list = [recipient.email]
                        
                        send_mail(subject, message, from_email, recipient_list)
                        
                        return redirect(f'{request.path}?business_slug={business_slug}&username={username}')
                else:
                    # User sending message to business
                    Message.objects.create(
                        sender=request.user,
                        recipient=business.seller,
                        business=business,
                        content=content
                    )
                    
                    # Send email to the business
                    subject = f"New message from {request.user.username}"
                    message = f"{request.user.username} has messaged {business.business_name}"
                    from_email = settings.DEFAULT_FROM_EMAIL
                    recipient_list = [business.email]
                    
                    send_mail(subject, message, from_email, recipient_list)
                    
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
                
                # Send email to the user
                subject = f"New message from {business.business_name}"
                message = f"{business.business_name} has messaged you"
                from_email = settings.DEFAULT_FROM_EMAIL
                recipient_list = [recipient.email]
                
                send_mail(subject, message, from_email, recipient_list)
                
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
            # Query messages for selected_business with selected_user
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


@login_required
def create_quote(request, username):
    recipient = get_object_or_404(CustomUser, username=username)
    business = Business.objects.filter(seller=request.user).first()

    if not business:
        return JsonResponse({'success': False, 'error': 'No business found for this user'})

    if request.method == 'POST':
        form = QuoteForm(request.POST)
        if form.is_valid():
            service = form.cleaned_data['service']
            price = form.cleaned_data['price']
            
            # Create the message
            message = Message.objects.create(
                sender=request.user,
                recipient=recipient,  # Send to the intended recipient
                business=business,
                content=f"Quote for {service.name} at ${price}"
            )
            
            # Create the quote
            Quote.objects.create(
                sender=request.user,
                recipient=recipient,  # The recipient is the user in the conversation
                service=service,
                price=price,
                message=message
            )
            
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})

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
        defaults={'price': quote.price}
    )
    
    if not created:
        cart_item.price = quote.price
        cart_item.save()

    return JsonResponse({'success': True})


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
            username = request.POST.get('username')
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            venue_email = request.POST.get('venue_email')
            venue_contact_number = request.POST.get('venue_contact_number')
            venue_name = request.POST.get('venue_name')
            venue_address = request.POST.get('venue_address')
            description = request.POST.get('description')
            price_per_event = request.POST.get('price_per_event')
            min_reception_guests = request.POST.get('min_reception_guests')
            max_reception_guests = request.POST.get('max_reception_guests')
            low_price_per_head = request.POST.get('low_price_per_head')
            high_price_per_head = request.POST.get('high_price_per_head')
            ceremony_indoors = request.POST.get('ceremony_indoors') == 'on'
            ceremony_outdoors = request.POST.get('ceremony_outdoors') == 'on'
            in_house_catering = request.POST.get('in_house_catering') == 'on'
            profile_picture = request.FILES.get('profile_picture')
            cover_photo = request.FILES.get('cover_photo')
            venue_image = request.FILES.get('venue_image')
            amenities_ids = request.POST.getlist('amenities')
            states_ids = request.POST.getlist('states')
            event_category_ids = request.POST.getlist('event_category')
            video_url = request.POST.get('video_url')

            if password1 != password2:
                messages.error(request, 'Passwords do not match.')
                return redirect('venue_vendor_register')

            try:
                user = CustomUser.objects.create_user(username=username, password=password1, first_name=first_name, last_name=last_name, email=venue_email)
            except IntegrityError:
                messages.error(request, 'Username already exists.')
                return redirect('venue_vendor_register')

            user.is_venue_vendor = True
            user.save()

            venue = Venue.objects.create(
                user=user,
                first_name=first_name,
                last_name=last_name,
                venue_email=venue_email,
                venue_contact_number=venue_contact_number,
                venue_name=venue_name,
                venue_address=venue_address,
                description=description,
                price_per_event=price_per_event,
                min_reception_guests=min_reception_guests,
                max_reception_guests=max_reception_guests,
                low_price_per_head=low_price_per_head,
                high_price_per_head=high_price_per_head,
                ceremony_indoors=ceremony_indoors,
                ceremony_outdoors=ceremony_outdoors,
                in_house_catering=in_house_catering,
                profile_picture=profile_picture,
                cover_photo=cover_photo,
                venue_image=venue_image,
                video_url=video_url
            )

            venue.states.set(states_ids)
            venue.event_category.set(event_category_ids)
            amenities = Amenity.objects.filter(id__in=amenities_ids)
            venue.amenities.set(amenities)

            venue.save()

            for day, day_display in VenueOpeningHour.DAY_CHOICES:
                is_closed = request.POST.get(f'opening_hours-{day}-is_closed') == 'on'
                opening_time = request.POST.get(f'opening_hours-{day}-opening_time')
                closing_time = request.POST.get(f'opening_hours-{day}-closing_time')

                if is_closed:
                    VenueOpeningHour.objects.create(
                        venue=venue,
                        day=day,
                        is_closed=True
                    )
                elif opening_time and closing_time:
                    VenueOpeningHour.objects.create(
                        venue=venue,
                        day=day,
                        opening_time=opening_time,
                        closing_time=closing_time
                    )

            for image in request.FILES.getlist('venue_images'):
                VenueImage.objects.create(venue=venue, image=image)

            messages.success(request, 'Registration successful. You can now log in as a venue vendor.')
            return redirect('login')
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('venue_vendor_register')

class VenueVendorLoginView(View):
    def get(self, request):
        return render(request, 'event/venue_vendor_login.html')

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_venue_vendor:
            login(request, user)
            messages.success(request, 'Login successful.')
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password.')
            return redirect('venue_vendor_login')
        
class VenueDetailView(View):
    def get(self, request, venue_slug):
        venue = get_object_or_404(Venue, venue_slug=venue_slug)

        # Increment view count and create a VenueView record
        venue.views_count = F('views_count') + 1
        venue.save(update_fields=['views_count'])  # Efficient update
        VenueView.objects.create(venue=venue)  # Log the view

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
                rating = int(rating)
                VenueReview.objects.create(
                    venue=venue,
                    user=request.user,
                    review_text=review_text,
                    rating=rating
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
            subject = f"Enquiry about {venue.venue_name}"
            message = (f"Name: {name}\n"
                       f"Email: {email}\n"
                       f"Phone: {phone}\n"
                       f"Event Date: {event_date}\n"
                       f"Number of Guests: {guests}\n"
                       f"Comments: {comments}\n")
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [venue.venue_email])
            VenueInquiry.objects.create(
                venue=venue,
                user=request.user,
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