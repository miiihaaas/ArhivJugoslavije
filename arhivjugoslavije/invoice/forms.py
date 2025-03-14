from flask_wtf import FlaskForm
from wtforms import StringField, DateField, DecimalField, SelectField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Optional, NumberRange
from datetime import date

class InvoiceForm(FlaskForm):
    invoice_number = StringField('Broj fakture', validators=[DataRequired()])
    issue_date = DateField('Datum izdavanja', validators=[DataRequired()], default=date.today)
    service_date = DateField('Datum usluge', validators=[DataRequired()], default=date.today)
    payment_due_date = DateField('Rok plaćanja', validators=[Optional()])
    partner_id = SelectField('Partner', validators=[DataRequired()], coerce=int)
    currency = SelectField('Valuta', validators=[DataRequired()], choices=[('RSD', 'RSD'), ('EUR', 'EUR'), ('USD', 'USD')], default='RSD')
    incoming = HiddenField('Ulazna faktura', default=False)
    submit = SubmitField('Sačuvaj')

class InvoiceItemForm(FlaskForm):
    service_id = SelectField('Usluga', validators=[DataRequired()], coerce=int)
    quantity = DecimalField('Količina', validators=[DataRequired(), NumberRange(min=0.01)], default=1.00)
    price = DecimalField('Cena', validators=[DataRequired(), NumberRange(min=0.01)])
    currency = SelectField('Valuta', validators=[DataRequired()], choices=[('RSD', 'RSD'), ('EUR', 'EUR'), ('USD', 'USD')], default='RSD')
    total = DecimalField('Ukupno', validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField('Dodaj stavku')
    
    def calculate_total(self):
        """Izračunava ukupnu vrednost stavke na osnovu količine i cene."""
        if self.quantity.data and self.price.data:
            self.total.data = self.quantity.data * self.price.data
        return self.total.data
