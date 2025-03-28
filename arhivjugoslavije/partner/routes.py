from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from arhivjugoslavije import db, app
from arhivjugoslavije.models import Partner, Invoice, StatementItem, BankStatement
from arhivjugoslavije.partner.forms import PartnerForm, EditPartnerForm
from arhivjugoslavije.partner.functions import generate_partner_card_pdf, get_partner_card_data
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

@partner.route('/supplier_card/<int:partner_id>', methods=['GET', 'POST'])
@login_required
def supplier_card(partner_id):
    partner = Partner.query.get_or_404(partner_id)
    
    if not partner.supplier:
        flash('Izabrani partner nije označen kao dobavljač.', 'warning')
        return redirect(url_for('partner.partners'))
    
    # Dobijanje datuma iz forme ili korišćenje podrazumevanih vrednosti
    if request.method == 'POST':
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date() if request.form.get('start_date') else None
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date() if request.form.get('end_date') else None
    else:
        start_date = None
        end_date = None
    
    # Dobijanje podataka za karticu dobavljača
    data = get_partner_card_data(partner_id, start_date, end_date, is_customer=False)
    
    # Provera da li je došlo do greške
    if 'error' in data:
        flash(data['message'], 'warning')
        return redirect(url_for('partner.partners'))
    
    # Priprema podataka za šablon
    return render_template('partner/supplier_card.html',
                           partner=data['partner'],
                           legend=f'Kartica dobavljača: {data["partner"].name}',
                           title=f'Kartica dobavljača: {data["partner"].name}',
                           invoices=data['invoices'],
                           statement_items=data['statement_items'],
                           combined_data=data['combined_data'],
                           total_debit=data['total_debit'],
                           total_credit=data['total_credit'],
                           current_date=data['current_date'],
                           start_date=data['start_date'],
                           end_date=data['end_date'])

@partner.route('/customer_card/<int:partner_id>', methods=['GET', 'POST'])
@login_required
def customer_card(partner_id):
    # Dobijanje datuma iz forme ili korišćenje podrazumevanih vrednosti
    if request.method == 'POST':
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date() if request.form.get('start_date') else None
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date() if request.form.get('end_date') else None
    else:
        start_date = None
        end_date = None
    
    # Dobijanje podataka za karticu kupca
    data = get_partner_card_data(partner_id, start_date, end_date, is_customer=True)
    
    # Provera da li je došlo do greške
    if 'error' in data:
        flash(data['message'], 'warning')
        return redirect(url_for('partner.partners'))
    
    # Priprema podataka za šablon
    return render_template('partner/customer_card.html',
                           partner=data['partner'],
                           legend=f'Kartica kupca: {data["partner"].name}',
                           title=f'Kartica kupca: {data["partner"].name}',
                           invoices=data['invoices'],
                           statement_items=data['statement_items'],
                           combined_data=data['combined_data'],
                           total_debit=data['total_debit'],
                           total_credit=data['total_credit'],
                           current_date=data['current_date'],
                           start_date=data['start_date'],
                           end_date=data['end_date'])

@partner.route('/customer_card/<int:partner_id>/pdf', methods=['GET'])
@login_required
def customer_card_pdf(partner_id):
    # Dobijanje datuma iz URL parametara ili korišćenje podrazumevanih vrednosti
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Dobijanje podataka za karticu kupca
    data = get_partner_card_data(partner_id, start_date, end_date, is_customer=True)
    
    # Provera da li je došlo do greške
    if 'error' in data:
        flash(data['message'], 'warning')
        return redirect(url_for('partner.partners'))
    
    # Generisanje PDF-a
    return generate_partner_card_pdf(
        partner_id, 
        data['start_date'], 
        data['end_date'], 
        data['combined_data'], 
        data['total_debit'], 
        data['total_credit'], 
        is_customer=True
    )


@partner.route('/supplier_card/<int:partner_id>/pdf', methods=['GET'])
@login_required
def supplier_card_pdf(partner_id):
    # Dobijanje datuma iz URL parametara ili korišćenje podrazumevanih vrednosti
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Dobijanje podataka za karticu dobavljača
    data = get_partner_card_data(partner_id, start_date, end_date, is_customer=False)
    
    # Provera da li je došlo do greške
    if 'error' in data:
        flash(data['message'], 'warning')
        return redirect(url_for('partner.partners'))
    
    # Generisanje PDF-a
    return generate_partner_card_pdf(
        partner_id, 
        data['start_date'], 
        data['end_date'], 
        data['combined_data'], 
        data['total_debit'], 
        data['total_credit'], 
        is_customer=False
    )