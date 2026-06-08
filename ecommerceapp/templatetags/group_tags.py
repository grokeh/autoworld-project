from django import template

register = template.Library()

@register.filter
def pluck(queryset, attr):
    return [getattr(item, attr, None) for item in queryset]
