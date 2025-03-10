# Uputstvo za rad sa Flask migracijama

## 1. Instalacija potrebnih paketa
```bash
pip install flask-migrate python-dotenv
```

## 2. Konfiguracija Flask aplikacije

### 2.1. Dodati Flask-Migrate u __init__.py
```python
from flask_migrate import Migrate
# ... ostali importi ...

# Nakon inicijalizacije db
db = SQLAlchemy(app)
migrate = Migrate(app, db)
```

### 2.2. Kreirati .flaskenv fajl
Kreirati fajl `.flaskenv` u root direktorijumu projekta sa sadržajem:
```
FLASK_APP=run:app
FLASK_ENV=development
```

## 3. Inicijalizacija migracija
```bash
flask db init
```
Ovo će kreirati `migrations` folder u projektu.

## 4. Rad sa migracijama

### 4.1. Kreiranje nove migracije
Nakon izmena u models.py (npr. dodavanje nove kolone ili tabele):
```bash
flask db migrate -m "opis promene"
```

### 4.2. Primena migracije na bazu
```bash
flask db upgrade
```

### 4.3. Vraćanje na prethodnu verziju
```bash
flask db downgrade
```

## 5. Korisne komande

### 5.1. Pregled istorije migracija
```bash
flask db history
```

### 5.2. Pregled trenutne verzije baze
```bash
flask db current
```

### 5.3. Pregled status migracija
```bash
flask db show
```

## 6. Primeri čestih operacija

### 6.1. Dodavanje nove kolone
1. Dodati kolonu u models.py:
```python
class User(db.Model):
    # postojeće kolone...
    nova_kolona = db.Column(db.String(50), nullable=True)
```

2. Kreirati migraciju:
```bash
flask db migrate -m "dodata nova_kolona u User tabelu"
```

3. Primeniti migraciju:
```bash
flask db upgrade
```

### 6.2. Brisanje kolone
1. Obrisati kolonu iz models.py
2. Kreirati migraciju: `flask db migrate -m "obrisana kolona"`
3. Primeniti migraciju: `flask db upgrade`

## Napomene
- Uvek proverite generisane migracione fajlove pre primene
- Napravite backup baze pre velikih promena
- Koristite jasne i opisne poruke u migrate komandi
- Testirajte migracije na testnoj bazi pre produkcije