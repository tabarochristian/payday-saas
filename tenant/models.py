from slugify import slugify
from extensions import db

class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    is_created = db.Column(db.Boolean(), default=False)

    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)

    def __repr__(self):
        return self.name
    
    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
    
    def slugify(self):
        return slugify(self.name)