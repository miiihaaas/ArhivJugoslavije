from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from arhivjugoslavije import db, app
from arhivjugoslavije.models import Partner, Invoice
from arhivjugoslavije.partner.forms import PartnerForm, EditPartnerForm
from datetime import datetime


partner = Blueprint('partner', __name__)


@partner.route('/partners', methods=['GET', 'POST'])
@login_required
def partners():
    endpoint = request.endpoint
    partners = Partner.query.all()
    form = PartnerForm()
    return render_template('partner/partners.html', 
                            endpoint=endpoint, 
                            partners=partners,
                            form=form,
                            legend='Poslovni partneri',
                            title='Poslovni partneri')

@partner.route('/add_partner', methods=['GET', 'POST'])
@login_required
def add_partner():
    form = PartnerForm()
    
    if form.validate_on_submit():
        # Kreiranje novog partnera iz podataka forme
        new_partner = Partner(
            name=form.name.data,
            address=form.address.data,
            city=form.city.data,
            country=form.country.data,
            account_number=form.account_number.data,
            pib=form.pib.data,
            mb=form.mb.data,
            phone_1=form.phone_1.data,
            phone_2=form.phone_2.data,
            email=form.email.data,
            customer=form.customer.data,
            supplier=form.supplier.data,
            international=form.international.data
        )
        
        # Dodavanje u bazu
        db.session.add(new_partner)
        db.session.commit()
        
        flash('Partner uspešno dodat!', 'success')
        return redirect(url_for('partner.partners'))
    
    # Ako forma nije validna, prikaži greške
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{error}', 'danger')
    
    # Vrati se na stranicu sa partnerima
    return redirect(url_for('partner.partners'))

@partner.route('/edit_partner/<int:partner_id>', methods=['GET', 'POST'])
@login_required
def edit_partner(partner_id):
    partner = Partner.query.get_or_404(partner_id)
    form = EditPartnerForm(original_partner_id=partner_id)
    
    # Popunjavanje forme postojećim podacima ako je GET zahtev
    if request.method == 'GET':
        form.name.data = partner.name
        form.address.data = partner.address
        form.city.data = partner.city
        form.country.data = partner.country
        form.account_number.data = partner.account_number
        form.pib.data = partner.pib
        form.mb.data = partner.mb
        form.phone_1.data = partner.phone_1
        form.phone_2.data = partner.phone_2
        form.email.data = partner.email
        form.active.data = partner.active
        form.customer.data = partner.customer
        form.supplier.data = partner.supplier
        form.international.data = partner.international
    
    # Obrada forme ako je POST zahtev
    if form.validate_on_submit():
        # Ažuriranje podataka partnera iz forme
        partner.name = form.name.data
        partner.address = form.address.data
        partner.city = form.city.data
        partner.country = form.country.data
        partner.account_number = form.account_number.data
        partner.pib = form.pib.data
        partner.mb = form.mb.data
        partner.phone_1 = form.phone_1.data
        partner.phone_2 = form.phone_2.data
        partner.email = form.email.data
        partner.active = form.active.data
        partner.customer = form.customer.data
        partner.supplier = form.supplier.data
        partner.international = form.international.data
        
        # Čuvanje izmena
        db.session.commit()
        
        flash('Partner uspešno izmenjen!', 'success')
        return redirect(url_for('partner.partners'))
    
    # Ako forma nije validna, prikaži greške
    if form.errors and request.method == 'POST':
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{error}', 'danger')
    
    return render_template('partner/edit_partner.html', 
                            partner=partner,
                            form=form,
                            legend='Izmena partnera',
                            title='Izmena partnera')

@partner.route('/supplier_card/<int:partner_id>')
@login_required
def supplier_card(partner_id):
    partner = Partner.query.get_or_404(partner_id)
    
    if not partner.supplier:
        flash('Izabrani partner nije označen kao dobavljač.', 'warning')
        return redirect(url_for('partner.partners'))
    
    invoices = Invoice.query.filter_by(partner_id=partner_id, incoming=True).order_by(Invoice.issue_date.desc()).all()
    return render_template('partner/supplier_card.html',
                            partner=partner,
                            legend=f'Kartica dobavljača: {partner.name}',
                            title=f'Kartica dobavljača: {partner.name}',
                            invoices=invoices,
                            current_date=datetime.now().date())

@partner.route('/customer_card/<int:partner_id>')
@login_required
def customer_card(partner_id):
    partner = Partner.query.get_or_404(partner_id)
    
    # Provera da li je partner kupac
    if not partner.customer:
        flash('Izabrani partner nije označen kao kupac.', 'warning')
        return redirect(url_for('partner.partners'))
    
    invoices = Invoice.query.filter_by(partner_id=partner_id).order_by(Invoice.issue_date.desc()).all()
    return render_template('partner/customer_card.html',
                            partner=partner,
                            legend=f'Kartica kupca: {partner.name}',
                            title=f'Kartica kupca: {partner.name}',
                            invoices=invoices,
                            current_date=datetime.now().date())