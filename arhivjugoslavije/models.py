from arhivjugoslavije import db, login_manager, app
from flask_login import UserMixin
from itsdangerous.url_safe import URLSafeTimedSerializer as Serializer
from datetime import datetime
from sqlalchemy.ext.declarative import declared_attr

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(20), nullable=False)
    surname = db.Column(db.String(20), nullable=False)
    password = db.Column(db.String(60), nullable=False)
    
    def get_reset_token(self, expires_sec=1800):
        s = Serializer(app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})
    
    @staticmethod
    def verify_reset_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=1800)['user_id']
        except:
            return None
        return User.query.get(user_id)
    
    def __repr__(self):
        return f"User('{self.name}', '{self.surname}', '{self.email}')"


class ArchiveSettings(db.Model):
    __tablename__ = 'archive_settings'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    
    address = db.Column(db.String(200), nullable=True)
    zip_code = db.Column(db.String(5), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    
    pib = db.Column(db.String(9), nullable=True)
    mb = db.Column(db.String(8), nullable=True)
    model = db.Column(db.String(2), nullable=True)
    poziv_na_broj = db.Column(db.String(20), nullable=True)
    
    phone_1 = db.Column(db.String(20), nullable=True)
    phone_2 = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    web_site = db.Column(db.String(120), nullable=True)
    
    logo = db.Column(db.String(255), nullable=True)
    stamp = db.Column(db.String(255), nullable=True)
    facsimile = db.Column(db.String(255), nullable=True)
    eur_rate = db.Column(db.Float, nullable=True)
    eur_rate_date = db.Column(db.DateTime, nullable=True)
    
    # Definišemo vezu sa bank_accounts
    bank_accounts = db.relationship('BankAccount', backref='archive_settings', lazy=True)
    
    def __repr__(self):
        return f"ArchiveSettings('{self.name}', '{self.address}')"


class BankAccount(db.Model):
    __tablename__ = 'bank_account'
    id = db.Column(db.Integer, primary_key=True)
    settings_id = db.Column(db.Integer, db.ForeignKey('archive_settings.id'), nullable=False)
    account_number = db.Column(db.String(50), nullable=False)
    purpose = db.Column(db.String(100), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    
    def __repr__(self):
        return f"BankAccount('{self.account_number}', '{self.purpose}', active: '{self.active}')"


class Partner(db.Model):
    __tablename__ = 'partner'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=True)
    city = db.Column(db.String(50), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    account_number = db.Column(db.String(50), nullable=True)
    phone_1 = db.Column(db.String(20), nullable=True)
    phone_2 = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    pib = db.Column(db.String(20), nullable=True)
    mb = db.Column(db.String(20), nullable=True)
    customer = db.Column(db.Boolean, default=False, nullable=False)
    supplier = db.Column(db.Boolean, default=False, nullable=False)
    international = db.Column(db.Boolean, default=False, nullable=False)
    
    # Definišemo veze sa invoice i statement_item
    invoices = db.relationship('Invoice', backref='partner', lazy=True)
    statement_items = db.relationship('StatementItem', backref='partner', lazy=True)
    
    def __repr__(self):
        return f"Partner('{self.name}', '{self.city}', customer: '{self.customer}', supplier: '{self.supplier}')"


class AccountLevel4(db.Model):
    __tablename__ = 'account_level_4'
    number = db.Column(db.String(4), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    
    # Definišemo vezu sa account_level_6
    accounts_level_6 = db.relationship('AccountLevel6', backref='account_level_4', lazy=True)
    
    def __repr__(self):
        return f"AccountLevel4('{self.number}', '{self.name}')"


class AccountLevel6(db.Model):
    __tablename__ = 'account_level_6'
    number = db.Column(db.String(6), primary_key=True)
    account_level_4_number = db.Column(db.String(4), db.ForeignKey('account_level_4.number'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    
    # Definišemo veze sa project_account i statement_item
    project_accounts = db.relationship('ProjectAccount', backref='account_level_6', lazy=True)
    statement_items = db.relationship('StatementItem', backref='account_level_6', lazy=True)
    
    def __repr__(self):
        return f"AccountLevel6('{self.number}', '{self.name}')"


class Project(db.Model):
    __tablename__ = 'project'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    note = db.Column(db.Text, nullable=True)
    year = db.Column(db.Integer, nullable=True)
    archived = db.Column(db.Boolean, default=False, nullable=False)
    
    # Definišemo veze sa project_account i statement_item
    project_accounts = db.relationship('ProjectAccount', backref='project', lazy=True)
    statement_items = db.relationship('StatementItem', backref='project', lazy=True)
    
    @property
    def amount(self):
        """Dinamički računa ukupan iznos projekta kao sumu svih povezanih ProjectAccount iznosa"""
        total = 0
        if self.project_accounts:
            for account in self.project_accounts:
                if account.amount:
                    total += account.amount
        return total
    
    def __repr__(self):
        return f"Project('{self.name}', year: '{self.year}', amount: '{self.amount}')"


class ProjectAccount(db.Model):
    __tablename__ = 'project_account'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    account_level_6_number = db.Column(db.String(6), db.ForeignKey('account_level_6.number'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=True)
    note = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f"ProjectAccount(project_id: '{self.project_id}', account: '{self.account_level_6_number}', amount: '{self.amount}')"


class UnitOfMeasure(db.Model):
    __tablename__ = 'unit_of_measure'
    id = db.Column(db.Integer, primary_key=True)
    name_sr = db.Column(db.String(50), nullable=False)
    name_en = db.Column(db.String(50), nullable=True)
    symbol = db.Column(db.String(10), nullable=False)
    
    # Definišemo vezu sa service
    services = db.relationship('Service', backref='unit_of_measure', lazy=True)
    
    def __repr__(self):
        return f"UnitOfMeasure('{self.name_sr}', '{self.symbol}')"


class Service(db.Model):
    __tablename__ = 'service'
    id = db.Column(db.Integer, primary_key=True)
    name_sr = db.Column(db.String(100), nullable=False)
    name_en = db.Column(db.String(100), nullable=True)
    note = db.Column(db.Text, nullable=True)
    unit_of_measure_id = db.Column(db.Integer, db.ForeignKey('unit_of_measure.id'), nullable=False)
    price_rsd = db.Column(db.Numeric(10, 2), nullable=True)
    price_eur = db.Column(db.Numeric(10, 2), nullable=True)
    archived = db.Column(db.Boolean, default=False, nullable=False)
    
    # Definišemo vezu sa invoice_item
    invoice_items = db.relationship('InvoiceItem', backref='service', lazy=True)
    
    def __repr__(self):
        return f"Service('{self.name_sr}', price_rsd: '{self.price_rsd}', price_eur: '{self.price_eur}')"


class Invoice(db.Model):
    __tablename__ = 'invoice'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), nullable=False)
    issue_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    service_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    payment_due_date = db.Column(db.Date, nullable=True)
    partner_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    paid = db.Column(db.Boolean, default=False, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='RSD')
    incoming = db.Column(db.Boolean, default=False, nullable=False)
    status = db.Column(db.String(20), nullable=True) #! izlazne (incoming=False): nacrt, sacuvano, poslato; dolazne (incoming=True): null
    
    # Definišemo veze sa invoice_item i statement_item
    invoice_items = db.relationship('InvoiceItem', backref='invoice', lazy=True)
    # statement_items = db.relationship('StatementItem', backref='invoice', lazy=True)
    
    def __repr__(self):
        return f"Invoice('{self.invoice_number}', issue_date: '{self.issue_date}', total: '{self.total_amount} {self.currency}')"


class InvoiceItem(db.Model):
    __tablename__ = 'invoice_item'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='RSD')
    total = db.Column(db.Numeric(10, 2), nullable=False)
    
    def __repr__(self):
        return f"InvoiceItem(invoice_id: '{self.invoice_id}', service_id: '{self.service_id}', quantity: '{self.quantity}', total: '{self.total} {self.currency}')"


class BankStatement(db.Model):
    __tablename__ = 'bank_statement'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.now())
    statement_number = db.Column(db.String(20), nullable=False)
    initial_balance = db.Column(db.Numeric(10, 2), nullable=False)
    total_credit = db.Column(db.Numeric(10, 2), nullable=False)
    total_debit = db.Column(db.Numeric(10, 2), nullable=False)
    final_balance = db.Column(db.Numeric(10, 2), nullable=False)
    bank_account_id = db.Column(db.Integer, db.ForeignKey('bank_account.id'), nullable=False)
    
    # Definišemo vezu sa statement_item
    statement_items = db.relationship('StatementItem', backref='bank_statement', lazy=True)
    # Definišemo vezu sa bank_account
    bank_account = db.relationship('BankAccount', backref='bank_statements', lazy=True)
    
    def __repr__(self):
        return f"BankStatement('{self.statement_number}', date: '{self.date}', final_balance: '{self.final_balance}')"


class StatementItem(db.Model):
    __tablename__ = 'statement_item'
    id = db.Column(db.Integer, primary_key=True)
    bank_statement_id = db.Column(db.Integer, db.ForeignKey('bank_statement.id'), nullable=False)
    
    # Polja koja se mogu editovati
    partner_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=True)
    account_level_6_number = db.Column(db.String(6), db.ForeignKey('account_level_6.number'), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=True)
    public_procurement = db.Column(db.String(100), nullable=True)  # Javna nabavka - zamenjuje invoice_id
    account_in_project = db.Column(db.Boolean, default=False, nullable=False) #? Označava da li se ova stavka knjiži u projekat. Ako je True, znači da se ova stavka uračunava u finansije projekta. Podrazumevana vrednost je False.
    #? Polje account_in_project nije redundantno iako imamo project_id i account_level_6_number.
    #? Razlog je što samo postojanje veze sa projektom (project_id) ne znači automatski da ta stavka treba da se knjiži u finansije projekta. account_in_project služi kao eksplicitna oznaka koja govori sistemu da li ovu stavku treba uključiti u finansijske izveštaje projekta.
    #? Moguće je da neka transakcija bude povezana sa projektom (ima project_id), ali da iz nekog razloga ne treba da utiče na finansijsko stanje projekta. U tom slučaju, account_in_project bi bilo postavljeno na False.
    #? Ovo omogućava fleksibilnost u knjigovodstvenom praćenju projekata i daje mogućnost da se neke transakcije isključe iz finansijskih izveštaja projekta iako su povezane sa njim.
    
    # Polja koja se ne mogu editovati (iz XML fajla)
    payer = db.Column(db.String(200), nullable=True)  # Uplatilac
    recipient = db.Column(db.String(200), nullable=True)  # Primalac
    amount = db.Column(db.Numeric(10, 2), nullable=False)  # Iznos uplate/isplate
    description = db.Column(db.Text, nullable=True) #? Tekstualni opis transakcije/svrha uplate, može biti prazan. Najčešće sadrži opis sa bankovnog izvoda.
    reference_number = db.Column(db.String(50), nullable=True)  # Poziv na broj
    is_debit = db.Column(db.Boolean, default=True, nullable=False) #! True = isplata, False = uplata
    document_number = db.Column(db.String(50), nullable=True) #! Broj dokumenta povezanog sa transakcijom (može biti broj fakture, ugovora i slično). Polje može biti prazno.
    
    
    def __repr__(self):
        return f"StatementItem(bank_statement_id: '{self.bank_statement_id}', amount: '{self.amount}', is_debit: '{self.is_debit}')"