# forms.py
from django.forms import modelform_factory
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

def crispy_modelform_factory(model, exclude=[], submit_label='Submit'):
    # Generate the form using modelform_factory
    ModelForm = modelform_factory(model, exclude=exclude)

    # Create a new form class that inherits from the generated ModelForm
    class CrispyForm(ModelForm):
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