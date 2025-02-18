from django.forms import modelform_factory
from crispy_forms.helper import FormHelper
from captcha.fields import CaptchaField
from crispy_forms.layout import Submit
from django.utils.translation import gettext_lazy as _

def crispy_modelform_factory(model, exclude=[], submit_label=_('Submit')):
    # Generate the form using modelform_factory
    try:
        ModelForm = modelform_factory(model, exclude=exclude)
    except Exception as e:
        raise RuntimeError(f"Error generating ModelForm: {e}")

    # Create a new form class that inherits from the generated ModelForm
    class CrispyForm(ModelForm):
        captcha = CaptchaField()
        
        def __init__(self, *args, **kwargs):
            super(CrispyForm, self).__init__(*args, **kwargs)
            self.helper = FormHelper()
            self.helper.form_method = 'POST'
            self.helper.add_input(
                Submit(
                    'submit', 
                    submit_label, 
                    css_class='btn-lg w-100'
                )
            )
    
    return CrispyForm
