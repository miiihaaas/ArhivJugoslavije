from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, make_response
from flask_login import login_required, current_user
from arhivjugoslavije import db
from arhivjugoslavije.models import Partner, Invoice, InvoiceItem, Service, ArchiveSettings, UnitOfMeasure
from arhivjugoslavije.invoice.forms import InvoiceForm, InvoiceItemForm
from arhivjugoslavije.invoice.functions import generate_invoice_pdf
import os
from pathlib import Path

invoices = Blueprint('invoices', __name__)

@invoices.route('/invoice_list')
@login_required
def invoice_list():
    endpoint = request.endpoint
    invoices = Invoice.query.all()
    suppliers = Partner.query.filter_by(supplier=True).all()
    return render_template('invoice/invoice_list.html', 
                            endpoint=endpoint, 
                            legend='Pregled faktura', 
                            title='Fakture',
                            invoices=invoices,
                            suppliers=suppliers)

@invoices.route('/create_supplier_invoice', methods=['GET', 'POST'])
@login_required
def create_supplier_invoice():
    endpoint = request.endpoint
    if request.method == 'POST':
        try:
            issue_date = datetime.strptime(request.form['issue_date'], '%Y-%m-%d').date()
            service_date = datetime.strptime(request.form['service_date'], '%Y-%m-%d').date()
            payment_due_date = None
            if request.form['payment_due_date']:
                payment_due_date = datetime.strptime(request.form['payment_due_date'], '%Y-%m-%d').date()
                
            new_invoice = Invoice(
                invoice_number=request.form['invoice_number'],
                issue_date=issue_date,
                service_date=service_date,
                payment_due_date=payment_due_date,
                total_amount=request.form['total_amount'],
                currency=request.form['currency'],
                partner_id=request.form['partner_id'],
                incoming=True
            )
            db.session.add(new_invoice)
            db.session.commit()
            flash('Ulazna faktura uspešno kreirana.', 'success')
            return redirect(url_for('invoices.invoice_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Došlo je do greške prilikom kreiranja fakture: {str(e)}.', 'danger')
            return redirect(url_for('invoices.invoice_list'))

@invoices.route('/create_customer_invoice', methods=['GET', 'POST'])
@login_required
def create_customer_invoice():
    endpoint = request.endpoint
    form = InvoiceForm()
    
    # Popuni izbor partnera (samo kupci)
    customers = Partner.query.filter_by(customer=True).all()
    form.partner_id.choices = [(p.id, p.name) for p in customers]
    
    if form.validate_on_submit():
        try:
            new_invoice = Invoice(
                invoice_number=form.invoice_number.data,
                issue_date=form.issue_date.data,
                service_date=form.service_date.data,
                payment_due_date=form.payment_due_date.data,
                partner_id=form.partner_id.data,
                currency=form.currency.data,
                total_amount=0,  # Početna vrednost, biće ažurirana nakon dodavanja stavki
                incoming=False
            )
            db.session.add(new_invoice)
            db.session.commit()
            
            flash('Izlazna faktura uspešno kreirana. Sada možete dodati stavke.', 'success')
            return redirect(url_for('invoices.edit_customer_invoice', invoice_id=new_invoice.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Došlo je do greške prilikom kreiranja fakture: {str(e)}.', 'danger')
    
    return render_template('invoice/create_customer_invoice.html', 
                           endpoint=endpoint, 
                           legend='Nova izlazna faktura', 
                           title='Nova izlazna faktura',
                           form=form)

@invoices.route('/edit_customer_invoice/<int:invoice_id>', methods=['GET', 'POST'])
@login_required
def edit_customer_invoice(invoice_id):
    endpoint = request.endpoint
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Proveri da li je izlazna faktura
    if invoice.incoming:
        flash('Izmena podataka ulazne fakture.', 'warning')
        return redirect(url_for('invoices.edit_supplier_invoice', invoice_id=invoice.id))
    
    # Forma za fakturu
    form = InvoiceForm(obj=invoice)
    customers = Partner.query.filter_by(customer=True).all()
    form.partner_id.choices = [(p.id, p.name) for p in customers]
    
    # Forma za stavke fakture
    item_form = InvoiceItemForm()
    services = Service.query.filter_by(archived=False).all()
    item_form.service_id.choices = [(s.id, s.name_sr) for s in services]
    
    # Postojeće stavke fakture
    invoice_items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
    
    if form.validate_on_submit():
        try:
            invoice.invoice_number = form.invoice_number.data
            invoice.issue_date = form.issue_date.data
            invoice.service_date = form.service_date.data
            invoice.payment_due_date = form.payment_due_date.data
            invoice.partner_id = form.partner_id.data
            invoice.currency = form.currency.data
            
            db.session.commit()
            flash('Faktura uspešno ažurirana.', 'success')
            return redirect(url_for('invoices.edit_customer_invoice', invoice_id=invoice.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Došlo je do greške prilikom ažuriranja fakture: {str(e)}.', 'danger')
    
    return render_template('invoice/edit_customer_invoice.html',
                            endpoint=endpoint,
                            legend=f'Uređivanje fakture {invoice.invoice_number}',
                            title='Uređivanje fakture',
                            form=form,
                            item_form=item_form,
                            invoice=invoice,
                            invoice_items=invoice_items)


@invoices.route('/edit_supplier_invoice/<int:invoice_id>', methods=['GET', 'POST'])
def edit_supplier_invoice(invoice_id):
    endpoint = request.endpoint
    invoice = Invoice.query.get_or_404(invoice_id)
    form = InvoiceForm(obj=invoice)
    suppliers = Partner.query.filter_by(supplier=True).all()
    form.partner_id.choices = [(p.id, p.name) for p in suppliers]
    
    # Provera da li je faktura ulazna
    if not invoice.incoming:
        flash('Izmena podataka izlazne fakture.', 'danger')
        return redirect(url_for('invoices.edit_customer_invoice', invoice_id=invoice.id))
    
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(invoice)
            invoice.incoming = True  # Osiguravamo da je ulazna faktura
            
            # Ručno ažuriranje total_amount i paid polja koja nisu u formi
            if 'total_amount' in request.form:
                invoice.total_amount = request.form['total_amount']
            
            # Ažuriranje statusa plaćanja
            invoice.paid = 'paid' in request.form
            
            db.session.commit()
            flash('Faktura je uspešno ažurirana.', 'success')
            return redirect(url_for('invoices.invoice_list'))
        else:
            flash('Došlo je do greške prilikom ažuriranja fakture. Proverite unete podatke.', 'danger')
    
    return render_template('invoice/edit_supplier_invoice.html',
                            endpoint=endpoint,
                            legend=f'Uređivanje fakture {invoice.invoice_number}',
                            title='Uređivanje fakture',
                            form=form,
                            invoice=invoice)

@invoices.route('/add_invoice_item/<int:invoice_id>', methods=['POST'])
@login_required
def add_invoice_item(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    form = InvoiceItemForm()
    services = Service.query.filter_by(archived=False).all()
    form.service_id.choices = [(s.id, s.name_sr) for s in services]
    
    if form.validate_on_submit():
        try:
            new_item = InvoiceItem(
                invoice_id=invoice_id,
                service_id=form.service_id.data,
                quantity=form.quantity.data,
                price=form.price.data,
                currency=form.currency.data,
                total=form.total.data
            )
            db.session.add(new_item)
            
            # Ažuriraj ukupan iznos fakture
            items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
            total_amount = sum(item.total for item in items) + form.total.data
            invoice.total_amount = total_amount
            
            db.session.commit()
            flash('Stavka uspešno dodata u fakturu.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Došlo je do greške prilikom dodavanja stavke: {str(e)}.', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Greška u polju {getattr(form, field).label.text}: {error}.', 'danger')
    
    return redirect(url_for('invoices.edit_customer_invoice', invoice_id=invoice_id))

@invoices.route('/remove_invoice_item/<int:item_id>', methods=['POST'])
@login_required
def remove_invoice_item(item_id):
    item = InvoiceItem.query.get_or_404(item_id)
    invoice_id = item.invoice_id
    invoice = Invoice.query.get(invoice_id)
    
    try:
        # Ažuriraj ukupan iznos fakture
        invoice.total_amount -= item.total
        
        db.session.delete(item)
        db.session.commit()
        flash('Stavka uspešno uklonjena iz fakture.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Došlo je do greške prilikom uklanjanja stavke: {str(e)}.', 'danger')
    
    return redirect(url_for('invoices.edit_customer_invoice', invoice_id=invoice_id))

@invoices.route('/get_service_price/<int:service_id>')
@login_required
def get_service_price(service_id):
    service = Service.query.get_or_404(service_id)
    return jsonify({
        'price_rsd': float(service.price_rsd) if service.price_rsd else 0,
        'price_eur': float(service.price_eur) if service.price_eur else 0
    })

@invoices.route('/generate_invoice_pdf/<int:invoice_id>')
@login_required
def generate_invoice_pdf_route(invoice_id):
    """
    Ruta za generisanje PDF fakture.
    Poziva funkciju iz functions.py koja sadrži svu logiku.
    """
    return generate_invoice_pdf(invoice_id)

@invoices.route('/get_invoice_item/<int:item_id>')
@login_required
def get_invoice_item(item_id):
    """Dohvata podatke o stavci fakture za uređivanje."""
    item = InvoiceItem.query.get_or_404(item_id)
    
    # Vraća podatke o stavci u JSON formatu
    return jsonify({
        'id': item.id,
        'invoice_id': item.invoice_id,
        'service_id': item.service_id,
        'quantity': float(item.quantity),
        'price': float(item.price),
        'currency': item.currency,
        'total': float(item.total)
    })

@invoices.route('/edit_invoice_item/<int:invoice_id>', methods=['POST'])
@login_required
def edit_invoice_item(invoice_id):
    """Ažurira postojeću stavku fakture."""
    invoice = Invoice.query.get_or_404(invoice_id)
    item_id = request.form.get('item_id')
    item = InvoiceItem.query.get_or_404(item_id)
    
    # Proveri da li stavka pripada ovoj fakturi
    if item.invoice_id != invoice_id:
        return jsonify({'success': False, 'message': 'Stavka ne pripada ovoj fakturi.'}), 400
    
    try:
        # Sačuvaj staru vrednost za ažuriranje ukupnog iznosa fakture
        old_total = item.total
        
        # Ažuriraj podatke stavke
        item.service_id = request.form.get('service_id')
        item.quantity = request.form.get('quantity')
        item.price = request.form.get('price')
        item.currency = request.form.get('currency')
        item.total = request.form.get('total')
        
        # Ažuriraj ukupan iznos fakture
        invoice.total_amount = float(invoice.total_amount) - float(old_total) + float(item.total)
        
        db.session.commit()
        flash('Stavka fakture je uspešno ažurirana.', 'success')
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        flash(f'Došlo je do greške prilikom ažuriranja stavke: {str(e)}.', 'danger')
        return jsonify({'success': False, 'message': str(e)}), 500
