from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError
from arhivjugoslavije.models import User
from flask_login import current_user


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Lozinka', validators=[DataRequired()])
    remember = BooleanField('Zapamti me')
    submit = SubmitField('Prijavite se')


class RequestResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Posalji mejl')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('Lozinka', validators=[DataRequired()])
    confirm_password = PasswordField('Potvrdi lozinku', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Resetuj lozinku')