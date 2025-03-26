from fpdf import FPDF
import os
import io
import logging
from datetime import datetime
from flask import make_response, flash, redirect, url_for, current_app
from arhivjugoslavije.models import Service, ArchiveSettings, UnitOfMeasure
from arhivjugoslavije import db


def generate_services_pdf(language='sr'):
    """
    Funkcija za generisanje PDF-a sa listom usluga koje nisu arhivirane.
    Parametar language određuje jezik na kojem će biti generisan PDF (sr - srpski, en - engleski).
    Vraća HTTP response sa PDF dokumentom.
    """
    try:
        # Dohvati sve usluge koje nisu arhivirane
        services = Service.query.filter_by(archived=False).all()
        
        if not services:
            flash('Nema aktivnih usluga za štampanje.', 'warning')
            return redirect(url_for('services.services_list'))
        
        # Dohvati podatke o arhivu
        archive_settings = ArchiveSettings.query.first()
        if not archive_settings:
            flash('Podaci o arhivu nisu podešeni. Molimo vas da prvo podesite podatke o arhivu.', 'danger')
            return redirect(url_for('services.services_list'))
        
        # Proveri da li postoje DejaVu fontovi - koristi apsolutnu putanju
        base_dir = current_app.root_path
        fonts_dir = os.path.join(base_dir, 'static', 'fonts')
        dejavu_regular = os.path.join(fonts_dir, 'DejaVuSansCondensed.ttf')
        dejavu_bold = os.path.join(fonts_dir, 'DejaVuSansCondensed-Bold.ttf')
        
        # Provera da li fontovi postoje
        if not os.path.exists(dejavu_regular):
            logging.error(f"Font nije pronađen na putanji: {dejavu_regular}")
            flash('Font DejaVuSansCondensed.ttf nije pronađen. Proverite da li je font dostupan u static/fonts direktorijumu.', 'danger')
            return redirect(url_for('services.services_list'))
        
        if not os.path.exists(dejavu_bold):
            logging.error(f"Font nije pronađen na putanji: {dejavu_bold}")
            flash('Font DejaVuSansCondensed-Bold.ttf nije pronađen. Proverite da li je font dostupan u static/fonts direktorijumu.', 'danger')
            return redirect(url_for('services.services_list'))
        
        # Kreiraj PDF sa podrškom za Unicode karaktere
        class ServicesPDF(FPDF):
            def __init__(self):
                super().__init__(orientation='P', unit='mm', format='A4')
                # Dodaj font koji podržava Unicode karaktere
                self.add_font('DejaVu', '', dejavu_regular, uni=True)
                self.add_font('DejaVu', 'B', dejavu_bold, uni=True)
                # Koristimo regular font za italic pošto nemamo pravi italic
                self.add_font('DejaVu', 'I', dejavu_regular, uni=True)
                self.set_font('DejaVu', '', 10)
            
            def header(self):
                # Logo iznad naziva arhiva
                logo_path = None
                if archive_settings.logo:
                    # Provera da li putanja već sadrži 'uploads/'
                    if 'uploads/' in archive_settings.logo:
                        logo_path = os.path.join(base_dir, 'static', archive_settings.logo)
                    else:
                        logo_path = os.path.join(base_dir, 'static', 'uploads', archive_settings.logo)
                
                logo_height = 0
                if logo_path and os.path.exists(logo_path):
                    # Postavlja logo na vrh stranice
                    self.image(logo_path, x=10, y=8, w=30)
                    logo_height = 20  # Procenjena visina loga
                
                # Naziv arhiva - leva strana (ispod loga)
                self.set_font('DejaVu', 'B', 12)
                self.set_xy(10, 8 + logo_height)
                self.cell(95, 6, archive_settings.name, 0, new_x="LMARGIN", new_y="NEXT", align="L")
                
                # Adresa arhiva - leva strana
                self.set_font('DejaVu', '', 10)
                self.set_x(10)
                self.cell(95, 5, f'{archive_settings.address}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                
                # Poštanski broj i grad - leva strana
                self.set_x(10)
                self.cell(95, 5, f'{archive_settings.zip_code} {archive_settings.city}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                
                # Kontakt podaci - desna strana
                self.set_font('DejaVu', '', 10)
                self.set_xy(105, 8)
                self.cell(95, 5, f'Tel: {archive_settings.phone_1}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                if archive_settings.phone_2:
                    self.set_xy(105, 13)
                    self.cell(95, 5, f'Tel: {archive_settings.phone_2}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                self.set_xy(105, 18)
                self.cell(95, 5, f'e-mail: {archive_settings.email}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                self.set_xy(105, 23)
                self.cell(95, 5, f'www: {archive_settings.web_site}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                
                # Naslov dokumenta
                self.ln(15)  # Prazan prostor između delova
                self.set_font('DejaVu', 'B', 14)
                
                # Postavi naslov u zavisnosti od jezika
                if language == 'en':
                    title = 'SERVICES PRICE LIST'
                else:  # default 'sr'
                    title = 'CENOVNIK USLUGA'
                
                self.cell(0, 10, title, 0, new_x="LMARGIN", new_y="NEXT", align="C")
                
                # Datum generisanja
                self.set_font('DejaVu', '', 10)
                current_date = datetime.now().strftime("%d.%m.%Y.")
                
                # Postavi datum u zavisnosti od jezika
                if language == 'en':
                    date_text = f'Date: {current_date}'
                else:  # default 'sr'
                    date_text = f'Datum: {current_date}'
                
                self.cell(0, 10, date_text, 0, new_x="LMARGIN", new_y="NEXT", align="C")
            
            def footer(self):
                # Broj stranice na dnu
                self.set_y(-15)  # 15mm od dna stranice
                self.set_font('DejaVu', 'I', 8)
                
                # Postavi tekst za stranicu u zavisnosti od jezika
                if language == 'en':
                    page_text = f'Page {self.page_no()}'
                else:  # default 'sr'
                    page_text = f'Strana {self.page_no()}'
                
                self.cell(0, 10, page_text, 0, new_x="LMARGIN", new_y="NEXT", align="C")
        
        # Kreiraj PDF dokument
        pdf = ServicesPDF()
        pdf.add_page()
        
        # Tabela sa uslugama
        pdf.ln(10)  # Pomeri se ispod headera
        pdf.set_font('DejaVu', 'B', 10)
        
        # Postavi zaglavlje tabele u zavisnosti od jezika
        if language == 'en':
            pdf.cell(10, 10, 'No.', 1, new_x="RIGHT", new_y="LAST", align="C")
            pdf.cell(80, 10, 'Service Description', 1, new_x="RIGHT", new_y="LAST", align="C")
            pdf.cell(25, 10, 'Unit', 1, new_x="RIGHT", new_y="LAST", align="C")
            pdf.cell(35, 10, 'Price (RSD)', 1, new_x="RIGHT", new_y="LAST", align="C")
            pdf.cell(35, 10, 'Price (EUR)', 1, new_x="LMARGIN", new_y="NEXT", align="C")
        else:  # default 'sr'
            pdf.cell(10, 10, 'Rb.', 1, new_x="RIGHT", new_y="LAST", align="C")
            pdf.cell(80, 10, 'Opis usluge', 1, new_x="RIGHT", new_y="LAST", align="C")
            pdf.cell(25, 10, 'Jed. mere', 1, new_x="RIGHT", new_y="LAST", align="C")
            pdf.cell(35, 10, 'Cena (RSD)', 1, new_x="RIGHT", new_y="LAST", align="C")
            pdf.cell(35, 10, 'Cena (EUR)', 1, new_x="LMARGIN", new_y="NEXT", align="C")
        
        # Stavke usluga
        pdf.set_font('DejaVu', '', 10)
        
        for i, service in enumerate(services, 1):
            # Dohvati jedinicu mere
            unit_of_measure = UnitOfMeasure.query.get(service.unit_of_measure_id)
            
            # Izračunaj cenu u EUR ako nije postavljena
            price_eur = service.price_eur
            if not price_eur and archive_settings.eur_rate and archive_settings.eur_rate > 0:
                price_eur = round(float(service.price_rsd) / archive_settings.eur_rate, 2)
            
            # Postavi vrednosti u zavisnosti od jezika
            if language == 'en':
                service_name = service.name_en if service.name_en else service.name_sr
                unit_name = unit_of_measure.name_en if unit_of_measure and unit_of_measure.name_en else (unit_of_measure.name_sr if unit_of_measure else '')
            else:  # default 'sr'
                service_name = service.name_sr
                unit_name = unit_of_measure.name_sr if unit_of_measure else ''
            
            # Dodaj simbol jedinice mere
            if unit_of_measure and unit_of_measure.symbol:
                unit_display = f"{unit_name} ({unit_of_measure.symbol})"
            else:
                unit_display = unit_name
            
            # Dodaj stavku u tabelu
            pdf.cell(10, 10, str(i), 1, new_x="RIGHT", new_y="LAST", align="C")
            pdf.cell(80, 10, service_name, 1, new_x="RIGHT", new_y="LAST", align="L")
            pdf.cell(25, 10, unit_display, 1, new_x="RIGHT", new_y="LAST", align="C")
            pdf.cell(35, 10, f"{service.price_rsd:.2f}", 1, new_x="RIGHT", new_y="LAST", align="R")
            pdf.cell(35, 10, f"{price_eur:.2f}" if price_eur else "-", 1, new_x="LMARGIN", new_y="NEXT", align="R")
        
        # Napomena o kursu evra
        pdf.ln(10)
        pdf.set_font('DejaVu', 'I', 9)
        
        # Postavi napomenu u zavisnosti od jezika
        if language == 'en':
            note_text = f"Note: EUR prices are calculated based on the exchange rate of {archive_settings.eur_rate:.2f} RSD for 1 EUR"
            if archive_settings.eur_rate_date:
                note_text += f" on {archive_settings.eur_rate_date.strftime('%d.%m.%Y.')}"
        else:  # default 'sr'
            note_text = f"Napomena: Cene u EUR su izračunate po kursu od {archive_settings.eur_rate:.2f} RSD za 1 EUR"
            if archive_settings.eur_rate_date:
                note_text += f" na dan {archive_settings.eur_rate_date.strftime('%d.%m.%Y.')}"
        
        pdf.cell(0, 10, note_text, 0, new_x="LMARGIN", new_y="NEXT", align="L")
        
        # Sačuvaj PDF u memoriju
        pdf_output = io.BytesIO()
        pdf.output(pdf_output)
        pdf_output.seek(0)
        
        # Kreiraj HTTP response
        response = make_response(pdf_output.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        
        # Postavi ime fajla u zavisnosti od jezika
        if language == 'en':
            filename = f"Services_Price_List_{datetime.now().strftime('%Y%m%d')}.pdf"
        else:  # default 'sr'
            filename = f"Cenovnik_Usluga_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
        
    except Exception as e:
        logging.error(f"Greška pri generisanju PDF-a sa uslugama: {str(e)}")
        flash(f'Došlo je do greške prilikom generisanja PDF-a: {str(e)}.', 'danger')
        return redirect(url_for('services.services_list'))