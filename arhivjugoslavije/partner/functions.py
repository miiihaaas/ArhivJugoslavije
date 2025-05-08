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
    
    # Kreiranje kombinovane liste podataka za tabelu
    combined_data = []
    
    # Dodavanje faktura u kombinovane podatke
    for invoice in invoices:
        if is_customer:
            # Izlazne fakture idu na potražuje
            combined_data.append({
                'date': invoice.service_date,
                'account': None,  # Fakture nemaju konto
                'document_type': 'invoice',
                'document_id': invoice.id,
                'document_number': invoice.invoice_number,
                'debit': None,
                'credit': invoice.total_amount
            })
        else:
            # Ulazne fakture idu na duguje
            combined_data.append({
                'date': invoice.service_date,
                'account': None,  # Fakture nemaju konto
                'document_type': 'invoice',
                'document_id': invoice.id,
                'document_number': invoice.invoice_number,
                'debit': invoice.total_amount,
                'credit': None
            })
    
    # Dodavanje stavki izvoda u kombinovane podatke
    for item in statement_items:
        if is_customer:
            # Uplate idu na duguje
            combined_data.append({
                'date': item.bank_statement.date,
                'account': item.account_level_6_number,
                'document_type': 'statement',
                'document_id': item.bank_statement.id,
                'document_number': f'{item.bank_statement.bank_account.account_number} ({item.bank_statement.date.year}/{item.bank_statement.statement_number})',
                'debit': item.amount,
                'credit': None
            })
        else:
            # Isplate idu na potražuje
            combined_data.append({
                'date': item.bank_statement.date,
                'account': item.account_level_6_number,
                'document_type': 'statement',
                'document_id': item.bank_statement.id,
                'document_number': f'{item.bank_statement.bank_account.account_number} ({item.bank_statement.date.year}/{item.bank_statement.statement_number})',
                'debit': None,
                'credit': item.amount
            })
    
    # Sortiranje po datumu, od najnovijeg ka najstarijem
    combined_data.sort(key=lambda x: x['date'], reverse=True)
    
    # Računanje ukupnih vrednosti za duguje i potražuje
    total_debit = sum(item['debit'] or 0 for item in combined_data)
    total_credit = sum(item['credit'] or 0 for item in combined_data)
    
    # Vraćanje rezultata
    return {
        'partner': partner,
        'invoices': invoices,
        'statement_items': statement_items,
        'combined_data': combined_data,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'start_date': start_date,
        'end_date': end_date,
        'current_date': today
    }


def generate_partner_card_pdf(partner_id, start_date, end_date, combined_data, total_debit, total_credit, is_customer=True):
    """
    Funkcija za generisanje PDF kartice partnera (kupca ili dobavljača).
    
    Args:
        partner_id (int): ID partnera
        start_date (date): Početni datum perioda
        end_date (date): Krajnji datum perioda
        combined_data (list): Lista kombinovanih podataka (fakture i stavke izvoda)
        total_debit (Decimal): Ukupan iznos na dugovnoj strani
        total_credit (Decimal): Ukupan iznos na potražuju strani
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