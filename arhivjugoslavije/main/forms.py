from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, FloatField, HiddenField, FileField
from wtforms.validators import DataRequired, Optional, Length, Regexp
from flask_wtf.file import FileAllowed


class SettingsForm(FlaskForm):
    name = StringField('Naziv', validators=[DataRequired()])
    address = StringField('Adresa', validators=[DataRequired()])
    zip_code = StringField('Poštanski broj', validators=[DataRequired(), Length(min=5, max=5, message='Poštanski broj mora imati tačno 5 cifara'), Regexp('^\d{5}$', message='Poštanski broj mora sadržati samo cifre')])
    city = StringField('Grad', validators=[DataRequired()])
    country = StringField('Država', validators=[DataRequired()])
    pib = StringField('PIB', validators=[DataRequired(), Length(min=9, max=9, message='PIB mora imati tačno 9 cifara'), Regexp('^\d{9}$', message='PIB mora sadržati samo cifre')])
    mb = StringField('MB', validators=[DataRequired(), Length(min=8, max=8, message='MB mora imati tačno 8 cifara'), Regexp('^\d{8}$', message='MB mora sadržati samo cifre')])
    model = StringField('Model', validators=[DataRequired(), Length(min=2, max=2, message='Model mora imati tačno 2 cifre'), Regexp('^\d{2}$', message='Model mora sadržati samo cifre')])
    poziv_na_broj = StringField('Poziv na broj', validators=[DataRequired(), Regexp('^\d+$', message='Poziv na broj mora sadržati samo cifre')])
    phone_1 = StringField('Telefon 1', validators=[DataRequired()])
    phone_2 = StringField('Telefon 2', validators=[DataRequired()])
    email = StringField('E-mail', validators=[DataRequired()])
    web_site = StringField('Web stranica', validators=[DataRequired()])
    logo = FileField('Logo', validators=[Optional(), FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Dozvoljen je samo upload slika!')])
    stamp = FileField('Pečat', validators=[Optional(), FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Dozvoljen je samo upload slika!')])
    facsimile = FileField('Faksimil', validators=[Optional(), FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Dozvoljen je samo upload slika!')])
    eur_rate = FloatField('Kurs EUR', validators=[Optional()])
    submit = SubmitField('Sačuvajte')


class BankAccountForm(FlaskForm):
    id = HiddenField('ID')
    account_number = StringField('Broj računa', validators=[DataRequired()])
    purpose = StringField('Namena', validators=[DataRequired()])
    active = BooleanField('Aktivan', default=True)
    submit = SubmitField('Sačuvaj')