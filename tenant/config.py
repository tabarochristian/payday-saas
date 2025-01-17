import os

class Config:
    # Secret key for session management and security
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24))

    # reCAPTCHA keys
    RECAPTCHA_PRIVATE_KEY = os.getenv('RECAPTCHA_PRIVATE_KEY', '6LeCurkqAAAAAOA1ntdvPLcJyBier54MdFfUoVCs')
    RECAPTCHA_PUBLIC_KEY = os.getenv('RECAPTCHA_PUBLIC_KEY', '6LeCurkqAAAAAIaZUOOExwl2Cs7UOSpV4zJiMXEK')

    # Babel configuration for localization
    BABEL_DEFAULT_LOCALE = os.getenv('BABEL_DEFAULT_LOCALE', 'fr')
    BABEL_TRANSLATION_DIRECTORIES = os.getenv('BABEL_TRANSLATION_DIRECTORIES', 'translations')

    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///example.db').replace('postgres', 'postgresql')
    SQLALCHEMY_TRACK_MODIFICATIONS = os.getenv('SQLALCHEMY_TRACK_MODIFICATIONS', 'False').lower() in ('true', '1', 't')

    # Celery configuration for background tasks
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')