from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    try:
        return float(value) * int(arg)
    except (ValueError, TypeError):
        return 0
