from wtforms import StringField, DateField, DecimalField, SelectField, BooleanField, SubmitField, HiddenField, TextAreaField
from wtforms.validators import DataRequired, Optional, NumberRange, ValidationError
from datetime import date
from flask_wtf import FlaskForm
from arhivjugoslavije.models import Invoice

class InvoiceForm(FlaskForm):
    invoice_number = StringField('Broj fakture', validators=[DataRequired()])
    issue_date = DateField('Datum izdavanja', validators=[DataRequired()], default=date.today)
    service_date = DateField('Datum prometa', validators=[DataRequired()], default=date.today)
    payment_due_date = DateField('Datum dospeća', validators=[Optional()])
    partner_id = SelectField('Partner', validators=[DataRequired()], coerce=int)
    currency = SelectField('Valuta', validators=[DataRequired()], choices=[('RSD', 'RSD'), ('EUR', 'EUR'), ('USD', 'USD')], default='RSD')
    incoming = HiddenField('Ulazna faktura', default=False)
    note = TextAreaField('Napomena', validators=[Optional()])
    submit = SubmitField('Sačuvaj')
    
    def validate_invoice_number(self, invoice_number):
        """Validacija da broj fakture nije već registrovan u bazi"""
        # Proveravamo samo izlazne fakture (incoming=False)
        invoice = Invoice.query.filter_by(invoice_number=invoice_number.data, incoming=False).first()
        if invoice:
            raise ValidationError(f'U bazi već postoji izlazna faktura sa brojem {invoice_number.data}.')

class EditInvoiceForm(InvoiceForm):
    """Forma za editovanje fakture"""
    invoice_id = HiddenField('ID fakture')
    note = TextAreaField('Napomena', validators=[Optional()])     
    
    def validate_invoice_number(self, invoice_number):
        """Validacija da broj fakture nije već registrovan kod druge fakture"""
        # Proveravamo samo izlazne fakture (incoming=False)
        # Dohvati trenutnu fakturu koja se edituje
        current_invoice = Invoice.query.get(int(self.invoice_id.data))
        
        # Ako je broj fakture nepromenjen, preskoči validaciju
        if current_invoice and current_invoice.invoice_number == invoice_number.data:
            return
            
        # Proveri da li postoji druga faktura sa istim brojem
        invoice = Invoice.query.filter_by(invoice_number=invoice_number.data, incoming=False).first()
        if invoice:
            raise ValidationError(f'U bazi već postoji izlazna faktura sa brojem {invoice_number.data}.')

class InvoiceItemForm(FlaskForm):
    service_id = SelectField('Usluga', validators=[DataRequired()], coerce=int)
    quantity = DecimalField('Količina', validators=[DataRequired(), NumberRange(min=0.01)], default=1.00)
    price = DecimalField('Cena', validators=[DataRequired(), NumberRange(min=0.01)])
    total = DecimalField('Ukupno', validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField('Dodaj stavku')
    
    def calculate_total(self):
        """Izračunava ukupnu vrednost stavke na osnovu količine i cene."""
        if self.quantity.data and self.price.data:
            self.total.data = self.quantity.data * self.price.data
        return self.total.data
