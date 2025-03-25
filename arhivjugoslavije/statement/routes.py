from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from arhivjugoslavije.models import Partner, AccountLevel6, Project, BankAccount, BankStatement, StatementItem
from arhivjugoslavije import db

statement = Blueprint('statement', __name__)

@statement.route('/statement_list', methods=['GET', 'POST'])
@login_required
def statement_list():
    endpoint = request.endpoint
    bank_statements = []
    error_mesage = None
    stavke = None
    datum_izvoda_element = None
    broj_izvoda_element = None
    racun_izvoda_element = None
    pocetno_stanje_element = None
    ukupno_duguje_element = None
    ukupno_potrazuje_element = None
    krajnje_stanje_element = None
    broj_pojavljivanja = None
    izvod_vec_postoji = False
    
    # Učitavanje podataka za padajuće menije
    partners = Partner.query.all()
    accounts_level_6 = AccountLevel6.query.all()
    projects = Project.query.filter_by(archived=False).all()
    suppliers = Partner.query.filter_by(supplier=True).all()
    customers = Partner.query.filter_by(customer=True).all()
        
    if request.method == 'POST' and 'submitBtnImportData' in request.form:
        if 'fileInput' not in request.files:
            error_mesage = 'Niste izabrali XML fajl za učitavanje!'
        else:
            xml_file = request.files['fileInput']
            
            if xml_file.filename == '':
                error_mesage = 'Niste izabrali XML fajl za učitavanje!'
            elif not xml_file.filename.endswith('.xml'):
                error_mesage = 'Izabrani fajl nije XML fajl!'
            else:
                try:
                    # Parsiranje XML fajla
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    
                    # Izvlačenje podataka iz XML-a
                    zaglavlje = root.find('Zaglavlje')
                    zbirni = root.find('Zbirni')
                    stavke_xml = root.findall('Stavka')
                    
                    if zaglavlje is not None and zbirni is not None:
                        datum_izvoda_element = zaglavlje.find('DatumIzvoda').text if zaglavlje.find('DatumIzvoda') is not None else None
                        broj_izvoda_element = zbirni.find('BrojIzvoda').text if zbirni.find('BrojIzvoda') is not None else None
                        racun_izvoda_element = zbirni.find('RacunIzvoda').text if zbirni.find('RacunIzvoda') is not None else None
                        
                        # Dodatni podaci iz Zbirni elementa
                        pocetno_stanje_element = zbirni.find('PrethodniSaldo').text if zbirni.find('PrethodniSaldo') is not None else None
                        ukupno_duguje_element = zbirni.find('IznosDuguje').text if zbirni.find('IznosDuguje') is not None else None
                        ukupno_potrazuje_element = zbirni.find('IznosPotrazuje').text if zbirni.find('IznosPotrazuje') is not None else None
                        krajnje_stanje_element = zbirni.find('Saldo').text if zbirni.find('Saldo') is not None else None
                        
                        # proverava da li je racun_izvoda_element u bank_accounts
                        bank_account = BankAccount.query.filter_by(account_number=racun_izvoda_element).first()
                        
                        if bank_account is None:
                            error_mesage = 'Račun izvoda nije pronađen u bankovnim računima!'
                            flash(error_mesage, 'danger')
                            return redirect(url_for('statement.statement_list'))

                        
                        # Provera da li izvod sa istim brojem i datumom već postoji
                        try:
                            # Konverzija datuma iz stringa u Python date objekat
                            datum_izvoda = datetime.strptime(datum_izvoda_element, '%d.%m.%Y').date()
                            
                            # Provera da li izvod sa istim brojem i datumom već postoji
                            existing_statement = BankStatement.query.filter_by(
                                date=datum_izvoda,
                                statement_number=broj_izvoda_element
                            ).first()
                            
                            if existing_statement:
                                # Ako izvod već postoji, omogući pregled podataka ali onemogući učitavanje
                                flash(f'Izvod broj {broj_izvoda_element} od {datum_izvoda_element} već postoji u bazi podataka. Možete pregledati podatke, ali ne možete ponovo sačuvati stavke.', 'warning')
                                # Postavljamo flag da je izvod već sačuvan
                                izvod_vec_postoji = True
                            else:
                                izvod_vec_postoji = False
                        except Exception as e:
                            error_mesage = f'Greška prilikom provere postojećeg izvoda: {str(e)}.'
                            flash(error_mesage, 'danger')
                            return redirect(url_for('statement.statement_list'))
                        
                        # Pretvaranje stavki u listu rečnika za lakše korišćenje u šablonu
                        stavke = []
                        for stavka_xml in stavke_xml:
                            stavka = {}
                            for element in stavka_xml:
                                stavka[element.tag] = element.text
                            
                            # Dodatna obrada podataka
                            stavka['PozivNaBrojApp'] = stavka.get('PozivOdobrenja', '')
                            
                            # Određivanje da li je stavka izlazna ili ulazna
                            if stavka.get('RacunOdobrenja', '') == racun_izvoda_element:
                                stavka['Izlazna'] = False
                            elif stavka.get('RacunZaduzenja', '') == racun_izvoda_element:
                                stavka['Izlazna'] = True
                            else:
                                stavka['Izlazna'] = None
                            
                            # Dodajemo stavku u listu
                            stavke.append(stavka)
                            print(f'{stavka=}')
                        
                        broj_pojavljivanja = len(stavke)
                    else:
                        error_mesage = 'XML fajl nema očekivanu strukturu!'
                except Exception as e:
                    error_mesage = f'Greška prilikom obrade XML fajla: {str(e)}'
    
    # Ako je korisnik kliknuo na dugme za čuvanje podataka
    if request.method == 'POST' and 'submitBtnSaveData' in request.form:
        try:
            # Konverzija datuma iz stringa u Python date objekat
            datum_izvoda = datetime.strptime(request.form.get('payment_date'), '%d.%m.%Y').date()
            broj_izvoda = request.form.get('statement_number')
            
            # Provera da li izvod sa istim brojem i datumom već postoji
            existing_statement = BankStatement.query.filter_by(
                date=datum_izvoda,
                statement_number=broj_izvoda
            ).first()
            
            if existing_statement:
                flash(f'Izvod broj {broj_izvoda} od {request.form.get("payment_date")} već postoji u bazi podataka. Ne možete ponovo sačuvati stavke.', 'warning')
                return redirect(url_for('statement.statement_list'))
            
            # Kreiranje novog BankStatement objekta
            bank_statement = BankStatement(
                date=datum_izvoda,
                statement_number=broj_izvoda,
                initial_balance=float(request.form.get('initial_balance').replace(',', '.')),
                total_credit=float(request.form.get('total_credit').replace(',', '.')),
                total_debit=float(request.form.get('total_debit').replace(',', '.')),
                final_balance=float(request.form.get('final_balance').replace(',', '.'))
            )
            
            # Dodavanje u bazu podataka
            db.session.add(bank_statement)
            db.session.commit()
            
            # Kreiranje stavki izvoda
            if 'amount[]' in request.form:
                amounts = request.form.getlist('amount[]')
                payers = request.form.getlist('payer[]')
                recipients = request.form.getlist('recipient[]')
                is_debits = request.form.getlist('is_debit[]')
                descriptions = request.form.getlist('description[]')
                reference_numbers = request.form.getlist('reference_number[]')
                document_numbers = request.form.getlist('document_number[]')
                partner_ids = request.form.getlist('partner_id[]')
                account_level_6_numbers = request.form.getlist('account_level_6_number[]')
                project_ids = request.form.getlist('project_id[]')
                public_procurements = request.form.getlist('public_procurement[]')
                account_in_projects = request.form.getlist('account_in_project[]')
                
                # Provera da li su liste jednake dužine
                if len(amounts) != len(payers) or len(amounts) != len(recipients) or len(amounts) != len(is_debits):
                    flash('Greška: Neusklađen broj stavki u formi.', 'danger')
                    db.session.rollback()
                    return redirect(url_for('statement.statement_list'))
                
                # Kreiranje StatementItem objekata za svaku stavku
                for i in range(len(amounts)):
                    # Konverzija vrednosti
                    try:
                        amount = float(amounts[i].replace(',', '.'))
                        is_debit = True if is_debits[i] == 'true' else False
                        partner_id = int(partner_ids[i]) if partner_ids[i] else None
                        project_id = int(project_ids[i]) if i < len(project_ids) and project_ids[i] != '' else None
                        
                        # Provera da li je checkbox za account_in_project čekiran
                        # Vrednost checkboxa je indeks stavke (loop.index iz šablona)
                        account_in_project = False
                        if str(i+1) in account_in_projects:
                            account_in_project = True
                    except (ValueError, IndexError) as e:
                        flash(f'Greška pri konverziji podataka za stavku {i+1}: {str(e)}.', 'danger')
                        db.session.rollback()
                        return redirect(url_for('statement.statement_list'))
                    
                    # Kreiranje nove stavke izvoda
                    statement_item = StatementItem(
                        bank_statement_id=bank_statement.id,
                        payer=payers[i] if i < len(payers) else None,
                        recipient=recipients[i] if i < len(recipients) else None,
                        amount=amount,
                        is_debit=is_debit,
                        description=descriptions[i] if i < len(descriptions) else None,
                        reference_number=reference_numbers[i] if i < len(reference_numbers) else None,
                        document_number=document_numbers[i] if i < len(document_numbers) else None,
                        partner_id=partner_id,
                        account_level_6_number=account_level_6_numbers[i] if i < len(account_level_6_numbers) and account_level_6_numbers[i] != '' else None,
                        project_id=project_id,
                        public_procurement=public_procurements[i] if i < len(public_procurements) and public_procurements[i] != '' else None,
                        account_in_project=account_in_project
                    )
                    
                    db.session.add(statement_item)
                
                # Čuvanje svih stavki u bazi
                db.session.commit()
                flash(f'Izvod broj {request.form.get("statement_number")} od {request.form.get("payment_date")} sa {len(amounts)} stavki je uspešno sačuvan u bazi podataka.', 'success')
            else:
                flash('Nema stavki za čuvanje.', 'warning')
            
            # Redirekcija na stranicu za pregled izvoda
            return redirect(url_for('statement.statement_list'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Greška prilikom čuvanja izvoda: {str(e)}.', 'danger')
            return redirect(url_for('statement.statement_list'))
    
    if request.method == 'GET':
        bank_statements = BankStatement.query.all()
    
    return render_template('statement/statement_list.html', 
                            endpoint=endpoint,
                            legend='Učitavanje izvoda',
                            title='Učitavanje izvoda',
                            stavke=stavke,
                            datum_izvoda_element=datum_izvoda_element,
                            broj_izvoda_element=broj_izvoda_element,
                            racun_izvoda_element=racun_izvoda_element,
                            pocetno_stanje_element=pocetno_stanje_element,
                            ukupno_duguje_element=ukupno_duguje_element,
                            ukupno_potrazuje_element=ukupno_potrazuje_element,
                            krajnje_stanje_element=krajnje_stanje_element,
                            broj_pojavljivanja=broj_pojavljivanja,
                            suppliers=suppliers,
                            customers=customers,
                            partners=partners,
                            accounts_level_6=accounts_level_6,
                            projects=projects,
                            error_message=error_mesage,
                            bank_statements=bank_statements,
                            izvod_vec_postoji=izvod_vec_postoji)


@statement.route('/statement_details/<int:statement_id>', methods=['GET', 'POST'])
@login_required
def statement_details(statement_id):
    endpoint = 'statement.statement_details'
    statement = BankStatement.query.get_or_404(statement_id)
    
    # Učitavanje potrebnih podataka za select elemente
    partners = Partner.query.order_by(Partner.name).all()
    accounts_level_6 = AccountLevel6.query.order_by(AccountLevel6.number).all()
    projects = Project.query.filter_by(archived=False).order_by(Project.name).all()
    
    # Obrada POST zahteva za ažuriranje stavki
    if request.method == 'POST':
        try:
            # Iteracija kroz sve stavke izvoda i ažuriranje podataka
            for item in statement.statement_items:
                item_id = str(item.id)
                
                # Ažuriranje editabilnih polja
                if f'partner_id_{item_id}' in request.form:
                    partner_id = request.form.get(f'partner_id_{item_id}')
                    item.partner_id = int(partner_id) if partner_id else None
                
                if f'account_level_6_number_{item_id}' in request.form:
                    account_number = request.form.get(f'account_level_6_number_{item_id}')
                    item.account_level_6_number = account_number if account_number else None
                
                if f'project_id_{item_id}' in request.form:
                    project_id = request.form.get(f'project_id_{item_id}')
                    item.project_id = int(project_id) if project_id else None
                
                if f'public_procurement_{item_id}' in request.form:
                    item.public_procurement = request.form.get(f'public_procurement_{item_id}')
                
                # Checkbox za knjiženje u projekat
                item.account_in_project = f'account_in_project_{item_id}' in request.form
            
            db.session.commit()
            flash('Stavke izvoda su uspešno ažurirane.', 'success')
            return redirect(url_for('statement.statement_details', statement_id=statement_id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Došlo je do greške prilikom ažuriranja stavki: {str(e)}.', 'danger')
    
    return render_template('statement/statement_details.html',
                          endpoint=endpoint,
                          legend='Detalji izvoda',
                          title='Detalji izvoda',
                          statement=statement,
                          partners=partners,
                          accounts_level_6=accounts_level_6,
                          projects=projects)
