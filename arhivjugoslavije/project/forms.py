from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, BooleanField, SelectField
from wtforms.validators import DataRequired, Length, Optional


class ProjectRegisterForm(FlaskForm):
    name = StringField(
        'Naziv projekta',
        validators=[
            DataRequired(), 
            Length(min=2, max=100, message='Naziv mora biti između 2 i 100 karaktera')
            ]
        )
    amount = StringField(
        'Vrednost projekta',
        validators=[
            Optional(), 
            Length(max=20, message='Vrednost projekta ne može biti duža od 20 karaktera')
            ]
        )
    note = TextAreaField(
        'Napomena',
        validators=[
            Optional(), 
            Length(max=200, message='Napomena ne može biti duža od 200 karaktera')
            ]
        )
    year = StringField(
        'Godina',
        validators=[
            Optional(), 
            Length(max=4, message='Godina ne može biti duža od 4 karaktera')
            ]
        )
    submit = SubmitField('Kreiraj projekt')


class ProjectEditForm(ProjectRegisterForm):
    archived = BooleanField('Arhivirano')
    submit = SubmitField('Sačuvaj projekat')