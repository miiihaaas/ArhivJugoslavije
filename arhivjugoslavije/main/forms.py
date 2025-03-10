from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired


class SettingsForm(FlaskForm):
    name = StringField('Naziv', validators=[DataRequired()])
    address = StringField('Adresa', validators=[DataRequired()])
    pib = StringField('PIB', validators=[DataRequired()])
    mb = StringField('MB', validators=[DataRequired()])
    city = StringField('Grad', validators=[DataRequired()])
    country = StringField('Država', validators=[DataRequired()])
    submit = SubmitField('Sačuvajte')