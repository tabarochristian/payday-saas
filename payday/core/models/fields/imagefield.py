from django.utils.safestring import mark_safe
from django.forms.widgets import Widget
from django.db import models
from django import forms

class ImageWidget(Widget):
    allow_multiple_selected = False
    template_name = 'fields/image-field.html'

    def format_value(self, value):
        """File input never renders a value."""
        return

    def value_from_datadict(self, data, files, name):
        "File widgets take data from FILES, not POST"
        getter = files.get
        if self.allow_multiple_selected:
            try:
                getter = files.getlist
            except AttributeError:
                pass
        return getter(name)

    def value_omitted_from_data(self, data, files, name):
        return name not in files

    def use_required_attribute(self, initial):
        return super().use_required_attribute(initial) and not initial

    def render(self, name, value, attrs=None, renderer=None):
        context = self.get_context(name, value, attrs)
        context['widget'].update({
            'verbose_name': self.attrs.get('verbose_name', name),
            'value': value if value else '',
        })
        return mark_safe(super().render(name, value, attrs, renderer))

    @property
    def media(self):
        return forms.Media(js=[mark_safe(self.get_js_script())])

    def get_js_script(self):
        return '''
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                const containers = document.querySelectorAll('.image-field-container');

                containers.forEach(container => {
                    const imageInput = container.querySelector('input[type="file"]');
                    const image = imageInput.getAttribute('data-url');
                    const canvas = container.querySelector('canvas');
                    
                    if (image) {
                        const img = new Image();
                        img.onload = function() {
                            canvas.width = img.width;
                            canvas.height = img.height;
                            canvas.style.display = 'block';
                            canvas.getContext('2d').drawImage(img, 0, 0);
                        };
                        img.src = image;
                    }

                    imageInput.addEventListener('change', function(event) {
                        const file = event.target.files[0];
                        if(!file) return;
                        
                        const reader = new FileReader();
                        reader.onload = function(e) {
                            const img = new Image();
                            img.onload = function() {
                                canvas.width = img.width;
                                canvas.height = img.height;
                                canvas.getContext('2d').drawImage(img, 0, 0);

                                canvas.width = img.width;
                                canvas.height = img.height;
                                canvas.style.display = 'block';
                                canvas.getContext('2d').drawImage(img, 0, 0);
                            };
                            img.src = e.target.result;
                        };
                        reader.readAsDataURL(file);
                    });
                });
            });
        </script>
        '''

class ImageField(models.ImageField):
    def __init__(self, *args, **kwargs):
        self.inline = kwargs.pop('inline', False)
        super().__init__(*args, **kwargs)

    #def formfield(self, **kwargs):
    #    kwargs['widget'] = ImageWidget
    #    return super().formfield(**kwargs)
