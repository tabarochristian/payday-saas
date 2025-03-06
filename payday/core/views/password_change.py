from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash, get_user_model
from django.utils.translation import gettext as _
from core.forms import InlineFormSetHelper  # May be used by BaseView or extended later
from .base import BaseView


class PasswordChange(BaseView):
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
    template_name = "registration/password_change.html"
    inline_formset_helper = InlineFormSetHelper()

    def get(self, request):
        """
        Handle GET requests by initializing and rendering the PasswordChangeForm.

        Args:
            request (HttpRequest): The incoming HTTP GET request.

        Returns:
            HttpResponse: The rendered password change form.
        """
        # Get the currently authenticated user.
        user = request.user
        # Initialize the form with the current user. No POST data is provided in GET requests.
        form = PasswordChangeForm(user)
        return render(request, self.template_name, locals())

    def post(self, request):
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
        user = request.user
        # Instantiate the PasswordChangeForm with POST data.
        form = PasswordChangeForm(user, request.POST)
        if not form.is_valid():
            # Show a warning message if the form has errors.
            messages.warning(request, _('Veuillez remplir le formulaire correctement'))
            context = {
                'form': form,
            }
            return render(request, self.template_name, context)

        # If form validation succeeds, update the password.
        updated_user = form.save()
        # Update the session authentication hash, so the user remains logged in.
        update_session_auth_hash(request, updated_user)
        messages.success(request, _('Votre mot de passe a été mis à jour avec succès'))
        return redirect("core:home")