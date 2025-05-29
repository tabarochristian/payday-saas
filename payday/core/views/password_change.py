from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash, get_user_model
from django.utils.translation import gettext as _
from core.forms import InlineFormSetHelper  # May be used by BaseView or extended later
from .base import Change
from core.forms.button import Button

from django.contrib.auth.mixins import PermissionRequiredMixin

class PasswordChange(Change):
    """
    A view dedicated to handling password change requests for the authenticated user.

    This view supports both GET and POST methods:
      - GET renders the password change form.
      - POST processes the submitted form, updates the password if valid, and
        updates the session so the user remains logged in.
    
    Attributes:
        template_name (str): The template path for rendering the password change form.
        inline_formset_helper: A helper instance (unused in this view, but available for consistency).
    """
    template_name = "change.html"
    inline_formset_helper = InlineFormSetHelper()

    def get_model(self):
        return get_user_model()

    def dispatch(self, request, *args, **kwargs):
        return PermissionRequiredMixin.dispatch(self, request, *args, **kwargs)

    def get_action_buttons(self, obj=None):
        """
        Generates action buttons based on user permissions and model configuration.
        
        Args:
            obj: Model instance to generate buttons for.
            
        Returns:
            List of Button objects for permitted actions.
        """

        return [
            Button(
                tag='button',
                permission=True,
                text=_('Sauvegarder'),
                classes='btn btn-light-success',
                attrs={'type': 'submit', 'form': f"form-{self.kwargs['model']}"}
            )
        ]

    def get(self, request, app='core', model='user'):
        """
        Handle GET requests by initializing and rendering the PasswordChangeForm.

        Args:
            request (HttpRequest): The incoming HTTP GET request.

        Returns:
            HttpResponse: The rendered password change form.
        """
        # Get the currently authenticated user.
        self.kwargs.update({
            'app': app,
            'model': model
        })
        obj = request.user
        model_class = get_user_model()
        # Initialize the form with the current user. No POST data is provided in GET requests.

        user = obj
        form = PasswordChangeForm(user)
        action_buttons = self.get_action_buttons(obj)
        return render(request, self.template_name, locals())

    def post(self, request, app='core', model='user'):
        """
        Process POST requests to update the user's password.

        Validates the form data, and if valid:
          - Saves the new password.
          - Updates the session to prevent the user from being logged out.
          - Displays a success message and redirects to the home page.
        Otherwise, re-renders the form with warning messages.

        Args:
            request (HttpRequest): The incoming HTTP POST request.

        Returns:
            HttpResponse or HttpResponseRedirect: The response, either re-displaying the form
            with errors or redirecting to the home page on success.
        """
        # Get the authenticated user.
        obj = request.user
        model_class = get_user_model()
        # Instantiate the PasswordChangeForm with POST data.
        form = PasswordChangeForm(obj, request.POST)
        if not form.is_valid():
            # Show a warning message if the form has errors.
            messages.warning(request, _('Veuillez remplir le formulaire correctement'))
            action_buttons = self.get_action_buttons(obj)
            return render(request, self.template_name, locals())

        # If form validation succeeds, update the password.
        updated_user = form.save()
        # Update the session authentication hash, so the user remains logged in.
        update_session_auth_hash(request, updated_user)
        messages.success(request, _('Votre mot de passe a été mis à jour avec succès'))
        return redirect("core:home")