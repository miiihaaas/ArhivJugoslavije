from fpdf import FPDF
import os
import io
import logging
from pathlib import Path
from datetime import datetime
from flask import make_response, redirect, url_for, flash, current_app
from arhivjugoslavije import db
from arhivjugoslavije.models import Partner, Invoice, StatementItem, BankStatement, ArchiveSettings


def generate_partner_card_pdf(partner_id, start_date, end_date, combined_data, total_debit, total_credit, is_customer=True):
    """
    Funkcija za generisanje PDF kartice partnera (kupca ili dobavljau010da).
    
    Args:
        partner_id (int): ID partnera
        start_date (date): Pou010detni datum perioda
        end_date (date): Krajnji datum perioda
        combined_data (list): Lista kombinovanih podataka (fakture i stavke izvoda)
        total_debit (Decimal): Ukupan iznos na dugovnoj strani
        total_credit (Decimal): Ukupan iznos na potrau017enoj strani
        is_customer (bool): True ako je kupac, False ako je dobavljau010d
    
    Returns:
        Response: HTTP response sa PDF dokumentom
    """
    try:
        # Dobavljanje podataka o partneru
        partner = Partner.query.get_or_404(partner_id)
        
        # Dobavljanje podataka o arhivu
        archive_settings = ArchiveSettings.query.first()
        if not archive_settings:
            flash('Nisu definisana podeu0161avanja arhiva. Molimo kontaktirajte administratora.', 'danger')
            if is_customer:
                return redirect(url_for('partner.customer_card', partner_id=partner_id))
            else:
                return redirect(url_for('partner.supplier_card', partner_id=partner_id))
        
        # Putanja do direktorijuma sa fontovima
        base_dir = Path(current_app.root_path)
        fonts_dir = os.path.join(base_dir, 'static', 'fonts')
        
        # Provera da li fontovi postoje
        dejavu_regular = os.path.join(fonts_dir, 'DejaVuSansCondensed.ttf')
        dejavu_bold = os.path.join(fonts_dir, 'DejaVuSansCondensed-Bold.ttf')
        
        # Provera da li fontovi postoje
        if not os.path.exists(dejavu_regular):
            error_msg = f"Font nije pronađen na putanji: {dejavu_regular}"
            logging.error(error_msg)
            flash('Font DejaVuSansCondensed.ttf nije pronađen. Proverite da li je font dostupan u static/fonts direktorijumu.', 'danger')
            if is_customer:
                return redirect(url_for('partner.customer_card', partner_id=partner_id))
            else:
                return redirect(url_for('partner.supplier_card', partner_id=partner_id))
        
        if not os.path.exists(dejavu_bold):
            error_msg = f"Font nije pronađen na putanji: {dejavu_bold}"
            logging.error(error_msg)
            flash('Font DejaVuSansCondensed-Bold.ttf nije pronađen. Proverite da li je font dostupan u static/fonts direktorijumu.', 'danger')
            if is_customer:
                return redirect(url_for('partner.customer_card', partner_id=partner_id))
            else:
                return redirect(url_for('partner.supplier_card', partner_id=partner_id))
        
        # Definisanje klase za PDF dokument
        class PartnerCardPDF(FPDF):
            def __init__(self):
                super().__init__()
                # Dodavanje fonta koji podržava naša slova
                self.add_font('DejaVu', '', os.path.join(fonts_dir, 'DejaVuSansCondensed.ttf'), uni=True)
                self.add_font('DejaVu', 'B', os.path.join(fonts_dir, 'DejaVuSansCondensed-Bold.ttf'), uni=True)
            
            def header(self):
                # Logo arhiva
                logo_path = None
                if archive_settings.logo:
                    # Provera da li putanja veu0107 sadrau017ei 'uploads/'
                    if 'uploads/' in archive_settings.logo:
                        logo_path = os.path.join(base_dir, 'static', archive_settings.logo)
                    else:
                        logo_path = os.path.join(base_dir, 'static', 'uploads', archive_settings.logo)
                
                if logo_path and os.path.exists(logo_path):
                    self.image(logo_path, x=10, y=10, w=30)
                
                # Naziv arhiva
                self.set_font('DejaVu', 'B', 14)
                self.set_xy(45, 10)
                self.cell(100, 8, archive_settings.name, 0, new_x="RIGHT", new_y="LAST", align="L")
                
                # Adresa i kontakt podaci arhiva
                self.set_font('DejaVu', '', 10)
                self.set_xy(45, 18)
                self.cell(100, 5, f"{archive_settings.address}, {archive_settings.zip_code} {archive_settings.city}", 0, new_x="LMARGIN", new_y="NEXT", align="L")
                self.set_xy(45, 23)
                self.cell(100, 5, f"PIB: {archive_settings.pib}, MB: {archive_settings.mb}", 0, new_x="LMARGIN", new_y="NEXT", align="L")
                
                # Naslov dokumenta
                self.ln(15)
                self.set_font('DejaVu', 'B', 16)
                if is_customer:
                    self.cell(0, 10, f"KARTICA KUPCA", 0, new_x="LMARGIN", new_y="NEXT", align="C")
                else:
                    self.cell(0, 10, f"KARTICA DOBAVLJAČA", 0, new_x="LMARGIN", new_y="NEXT", align="C")
                
                # Podaci o partneru
                self.ln(5)
                self.set_font('DejaVu', 'B', 12)
                self.cell(0, 8, partner.name, 0, new_x="LMARGIN", new_y="NEXT", align="C")
                
                self.set_font('DejaVu', '', 10)
                address_line = ""
                if partner.address:
                    address_line += partner.address
                if partner.city:
                    if address_line:
                        address_line += ", "
                    address_line += partner.city
                if partner.country and partner.country != "Srbija":
                    if address_line:
                        address_line += ", "
                    address_line += partner.country
                
                if address_line:
                    self.cell(0, 6, address_line, 0, new_x="LMARGIN", new_y="NEXT", align="C")
                
                id_line = ""
                if partner.pib:
                    id_line += f"PIB: {partner.pib}"
                if partner.mb:
                    if id_line:
                        id_line += ", "
                    id_line += f"MB: {partner.mb}"
                
                if id_line:
                    self.cell(0, 6, id_line, 0, new_x="LMARGIN", new_y="NEXT", align="C")
                
                # Period
                self.ln(5)
                self.set_font('DejaVu', 'B', 11)
                self.cell(0, 8, f"Period: {start_date.strftime('%d.%m.%Y.')} - {end_date.strftime('%d.%m.%Y.')}", 0, new_x="LMARGIN", new_y="NEXT", align="C")
                
                # Datum generisanja
                self.set_font('DejaVu', '', 10)
                today = datetime.now().strftime("%d.%m.%Y.")
                self.cell(0, 6, f"Datum generisanja: {today}", 0, new_x="LMARGIN", new_y="NEXT", align="C")
                
                # Linija ispod headera
                self.ln(5)
                self.line(10, self.get_y(), 200, self.get_y())
                self.ln(5)
            
            def footer(self):
                # Postavi Y poziciju za footer (15mm od dna stranice)
                self.set_y(-15)
                
                # Broj stranice
                self.set_font('DejaVu', '', 8)  # Koristimo regular font umesto italic
                self.cell(0, 10, f'Strana {self.page_no()}', 0, new_x="LMARGIN", new_y="NEXT", align="C")
        
        # Kreiraj PDF dokument
        pdf = PartnerCardPDF()
        pdf.add_page()
        
        # Tabela sa podacima
        pdf.set_font('DejaVu', 'B', 10)
        
        # Zaglavlje tabele
        col_widths = [25, 20, 70, 35, 35]  # u0160irine kolona u mm
        pdf.cell(col_widths[0], 10, 'Datum', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(col_widths[1], 10, 'Konto', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(col_widths[2], 10, 'Dokument', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(col_widths[3], 10, 'Duguje', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(col_widths[4], 10, 'Potrau017euje', 1, new_x="LMARGIN", new_y="NEXT", align="C")
        
        # Podaci u tabeli
        pdf.set_font('DejaVu', '', 9)
        for item in combined_data:
            # Datum
            pdf.cell(col_widths[0], 8, item['date'].strftime('%d.%m.%Y.'), 1, new_x="RIGHT", new_y="LAST", align="C")
            
            # Konto
            konto_text = item['account'] if item['account'] else '-'
            pdf.cell(col_widths[1], 8, konto_text, 1, new_x="RIGHT", new_y="LAST", align="C")
            
            # Dokument
            if item['document_type'] == 'invoice':
                if is_customer:
                    doc_text = f"Izlazna faktura: {item['document_number']}"
                else:
                    doc_text = f"Ulazna faktura: {item['document_number']}"
            else:
                doc_text = f"Izvod: {item['document_number']}"
            
            pdf.cell(col_widths[2], 8, doc_text, 1, new_x="RIGHT", new_y="LAST", align="L")
            
            # Duguje
            debit_text = f"{item['debit']:.2f} RSD" if item['debit'] else '-'
            pdf.cell(col_widths[3], 8, debit_text, 1, new_x="RIGHT", new_y="LAST", align="R")
            
            # Potrau017euje
            credit_text = f"{item['credit']:.2f} RSD" if item['credit'] else '-'
            pdf.cell(col_widths[4], 8, credit_text, 1, new_x="LMARGIN", new_y="NEXT", align="R")
        
        # Ukupno
        pdf.set_font('DejaVu', 'B', 10)
        pdf.cell(col_widths[0] + col_widths[1] + col_widths[2], 10, 'UKUPNO:', 1, new_x="RIGHT", new_y="LAST", align="R")
        pdf.cell(col_widths[3], 10, f"{total_debit:.2f} RSD", 1, new_x="RIGHT", new_y="LAST", align="R")
        pdf.cell(col_widths[4], 10, f"{total_credit:.2f} RSD", 1, new_x="LMARGIN", new_y="NEXT", align="R")
        
        # Saldo
        saldo = total_debit - total_credit
        pdf.cell(col_widths[0] + col_widths[1] + col_widths[2], 10, 'SALDO:', 1, new_x="RIGHT", new_y="LAST", align="R")
        pdf.cell(col_widths[3] + col_widths[4], 10, f"{saldo:.2f} RSD", 1, new_x="LMARGIN", new_y="NEXT", align="R")
        
        # Generisanje PDF-a
        pdf_bytes = io.BytesIO()
        pdf.output(pdf_bytes)
        pdf_bytes.seek(0)
        
        # Kreiranje HTTP response-a
        response = make_response(pdf_bytes.getvalue())
        partner_type = "kupca" if is_customer else "dobavljaca"
        response.headers.set('Content-Disposition', f'inline; filename=kartica_{partner_type}_{partner.id}.pdf')
        response.headers.set('Content-Type', 'application/pdf')
        
        return response
        
    except Exception as e:
        error_msg = f"Greška prilikom generisanja PDF-a: {str(e)}"
        logging.error(error_msg)
        flash(f'Došlo je do greške prilikom generisanja PDF-a: {str(e)}.', 'danger')
        if is_customer:
            return redirect(url_for('partner.customer_card', partner_id=partner_id))
        else:
            return redirect(url_for('partner.supplier_card', partner_id=partner_id))