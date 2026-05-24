from fpdf import FPDF
import os
import io
import logging
from pathlib import Path
from datetime import datetime
from flask import make_response, redirect, url_for, flash, current_app
from arhivjugoslavije import db
from arhivjugoslavije.models import Partner, Invoice, StatementItem, BankStatement, ArchiveSettings


def get_partner_card_data(partner_id, start_date=None, end_date=None, is_customer=True):
    """
    Funkcija za dobijanje podataka za karticu partnera (kupca ili dobavljača).
    
    Args:
        partner_id (int): ID partnera
        start_date (date, optional): Početni datum perioda. Ako nije naveden, koristi se 1. januar tekuće godine.
        end_date (date, optional): Krajnji datum perioda. Ako nije naveden, koristi se današnji datum.
        is_customer (bool, optional): True ako je kupac, False ako je dobavljač. Default je True.
    
    Returns:
        dict: Rečnik sa podacima za karticu partnera
    """
    # Dobavljanje podataka o partneru
    partner = Partner.query.get_or_404(partner_id)
    
    # Provera da li je partner odgovarajućeg tipa
    if is_customer and not partner.customer:
        return {
            'error': 'not_customer',
            'message': 'Izabrani partner nije označen kao kupac.'
        }
    elif not is_customer and not partner.supplier:
        return {
            'error': 'not_supplier',
            'message': 'Izabrani partner nije označen kao dobavljač.'
        }
    
    # Postavljanje podrazumevanih datuma (1. januar tekuće godine do danas)
    today = datetime.now().date()
    default_start_date = datetime(today.year, 1, 1).date()
    
    # Korišćenje prosleđenih datuma ili podrazumevanih vrednosti
    if not start_date:
        start_date = default_start_date
    if not end_date:
        end_date = today
    
    # Filtriranje faktura po datumu prometa
    if is_customer:
        # Za kupca, prikazujemo izlazne fakture
        invoices = Invoice.query.filter_by(partner_id=partner_id, incoming=False)\
                                .filter(Invoice.status != 'nacrt')\
                                .filter(Invoice.service_date >= start_date)\
                                .filter(Invoice.service_date <= end_date)\
                                .order_by(Invoice.service_date.desc()).all()
        
        # Filtriranje stavki izvoda po datumu (uplate od kupaca)
        statement_items_query = StatementItem.query.filter_by(partner_id=partner_id, is_debit=False)\
                                                .join(BankStatement, StatementItem.bank_statement_id == BankStatement.id)\
                                                .filter(BankStatement.date >= start_date)\
                                                .filter(BankStatement.date <= end_date)
    else:
        # Za dobavljača, prikazujemo ulazne fakture
        invoices = Invoice.query.filter_by(partner_id=partner_id, incoming=True)\
                                .filter(Invoice.service_date >= start_date)\
                                .filter(Invoice.service_date <= end_date)\
                                .order_by(Invoice.service_date.desc()).all()
        
        # Filtriranje stavki izvoda po datumu (isplate dobavljačima)
        statement_items_query = StatementItem.query.filter_by(partner_id=partner_id, is_debit=True)\
                                                .join(BankStatement, StatementItem.bank_statement_id == BankStatement.id)\
                                                .filter(BankStatement.date >= start_date)\
                                                .filter(BankStatement.date <= end_date)
    
    statement_items = statement_items_query.all()
    
    # Kreiranje kombinovane liste podataka za knjigovodstvenu karticu.
    # Kupac (potraživanje/aktiva):  izlazna faktura -> duguje, uplata -> potražuje
    # Dobavljač (obaveza/pasiva):   ulazna faktura -> potražuje, isplata -> duguje
    combined_data = []

    # Dodavanje faktura u kombinovane podatke
    for invoice in invoices:
        combined_data.append({
            'date': invoice.service_date,
            'account': None,  # Fakture nemaju konto
            'document_type': 'invoice',
            'document_id': invoice.id,
            'document_number': invoice.invoice_number,
            'debit': invoice.total_amount if is_customer else None,
            'credit': None if is_customer else invoice.total_amount
        })

    # Dodavanje stavki izvoda u kombinovane podatke
    for item in statement_items:
        combined_data.append({
            'date': item.bank_statement.date,
            'account': item.account_level_6_number,
            'document_type': 'statement',
            'document_id': item.bank_statement.id,
            'document_number': f'{item.bank_statement.bank_account.account_number} ({item.bank_statement.date.year}/{item.bank_statement.statement_number})',
            'debit': None if is_customer else item.amount,
            'credit': item.amount if is_customer else None
        })

    # Sortiranje hronološki rastuće (najstarije prvo) radi ispravnog tekućeg salda
    combined_data.sort(key=lambda x: x['date'])

    # Računanje tekućeg (running) salda po redu.
    # Kupac:     saldo = duguje - potražuje (pozitivno = kupac nam duguje)
    # Dobavljač: saldo = potražuje - duguje (pozitivno = mi dugujemo dobavljaču)
    running_saldo = 0
    for entry in combined_data:
        debit = entry['debit'] or 0
        credit = entry['credit'] or 0
        running_saldo += (debit - credit) if is_customer else (credit - debit)
        entry['saldo'] = running_saldo

    # Računanje ukupnih vrednosti za duguje i potražuje
    total_debit = sum(entry['debit'] or 0 for entry in combined_data)
    total_credit = sum(entry['credit'] or 0 for entry in combined_data)
    saldo = running_saldo

    # Vraćanje rezultata
    return {
        'partner': partner,
        'invoices': invoices,
        'statement_items': statement_items,
        'combined_data': combined_data,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'saldo': saldo,
        'start_date': start_date,
        'end_date': end_date,
        'current_date': today
    }


def get_combined_partner_card_data(partner_id, start_date=None, end_date=None):
    """
    Objedinjena kartica partnera koji je istovremeno i kupac i dobavljač.

    Spaja promet kartice kupca i kartice dobavljača u jedan hronološki pregled sa
    jedinstvenim (neto) saldom Duguje - Potražuje, gde je:
        - Duguje:    izlazne fakture (prodaja) + isplate dobavljaču
        - Potražuje: ulazne fakture (nabavka) + uplate od kupca
    Neto saldo (Duguje - Potražuje) po računovodstvenoj konvenciji:
        - pozitivno = dugovni saldo  => partner nam ukupno duguje (potraživanje)
        - negativno = potražni saldo => mi ukupno dugujemo partneru (obaveza)

    Args:
        partner_id (int): ID partnera
        start_date (date, optional): Početni datum perioda
        end_date (date, optional): Krajnji datum perioda

    Returns:
        dict: Podaci za objedinjenu karticu (ili {'error': ...} ako partner nije i kupac i dobavljač)
    """
    partner = Partner.query.get_or_404(partner_id)

    if not (partner.customer and partner.supplier):
        return {
            'error': 'not_both',
            'message': 'Objedinjena kartica je dostupna samo za partnere koji su istovremeno i kupac i dobavljač.'
        }

    # Ponovno korišćenje postojeće logike za svaku stranu
    customer_data = get_partner_card_data(partner_id, start_date, end_date, is_customer=True)
    supplier_data = get_partner_card_data(partner_id, start_date, end_date, is_customer=False)

    # Prosleđivanje eventualne greške (teorijski se ne dešava jer su oba flega True)
    for d in (customer_data, supplier_data):
        if 'error' in d:
            return d

    # Spajanje prometa uz označavanje uloge (radi ispravnog linka i naziva dokumenta)
    combined_data = []
    for entry in customer_data['combined_data']:
        entry['role'] = 'customer'
        combined_data.append(entry)
    for entry in supplier_data['combined_data']:
        entry['role'] = 'supplier'
        combined_data.append(entry)

    # Hronološko sortiranje (najstarije prvo) radi ispravnog tekućeg salda
    combined_data.sort(key=lambda x: x['date'])

    # Jedinstveni (neto) tekući saldo: Duguje - Potražuje
    running_saldo = 0
    for entry in combined_data:
        debit = entry['debit'] or 0
        credit = entry['credit'] or 0
        running_saldo += debit - credit
        entry['saldo'] = running_saldo

    total_debit = sum(entry['debit'] or 0 for entry in combined_data)
    total_credit = sum(entry['credit'] or 0 for entry in combined_data)

    return {
        'partner': partner,
        'combined_data': combined_data,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'saldo_customer': customer_data['saldo'],   # potraživanje (izlazne - uplate)
        'saldo_supplier': supplier_data['saldo'],   # obaveza (ulazne - isplate)
        'neto_saldo': running_saldo,                 # potraživanje - obaveza
        'start_date': customer_data['start_date'],
        'end_date': customer_data['end_date'],
        'current_date': customer_data['current_date']
    }


def generate_partner_card_pdf(partner_id, start_date, end_date, combined_data, total_debit, total_credit, saldo, is_customer=True):
    """
    Funkcija za generisanje PDF kartice partnera (kupca ili dobavljača).
    
    Args:
        partner_id (int): ID partnera
        start_date (date): Početni datum perioda
        end_date (date): Krajnji datum perioda
        combined_data (list): Lista kombinovanih podataka (fakture i stavke izvoda)
        total_debit (Decimal): Ukupan iznos na dugovnoj strani
        total_credit (Decimal): Ukupan iznos na potražuju strani
        saldo (Decimal): Završni saldo kartice (pozitivno = duguje nam kupac / dugujemo dobavljaču)
        is_customer (bool): True ako je kupac, False ako je dobavljač
    
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
        col_widths = [22, 16, 56, 32, 32, 32]  # širine kolona u mm
        pdf.cell(col_widths[0], 10, 'Datum', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(col_widths[1], 10, 'Konto', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(col_widths[2], 10, 'Dokument', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(col_widths[3], 10, 'Duguje', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(col_widths[4], 10, 'Potražuje', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(col_widths[5], 10, 'Saldo', 1, new_x="LMARGIN", new_y="NEXT", align="C")

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

            # Potražuje
            credit_text = f"{item['credit']:.2f} RSD" if item['credit'] else '-'
            pdf.cell(col_widths[4], 8, credit_text, 1, new_x="RIGHT", new_y="LAST", align="R")

            # Saldo (tekući)
            pdf.cell(col_widths[5], 8, f"{item['saldo']:.2f}", 1, new_x="LMARGIN", new_y="NEXT", align="R")

        # Ukupno
        pdf.set_font('DejaVu', 'B', 10)
        pdf.cell(col_widths[0] + col_widths[1] + col_widths[2], 10, 'UKUPNO:', 1, new_x="RIGHT", new_y="LAST", align="R")
        pdf.cell(col_widths[3], 10, f"{total_debit:.2f} RSD", 1, new_x="RIGHT", new_y="LAST", align="R")
        pdf.cell(col_widths[4], 10, f"{total_credit:.2f} RSD", 1, new_x="RIGHT", new_y="LAST", align="R")
        pdf.cell(col_widths[5], 10, f"{saldo:.2f}", 1, new_x="LMARGIN", new_y="NEXT", align="R")

        # Završni saldo
        pdf.cell(col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3], 10, 'SALDO:', 1, new_x="RIGHT", new_y="LAST", align="R")
        pdf.cell(col_widths[4] + col_widths[5], 10, f"{saldo:.2f} RSD", 1, new_x="LMARGIN", new_y="NEXT", align="R")
        
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


def generate_combined_partner_card_pdf(partner_id, start_date, end_date, combined_data,
                                       total_debit, total_credit,
                                       saldo_customer, saldo_supplier, neto_saldo):
    """
    Generisanje PDF objedinjene kartice partnera (kupac + dobavljač) sa neto saldom.

    Args:
        partner_id (int): ID partnera
        start_date (date): Početni datum perioda
        end_date (date): Krajnji datum perioda
        combined_data (list): Spojeni promet (svaka stavka ima 'role': 'customer'/'supplier')
        total_debit (Decimal): Ukupno Duguje (izlazne fakture + isplate)
        total_credit (Decimal): Ukupno Potražuje (ulazne fakture + uplate)
        saldo_customer (Decimal): Saldo kao kupac (potraživanje)
        saldo_supplier (Decimal): Saldo kao dobavljač (obaveza)
        neto_saldo (Decimal): Neto saldo (potraživanje - obaveza)

    Returns:
        Response: HTTP response sa PDF dokumentom
    """
    try:
        partner = Partner.query.get_or_404(partner_id)

        archive_settings = ArchiveSettings.query.first()
        if not archive_settings:
            flash('Nisu definisana podešavanja arhiva. Molimo kontaktirajte administratora.', 'danger')
            return redirect(url_for('partner.partner_card', partner_id=partner_id))

        base_dir = Path(current_app.root_path)
        fonts_dir = os.path.join(base_dir, 'static', 'fonts')

        dejavu_regular = os.path.join(fonts_dir, 'DejaVuSansCondensed.ttf')
        dejavu_bold = os.path.join(fonts_dir, 'DejaVuSansCondensed-Bold.ttf')

        if not os.path.exists(dejavu_regular) or not os.path.exists(dejavu_bold):
            logging.error(f"Font nije pronađen u: {fonts_dir}")
            flash('DejaVu fontovi nisu pronađeni u static/fonts direktorijumu.', 'danger')
            return redirect(url_for('partner.partner_card', partner_id=partner_id))

        class CombinedPartnerCardPDF(FPDF):
            def __init__(self):
                super().__init__()
                self.add_font('DejaVu', '', os.path.join(fonts_dir, 'DejaVuSansCondensed.ttf'), uni=True)
                self.add_font('DejaVu', 'B', os.path.join(fonts_dir, 'DejaVuSansCondensed-Bold.ttf'), uni=True)

            def header(self):
                logo_path = None
                if archive_settings.logo:
                    if 'uploads/' in archive_settings.logo:
                        logo_path = os.path.join(base_dir, 'static', archive_settings.logo)
                    else:
                        logo_path = os.path.join(base_dir, 'static', 'uploads', archive_settings.logo)

                if logo_path and os.path.exists(logo_path):
                    self.image(logo_path, x=10, y=10, w=30)

                self.set_font('DejaVu', 'B', 14)
                self.set_xy(45, 10)
                self.cell(100, 8, archive_settings.name, 0, new_x="RIGHT", new_y="LAST", align="L")

                self.set_font('DejaVu', '', 10)
                self.set_xy(45, 18)
                self.cell(100, 5, f"{archive_settings.address}, {archive_settings.zip_code} {archive_settings.city}", 0, new_x="LMARGIN", new_y="NEXT", align="L")
                self.set_xy(45, 23)
                self.cell(100, 5, f"PIB: {archive_settings.pib}, MB: {archive_settings.mb}", 0, new_x="LMARGIN", new_y="NEXT", align="L")

                self.ln(15)
                self.set_font('DejaVu', 'B', 16)
                self.cell(0, 10, "OBJEDINJENA KARTICA PARTNERA", 0, new_x="LMARGIN", new_y="NEXT", align="C")

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

                self.ln(5)
                self.set_font('DejaVu', 'B', 11)
                self.cell(0, 8, f"Period: {start_date.strftime('%d.%m.%Y.')} - {end_date.strftime('%d.%m.%Y.')}", 0, new_x="LMARGIN", new_y="NEXT", align="C")

                self.set_font('DejaVu', '', 10)
                today = datetime.now().strftime("%d.%m.%Y.")
                self.cell(0, 6, f"Datum generisanja: {today}", 0, new_x="LMARGIN", new_y="NEXT", align="C")

                self.ln(5)
                self.line(10, self.get_y(), 200, self.get_y())
                self.ln(5)

            def footer(self):
                self.set_y(-15)
                self.set_font('DejaVu', '', 8)
                self.cell(0, 10, f'Strana {self.page_no()}', 0, new_x="LMARGIN", new_y="NEXT", align="C")

        pdf = CombinedPartnerCardPDF()
        pdf.add_page()

        # Zaglavlje tabele
        pdf.set_font('DejaVu', 'B', 10)
        col_widths = [22, 16, 56, 32, 32, 32]
        pdf.cell(col_widths[0], 10, 'Datum', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(col_widths[1], 10, 'Konto', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(col_widths[2], 10, 'Dokument', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(col_widths[3], 10, 'Duguje', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(col_widths[4], 10, 'Potražuje', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(col_widths[5], 10, 'Saldo', 1, new_x="LMARGIN", new_y="NEXT", align="C")

        # Podaci u tabeli
        pdf.set_font('DejaVu', '', 9)
        for item in combined_data:
            pdf.cell(col_widths[0], 8, item['date'].strftime('%d.%m.%Y.'), 1, new_x="RIGHT", new_y="LAST", align="C")

            konto_text = item['account'] if item['account'] else '-'
            pdf.cell(col_widths[1], 8, konto_text, 1, new_x="RIGHT", new_y="LAST", align="C")

            role = item.get('role')
            if item['document_type'] == 'invoice':
                doc_text = (f"Izlazna faktura: {item['document_number']}" if role == 'customer'
                            else f"Ulazna faktura: {item['document_number']}")
            else:
                doc_text = (f"Uplata: {item['document_number']}" if role == 'customer'
                            else f"Isplata: {item['document_number']}")
            pdf.cell(col_widths[2], 8, doc_text, 1, new_x="RIGHT", new_y="LAST", align="L")

            debit_text = f"{item['debit']:.2f} RSD" if item['debit'] else '-'
            pdf.cell(col_widths[3], 8, debit_text, 1, new_x="RIGHT", new_y="LAST", align="R")

            credit_text = f"{item['credit']:.2f} RSD" if item['credit'] else '-'
            pdf.cell(col_widths[4], 8, credit_text, 1, new_x="RIGHT", new_y="LAST", align="R")

            pdf.cell(col_widths[5], 8, f"{item['saldo']:.2f}", 1, new_x="LMARGIN", new_y="NEXT", align="R")

        # Ukupno
        pdf.set_font('DejaVu', 'B', 10)
        pdf.cell(col_widths[0] + col_widths[1] + col_widths[2], 10, 'UKUPNO:', 1, new_x="RIGHT", new_y="LAST", align="R")
        pdf.cell(col_widths[3], 10, f"{total_debit:.2f} RSD", 1, new_x="RIGHT", new_y="LAST", align="R")
        pdf.cell(col_widths[4], 10, f"{total_credit:.2f} RSD", 1, new_x="RIGHT", new_y="LAST", align="R")
        pdf.cell(col_widths[5], 10, f"{neto_saldo:.2f}", 1, new_x="LMARGIN", new_y="NEXT", align="R")

        # Sažetak salda
        full_width = sum(col_widths)
        pdf.ln(4)
        pdf.set_font('DejaVu', '', 10)
        pdf.cell(full_width, 8, f"Saldo kao kupac (potraživanje): {saldo_customer:.2f} RSD", 1, new_x="LMARGIN", new_y="NEXT", align="R")
        pdf.cell(full_width, 8, f"Saldo kao dobavljač (obaveza): {saldo_supplier:.2f} RSD", 1, new_x="LMARGIN", new_y="NEXT", align="R")

        if neto_saldo > 0:
            neto_opis = "partner duguje arhivu (dugovni saldo)"
        elif neto_saldo < 0:
            neto_opis = "arhiv duguje partneru (potražni saldo)"
        else:
            neto_opis = "poravnato"
        pdf.set_font('DejaVu', 'B', 11)
        pdf.cell(full_width, 9, f"NETO (pravo stanje): {neto_saldo:.2f} RSD  —  {neto_opis}", 1, new_x="LMARGIN", new_y="NEXT", align="R")

        pdf_bytes = io.BytesIO()
        pdf.output(pdf_bytes)
        pdf_bytes.seek(0)

        response = make_response(pdf_bytes.getvalue())
        response.headers.set('Content-Disposition', f'inline; filename=objedinjena_kartica_{partner.id}.pdf')
        response.headers.set('Content-Type', 'application/pdf')
        return response

    except Exception as e:
        error_msg = f"Greška prilikom generisanja PDF-a: {str(e)}"
        logging.error(error_msg)
        flash(f'Došlo je do greške prilikom generisanja PDF-a: {str(e)}.', 'danger')
        return redirect(url_for('partner.partner_card', partner_id=partner_id))