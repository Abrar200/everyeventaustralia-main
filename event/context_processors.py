from collections import defaultdict
from .models import Product, Cart, CartItemVariation, Message, Order, OrderItem
from django.db.models import Sum
from django.contrib.messages import get_messages
import logging
from django.db.models import Q, Exists, OuterRef
from django.contrib.sites.models import Site
from django.conf import settings

def static_urls(request):
    current_site = Site.objects.get_current()
    protocol = 'http'
    domain = current_site.domain
    return {
        'STATIC_URL': f"{protocol}://{domain}{settings.STATIC_URL}",
    }

def cart_data(request):
    if request.user.is_authenticated:
        cart_items = Cart.objects.filter(user=request.user)
        total_price = sum(item.product.price * item.quantity for item in cart_items)

        # Create a dictionary to store individual item prices
        item_prices = defaultdict(float)

        # Create a dictionary to store variations for each cart item
        cart_variations = defaultdict(list)

        for item in cart_items:
            item_price = item.product.price * item.quantity
            item_prices[item.id] = item_price

            # Fetch variations for the cart item
            variations = CartItemVariation.objects.filter(cart=item)
            cart_variations[item.id] = [v.product_variation.value for v in variations]

    else:
        cart_items = []
        total_price = 0
        item_prices = {}
        cart_variations = {}

    return {
        'cart_items': cart_items,
        'total_price': total_price,
        'item_prices': item_prices,
        'cart_variations': cart_variations,
    }



def cart_item_count(request):
    if request.user.is_authenticated:
        cart_items = Cart.objects.filter(user=request.user).aggregate(total_quantity=Sum('quantity'))
        return {'cart_item_count': cart_items['total_quantity'] or 0}
    else:
        return {'cart_item_count': 0}




def unread_message_count(request):
    if request.user.is_authenticated:
        unread_count = Message.objects.filter(
            recipient=request.user, 
            is_read=False
        ).filter(
            Q(business__isnull=True) | Q(business__isnull=False)
        ).count()
    else:
        unread_count = 0
    return {
        'unread_message_count': unread_count,
    }

def popular_products(request):
    popular_products = Product.objects.filter(is_popular=True)
    return {
        'popular_products': popular_products
    }

def business_order_count(request):
    order_count = 0
    pending_order_count = 0

    if request.user.is_authenticated and hasattr(request.user, 'business'):
        business = request.user.business
        
        # Subquery for items related to the business
        business_items = OrderItem.objects.filter(
            Q(product__business=business) | Q(service__business=business),
            order=OuterRef('pk')
        )

        # Count orders with any items that need approval
        pending_order_count = Order.objects.filter(
            Exists(business_items.filter(status='pending'))
        ).distinct().count()

        # Count orders that are fully processed (all items either approved or rejected)
        order_count = Order.objects.filter(
            Exists(business_items)
        ).exclude(
            Exists(business_items.filter(status='pending'))
        ).distinct().count()

        print(f"User: {request.user.username}")
        print(f"Business: {business.business_name}")
        print(f"Processed Order Count: {order_count}")
        print(f"Pending Order Count: {pending_order_count}")

    return {
        'business_order_count': order_count,
        'pending_order_count': pending_order_count,
    }


