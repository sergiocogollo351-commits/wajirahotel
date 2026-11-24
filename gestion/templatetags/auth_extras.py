from django import template

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    """Return True if the user belongs to the given group.
    Usage in template: {% if request.user|has_group:"Administrador" %}
    """
    if not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()
