from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
import os
import xml.etree.ElementTree as ET
from datetime import datetime

payments = Blueprint('payments', __name__)

@payments.route('/posting_payment', methods=['GET', 'POST'])
@login_required
def posting_payment():
    endpoint = request.endpoint
    error_mesage = None
    stavke = None
    datum_izvoda_element = None
    broj_izvoda_element = None
    racun_izvoda_element = None
    iznos_potrazuje_element = None
    broj_pojavljivanja = None
    
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
                        iznos_potrazuje_element = zbirni.find('IznosPotrazuje').text if zbirni.find('IznosPotrazuje') is not None else None
                        
                        # Pretvaranje stavki u listu rečnika za lakše korišćenje u šablonu
                        stavke = []
                        for stavka_xml in stavke_xml:
                            stavka = {}
                            for element in stavka_xml:
                                stavka[element.tag] = element.text
                            
                            # Dodatna obrada podataka ako je potrebno
                            stavka['PozivNaBrojApp'] = stavka.get('PozivOdobrenja', '')
                            
                            # Dodajemo stavku u listu
                            stavke.append(stavka)
                        
                        broj_pojavljivanja = len(stavke)
                    else:
                        error_mesage = 'XML fajl nema očekivanu strukturu!'
                except Exception as e:
                    error_mesage = f'Greška prilikom obrade XML fajla: {str(e)}'
    
    # Ako je korisnik kliknuo na dugme za čuvanje podataka, ovde bismo implementirali logiku za čuvanje u bazi
    # To ćemo implementirati kasnije
    
    return render_template('payments/posting_payment.html', 
                            endpoint=endpoint,
                            legend='Učitavanje izvoda',
                            title='Učitavanje izvoda',
                            stavke=stavke,
                            datum_izvoda_element=datum_izvoda_element,
                            broj_izvoda_element=broj_izvoda_element,
                            racun_izvoda_element=racun_izvoda_element,
                            iznos_potrazuje_element=iznos_potrazuje_element,
                            broj_pojavljivanja=broj_pojavljivanja,
                            error_message=error_mesage)


@payments.route('/payment_list', methods=['GET', 'POST'])
@login_required
def payment_list():
    endpoint = request.endpoint
    return render_template('payments/payment_list.html', 
                            endpoint=endpoint,
                            legend='Pregled izvoda',
                            title='Izvodi')