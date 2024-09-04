from django.contrib import admin
from .models import Business, Service, Product, OpeningHour, Cart, Message, State, Variation, ProductVariation, CartItemVariation, Order, OrderItem, ProductCategory, ServiceCategory, ServiceReview, Quote, EventCategory, Award, ServiceVariation, ServiceVariationOption, Venue, VenueOpeningHour, Amenity, VenueReview, VenueView, VenueInquiry, OrderApproval, OrderTermsSignature, DeliveryByRadius, BlogPost, Paragraph, Image
from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
from nested_admin import NestedStackedInline, NestedModelAdmin, NestedTabularInline

admin.site.register(Business)
admin.site.register(Service)
admin.site.register(Product)
admin.site.register(OpeningHour)
admin.site.register(Cart)
admin.site.register(Message)
admin.site.register(State)
admin.site.register(Variation)
admin.site.register(ProductVariation)
admin.site.register(CartItemVariation)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(ProductCategory)
admin.site.register(ServiceCategory)
admin.site.register(ServiceReview)
admin.site.register(Quote)
admin.site.register(EventCategory)
admin.site.register(Award)
admin.site.register(ServiceVariation)
admin.site.register(ServiceVariationOption)
admin.site.register(Venue)
admin.site.register(VenueOpeningHour)
admin.site.register(Amenity)
admin.site.register(VenueReview)
admin.site.register(VenueView)
admin.site.register(VenueInquiry)
admin.site.register(OrderApproval)
admin.site.register(OrderTermsSignature)
admin.site.register(DeliveryByRadius)


class ParagraphAdminForm(forms.ModelForm):
    class Meta:
        model = Paragraph
        fields = '__all__'
        widgets = {
            'content': CKEditor5Widget(
                config_name='default',
                attrs={'class': 'django_ckeditor_5'},
            )
        }


class ImageInline(NestedTabularInline):
    model = Image
    extra = 1

class ParagraphInline(NestedStackedInline):
    model = Paragraph
    form = ParagraphAdminForm
    extra = 1
    inlines = [ImageInline]

class BlogPostAdmin(NestedModelAdmin):
    list_display = ('title', 'pub_date')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ParagraphInline]

admin.site.register(BlogPost, BlogPostAdmin)