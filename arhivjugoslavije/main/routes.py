from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required, current_user
from arhivjugoslavije import db, app
from arhivjugoslavije.models import ArchiveSettings, BankStatement, StatementItem, BankAccount
from arhivjugoslavije.main.forms import SettingsForm, BankAccountForm
import xml.etree.ElementTree as ET
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from werkzeug.utils import secure_filename
import os

main = Blueprint('main', __name__)

@main.route('/')
@main.route('/home')
@login_required
def home():
    return render_template('home.html')

@main.route('/settings/<int:id>', methods=['GET', 'POST'])
@login_required
def settings(id):
    archive = ArchiveSettings.query.get_or_404(id)
    form = SettingsForm()
    bank_account_form = BankAccountForm()
    
    if request.method == 'GET':
        form.name.data = archive.name
        form.address.data = archive.address
        form.zip_code.data = archive.zip_code
        form.city.data = archive.city
        form.country.data = archive.country
        form.pib.data = archive.pib
        form.mb.data = archive.mb
        form.model.data = archive.model
        form.poziv_na_broj.data = archive.poziv_na_broj
        form.phone_1.data = archive.phone_1
        form.phone_2.data = archive.phone_2
        form.email.data = archive.email
        form.web_site.data = archive.web_site
    
    # Proveravamo da li postoji aktivna inventarna lista
    active_inventory_list = False  # Ovde možete dodati logiku za proveru aktivne inventarne liste
    
    # Pripremamo putanje do slika za prikaz
    logo_url = None
    stamp_url = None
    facsimile_url = None
    
    if archive.logo:
        logo_url = url_for('static', filename=archive.logo)
    if archive.stamp:
        stamp_url = url_for('static', filename=archive.stamp)
    if archive.facsimile:
        facsimile_url = url_for('static', filename=archive.facsimile)
    
    return render_template('settings.html', title='Podešavanja', 
                           archive=archive, form=form, id=id,
                           active_inventory_list=active_inventory_list,
                           bank_account_form=bank_account_form,
                           logo_url=logo_url, stamp_url=stamp_url, facsimile_url=facsimile_url)

@main.route('/edit_settings/<int:id>', methods=['POST'])
@login_required
def edit_settings(id):
    archive = ArchiveSettings.query.get_or_404(id)
    form = SettingsForm()
    
    if form.validate_on_submit():
        archive.name = form.name.data
        archive.address = form.address.data
        archive.zip_code = form.zip_code.data
        archive.city = form.city.data
        archive.country = form.country.data
        archive.pib = form.pib.data
        archive.mb = form.mb.data
        archive.model = form.model.data
        archive.poziv_na_broj = form.poziv_na_broj.data
        archive.phone_1 = form.phone_1.data
        archive.phone_2 = form.phone_2.data
        archive.email = form.email.data
        archive.web_site = form.web_site.data
        
        # Obrada slika
        if form.logo.data:
            logo_filename = secure_filename(form.logo.data.filename)
            logo_path = os.path.join(current_app.root_path, 'static/uploads', logo_filename)
            form.logo.data.save(logo_path)
            archive.logo = 'uploads/' + logo_filename
        
        if form.stamp.data:
            stamp_filename = secure_filename(form.stamp.data.filename)
            stamp_path = os.path.join(current_app.root_path, 'static/uploads', stamp_filename)
            form.stamp.data.save(stamp_path)
            archive.stamp = 'uploads/' + stamp_filename
        
        if form.facsimile.data:
            facsimile_filename = secure_filename(form.facsimile.data.filename)
            facsimile_path = os.path.join(current_app.root_path, 'static/uploads', facsimile_filename)
            form.facsimile.data.save(facsimile_path)
            archive.facsimile = 'uploads/' + facsimile_filename
        
        db.session.commit()
        flash('Podaci arhiva su uspešno ažurirani.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Greška u polju {getattr(form, field).label.text}: {error}', 'danger')
    
    return redirect(url_for('main.settings', id=id))

@main.route('/update_eur_rate/<int:id>', methods=['POST'])
@login_required
def update_eur_rate(id):
    archive = ArchiveSettings.query.get_or_404(id)
    try:
        eur_rate_str = request.form.get('eur_rate')
        if not eur_rate_str:
            flash('Morate uneti vrednost kursa evra.', 'warning')
            return redirect(url_for('main.settings', id=id))
        try:
            eur_rate = float(eur_rate_str.replace(',', '.'))
            eur_rate = round(eur_rate, 2)
            if eur_rate <= 0:
                flash('Kurs evra mora biti pozitivan broj.', 'danger')
                return redirect(url_for('main.settings', id=id))
        except ValueError:
            flash('Uneta vrednost kursa nije validan broj.', 'danger')
            return redirect(url_for('main.settings', id=id))
        archive.eur_rate = eur_rate
        archive.eur_rate_date = datetime.now()
        db.session.commit()
        flash('Kurs evra je uspešno sačuvan.', 'success')
    except Exception as e:
        flash(f'Greška pri čuvanju kursa evra: {str(e)}.', 'danger')
    return redirect(url_for('main.settings', id=id))

@main.route('/add_bank_account/<int:settings_id>', methods=['POST'])
@login_required
def add_bank_account(settings_id):
    archive = ArchiveSettings.query.get_or_404(settings_id)
    form = BankAccountForm()
    
    if form.validate_on_submit():
        bank_account = BankAccount(
            settings_id=settings_id,
            account_number=form.account_number.data,
            sub_account_number=form.sub_account_number.data,
            account_type=form.account_type.data,
            purpose=form.purpose.data,
            active=form.active.data
        )
        
        db.session.add(bank_account)
        db.session.commit()
        flash('Žiro račun je uspešno dodat.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Greška u polju {getattr(form, field).label.text}: {error}', 'danger')
    
    return redirect(url_for('main.settings', id=settings_id))

@main.route('/edit_bank_account/<int:account_id>', methods=['POST'])
@login_required
def edit_bank_account(account_id):
    bank_account = BankAccount.query.get_or_404(account_id)
    form = BankAccountForm()
    
    if form.validate_on_submit():
        bank_account.account_number = form.account_number.data
        bank_account.sub_account_number = form.sub_account_number.data
        bank_account.account_type = form.account_type.data
        bank_account.purpose = form.purpose.data
        bank_account.active = form.active.data
        
        db.session.commit()
        flash('Žiro račun je uspešno ažuriran.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Greška u polju {getattr(form, field).label.text}: {error}', 'danger')
    
    return redirect(url_for('main.settings', id=bank_account.settings_id))

@main.route('/delete_bank_account/<int:account_id>', methods=['POST'])
@login_required
def delete_bank_account(account_id):
    bank_account = BankAccount.query.get_or_404(account_id)
    settings_id = bank_account.settings_id
    
    db.session.delete(bank_account)
    db.session.commit()
    flash('Žiro račun je uspešno obrisan.', 'success')
    
    return redirect(url_for('main.settings', id=settings_id))

@main.route('/get_bank_account/<int:account_id>', methods=['GET'])
@login_required
def get_bank_account(account_id):
    bank_account = BankAccount.query.get_or_404(account_id)
    return jsonify({
        'id': bank_account.id,
        'account_number': bank_account.account_number,
        'sub_account_number': bank_account.sub_account_number,
        'account_type': bank_account.account_type,
        'purpose': bank_account.purpose,
        'active': bank_account.active
    })
