from flask import Blueprint, render_template, redirect, flash #, url_for
from tasks import create_organization_schema
from forms import OrganizationForm
from models import Organization
from extensions import db, executor

main_bp = Blueprint('main', __name__)

@main_bp.route('/', methods=['GET', 'POST'])
def home():
    form = OrganizationForm()
    if not form.validate_on_submit():
        return render_template('index.html', form=form)

    qs = Organization.query.filter(
        (Organization.name == form.name.data) | 
        (Organization.email == form.email.data) |
        (Organization.phone == form.phone.data)
    )
    if qs.first():
        flash('Organization with this name, email or phone already exists.', 'danger')
        return render_template('index.html', form=form)
    
    organization = Organization(
        name = form.name.data, 
        email = form.email.data, 
        phone = form.phone.data,
        is_created = False
    )

    db.session.add(organization)
    db.session.commit()
    

    # Run the task in a separate process
    args = organization.to_dict()
    #Thread(target=create_organization_schema, args=(args,)).start()
    executor.submit(create_organization_schema, args)

    flash('Organization created successfully!', 'success')
    
    tenant = organization.tenant()
    return redirect(f"http://{tenant}.payday.cd")