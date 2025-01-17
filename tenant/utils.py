from flask import request

#@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(['fr', 'en'])  # Supported languages