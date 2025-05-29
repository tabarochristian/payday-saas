from django import forms
from django.forms.widgets import Widget
from django.utils.safestring import mark_safe
from django.db import models

class CaptureWidget(Widget):
    template_name = 'fields/capture-field.html'
    allow_multiple_selected = False

    def __init__(self, attrs=None):
        default_attrs = {'accept': 'image/*'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    def format_value(self, value):
        # File input never renders a value in the input itself
        return None

    def value_from_datadict(self, data, files, name):
        # File widgets take data from FILES, not POST
        return files.get(name)

    def value_omitted_from_data(self, data, files, name):
        return name not in files

    def use_required_attribute(self, initial):
        # Only require the field if there’s no initial value
        return super().use_required_attribute(initial) and not initial

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget'].update({
            'verbose_name': self.attrs.get('verbose_name', name.replace('_', ' ').title()),
            'value': value.url if value and hasattr(value, 'url') else '',
        })
        return context

    @property
    def media(self):
        return forms.Media(js=['js/capture_widget.js'])

class CaptureField(models.ImageField):
    def __init__(self, *args, **kwargs):
        self.inline = kwargs.pop('inline', False)
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'widget': CaptureWidget}
        defaults.update(kwargs)
        return super().formfield(**defaults)