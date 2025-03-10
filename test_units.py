from arhivjugoslavije import app, db
from arhivjugoslavije.models import UnitOfMeasure, Service

with app.app_context():
    units = UnitOfMeasure.query.all()
    print("Units of measure:")
    for unit in units:
        print(f"ID: {unit.id}, Name: {unit.name_sr}, Symbol: {unit.symbol}")
    
    services = Service.query.all()
    print("\nServices:")
    for service in services:
        print(f"ID: {service.id}, Name: {service.name_sr}, Unit ID: {service.unit_of_measure_id}")
