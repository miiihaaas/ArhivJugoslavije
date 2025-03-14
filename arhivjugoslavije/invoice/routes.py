from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from arhivjugoslavije import db
from arhivjugoslavije.models import Partner, Invoice

invoices = Blueprint('invoices', __name__)

@invoices.route('/invoice_list', methods=['GET', 'POST'])
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
        issue_date = datetime.strptime(request.form['issue_date'], '%Y-%m-%d').date()
        service_date = datetime.strptime(request.form['service_date'], '%Y-%m-%d').date()
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

@invoices.route('/create_customer_invoice', methods=['GET', 'POST'])
@login_required
def create_customer_invoice():
    endpoint = request.endpoint
    if request.method == 'POST':
        return redirect(url_for('invoices.invoice_list'))
    return render_template('invoice/create_customer_invoice.html', endpoint=endpoint, legend='Nova izlazna faktura', title='Nova izlazna faktura')
