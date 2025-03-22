from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField, EmailField, IntegerField
from wtforms.validators import DataRequired, Email, Length, ValidationError, Optional, Regexp, NumberRange
from arhivjugoslavije.models import Partner


class PartnerForm(FlaskForm):
    """Osnovna forma za kreiranje i editovanje partnera"""
    name = StringField('Naziv partnera', validators=[
        DataRequired(message='Naziv partnera je obavezan.')
    ])
    address = StringField('Adresa')
    city = StringField('Grad')
    country = StringField('Država', default='Srbija')
    account_number = StringField('Tekući račun')
    phone_1 = StringField('Telefon 1')
    phone_2 = StringField('Telefon 2')
    email = EmailField('Email', validators=[
        Optional(),
        Email(message='Unesite ispravnu email adresu.')
    ])
    pib = StringField('PIB', validators=[
        DataRequired(message='PIB je obavezan.'),
        Length(min=9, max=9, message='PIB mora sadržati tačno 9 cifara.'),
        Regexp('^[0-9]*$', message='PIB može sadržati samo cifre.')
    ])
    mb = StringField('Matični broj', validators=[
        DataRequired(message='Matični broj je obavezan.'),
        Length(min=8, max=8, message='Matični broj mora sadržati tačno 8 cifara.'),
        Regexp('^[0-9]*$', message='Matični broj može sadržati samo cifre.')
    ])
    customer = BooleanField('Kupac')
    supplier = BooleanField('Dobavljač')
    international = BooleanField('Strani partner')
    submit = SubmitField('Sačuvaj')
    
    def validate_pib(self, pib):
        """Validacija da PIB nije već registrovan kod drugog partnera"""
        # Ova validacija se primenjuje samo pri kreiranju novog partnera
        # Za editovanje se koristi posebna validacija u EditPartnerForm
        partner = Partner.query.filter_by(pib=pib.data).first()
        if partner:
            raise ValidationError(f'U bazi već postoji partner sa PIB brojem {pib.data}.')


class EditPartnerForm(PartnerForm):
    """Forma za editovanje partnera, nasleđuje osnovnu PartnerForm"""
    submit = SubmitField('Sačuvaj izmene')
    
    def __init__(self, original_partner_id, *args, **kwargs):
        super(EditPartnerForm, self).__init__(*args, **kwargs)
        self.original_partner_id = original_partner_id
    
    def validate_pib(self, pib):
        """Validacija da PIB nije već registrovan kod drugog partnera"""
        partner = Partner.query.filter_by(pib=pib.data).first()
        if partner and partner.id != self.original_partner_id:
            raise ValidationError(f'U bazi već postoji partner sa PIB brojem {pib.data}.')