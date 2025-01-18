from flask import Blueprint, render_template, redirect, flash
from tasks import create_organization_schema
from extensions import db, executor
from forms import OrganizationForm
from models import Organization
from slugify import slugify
import logging

main_bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

@main_bp.route('/', methods=['GET', 'POST'])
def home():
    form = OrganizationForm()

    if form.validate_on_submit():
        # Check if an organization with the same name, email, or phone already exists
        existing_organization = Organization.query.filter(
            (Organization.name == form.name.data) | 
            (Organization.email == form.email.data) |
            (Organization.phone == form.phone.data)
        ).first()

        if existing_organization:
            flash('Organization with this name, email, or phone already exists.', 'danger')
            return render_template('index.html', form=form)

        # Create a new organization
        organization = Organization(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            schema=slugify(form.name.data),
            is_created=False
        )

        try:
            # Save the organization to the database
            db.session.add(organization)
            db.session.commit()
            logger.info(f"Organization created: {organization.name}")
        except Exception as e:
            # Rollback the transaction in case of an error
            db.session.rollback()
            logger.error(f"Error creating organization: {e}")
            flash('An error occurred while creating the organization. Please try again.', 'danger')
            return render_template('index.html', form=form)

        try:
            # Submit the background task to create the organization schema
            args = organization.to_dict()
            executor.submit(create_organization_schema, args)
            logger.debug(f"Background task submitted for organization: {organization.name}")
        except Exception as e:
            logger.error(f"Error submitting background task: {e}")
            flash('An error occurred while scheduling the background task. Please contact support.', 'warning')

        # Notify the user and redirect to the tenant's subdomain
        flash('Organization created successfully!', 'success')
        tenant = organization.tenant()
        return redirect(f"http://{tenant}.payday.cd")

    # Render the form template for GET requests or invalid form submissions
    return render_template('index.html', form=form)