from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from arhivjugoslavije import db, app
from arhivjugoslavije.models import ArchiveSettings, BankStatement, StatementItem
from arhivjugoslavije.main.forms import SettingsForm
import xml.etree.ElementTree as ET
from datetime import datetime

main = Blueprint('main', __name__)

@main.route('/')
@main.route('/home')
@login_required
def home():
    return render_template('home.html')

@main.route('/settings/<int:id>', methods=['GET', 'POST'])
@login_required
def settings(id):
    # if current_user.user_type != 'admin':
    #     flash('Nemate prava za pristup ovom stranici.', 'danger')
    #     return redirect(url_for('main.home'))
    endpoint = request.endpoint
    archive = ArchiveSettings.query.get_or_404(id)
    form = SettingsForm()
    if form.validate_on_submit():
        archive.name = form.name.data
        archive.address = form.address.data
        archive.pib = form.pib.data
        archive.mb = form.mb.data
        db.session.commit()
        flash('Postavke su uspešno izmenjene.', 'success')
        return redirect(url_for('main.settings', id=id))
    elif request.method == 'GET':
        form.name.data = archive.name
        form.address.data = archive.address
        form.pib.data = archive.pib
        form.mb.data = archive.mb
    return render_template('settings.html',
                            endpoint=endpoint,
                            id=id,
                            archive=archive,
                            form=form)
