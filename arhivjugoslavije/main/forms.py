from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, FloatField
from wtforms.validators import DataRequired, Optional


class SettingsForm(FlaskForm):
    name = StringField('Naziv', validators=[DataRequired()])
    address = StringField('Adresa', validators=[DataRequired()])
    pib = StringField('PIB', validators=[DataRequired()])
    mb = StringField('MB', validators=[DataRequired()])
    city = StringField('Grad', validators=[DataRequired()])
    country = StringField('Država', validators=[DataRequired()])
    logo = StringField('Logo', validators=[Optional()])
    stamp = StringField('Pečat', validators=[Optional()])
    facsimile = StringField('Faksimil', validators=[Optional()])
    use_eur = BooleanField('Koristi EUR', validators=[Optional()])
    eur_rate = FloatField('Kurs EUR', validators=[Optional()])
    submit = SubmitField('Sačuvajte')