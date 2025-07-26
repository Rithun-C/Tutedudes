from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """Multiply numeric template values: {{ price|mul:qty }}"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def sub(value, arg):
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return ''
