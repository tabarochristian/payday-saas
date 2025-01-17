from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap5
from flask_babel import Babel
from flask_executor import Executor

db = SQLAlchemy()
babel = Babel()
bootstrap = Bootstrap5()
executor = Executor()