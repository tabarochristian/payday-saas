from flask import request
from flask_mail import Message
from flask import render_template
from extensions import babel, mail

#@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(['fr', 'en'])  # Supported languages


def send_email(subject, recipients, template, **kwargs):
    """
    Send an email using a Jinja2 template.

    :param subject: Email subject
    :param recipients: List of recipient email addresses
    :param template: Name of the template file (without extension)
    :param kwargs: Data to pass to the template
    """
    msg = Message(subject, recipients=recipients)
    msg.body = render_template(f"{template}.txt", **kwargs)
    msg.html = render_template(f"{template}.html", **kwargs)
    mail.send(msg)