import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate

# Učitavanje .env konfiguracije
root_path = Path(__file__).resolve().parent.parent
env_path = root_path / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# Podešavanje logovanja
if not os.path.exists('app_logs'):
    os.makedirs('app_logs')
file_handler = RotatingFileHandler('app_logs/arhivjugoslavije.log', maxBytes=10240, backupCount=10, encoding='utf-8')
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s in %(module)s [%(pathname)s:%(lineno)d]: %(message)s'
))
file_handler.setLevel(logging.DEBUG)

# Inicijacija Flask aplikacije
app = Flask(__name__)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.DEBUG)
app.logger.info('ArhivJugoslavije started')

# Osnovne konfiguracije
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI')
# print(f"Nakon dodeljivanja app.config: {app.config['SQLALCHEMY_DATABASE_URI']=}")
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 299,
    'pool_timeout': 20,
    'pool_pre_ping': True
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['FLASK_APP'] = 'run.py'

# Inicijalizacija ekstenzija
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
bcrypt = Bcrypt()

# Konfigurisanje ekstenzija
login_manager.login_view = 'users.login'
login_manager.login_message_category = 'info'
login_manager.login_message = 'Molimo prijavite se.'

# Inicijalizacija sa aplikacijom
db.init_app(app)
migrate.init_app(app, db)
bcrypt.init_app(app)
login_manager.init_app(app)

# Konfiguracija za e-mail
app.config['JSON_AS_ASCII'] = False
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 465))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'False').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'True').lower() == 'true'
print(f'{app.config["MAIL_SERVER"]=}, {app.config["MAIL_PORT"]=}, {app.config["MAIL_USE_TLS"]=}, {app.config["MAIL_USE_SSL"]=}')
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
sender_raw = os.environ.get('MAIL_DEFAULT_SENDER')
if sender_raw and sender_raw.startswith('(') and ',' in sender_raw:
    name, email = sender_raw.strip('()').split(',')
    app.config['MAIL_DEFAULT_SENDER'] = (name.strip(), email.strip())
else:
    app.config['MAIL_DEFAULT_SENDER'] = sender_raw

print(f'{app.config["MAIL_USERNAME"]=}, {app.config["MAIL_PASSWORD"]=}, {app.config["MAIL_DEFAULT_SENDER"]=}')
mail = Mail(app)

# Dodavanje filtera za formatiranje valute
@app.template_filter('format_currency')
def format_currency(value):
    if value is None:
        return "-"
    try:
        # Formatiranje brojeva sa razmakom kao separatorom hiljada i zarezom za decimale
        value = float(value)
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", " ") + " RSD"
    except (ValueError, TypeError):
        return str(value)

# Import modela
from arhivjugoslavije import models

# Definišemo funkciju za učitavanje korisnika
@login_manager.user_loader
def load_user(user_id):
    with app.app_context():
        from arhivjugoslavije.models import User
        return User.query.get(int(user_id))
app.logger.info(f"ID login_manager objekta u init: {id(login_manager)}")


# Registracija blueprint-a
from arhivjugoslavije.accounts.routes import account
from arhivjugoslavije.errors.routes import errors
from arhivjugoslavije.invoice.routes import invoices
from arhivjugoslavije.main.routes import main
from arhivjugoslavije.partner.routes import partner
from arhivjugoslavije.purchase_plan.routes import purchase_plan
from arhivjugoslavije.project.routes import project
from arhivjugoslavije.reports.routes import reports
# from arhivjugoslavije.payments.routes import payments
from arhivjugoslavije.statement.routes import statement
from arhivjugoslavije.srvices.routes import services
from arhivjugoslavije.users.routes import users

app.register_blueprint(account)
app.register_blueprint(errors)
app.register_blueprint(invoices)
app.register_blueprint(main)
app.register_blueprint(partner)
app.register_blueprint(purchase_plan)
app.register_blueprint(project)
app.register_blueprint(reports)
# app.register_blueprint(payments)
app.register_blueprint(statement)
app.register_blueprint(services)
app.register_blueprint(users)
