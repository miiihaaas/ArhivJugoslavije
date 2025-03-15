from fpdf import FPDF
import os
from pathlib import Path
from flask import make_response, flash, redirect, url_for
from arhivjugoslavije.models import Invoice, Partner, InvoiceItem, Service, ArchiveSettings, UnitOfMeasure
import io


def generate_invoice_pdf(invoice_id):
    """
    Funkcija za generisanje PDF fakture na osnovu ID-a fakture.
    Vraća HTTP response sa PDF dokumentom ili None u slučaju greške.
    """
    try:
        # Dohvati fakturu
        invoice = Invoice.query.get_or_404(invoice_id)
        
        # Proveri da li je izlazna faktura
        if invoice.incoming:
            flash('Generisanje PDF-a je dostupno samo za izlazne fakture.', 'warning')
            return redirect(url_for('invoices.invoice_list'))
        
        # Dohvati podatke o arhivu
        archive_settings = ArchiveSettings.query.first()
        if not archive_settings:
            flash('Podaci o arhivu nisu podešeni. Molimo vas da prvo podesite podatke o arhivu.', 'danger')
            return redirect(url_for('invoices.edit_customer_invoice', invoice_id=invoice_id))
        
        # Dohvati partnera (kupca)
        partner = Partner.query.get(invoice.partner_id)
        if not partner:
            flash('Podaci o partneru nisu pronađeni.', 'danger')
            return redirect(url_for('invoices.edit_customer_invoice', invoice_id=invoice_id))
        
        # Dohvati stavke fakture
        invoice_items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
        if not invoice_items:
            flash('Faktura nema stavke. Molimo vas da dodate bar jednu stavku.', 'warning')
            return redirect(url_for('invoices.edit_customer_invoice', invoice_id=invoice_id))
        
        # Proveri da li postoje DejaVu fontovi
        fonts_dir = os.path.join('arhivjugoslavije', 'static', 'fonts')
        dejavu_regular = os.path.join(fonts_dir, 'DejaVuSansCondensed.ttf')
        dejavu_bold = os.path.join(fonts_dir, 'DejaVuSansCondensed-Bold.ttf')
        
        # Kreiraj PDF sa podrškom za Unicode karaktere
        class InvoicePDF(FPDF):
            def __init__(self):
                super().__init__(orientation='P', unit='mm', format='A4')
                # Dodaj font koji podržava Unicode karaktere
                self.add_font('DejaVu', '', dejavu_regular, uni=True)
                self.add_font('DejaVu', 'B', dejavu_bold, uni=True)
                # Koristimo regular font za italic pošto nemamo pravi italic
                self.add_font('DejaVu', 'I', dejavu_regular, uni=True)
                self.set_font('DejaVu', '', 10)
            
            def header(self):
                # Logo i podaci o arhivu na levoj strani
                if archive_settings.logo and os.path.exists(os.path.join('arhivjugoslavije', 'static', 'uploads', archive_settings.logo)):
                    self.image(os.path.join('arhivjugoslavije', 'static', 'uploads', archive_settings.logo), 10, 8, 30)
                
                # Podaci o arhivu - leva strana
                self.set_font('DejaVu', 'B', 12)
                self.cell(95, 10, archive_settings.name, 0, 0, 'L')
                
                # Podaci o partneru (kupcu) - desna strana
                self.set_font('DejaVu', 'B', 10)
                self.cell(95, 10, 'PRIMALAC:', 0, 1, 'R')
                
                # Nastavi sa podacima o arhivu - leva strana
                self.set_font('DejaVu', '', 10)
                self.cell(95, 6, f'Adresa: {archive_settings.address}', 0, 0, 'L')
                
                # Nastavi sa podacima o partneru - desna strana
                self.set_font('DejaVu', '', 10)
                self.cell(95, 6, partner.name, 0, 1, 'R')
                
                # PIB Arhiva - leva strana
                self.cell(95, 6, f'PIB: {archive_settings.pib}', 0, 0, 'L')
                
                # Adresa partnera - desna strana
                if partner.address:
                    self.cell(95, 6, partner.address, 0, 1, 'R')
                else:
                    self.ln(6)
                
                # MB Arhiva - leva strana
                self.cell(95, 6, f'MB: {archive_settings.mb}', 0, 0, 'L')
                
                # Grad partnera - desna strana
                if partner.city:
                    self.cell(95, 6, partner.city, 0, 1, 'R')
                else:
                    self.ln(6)
                
                # Prazan red - leva strana
                self.cell(95, 6, '', 0, 0, 'L')
                
                # PIB partnera - desna strana
                if partner.pib:
                    self.cell(95, 6, f'PIB: {partner.pib}', 0, 1, 'R')
                else:
                    self.ln(6)
                
                # Naslov fakture
                self.ln(10)
                self.set_font('DejaVu', 'B', 14)
                self.cell(0, 10, f'Račun br.: {invoice.invoice_number}', 0, 1, 'C')
                
                # Datumi
                self.ln(5)
                self.set_font('DejaVu', '', 10)
                self.cell(0, 6, f'Mesto i datum izdavanja: {archive_settings.city}, {invoice.issue_date.strftime("%d.%m.%Y.")}', 0, 1, 'L')
                self.cell(0, 6, f'Datum prometa: {invoice.service_date.strftime("%d.%m.%Y.")}', 0, 1, 'L')
                if invoice.payment_due_date:
                    self.cell(0, 6, f'Rok plaćanja: {invoice.payment_due_date.strftime("%d.%m.%Y.")}', 0, 1, 'L')
            
            def footer(self):
                self.set_y(-15)
                self.set_font('DejaVu', 'I', 8)
                self.cell(0, 10, f'Strana {self.page_no()}', 0, 0, 'C')
        
        # Kreiraj PDF dokument
        pdf = InvoicePDF()
        pdf.add_page()
        
        # Tabela sa stavkama fakture
        pdf.ln(70)  # Pomeri se ispod headera
        pdf.set_font('DejaVu', 'B', 10)
        pdf.cell(10, 10, 'Rb.', 1, 0, 'C')
        pdf.cell(80, 10, 'Opis', 1, 0, 'C')
        pdf.cell(25, 10, 'Jed. mere', 1, 0, 'C')
        pdf.cell(20, 10, 'Kol.', 1, 0, 'C')
        pdf.cell(25, 10, 'Cena', 1, 0, 'C')
        pdf.cell(30, 10, 'Ukupno', 1, 1, 'C')
        
        # Stavke fakture
        pdf.set_font('DejaVu', '', 10)
        for i, item in enumerate(invoice_items):
            service = Service.query.get(item.service_id)
            unit = UnitOfMeasure.query.get(service.unit_of_measure_id)
            unit_name = unit.name_sr if unit else ''
            
            pdf.cell(10, 10, str(i + 1), 1, 0, 'C')
            pdf.cell(80, 10, service.name_sr if service.name_sr else '', 1, 0, 'L')
            pdf.cell(25, 10, unit_name, 1, 0, 'C')
            pdf.cell(20, 10, str(item.quantity), 1, 0, 'C')
            pdf.cell(25, 10, f'{item.price} {item.currency}', 1, 0, 'C')
            pdf.cell(30, 10, f'{item.total} {item.currency}', 1, 1, 'C')
        
        # Ukupan iznos fakture
        pdf.ln(10)
        pdf.set_font('DejaVu', 'B', 12)
        pdf.cell(0, 10, f'Ukupno za uplatu: {invoice.total_amount} {invoice.currency}', 0, 1, 'R')
        
        # Napomena
        pdf.ln(10)
        pdf.set_font('DejaVu', '', 10)
        pdf.cell(0, 6, 'Napomena: ARHIV JUGOSLAVIJE nije u sistemu PDV-a u skladu sa Zakonom o PDV-u.', 0, 1, 'L')
        
        # Pečat i potpis
        pdf.ln(20)
        pdf.cell(95, 6, '', 0, 0, 'C')
        pdf.cell(95, 6, 'Potpis odgovornog lica', 0, 1, 'C')
        
        # Dodaj pečat ako postoji
        if archive_settings.stamp and os.path.exists(os.path.join('arhivjugoslavije', 'static', 'uploads', archive_settings.stamp)):
            pdf.image(os.path.join('arhivjugoslavije', 'static', 'uploads', archive_settings.stamp), x=40, y=pdf.get_y()-20, w=30)
        
        # Dodaj faksimil ako postoji
        if archive_settings.facsimile and os.path.exists(os.path.join('arhivjugoslavije', 'static', 'uploads', archive_settings.facsimile)):
            pdf.image(os.path.join('arhivjugoslavije', 'static', 'uploads', archive_settings.facsimile), x=140, y=pdf.get_y()-20, w=30)
        
        # Generisanje PDF-a
        pdf_bytes = io.BytesIO()
        pdf.output(pdf_bytes)
        pdf_bytes.seek(0)
        
        response = make_response(pdf_bytes.getvalue())
        response.headers.set('Content-Disposition', f'inline; filename=faktura_{invoice.invoice_number}.pdf')
        response.headers.set('Content-Type', 'application/pdf')
        
        return response
        
    except Exception as e:
        # Loguj grešku
        print(f"Greška pri generisanju PDF-a: {str(e)}")
        flash(f'Došlo je do greške prilikom generisanja PDF-a: {str(e)}.', 'danger')
        return redirect(url_for('invoices.edit_customer_invoice', invoice_id=invoice_id))