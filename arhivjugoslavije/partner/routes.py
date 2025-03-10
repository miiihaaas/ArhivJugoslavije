from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from arhivjugoslavije import db, app
from arhivjugoslavije.models import Partner


partner = Blueprint('partner', __name__)


@partner.route('/partners', methods=['GET', 'POST'])
@login_required
def partners():
    endpoint = request.endpoint
    partners = Partner.query.all()
    return render_template('partners.html', 
                            endpoint=endpoint, 
                            partners=partners,
                            legend='Poslovni partneri',
                            title='Poslovni partneri')

@partner.route('/add_partner', methods=['POST'])
@login_required
def add_partner():
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        city = request.form.get('city')
        country = request.form.get('country')
        account_number = request.form.get('account_number')
        pib = request.form.get('pib')
        mb = request.form.get('mb')
        phones = request.form.get('phones')
        fax = request.form.get('fax')
        email = request.form.get('email')
        
        # Checkbox vrednosti
        customer = True if request.form.get('customer') else False
        supplier = True if request.form.get('supplier') else False
        international = True if request.form.get('international') else False
        
        # Validacija
        if not name:
            flash('Naziv partnera je obavezan!', 'danger')
            return redirect(url_for('partner.partners'))
        
        # Provera da li PIB već postoji u bazi
        if pib and pib.strip():
            existing_partner = Partner.query.filter_by(pib=pib).first()
            if existing_partner:
                flash(f'U bazi već postoji partner sa PIB brojem {pib}!', 'warning')
                return redirect(url_for('partner.edit_partner', partner_id=existing_partner.id))
        
        # Kreiranje novog partnera
        new_partner = Partner(
            name=name,
            address=address,
            city=city,
            country=country,
            account_number=account_number,
            pib=pib,
            mb=mb,
            phones=phones,
            fax=fax,
            email=email,
            customer=customer,
            supplier=supplier,
            international=international
        )
        
        # Dodavanje u bazu
        db.session.add(new_partner)
        db.session.commit()
        
        flash('Partner uspešno dodat!', 'success')
        return redirect(url_for('partner.partners'))

@partner.route('/edit_partner/<int:partner_id>', methods=['GET', 'POST'])
@login_required
def edit_partner(partner_id):
    partner = Partner.query.get_or_404(partner_id)
    
    if request.method == 'POST':
        # Prikupljanje podataka iz forme
        partner.name = request.form.get('name')
        partner.address = request.form.get('address')
        partner.city = request.form.get('city')
        partner.country = request.form.get('country')
        partner.account_number = request.form.get('account_number')
        pib = request.form.get('pib')
        partner.mb = request.form.get('mb')
        partner.phones = request.form.get('phones')
        partner.fax = request.form.get('fax')
        partner.email = request.form.get('email')
        
        # Checkbox vrednosti
        partner.customer = True if request.form.get('customer') else False
        partner.supplier = True if request.form.get('supplier') else False
        partner.international = True if request.form.get('international') else False
        
        # Validacija
        if not partner.name:
            flash('Naziv partnera je obavezan!', 'danger')
            return render_template('edit_partner.html', 
                                  partner=partner,
                                  legend='Izmena partnera',
                                  title='Izmena partnera')
        
        # Provera da li PIB već postoji u bazi kod drugog partnera
        if pib and pib.strip():
            existing_partner = Partner.query.filter_by(pib=pib).first()
            if existing_partner and existing_partner.id != partner_id:
                flash(f'U bazi već postoji partner sa PIB brojem {pib}!', 'warning')
                return redirect(url_for('partner.edit_partner', partner_id=existing_partner.id))
        
        # Ažuriranje PIB-a nakon validacije
        partner.pib = pib
        
        # Čuvanje izmena
        db.session.commit()
        
        flash('Partner uspešno izmenjen!', 'success')
        return redirect(url_for('partner.partners'))
    
    return render_template('edit_partner.html', 
                          partner=partner,
                          legend='Izmena partnera',
                          title='Izmena partnera')