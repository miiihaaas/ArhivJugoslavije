from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, FloatField, HiddenField, FileField
from wtforms.validators import DataRequired, Optional
from flask_wtf.file import FileAllowed


class SettingsForm(FlaskForm):
    name = StringField('Naziv', validators=[DataRequired()])
    address = StringField('Adresa', validators=[DataRequired()])
    zip_code = StringField('Poštanski broj', validators=[DataRequired()])
    city = StringField('Grad', validators=[DataRequired()])
    country = StringField('Država', validators=[DataRequired()])
    pib = StringField('PIB', validators=[DataRequired()])
    mb = StringField('MB', validators=[DataRequired()])
    phones = StringField('Telefoni', validators=[DataRequired()])
    fax = StringField('Faks', validators=[DataRequired()])
    email = StringField('E-mail', validators=[DataRequired()])
    web_site = StringField('Web stranica', validators=[DataRequired()])
    logo = FileField('Logo', validators=[Optional(), FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Dozvoljen je samo upload slika!')])
    stamp = FileField('Pečat', validators=[Optional(), FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Dozvoljen je samo upload slika!')])
    facsimile = FileField('Faksimil', validators=[Optional(), FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Dozvoljen je samo upload slika!')])
    use_eur = BooleanField('Koristi EUR', validators=[Optional()])
    eur_rate = FloatField('Kurs EUR', validators=[Optional()])
    submit = SubmitField('Sačuvajte')


class BankAccountForm(FlaskForm):
    id = HiddenField('ID')
    account_number = StringField('Broj računa', validators=[DataRequired()])
    bank = StringField('Banka', validators=[DataRequired()])
    active = BooleanField('Aktivan', default=True)
    submit = SubmitField('Sačuvaj')