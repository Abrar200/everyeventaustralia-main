from django import template
from django.template.defaultfilters import linebreaksbr
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def split_paragraphs(value):
    paragraphs = value.split('\n')
    return mark_safe(''.join(f'<p>{linebreaksbr(p)}</p>' for p in paragraphs if p.strip()))

@register.filter
def get_opening_time(opening_hours, day):
    return opening_hours.filter(day=day).first().opening_time

@register.filter
def get_closing_time(opening_hours, day):
    return opening_hours.filter(day=day).first().closing_time

@register.filter
def get_is_closed(opening_hours, day):
    return opening_hours.filter(day=day).first().is_closed

@register.filter(name='endswith')
def endswith(value, suffix):
    return str(value).lower().endswith(suffix.lower())

@register.filter
def subtract(value, arg):
    return value - arg