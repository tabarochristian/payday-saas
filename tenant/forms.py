from flask_wtf import FlaskForm, Recaptcha
from wtforms import StringField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Regexp

class OrganizationForm(FlaskForm):
    name = StringField(
        'Organization Name', 
        validators=[
            DataRequired()
        ]
    )

    email = StringField(
        'Email', 
        validators=[
            DataRequired(), 
            Email()
        ]
    )

    phone = StringField(
        'Phone Number', 
        validators=[
            DataRequired(),
            Regexp(r'^\+?1?\d{9,15}$', message="Invalid phone number. It should contain 9-15 digits.")
        ], 
        description="+243 XXX XXX XXX"
    )
    
    employee_range = SelectField(
        'Number of Employees', 
        choices=[
            ('1-10', '1-10'), 
            ('11-50', '11-50'), 
            ('51-200', '51-200'), 
            ('201-500', '201-500'), 
            ('501-1000', '501-1000'), 
            ('1001+', '1001+')
        ], validators=[
            DataRequired()
        ],
        description="This information helps us tailor our services to better meet your needs."
    )

    # recaptcha = Recaptcha()
    submit = SubmitField('Sign Up')