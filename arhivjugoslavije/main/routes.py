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
        form.phones.data = archive.phones
        form.fax.data = archive.fax
        form.email.data = archive.email
        form.web_site.data = archive.web_site
        form.use_eur.data = archive.use_eur
    
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
        archive.phones = form.phones.data
        archive.fax = form.fax.data
        archive.email = form.email.data
        archive.web_site = form.web_site.data
        archive.use_eur = form.use_eur.data
        
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
        # Direktno preuzimanje HTML stranice sa kursom evra
        url = 'https://www.kursna-lista.com/kursna-lista-nbs'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            try:
                # Parsiranje HTML-a da bismo pronašli kurs evra
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Tražimo red sa evrom u tabeli
                eur_rate = None
                
                # Tražimo sve redove u tabeli
                rows = soup.find_all('tr')
                for row in rows:
                    # Tražimo ćelije u redu
                    cells = row.find_all('td')
                    # Proveravamo da li red sadrži tekst "Evro" ili "EUR"
                    if cells and len(cells) > 0:
                        row_text = row.text.strip()
                        if 'Evro' in row_text or 'EUR' in row_text:
                            # Na osnovu slike, srednji kurs je u petoj koloni (indeks 4)
                            if len(cells) >= 5:
                                try:
                                    # Pokušavamo da dobijemo vrednost srednjeg kursa
                                    srednji_kurs_text = cells[5].text.strip().replace(',', '.')
                                    eur_rate = round(float(srednji_kurs_text), 2)
                                    break
                                except (ValueError, IndexError):
                                    pass
                
                # Ako nismo pronašli kurs evra, probajmo još jedan način
                if not eur_rate:
                    # Tražimo direktno vrednost za EUR u srednjem kursu
                    eur_elements = soup.find_all(string=lambda text: 'EUR' in text if text else False)
                    for element in eur_elements:
                        parent = element.parent
                        if parent:
                            # Tražimo najbliži red koji sadrži ovaj element
                            row = parent
                            while row and row.name != 'tr':
                                row = row.parent
                            
                            if row:
                                # Tražimo ćeliju sa srednjim kursom
                                cells = row.find_all('td')
                                if cells and len(cells) >= 5:
                                    try:
                                        srednji_kurs_text = cells[4].text.strip().replace(',', '.')
                                        eur_rate = round(float(srednji_kurs_text), 2)
                                        break
                                    except (ValueError, IndexError):
                                        pass
                
                # Ako smo uspešno dobili kurs evra, ažuriramo podatke
                if eur_rate:
                    archive.eur_rate = eur_rate
                    archive.eur_rate_date = datetime.now()
                    db.session.commit()
                    flash('Kurs evra je uspešno ažuriran.', 'success')
                else:
                    flash('Nije pronađen kurs evra na stranici. Podaci nisu promenjeni.', 'warning')
            except Exception as e:
                flash(f'Greška pri parsiranju HTML stranice: {str(e)}.', 'danger')
        else:
            flash('Nije moguće pristupiti stranici sa kursnom listom.', 'danger')
    except Exception as e:
        flash(f'Greška pri komunikaciji sa sajtom: {str(e)}.', 'danger')
    
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
            bank=form.bank.data,
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
        bank_account.bank = form.bank.data
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
        'bank': bank_account.bank,
        'active': bank_account.active
    })
