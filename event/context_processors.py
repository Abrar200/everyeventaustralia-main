from collections import defaultdict
from .models import Product, Cart, CartItemVariation, Message, Order
from django.db.models import Sum
from django.contrib.messages import get_messages
import logging
from django.db.models import Q

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
    




def business_order_count(request):
    order_count = 0
    if request.user.is_authenticated and hasattr(request.user, 'business'):
        business = request.user.business
        order_count = Order.objects.filter(items__product__business=business, order_status='ordered').distinct().count()
    return {'business_order_count': order_count}



def popular_products(request):
    popular_products = Product.objects.filter(is_popular=True)
    return {
        'popular_products': popular_products
    }