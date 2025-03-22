from arhivjugoslavije.models import Service, UnitOfMeasure, ArchiveSettings
from arhivjugoslavije.srvices.forms import ServiceRegisterForm, ServiceEditForm
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from arhivjugoslavije import db, app
from flask_login import login_required, current_user

services = Blueprint('services', __name__)


@services.route('/services_list')
@login_required
def services_list():
    services = Service.query.all()
    units = UnitOfMeasure.query.all()
    register_form = ServiceRegisterForm()
    edit_form = ServiceEditForm()
    
    # Dobavljanje postavki arhiva za kurs evra
    archive_settings = ArchiveSettings.query.first()
    
    # Inicijalizacija izbora za polje u formi
    register_form.service_unit_of_measure.choices = [(unit.id, f'{unit.name_sr} ({unit.symbol})') for unit in units]
    edit_form.service_unit_of_measure.choices = [(unit.id, f'{unit.name_sr} ({unit.symbol})') for unit in units]
    
    return render_template('services_list.html', 
                            services=services,
                            units=units,
                            register_form=register_form,
                            edit_form=edit_form,
                            legend='Lista usluga',
                            title='Usluge',
                            archive_settings=archive_settings)


@services.route('/create_service', methods=['GET', 'POST'])
@login_required
def create_service():
    endpoint = request.endpoint
    register_form = ServiceRegisterForm()
    units = UnitOfMeasure.query.all()
    register_form.service_unit_of_measure.choices = [(unit.id, f'{unit.name_sr} ({unit.symbol})') for unit in units]
    
    if register_form.validate_on_submit():
        new_service = Service(
            name_sr=register_form.service_name_rs.data,
            name_en=register_form.service_name_en.data,
            price_rsd=register_form.service_value.data,
            price_eur=round(float(register_form.service_value.data) / ArchiveSettings.query.first().eur_rate, 2),
            note=register_form.service_description.data,
            unit_of_measure_id=register_form.service_unit_of_measure.data,
            archived=False
        )
        db.session.add(new_service)
        db.session.commit()
        flash('Usluga uspešno kreirana.', 'success')
        return redirect(url_for('services.services_list'))
    return render_template('services_list.html', 
                            endpoint=endpoint,
                            register_form=register_form,
                            legend='Kreiranje usluge',
                            title='Kreiranje usluge')


@services.route('/edit_service/<int:service_id>', methods=['GET', 'POST'])
@login_required
def edit_service(service_id):
    form_service_id = request.form.get('service_id')
    if form_service_id:
        service_id = int(form_service_id)
        
    service = Service.query.get_or_404(service_id)
    edit_form = ServiceEditForm()
    
    units = UnitOfMeasure.query.all()
    edit_form.service_unit_of_measure.choices = [(unit.id, f'{unit.name_sr} ({unit.symbol})') for unit in units]
    
    if edit_form.validate_on_submit():
        service.name_sr = edit_form.service_name_rs.data
        service.name_en = edit_form.service_name_en.data
        service.note = edit_form.service_description.data
        service.unit_of_measure_id = edit_form.service_unit_of_measure.data
        service.price_rsd = edit_form.service_value.data
        service.price_eur = round(float(edit_form.service_value.data) / ArchiveSettings.query.first().eur_rate, 2)
        service.archived = bool(int(edit_form.archived.data))
        
        db.session.commit()
        flash('Usluga uspešno izmenjena.', 'success')
        
    return redirect(url_for('services.services_list'))


@services.route('/get_service/<int:service_id>')
@login_required
def get_service(service_id):
    service = Service.query.get_or_404(service_id)
    
    # Provera da li jedinica mere postoji
    unit_of_measure_id = service.unit_of_measure_id if service.unit_of_measure_id else None
    
    return jsonify({
        'service_name_rs': service.name_sr,
        'service_name_en': service.name_en,
        'service_description': service.note,
        'service_unit_of_measure': unit_of_measure_id,
        'service_value': service.price_rsd,
        'service_value_eur': service.price_eur,
        'archived': service.archived
    })