from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import asc
from arhivjugoslavije import db
from arhivjugoslavije.models import AccountLevel4, AccountLevel6

account = Blueprint('account', __name__)

@account.route('/account_list', methods=['GET'])
@login_required
def account_list():
    # Dobavljanje svih konta nivoa 4 i 6, sortiranih po broju konta
    accounts4 = AccountLevel4.query.order_by(asc(AccountLevel4.number)).all()
    accounts6 = AccountLevel6.query.order_by(asc(AccountLevel6.number)).all()
    
    return render_template('accounts/account_list.html', 
                            accounts4=accounts4, 
                            accounts6=accounts6, 
                            title='Konta')

@account.route('/add_account_level4', methods=['POST'])
@login_required
def add_account_level4():
    # Dobijanje podataka iz form zahteva
    number = request.form.get('number')
    name = request.form.get('name')
    
    # Validacija podataka
    if not number or not name:
        flash('Broj konta i naziv su obavezni', 'danger')
        return redirect(url_for('account.account_list'))
    
    if len(number) != 4 or not number.isdigit():
        flash('Broj konta mora biti četvorocifreni broj', 'danger')
        return redirect(url_for('account.account_list'))
    
    # Provera da li konto već postoji
    existing_account = AccountLevel4.query.filter_by(number=number).first()
    if existing_account:
        flash(f'Konto {number} već postoji', 'danger')
        return redirect(url_for('account.account_list'))
    
    try:
        # Kreiranje novog konta nivoa 4
        new_account = AccountLevel4(number=number, name=name)
        db.session.add(new_account)
        db.session.commit()
        
        flash(f'Konto {number} uspešno dodat', 'success')
        return redirect(url_for('account.account_list'))
    except Exception as e:
        db.session.rollback()
        flash(f'Greška pri dodavanju konta: {str(e)}', 'danger')
        return redirect(url_for('account.account_list'))

@account.route('/add_account_level6', methods=['POST'])
@login_required
def add_account_level6():
    # Dobijanje podataka iz form zahteva
    number = request.form.get('number')
    name = request.form.get('name')
    account_level_4_number = request.form.get('account_level_4_number')
    
    # Validacija podataka
    if not number or not name or not account_level_4_number:
        flash('Svi podaci su obavezni', 'danger')
        return redirect(url_for('account.account_list'))
    
    if len(number) != 6 or not number.isdigit():
        flash('Broj konta mora biti šestocifreni broj', 'danger')
        return redirect(url_for('account.account_list'))
    
    # Provera da li konto već postoji
    existing_account = AccountLevel6.query.filter_by(number=number).first()
    if existing_account:
        flash(f'Konto {number} već postoji', 'danger')
        return redirect(url_for('account.account_list'))
    
    # Provera da li postoji nadređeni konto nivoa 4
    parent_account = AccountLevel4.query.filter_by(number=account_level_4_number).first()
    if not parent_account:
        flash(f'Konto nivoa 4 sa brojem {account_level_4_number} ne postoji', 'danger')
        return redirect(url_for('account.account_list'))
    
    # Provera da li prvih 4 cifara konta nivoa 6 odgovaraju kontu nivoa 4
    if number[:4] != account_level_4_number:
        flash(f'Prve 4 cifre konta nivoa 6 moraju odgovarati kontu nivoa 4 ({account_level_4_number})', 'danger')
        return redirect(url_for('account.account_list'))
    
    try:
        # Kreiranje novog konta nivoa 6
        new_account = AccountLevel6(
            number=number, 
            name=name, 
            account_level_4_number=account_level_4_number
        )
        db.session.add(new_account)
        db.session.commit()
        
        flash(f'Konto {number} uspešno dodat', 'success')
        return redirect(url_for('account.account_list'))
    except Exception as e:
        db.session.rollback()
        flash(f'Greška pri dodavanju konta: {str(e)}', 'danger')
        return redirect(url_for('account.account_list'))


@account.route('/get_account_level4/<number>', methods=['GET'])
@login_required
def get_account_level4(number):
    # Dobavljanje konta nivoa 4 po broju
    account = AccountLevel4.query.filter_by(number=number).first()
    
    if not account:
        return jsonify({'success': False, 'message': f'Konto {number} nije pronađen'}), 404
    
    return jsonify({
        'success': True,
        'account': {
            'number': account.number,
            'name': account.name
        }
    })


@account.route('/get_account_level6/<number>', methods=['GET'])
@login_required
def get_account_level6(number):
    # Dobavljanje konta nivoa 6 po broju
    account = AccountLevel6.query.filter_by(number=number).first()
    
    if not account:
        return jsonify({'success': False, 'message': f'Konto {number} nije pronađen'}), 404
    
    return jsonify({
        'success': True,
        'account': {
            'number': account.number,
            'name': account.name,
            'account_level_4_number': account.account_level_4_number
        }
    })


@account.route('/update_account_level4', methods=['POST'])
@login_required
def update_account_level4():
    # Dobijanje podataka iz form zahteva
    number = request.form.get('number')
    name = request.form.get('name')
    
    # Validacija podataka
    if not number or not name:
        flash('Broj konta i naziv su obavezni', 'danger')
        return redirect(url_for('account.account_list'))
    
    if len(number) != 4 or not number.isdigit():
        flash('Broj konta mora biti četvorocifreni broj', 'danger')
        return redirect(url_for('account.account_list'))
    
    # Pronalaženje konta za ažuriranje
    account = AccountLevel4.query.filter_by(number=number).first()
    if not account:
        flash(f'Konto {number} ne postoji', 'danger')
        return redirect(url_for('account.account_list'))
    
    try:
        # Ažuriranje konta nivoa 4
        account.name = name
        db.session.commit()
        
        flash(f'Konto {number} uspešno izmenjen', 'success')
        return redirect(url_for('account.account_list'))
    except Exception as e:
        db.session.rollback()
        flash(f'Greška pri izmeni konta: {str(e)}', 'danger')
        return redirect(url_for('account.account_list'))


@account.route('/update_account_level6', methods=['POST'])
@login_required
def update_account_level6():
    # Dobijanje podataka iz form zahteva
    number = request.form.get('number')
    name = request.form.get('name')
    account_level_4_number = request.form.get('account_level_4_number')
    
    # Validacija podataka
    if not number or not name or not account_level_4_number:
        flash('Svi podaci su obavezni', 'danger')
        return redirect(url_for('account.account_list'))
    
    if len(number) != 6 or not number.isdigit():
        flash('Broj konta mora biti šestocifreni broj', 'danger')
        return redirect(url_for('account.account_list'))
    
    # Pronalaženje konta za ažuriranje
    account = AccountLevel6.query.filter_by(number=number).first()
    if not account:
        flash(f'Konto {number} ne postoji', 'danger')
        return redirect(url_for('account.account_list'))
    
    # Provera da li postoji nadređeni konto nivoa 4
    parent_account = AccountLevel4.query.filter_by(number=account_level_4_number).first()
    if not parent_account:
        flash(f'Konto nivoa 4 sa brojem {account_level_4_number} ne postoji', 'danger')
        return redirect(url_for('account.account_list'))
    
    # Provera da li prvih 4 cifara konta nivoa 6 odgovaraju kontu nivoa 4
    if number[:4] != account_level_4_number:
        flash(f'Prve 4 cifre konta nivoa 6 moraju odgovarati kontu nivoa 4 ({account_level_4_number})', 'danger')
        return redirect(url_for('account.account_list'))
    
    try:
        # Ažuriranje konta nivoa 6
        account.name = name
        account.account_level_4_number = account_level_4_number
        db.session.commit()
        
        flash(f'Konto {number} uspešno izmenjen', 'success')
        return redirect(url_for('account.account_list'))
    except Exception as e:
        db.session.rollback()
        flash(f'Greška pri izmeni konta: {str(e)}', 'danger')
        return redirect(url_for('account.account_list'))
