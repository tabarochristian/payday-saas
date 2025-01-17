from flask_babel import Babel
from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap5
from celery import Celery

db = SQLAlchemy()
babel = Babel()
bootstrap = Bootstrap5()

# Initialize Celery
celery = Celery()