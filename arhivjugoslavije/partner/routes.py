from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from arhivjugoslavije import db, app
from arhivjugoslavije.models import Partner, Invoice, StatementItem, BankStatement
from arhivjugoslavije.partner.forms import PartnerForm, EditPartnerForm
from arhivjugoslavije.partner.functions import generate_partner_card_pdf
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
    
    # Postavljanje podrazumevanih datuma (1. januar tekuće godine do danas)
    today = datetime.now().date()
    default_start_date = datetime(today.year, 1, 1).date()
    
    # Dobijanje datuma iz forme ili korišćenje podrazumevanih vrednosti
    if request.method == 'POST':
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date() if request.form.get('start_date') else default_start_date
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date() if request.form.get('end_date') else today
    else:
        start_date = default_start_date
        end_date = today
    
    # Filtriranje faktura po datumu prometa
    invoices = Invoice.query.filter_by(partner_id=partner_id, incoming=True)\
                            .filter(Invoice.service_date >= start_date)\
                            .filter(Invoice.service_date <= end_date)\
                            .order_by(Invoice.service_date.desc()).all()
    
    # Filtriranje stavki izvoda po datumu
    statement_items_query = StatementItem.query.filter_by(partner_id=partner_id, is_debit=True)\
                                         .join(BankStatement, StatementItem.bank_statement_id == BankStatement.id)\
                                         .filter(BankStatement.date >= start_date)\
                                         .filter(BankStatement.date <= end_date)
    
    statement_items = statement_items_query.all()
    
    # Kreiranje kombinovane liste podataka za tabelu
    combined_data = []
    
    # Dodavanje faktura u kombinovane podatke
    for invoice in invoices:
        combined_data.append({
            'date': invoice.service_date,
            'account': None,  # Fakture nemaju konto
            'document_type': 'invoice',
            'document_id': invoice.id,
            'document_number': invoice.invoice_number,
            'debit': invoice.total_amount,  # Ulazne fakture idu na duguje
            'credit': None
        })
    
    # Dodavanje stavki izvoda u kombinovane podatke
    for item in statement_items:
        combined_data.append({
            'date': item.bank_statement.date,
            'account': item.account_level_6_number,
            'document_type': 'statement',
            'document_id': item.bank_statement.id,
            'document_number': f'{item.bank_statement.bank_account.account_number} ({item.bank_statement.date.year}/{item.bank_statement.statement_number})',
            'debit': None,
            'credit': item.amount  # Isplate idu na potražuje
        })
    
    # Sortiranje po datumu, od najnovijeg ka najstarijem
    combined_data.sort(key=lambda x: x['date'], reverse=True)
    
    # Računanje ukupnih vrednosti za duguje i potražuje
    total_debit = sum(item['debit'] or 0 for item in combined_data)
    total_credit = sum(item['credit'] or 0 for item in combined_data)
    
    return render_template('partner/supplier_card.html',
                            partner=partner,
                            legend=f'Kartica dobavljača: {partner.name}',
                            title=f'Kartica dobavljača: {partner.name}',
                            invoices=invoices,
                            statement_items=statement_items,
                            combined_data=combined_data,
                            total_debit=total_debit,
                            total_credit=total_credit,
                            current_date=today,
                            start_date=start_date,
                            end_date=end_date)

@partner.route('/customer_card/<int:partner_id>', methods=['GET', 'POST'])
@login_required
def customer_card(partner_id):
    partner = Partner.query.get_or_404(partner_id)
    
    # Provera da li je partner kupac
    if not partner.customer:
        flash('Izabrani partner nije označen kao kupac.', 'warning')
        return redirect(url_for('partner.partners'))
    
    # Postavljanje podrazumevanih datuma (1. januar tekuće godine do danas)
    today = datetime.now().date()
    default_start_date = datetime(today.year, 1, 1).date()
    
    # Dobijanje datuma iz forme ili korišćenje podrazumevanih vrednosti
    if request.method == 'POST':
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date() if request.form.get('start_date') else default_start_date
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date() if request.form.get('end_date') else today
    else:
        start_date = default_start_date
        end_date = today
    
    # Filtriranje faktura po datumu prometa
    invoices = Invoice.query.filter_by(partner_id=partner_id, incoming=False)\
                            .filter(Invoice.status != 'nacrt')\
                            .filter(Invoice.service_date >= start_date)\
                            .filter(Invoice.service_date <= end_date)\
                            .order_by(Invoice.service_date.desc()).all()
    
    # Filtriranje stavki izvoda po datumu
    statement_items_query = StatementItem.query.filter_by(partner_id=partner_id, is_debit=False)\
                                         .join(BankStatement, StatementItem.bank_statement_id == BankStatement.id)\
                                         .filter(BankStatement.date >= start_date)\
                                         .filter(BankStatement.date <= end_date)
    
    statement_items = statement_items_query.all()
    
    # Kreiranje kombinovane liste podataka za tabelu
    combined_data = []
    
    # Dodavanje faktura u kombinovane podatke
    for invoice in invoices:
        combined_data.append({
            'date': invoice.service_date,
            'account': None,  # Fakture nemaju konto
            'document_type': 'invoice',
            'document_id': invoice.id,
            'document_number': invoice.invoice_number,
            'debit': None,
            'credit': invoice.total_amount  # Izlazne fakture idu na potražuje
        })
    
    # Dodavanje stavki izvoda u kombinovane podatke
    for item in statement_items:
        combined_data.append({
            'date': item.bank_statement.date,
            'account': item.account_level_6_number,
            'document_type': 'statement',
            'document_id': item.bank_statement.id,
            'document_number': f'{item.bank_statement.bank_account.account_number} ({item.bank_statement.date.year}/{item.bank_statement.statement_number})',
            'debit': item.amount,  # Uplate idu na duguje
            'credit': None
        })
    
    # Sortiranje po datumu, od najnovijeg ka najstarijem
    combined_data.sort(key=lambda x: x['date'], reverse=True)
    
    # Računanje ukupnih vrednosti za duguje i potražuje
    total_debit = sum(item['debit'] or 0 for item in combined_data)
    total_credit = sum(item['credit'] or 0 for item in combined_data)
    
    return render_template('partner/customer_card.html',
                            partner=partner,
                            legend=f'Kartica kupca: {partner.name}',
                            title=f'Kartica kupca: {partner.name}',
                            invoices=invoices,
                            statement_items=statement_items,
                            combined_data=combined_data,
                            total_debit=total_debit,
                            total_credit=total_credit,
                            current_date=today,
                            start_date=start_date,
                            end_date=end_date)

@partner.route('/customer_card/<int:partner_id>/pdf', methods=['GET'])
@login_required
def customer_card_pdf(partner_id):
    partner = Partner.query.get_or_404(partner_id)
    
    # Provera da li je partner kupac
    if not partner.customer:
        flash('Izabrani partner nije označen kao kupac.', 'warning')
        return redirect(url_for('partner.partners'))
    
    # Dobijanje datuma iz URL parametara ili korišćenje podrazumevanih vrednosti
    today = datetime.now().date()
    default_start_date = datetime(today.year, 1, 1).date()
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = default_start_date
        
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        end_date = today
    
    # Filtriranje faktura po datumu prometa
    invoices = Invoice.query.filter_by(partner_id=partner_id, incoming=False)\
                            .filter(Invoice.status != 'nacrt')\
                            .filter(Invoice.service_date >= start_date)\
                            .filter(Invoice.service_date <= end_date)\
                            .order_by(Invoice.service_date.desc()).all()
    
    # Filtriranje stavki izvoda po datumu
    statement_items_query = StatementItem.query.filter_by(partner_id=partner_id, is_debit=False)\
                                         .join(BankStatement, StatementItem.bank_statement_id == BankStatement.id)\
                                         .filter(BankStatement.date >= start_date)\
                                         .filter(BankStatement.date <= end_date)
    
    statement_items = statement_items_query.all()
    
    # Kreiranje kombinovane liste podataka za tabelu
    combined_data = []
    
    # Dodavanje faktura u kombinovane podatke
    for invoice in invoices:
        combined_data.append({
            'date': invoice.service_date,
            'account': None,  # Fakture nemaju konto
            'document_type': 'invoice',
            'document_id': invoice.id,
            'document_number': invoice.invoice_number,
            'debit': None,
            'credit': invoice.total_amount  # Izlazne fakture idu na potražuje
        })
    
    # Dodavanje stavki izvoda u kombinovane podatke
    for item in statement_items:
        combined_data.append({
            'date': item.bank_statement.date,
            'account': item.account_level_6_number,
            'document_type': 'statement',
            'document_id': item.bank_statement.id,
            'document_number': f'{item.bank_statement.bank_account.account_number} ({item.bank_statement.date.year}/{item.bank_statement.statement_number})',
            'debit': item.amount,  # Uplate idu na duguje
            'credit': None
        })
    
    # Sortiranje po datumu, od najnovijeg ka najstarijem
    combined_data.sort(key=lambda x: x['date'], reverse=True)
    
    # Računanje ukupnih vrednosti za duguje i potražuje
    total_debit = sum(item['debit'] or 0 for item in combined_data)
    total_credit = sum(item['credit'] or 0 for item in combined_data)
    
    # Generisanje PDF-a
    return generate_partner_card_pdf(partner_id, start_date, end_date, combined_data, total_debit, total_credit, is_customer=True)


@partner.route('/supplier_card/<int:partner_id>/pdf', methods=['GET'])
@login_required
def supplier_card_pdf(partner_id):
    partner = Partner.query.get_or_404(partner_id)
    
    # Provera da li je partner dobavljač
    if not partner.supplier:
        flash('Izabrani partner nije označen kao dobavljač.', 'warning')
        return redirect(url_for('partner.partners'))
    
    # Dobijanje datuma iz URL parametara ili korišćenje podrazumevanih vrednosti
    today = datetime.now().date()
    default_start_date = datetime(today.year, 1, 1).date()
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = default_start_date
        
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        end_date = today
    
    # Filtriranje faktura po datumu prometa
    invoices = Invoice.query.filter_by(partner_id=partner_id, incoming=True)\
                            .filter(Invoice.service_date >= start_date)\
                            .filter(Invoice.service_date <= end_date)\
                            .order_by(Invoice.service_date.desc()).all()
    
    # Filtriranje stavki izvoda po datumu
    statement_items_query = StatementItem.query.filter_by(partner_id=partner_id, is_debit=True)\
                                         .join(BankStatement, StatementItem.bank_statement_id == BankStatement.id)\
                                         .filter(BankStatement.date >= start_date)\
                                         .filter(BankStatement.date <= end_date)
    
    statement_items = statement_items_query.all()
    
    # Kreiranje kombinovane liste podataka za tabelu
    combined_data = []
    
    # Dodavanje faktura u kombinovane podatke
    for invoice in invoices:
        combined_data.append({
            'date': invoice.service_date,
            'account': None,  # Fakture nemaju konto
            'document_type': 'invoice',
            'document_id': invoice.id,
            'document_number': invoice.invoice_number,
            'debit': invoice.total_amount,  # Ulazne fakture idu na duguje
            'credit': None
        })
    
    # Dodavanje stavki izvoda u kombinovane podatke
    for item in statement_items:
        combined_data.append({
            'date': item.bank_statement.date,
            'account': item.account_level_6_number,
            'document_type': 'statement',
            'document_id': item.bank_statement.id,
            'document_number': f'{item.bank_statement.bank_account.account_number} ({item.bank_statement.date.year}/{item.bank_statement.statement_number})',
            'debit': None,
            'credit': item.amount  # Isplate idu na potražuje
        })
    
    # Sortiranje po datumu, od najnovijeg ka najstarijem
    combined_data.sort(key=lambda x: x['date'], reverse=True)
    
    # Računanje ukupnih vrednosti za duguje i potražuje
    total_debit = sum(item['debit'] or 0 for item in combined_data)
    total_credit = sum(item['credit'] or 0 for item in combined_data)
    
    # Generisanje PDF-a
    return generate_partner_card_pdf(partner_id, start_date, end_date, combined_data, total_debit, total_credit, is_customer=False)