from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        query[key] = value
    return query.urlencode()


@register.filter
def euro(valor):
    try:
        numero = Decimal(valor or 0)
    except (InvalidOperation, TypeError, ValueError):
        return "0,00 €"
    texto = f"{numero:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


@register.filter
def importe(valor):
    try:
        numero = Decimal(valor or 0)
    except (InvalidOperation, TypeError, ValueError):
        return "0,00"
    texto = f"{numero:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


@register.filter
def pct(valor):
    try:
        return f"{Decimal(valor or 0):.0f} %"
    except (InvalidOperation, TypeError, ValueError):
        return "0 %"
