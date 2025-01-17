import os

class Config:
    # Secret key for session management and security
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24))

    # reCAPTCHA keys
    RECAPTCHA_PUBLIC_KEY = os.getenv('RECAPTCHA_PUBLIC_KEY', '6LeCurkqAAAAAIaZUOOExwl2Cs7UOSpV4zJiMXEK')
    RECAPTCHA_PRIVATE_KEY = os.getenv('RECAPTCHA_PRIVATE_KEY', '6LeCurkqAAAAAOA1ntdvPLcJyBier54MdFfUoVCs')

    # Babel configuration for localization
    BABEL_DEFAULT_LOCALE = os.getenv('BABEL_DEFAULT_LOCALE', 'fr')
    BABEL_TRANSLATION_DIRECTORIES = os.getenv('BABEL_TRANSLATION_DIRECTORIES', 'translations')

    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///example.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = os.getenv('SQLALCHEMY_TRACK_MODIFICATIONS', 'False').lower() in ('true', '1', 't')

    # Celery configuration for background tasks
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

    # Flask-Mail configuration
    MAIL_SERVER = os.getenv('EMAIL_HOST', 'smtp.example.com')
    MAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.getenv('EMAIL_HOST_USER', 'your-email@example.com')
    MAIL_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', 'your-email-password')
    MAIL_DEFAULT_SENDER = os.getenv('EMAIL_HOST_USER', 'your-email@example.com')