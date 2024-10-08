from django.db import models
from users.models import CustomUser
from django.utils.text import slugify
from django.core.serializers import serialize
import json
from django.utils import timezone
from django.db.models import Avg, Count
from django.db.models import JSONField
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class State(models.Model):
    name = models.CharField(max_length=100)
    abbreviation = models.CharField(max_length=3)

    def __str__(self):
        return self.name
    

class EventCategory(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
    

class ProductCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class ServiceCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class DeliveryByRadius(models.Model):
    business = models.ForeignKey('Business', on_delete=models.CASCADE, related_name='delivery_radius_options')
    radius = models.IntegerField(validators=[MinValueValidator(1)], help_text='Enter the delivery radius in kilometers.')
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Enter the delivery fee for this radius.')

    class Meta:
        unique_together = ('business', 'radius')

    def __str__(self):
        return f"{self.business.business_name} - {self.radius} km - ${self.price}"


class Business(models.Model):
    seller = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='business')
    business_name = models.CharField(max_length=100)
    description = models.TextField()
    business_slug = models.SlugField(unique=True, blank=True)
    states = models.ManyToManyField(State)
    address = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    phone = models.CharField(max_length=20)
    terms_and_conditions = models.TextField(blank=True, null=True)
    terms_and_conditions_pdf = models.FileField(upload_to='terms_and_conditions/', blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='business_profiles/', blank=True, null=True)
    banner_image = models.ImageField(upload_to='business_banners/', blank=True, null=True)
    event_categories = models.ManyToManyField(EventCategory, related_name='businesses')
    is_featured = models.BooleanField(default=False)
    stripe_account_id = models.CharField(max_length=255, blank=True, null=True)
    delivery_type = models.CharField(max_length=50, choices=[('price_per_way', 'Price Per Way'), ('by_radius', 'By Radius')], blank=True, null=True)
    max_delivery_distance = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1)], help_text='Enter the maximum delivery distance in kilometers for Price Per Way.')
    delivery_price_per_way = models.IntegerField(null=True, blank=True, help_text='Enter the delivery fee per way. The total fee will be twice this amount for a round trip.')

    def __str__(self):
        return self.business_name

    def save(self, *args, **kwargs):
        if not self.business_slug:
            self.business_slug = slugify(self.business_name)
        super().save(*args, **kwargs)


class Award(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='awards')
    image = models.ImageField(upload_to='awards/', blank=True, null=True)

    def __str__(self):
        return f"Award for {self.business.business_name}"


class OpeningHour(models.Model):
    DAY_CHOICES = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
        ('public_holiday', 'Public Holiday'),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='opening_hours')
    day = models.CharField(max_length=20, choices=DAY_CHOICES)
    is_closed = models.BooleanField(default=False)
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)

    def __str__(self):
        if self.is_closed:
            return f"{self.business.business_name} - {self.get_day_display()} (Closed)"
        else:
            return f"{self.business.business_name} - {self.get_day_display()} ({self.opening_time} - {self.closing_time})"
    
class Product(models.Model):
    COLOUR_CHOICES = [
        ('red', 'Red'),
        ('blue', 'Blue'),
        ('green', 'Green'),
        ('yellow', 'Yellow'),
        ('black', 'Black'),
        ('white', 'White'),
    ]

    name = models.CharField(max_length=100)
    category = models.ForeignKey('ProductCategory', on_delete=models.SET_NULL, null=True, related_name='products')
    product_slug = models.SlugField(unique=True, blank=True)
    description = models.TextField()
    hire_price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/')
    image2 = models.ImageField(upload_to='products/', null=True, blank=True)
    image3 = models.ImageField(upload_to='products/', null=True, blank=True)
    image4 = models.ImageField(upload_to='products/', null=True, blank=True)
    business = models.ForeignKey('Business', on_delete=models.CASCADE, related_name='products')
    in_stock = models.BooleanField(default=True)
    stock_level = models.IntegerField(validators=[MinValueValidator(0)], help_text='Enter the number of products in stock.', null=True)
    is_popular = models.BooleanField(default=False)
    is_best_seller = models.BooleanField(default=False)
    trending = models.BooleanField(default=False)
    new_arrivals = models.BooleanField(default=False)
    has_variations = models.BooleanField(default=False)
    for_purchase = models.BooleanField(default=False)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    for_pickup = models.BooleanField(default=False)
    pickup_location = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    can_deliver = models.BooleanField(default=False)
    main_colour_theme = models.CharField(max_length=10, choices=COLOUR_CHOICES, null=True, blank=True)
    setup_packdown_fee = models.BooleanField(default=False)
    setup_packdown_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f'{self.business.business_name}, {self.name}'
    
    def get_item_type(self):
        return 'product'

    def get_json_data(self):
        data = {
            'id': self.id,
            'name': self.name,
            'hire_price': float(self.hire_price),
            'purchase_price': float(self.purchase_price) if self.purchase_price else None,
            'description': self.description,
            'images': [self.image.url, self.image2.url] if self.image and self.image2 else [],
            'for_purchase': self.for_purchase,
            'for_pickup': self.for_pickup,
            'pickup_location': self.pickup_location,
            'can_deliver': self.can_deliver,
            'main_colour_theme': self.main_colour_theme,
            'setup_packdown_fee': self.setup_packdown_fee,
            'setup_packdown_fee_amount': float(self.setup_packdown_fee_amount) if self.setup_packdown_fee_amount else None,
        }
        return json.dumps(data)

    def save(self, *args, **kwargs):
        if not self.product_slug:
            self.product_slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def overall_review(self):
        avg_rating = self.reviews.aggregate(Avg('rating'))['rating__avg']
        return round(avg_rating, 1) if avg_rating else 0

    def star_rating_percentage(self, star):
        total_reviews = self.reviews.count()
        if total_reviews == 0:
            return 0
        star_count = self.reviews.filter(rating=star).count()
        return round((star_count / total_reviews) * 100)


class Variation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variations')
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class ProductVariation(models.Model):
    variation = models.ForeignKey(Variation, on_delete=models.CASCADE, related_name='values')
    value = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_varies = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.variation.product.name} - {self.variation.name} - {self.value} (${self.price})"


class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    review_text = models.TextField()
    rating = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Review by {self.user.username} on {self.product.name}'

    @property
    def date(self):
        return (timezone.now() - self.created_at).days

class Service(models.Model):
    name = models.CharField(max_length=100)
    service_slug = models.SlugField(unique=True, blank=True)
    category = models.ForeignKey(ServiceCategory, on_delete=models.SET_NULL, null=True, related_name='services')
    image = models.ImageField(upload_to='services/', null=True)
    description = models.TextField()
    hire_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    available_by_quotation_only = models.BooleanField(default=False)
    setup_packdown_fee = models.BooleanField(default=False)
    setup_packdown_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    has_variations = models.BooleanField(default=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='services')
    is_best_seller = models.BooleanField(default=False)
    new_arrivals = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.business.business_name}, {self.name}'

    def get_item_type(self):
        return 'service'

    def save(self, *args, **kwargs):
        if not self.service_slug:
            self.service_slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def overall_review(self):
        avg_rating = self.reviews.aggregate(Avg('rating'))['rating__avg']
        return round(avg_rating, 1) if avg_rating else 0

    def star_rating_percentage(self, star):
        total_reviews = self.reviews.count()
        if total_reviews == 0:
            return 0
        star_count = self.reviews.filter(rating=star).count()
        return round((star_count / total_reviews) * 100)


class ServiceImage(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='services/')

    def __str__(self):
        return f"Image for {self.service.name}"

class ServiceReview(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    review_text = models.TextField()
    rating = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Review by {self.user.username} on {self.service.name}'

    @property
    def date(self):
        return (timezone.now() - self.created_at).days

class ServiceVariation(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='variations')
    name = models.CharField(max_length=100)
    

    def __str__(self):
        return f"{self.service.name} - {self.name}"

class ServiceVariationOption(models.Model):
    variation = models.ForeignKey(ServiceVariation, on_delete=models.CASCADE, related_name='options')
    value = models.CharField(max_length=100)
    price_varies = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.variation.service.name} - {self.variation.name} - {self.value} (${self.price})"
    


class Cart(models.Model):
    DELIVERY_METHOD_CHOICES = [
        ('pickup', 'Pickup'),
        ('delivery', 'Delivery'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='cart')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    variation_key = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    hire = models.BooleanField(default=False)
    delivery_method = models.CharField(max_length=10, choices=DELIVERY_METHOD_CHOICES, default='delivery')
    customer_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    customer_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.product.name if self.product else self.service.name}"

    
    def calculate_total_price(self):
        if self.product:
            base_price = self.product.hire_price if self.hire else self.product.purchase_price
        elif self.service:
            if self.service.available_by_quotation_only:
                base_price = self.price  # Use the price set when adding the quote to cart
            else:
                base_price = self.service.hire_price
        else:
            base_price = Decimal('0')

        variations_price = Decimal('0')
        for variation in self.variations.all():
            if variation.product_variation and variation.product_variation.price:
                variations_price += variation.product_variation.price
            elif variation.service_variation and variation.service_variation.price:
                variations_price += variation.service_variation.price

        self.price = base_price + variations_price
        self.save()

    def save(self, *args, **kwargs):
        print(f"Saving cart item. Hire: {self.hire}, Price: {self.price}")
        super().save(*args, **kwargs)


class CartItemVariation(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='variations')
    product_variation = models.ForeignKey(ProductVariation, on_delete=models.CASCADE, null=True, blank=True)
    service_variation = models.ForeignKey(ServiceVariationOption, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"{self.cart} - {self.product_variation if self.product_variation else self.service_variation}"

class Order(models.Model):
    ORDER_STATUS_CHOICES = [
        ('ordered', 'ordered'),
        ('delivered', 'delivered'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partially_approved', 'Partially Approved'),
        ('approved', 'Approved'),
        ('partially_rejected', 'Partially Rejected'),
        ('rejected', 'Rejected'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders')
    ref_code = models.CharField(max_length=20, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    address = models.CharField(max_length=255, verbose_name="Delivery/Event Address")
    billing_address = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    city = models.CharField(max_length=100, null=True)
    state = models.CharField(max_length=100, null=True)
    postal_code = models.CharField(max_length=20, null=True)
    note = models.TextField(null=True, blank=True)
    refund_requested = models.BooleanField(default=False)
    refund_granted = models.BooleanField(default=False)
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default="ordered")
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    setup_packdown_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    afterpay_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    event_date = models.DateField(null=True, blank=True)
    event_time = models.TimeField(null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=[('card', 'Credit Card'), ('afterpay_clearpay', 'Afterpay')], default='card')  # New field
    payment_intent = models.CharField(max_length=255, null=True, blank=True)
    business_delivery_fees = models.JSONField(default=dict)
    
    def __str__(self):
        return f"Order #{self.id} by {self.user.username} #{self.ref_code}"
    
    def all_businesses_responded(self):
        return self.approvals.count() == self.items.values('product__business').distinct().count()


    def update_status(self):
        approved_items = self.items.filter(status='approved')
        rejected_items = self.items.filter(status='rejected')
        pending_items = self.items.filter(status='pending')
        
        if pending_items.exists():
            self.status = 'partially_approved' if approved_items.exists() else 'pending'
        elif rejected_items.exists():
            self.status = 'partially_rejected' if approved_items.exists() else 'rejected'
        else:
            self.status = 'approved'
        self.save()


class OrderItem(models.Model):
    ORDER_ITEM_DELIVERY_METHOD_CHOICES = [
        ('pickup', 'Pickup'),
        ('delivery', 'Delivery')
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    variations = JSONField(null=True, blank=True)
    hire = models.BooleanField(default=False)
    delivery_method = models.CharField(max_length=10, choices=ORDER_ITEM_DELIVERY_METHOD_CHOICES, default='delivery')

    def __str__(self):
        item_name = self.product.name if self.product else self.service.name
        if isinstance(self.variations, dict):
            variations_str = ', '.join([f'{k}: {v}' for k, v in self.variations.items()]) if self.variations else ''
        elif isinstance(self.variations, list):
            variations_str = ', '.join([f'{v["variation_name"]}: {v["variation_value"]}' for v in self.variations]) if self.variations else ''
        else:
            variations_str = ''
        return f"{self.quantity} of {item_name} ({variations_str})"

class OrderApproval(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='approvals')
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    approved = models.BooleanField(default=False)
    approval_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('order', 'business')

    def __str__(self):
        return f"Order {self.order.ref_code} - {self.business.business_name} - {'Approved' if self.approved else 'Pending'}"
    

class OrderTermsSignature(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='signatures')
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    signature = models.ImageField(upload_to='order_signatures/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Signature for {self.order.ref_code} - {self.business.business_name}"
    

class Refund(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    reason = models.TextField()
    email = models.EmailField()
    accepted = models.BooleanField(default=False)


    def __str__(self):
        return f"{self.pk}"


class Message(models.Model):
    sender = models.ForeignKey(CustomUser, related_name='sent_messages', on_delete=models.CASCADE)
    recipient = models.ForeignKey(CustomUser, related_name='received_messages', on_delete=models.CASCADE)
    business = models.ForeignKey(Business, related_name='messages', on_delete=models.CASCADE, null=True)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.pk}"

    @property
    def sender_is_business(self):
        return self.sender.business.exists()

    @property
    def recipient_is_business(self):
        return self.recipient.business.exists()


class Quote(models.Model):
    sender = models.ForeignKey(CustomUser, related_name='sent_quotes', on_delete=models.CASCADE)
    recipient = models.ForeignKey(CustomUser, related_name='received_quotes', on_delete=models.CASCADE)
    service = models.ForeignKey(Service, related_name='quotes', on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    message = models.ForeignKey(Message, related_name='quotes', on_delete=models.CASCADE)
    is_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Quote from {self.sender} to {self.recipient} for {self.service.name}"


class Amenity(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='amenity_images/')

    def __str__(self):
        return self.name

class Venue(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='venue')
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    venue_slug = models.SlugField(unique=True, blank=True)
    venue_email = models.EmailField()
    venue_contact_number = models.CharField(max_length=20)
    venue_name = models.CharField(max_length=100)
    venue_address = models.CharField(max_length=255)
    event_category = models.ManyToManyField('EventCategory')
    description = models.TextField()
    price_per_event = models.DecimalField(max_digits=10, decimal_places=2)
    profile_picture = models.ImageField(upload_to='venue_profiles/', blank=True, null=True)
    cover_photo = models.ImageField(upload_to='venue_covers/', blank=True, null=True)
    venue_image = models.ImageField(upload_to='venue_images/')
    min_reception_guests = models.IntegerField()
    max_reception_guests = models.IntegerField()
    low_price_per_head = models.DecimalField(max_digits=10, decimal_places=2)
    high_price_per_head = models.DecimalField(max_digits=10, decimal_places=2)
    ceremony_indoors = models.BooleanField(default=False)
    ceremony_outdoors = models.BooleanField(default=False)
    in_house_catering = models.BooleanField(default=False)
    amenities = models.ManyToManyField(Amenity)
    video_url = models.CharField(max_length=255, blank=True, null=True)
    states = models.ManyToManyField('State')
    views_count = models.IntegerField(default=0)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.venue_name
    
    def save(self, *args, **kwargs):
        if not self.venue_slug:
            self.venue_slug = slugify(self.venue_name)
        super().save(*args, **kwargs)

    @property
    def overall_review(self):
        avg_rating = self.reviews.aggregate(Avg('rating'))['rating__avg']
        return round(avg_rating, 1) if avg_rating else 0

    def star_rating_percentage(self, star):
        total_reviews = self.reviews.count()
        if total_reviews == 0:
            return 0
        star_count = self.reviews.filter(rating=star).count()
        return round((star_count / total_reviews) * 100)

class VenueOpeningHour(models.Model):
    DAY_CHOICES = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
        ('public_holiday', 'Public Holiday'),
    ]
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='venue_opening_hours')
    day = models.CharField(max_length=20, choices=DAY_CHOICES)
    is_closed = models.BooleanField(default=False)
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)

    def __str__(self):
        if self.is_closed:
            return f"{self.venue.venue_name} - {self.get_day_display()} (Closed)"
        else:
            return f"{self.venue.venue_name} - {self.get_day_display()} ({self.opening_time} - {self.closing_time})"

class VenueImage(models.Model):
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='venues/')

    def __str__(self):
        return f"Image for {self.venue.venue_name}"

class VenueReview(models.Model):
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    review_text = models.TextField()
    rating = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Review by {self.user.username} on {self.venue.venue_name}'

    @property
    def date(self):
        return (timezone.now() - self.created_at).days

class VenueView(models.Model):
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='views')
    viewed_at = models.DateTimeField(auto_now_add=True)

class VenueInquiry(models.Model):
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='inquiries')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    event_date = models.DateField()
    guests = models.PositiveIntegerField()
    comments = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Inquiry by {self.user.username} for {self.venue.venue_name}"
    
from django_ckeditor_5.fields import CKEditor5Field

class BlogPost(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True, null=True)
    blog_banner_image = models.ImageField(upload_to='blog_banner_images/')
    blog_preview = models.TextField()
    pub_date = models.DateField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Paragraph(models.Model):
    blog_post = models.ForeignKey(BlogPost, related_name='paragraphs', on_delete=models.CASCADE)
    content = CKEditor5Field('Content', config_name='default')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'Paragraph {self.order} in {self.blog_post.title}'

class Image(models.Model):
    paragraph = models.ForeignKey(Paragraph, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='blog_images/')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'Image {self.order} in Paragraph {self.paragraph.order} of {self.paragraph.blog_post.title}'