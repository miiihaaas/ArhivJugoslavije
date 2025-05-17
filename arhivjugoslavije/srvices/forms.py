from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField, BooleanField, SelectField, DecimalField
from wtforms.validators import DataRequired, Length, Optional, NumberRange

class ServiceRegisterForm(FlaskForm):
    service_name_rs = TextAreaField(
        'Naziv usluge (srpski)',
        validators=[
            DataRequired(), 
            Length(min=2, max=100, message='Naziv mora biti između 2 i 100 karaktera')
            ]
        )
    service_name_en = TextAreaField(
        'Naziv usluge (engleski)',
        validators=[
            Optional(), 
            Length(min=2, max=100, message='Naziv mora biti između 2 i 100 karaktera')
            ]
        )
    service_description = TextAreaField(
        'Napomena',
        validators=[
            Optional(), 
            Length(max=500, message='Napomena ne može biti duža od 500 karaktera')
            ]
        )
    service_unit_of_measure = SelectField(
        'Jedinica mere',
        choices=[],
        coerce=int,
        validators=[DataRequired()]
        )
    service_value = DecimalField(
        'Cena',
        places=2,  
        validators=[
            DataRequired(),
            NumberRange(min=0.01, message='Cena mora biti veća od 0.')
            ]
        )
    submit = SubmitField('Kreiraj uslugu')


class ServiceEditForm(ServiceRegisterForm):
    archived = BooleanField('Arhivirano')
    submit = SubmitField('Sačuvaj uslugu')