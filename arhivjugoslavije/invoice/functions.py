from fpdf import FPDF
import os
import io
import logging
from pathlib import Path
from flask import make_response, flash, redirect, url_for, current_app
from arhivjugoslavije.models import Invoice, Partner, InvoiceItem, Service, ArchiveSettings, UnitOfMeasure, BankAccount
from arhivjugoslavije import db, mail
from flask_mail import Message


def save_invoice_to_db(invoice_id):
    """
    Funkcija za sačuvanje fakture u data bazi.
    Vraća poruku sa statusom sačuvanja.
    """
    invoice = Invoice.query.get_or_404(invoice_id)
    message = {}
    if invoice.status != 'nacrt':
        message['error'] = f'Faktura {invoice.invoice_number} nije u nacrtu, ne može se sačuvati.'
        return message
    invoice.status = 'sacuvano'
    db.session.commit()
    message['success'] = f'Faktura {invoice.invoice_number} je uspešno sačuvana u data bazi.'
    return message


def send_invoice_to_partner(invoice_id):
    """
    Funkcija za slanje fakture partneru.
    Vraća poruku sa statusom slanja.
    """
    invoice = Invoice.query.get_or_404(invoice_id)
    message = {}
    if invoice.incoming:
        message['error'] = f'Nije moguće poslati izlaznu fakturu dobavljaču.'
        return message
    
    if invoice.status != 'poslato':
        # Pokušaj slanja emaila
        email_sent = send_email(invoice)
        
        if email_sent:
            invoice.status = 'poslato'
            db.session.commit()
            message['success'] = f'Faktura {invoice.invoice_number} je uspešno poslata partneru.'
        else:
            message['error'] = f'Došlo je do greške prilikom slanja fakture {invoice.invoice_number}. Proverite log fajl za više detalja.'
        
        return message
    else:
        message['error'] = f'Faktura {invoice.invoice_number} je već poslata.'
        return message


def send_email(invoice):
    """
    Funkcija za slanje e-maila partneru sa priloženom fakturom.
    Generiše PDF fakturu, dodaje je kao prilog i šalje email partneru.
    """
    try:
        # Dohvati partnera
        partner = Partner.query.get(invoice.partner_id)
        if not partner or not partner.email:
            current_app.logger.error(f"Nije moguće poslati email: Partner nema email adresu za fakturu {invoice.invoice_number}")
            return False
        
        # Dohvati podatke o arhivu
        archive_settings = ArchiveSettings.query.first()
        if not archive_settings:
            current_app.logger.error(f"Nije moguće poslati email: Podaci o arhivu nisu podešeni za fakturu {invoice.invoice_number}")
            return False
        
        # Generiši PDF fakturu
        pdf_buffer = generate_invoice_pdf(invoice.id, is_attachment=True)
        if not pdf_buffer:
            current_app.logger.error(f"Nije moguće generisati PDF za fakturu {invoice.invoice_number}")
            return False
        
        # Pripremi email poruku
        subject = f'Faktura {invoice.invoice_number}'
        sender = current_app.config.get('MAIL_DEFAULT_SENDER', archive_settings.email)
        
        # Kreiraj HTML sadržaj emaila
        html_body = f'''
        <html>
            <body>
                <p>Poštovani,</p>
                <p>U prilogu Vam dostavljamo fakturu broj {invoice.invoice_number}.</p>
                <p>Molimo Vas da izvršite plaćanje u roku navedenom na fakturi.</p>
                <p>S poštovanjem,<br>
                {archive_settings.name}</p>
            </body>
        </html>
        '''
        
        # Kreiraj poruku
        msg = Message(
            subject=subject,
            recipients=[partner.email],
            html=html_body,
            sender=sender
        )
        
        # Dodaj PDF kao prilog
        msg.attach(
            filename=f"Faktura_{invoice.invoice_number}.pdf",
            content_type="application/pdf",
            data=pdf_buffer.read()
        )
        
        # Pošalji email
        mail.send(msg)
        current_app.logger.info(f"Email sa fakturom {invoice.invoice_number} uspešno poslat na {partner.email}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Greška prilikom slanja emaila za fakturu {invoice.invoice_number}: {str(e)}")
        return False



def generate_invoice_pdf(invoice_id, is_attachment=False):
    """
    Funkcija za generisanje PDF fakture na osnovu ID-a fakture.
    Ako je is_attachment=False, vraća HTTP response sa PDF dokumentom.
    Ako je is_attachment=True, vraća BytesIO objekat sa PDF sadržajem za prilog emailu.
    """
    try:
        # Dohvati fakturu
        invoice = Invoice.query.get_or_404(invoice_id)
        
        # Proveri da li je izlazna faktura
        if invoice.incoming:
            if is_attachment:
                current_app.logger.warning('Generisanje PDF-a je dostupno samo za izlazne fakture.')
                return None
            else:
                flash('Generisanje PDF-a je dostupno samo za izlazne fakture.', 'warning')
                return redirect(url_for('invoices.invoice_list'))
        
        # Dohvati podatke o arhivu
        archive_settings = ArchiveSettings.query.first()
        if not archive_settings:
            if is_attachment:
                current_app.logger.error('Podaci o arhivu nisu podešeni.')
                return None
            else:
                flash('Podaci o arhivu nisu podešeni. Molimo vas da prvo podesite podatke o arhivu.', 'danger')
                return redirect(url_for('invoices.edit_customer_invoice', invoice_id=invoice_id))
        
        # Dohvati partnera (kupca)
        partner = Partner.query.get(invoice.partner_id)
        if not partner:
            if is_attachment:
                current_app.logger.error('Podaci o partneru nisu pronađeni.')
                return None
            else:
                flash('Podaci o partneru nisu pronađeni.', 'danger')
                return redirect(url_for('invoices.edit_customer_invoice', invoice_id=invoice_id))
        
        # Dohvati stavke fakture
        invoice_items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
        if not invoice_items:
            if is_attachment:
                current_app.logger.warning('Faktura nema stavke.')
                return None
            else:
                flash('Faktura nema stavke. Molimo vas da dodate bar jednu stavku.', 'warning')
                return redirect(url_for('invoices.edit_customer_invoice', invoice_id=invoice_id))
        
        # Proveri da li postoje DejaVu fontovi - koristi apsolutnu putanju
        base_dir = current_app.root_path
        fonts_dir = os.path.join(base_dir, 'static', 'fonts')
        dejavu_regular = os.path.join(fonts_dir, 'DejaVuSansCondensed.ttf')
        dejavu_bold = os.path.join(fonts_dir, 'DejaVuSansCondensed-Bold.ttf')
        
        # Provera da li fontovi postoje
        if not os.path.exists(dejavu_regular):
            if is_attachment:
                current_app.logger.error(f"Font nije pronađen na putanji: {dejavu_regular}")
                return None
            else:
                logging.error(f"Font nije pronađen na putanji: {dejavu_regular}")
                flash('Font DejaVuSansCondensed.ttf nije pronađen. Proverite da li je font dostupan u static/fonts direktorijumu.', 'danger')
                return redirect(url_for('invoices.edit_customer_invoice', invoice_id=invoice_id))
        
        if not os.path.exists(dejavu_bold):
            if is_attachment:
                current_app.logger.error(f"Font nije pronađen na putanji: {dejavu_bold}")
                return None
            else:
                logging.error(f"Font nije pronađen na putanji: {dejavu_bold}")
                flash('Font DejaVuSansCondensed-Bold.ttf nije pronađen. Proverite da li je font dostupan u static/fonts direktorijumu.', 'danger')
                return redirect(url_for('invoices.edit_customer_invoice', invoice_id=invoice_id))
        
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
                # ===== PRVI DEO: PODACI O ARHIVU I KONTAKT PODACI =====
                
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
                
                # Matični broj i PIB - leva strana
                self.set_x(10)
                self.cell(95, 5, f'MB: {archive_settings.mb}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                self.set_x(10)
                self.cell(95, 5, f'PIB: {archive_settings.pib}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                
                # Kontakt podaci - desna strana
                self.set_font('DejaVu', '', 10)
                self.set_xy(105, 8)
                self.cell(95, 5, f'Tel: {archive_settings.phone_1}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                self.set_xy(105, 13)
                self.cell(95, 5, f'Tel: {archive_settings.phone_2}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                self.set_xy(105, 18)
                self.cell(95, 5, f'e-mail: {archive_settings.email}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                self.set_xy(105, 23)
                self.cell(95, 5, f'www: {archive_settings.web_site}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                
                # Tekući račun - leva strana
                bank_accounts = BankAccount.query.filter_by(settings_id=archive_settings.id).all()
                if bank_accounts:
                    self.set_xy(105, 28)
                    self.cell(95, 5, f'Tek. rač: {bank_accounts[0].account_number}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                
                # ===== DRUGI DEO: DATUMI I PODACI O PARTNERU =====
                self.ln(10)  # Prazan prostor između delova
                
                # Podaci o partneru (kupcu) - desna strana
                self.set_font('DejaVu', 'B', 10)
                self.set_xy(105, 45)
                self.cell(95, 5, 'PRIMALAC:', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                
                # Naziv partnera - desna strana
                self.set_font('DejaVu', '', 10)
                self.set_xy(105, 50)
                self.cell(95, 5, partner.name, 0, new_x="LMARGIN", new_y="NEXT", align="L")
                
                # Adresa partnera - desna strana
                y_position = 55
                if partner.address:
                    self.set_xy(105, y_position)
                    self.cell(95, 5, partner.address, 0, new_x="LMARGIN", new_y="NEXT", align="L")
                    y_position += 5
                
                # Grad partnera - desna strana
                if partner.city:
                    self.set_xy(105, y_position)
                    self.cell(95, 5, partner.city, 0, new_x="LMARGIN", new_y="NEXT", align="L")
                    y_position += 5
                
                # PIB partnera - desna strana
                if partner.pib:
                    self.set_xy(105, y_position)
                    self.cell(95, 5, f'PIB: {partner.pib}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                    y_position += 5
                
                # Matični broj partnera - desna strana
                if partner.mb:
                    self.set_xy(105, y_position)
                    self.cell(95, 5, f'MB: {partner.mb}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                    y_position += 5
                
                # Mesto i datum izdavanja - leva strana
                self.set_font('DejaVu', '', 10)
                self.set_xy(10, 45)
                self.cell(95, 5, f'Mesto izdavanja: {archive_settings.city}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                
                # Datum izdavanja - leva strana
                self.set_xy(10, 50)
                self.cell(95, 5, f'Datum izdavanja: {invoice.issue_date.strftime("%d.%m.%Y.")}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                
                # Datum prometa - leva strana
                self.set_xy(10, 55)
                self.cell(95, 5, f'Datum prometa: {invoice.service_date.strftime("%d.%m.%Y.")}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                
                # Rok plaćanja - leva strana
                if invoice.payment_due_date:
                    self.set_xy(10, 60)
                    self.cell(95, 5, f'Rok plaćanja: {invoice.payment_due_date.strftime("%d.%m.%Y.")}', 0, new_x="LMARGIN", new_y="NEXT", align="L")
                
                # ===== TREĆI DEO: NASLOV FAKTURE =====
                self.ln(10)  # Prazan prostor između delova
                
                # Naslov fakture
                self.set_font('DejaVu', 'B', 14)
                self.cell(0, 10, f'Račun br.: {invoice.invoice_number}', 0, new_x="LMARGIN", new_y="NEXT", align="C")
            
            def footer(self):
                # Postavi Y poziciju za footer (30mm od dna stranice)
                self.set_y(-30)
                
                # Dodaj pečat u sredini footera ako postoji
                stamp_path = None
                if archive_settings.stamp:
                    # Provera da li putanja već sadrži 'uploads/'
                    if 'uploads/' in archive_settings.stamp:
                        stamp_path = os.path.join(base_dir, 'static', archive_settings.stamp)
                    else:
                        stamp_path = os.path.join(base_dir, 'static', 'uploads', archive_settings.stamp)
                
                if stamp_path and os.path.exists(stamp_path):
                    # Postavi pečat u sredini
                    page_width = self.w
                    stamp_width = 30  # širina pečata u mm
                    stamp_x = (page_width - stamp_width) / 2
                    self.image(stamp_path, x=stamp_x, y=self.get_y(), w=stamp_width)
                
                # Tekst potpisa na desnoj strani (iznad faksimila)
                self.set_y(-25)  # 25mm od dna stranice
                self.set_font('DejaVu', '', 10)
                self.cell(0, 6, 'Potpis odgovornog lica', 0, new_x="LMARGIN", new_y="NEXT", align="R")
                
                # Dodaj faksimil na desnoj strani footera ako postoji
                facsimile_path = None
                if archive_settings.facsimile:
                    # Provera da li putanja već sadrži 'uploads/'
                    if 'uploads/' in archive_settings.facsimile:
                        facsimile_path = os.path.join(base_dir, 'static', archive_settings.facsimile)
                    else:
                        facsimile_path = os.path.join(base_dir, 'static', 'uploads', archive_settings.facsimile)
                
                if facsimile_path and os.path.exists(facsimile_path):
                    # Postavi faksimil na desnoj strani
                    facsimile_width = 30  # širina faksimila u mm
                    facsimile_x = page_width - facsimile_width - 10  # 10mm od desne ivice
                    self.image(facsimile_path, x=facsimile_x, y=self.get_y(), w=facsimile_width)
                
                # Broj stranice na dnu
                self.set_y(-5)  # 5mm od dna stranice
                self.set_font('DejaVu', 'I', 8)
                self.cell(0, 5, f'Strana {self.page_no()}', 0, new_x="LMARGIN", new_y="NEXT", align="C")
        
        # Kreiraj PDF dokument
        pdf = InvoicePDF()
        pdf.add_page()
        
        # Tabela sa stavkama fakture
        pdf.ln(10)  # Pomeri se ispod headera
        pdf.set_font('DejaVu', 'B', 10)
        pdf.cell(10, 10, 'Rb.', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(80, 10, 'Opis', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(25, 10, 'Jed. mere', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(20, 10, 'Kol.', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(25, 10, 'Cena', 1, new_x="RIGHT", new_y="LAST", align="C")
        pdf.cell(30, 10, 'Ukupno', 1, new_x="LMARGIN", new_y="NEXT", align="C")
        
        # Stavke fakture
        pdf.set_font('DejaVu', '', 10)
        for i, item in enumerate(invoice_items):
            service = Service.query.get(item.service_id)
            unit = UnitOfMeasure.query.get(service.unit_of_measure_id)
            unit_name = unit.name_sr if unit else ''
            
            pdf.cell(10, 10, str(i + 1), 1, new_x="RIGHT", new_y="LAST", align="C")
            pdf.cell(80, 10, service.name_sr if service.name_sr else '', 1, new_x="RIGHT", new_y="LAST", align="L")
            pdf.cell(25, 10, unit_name, 1, new_x="RIGHT", new_y="LAST", align="C")
            pdf.cell(20, 10, str(item.quantity), 1, new_x="RIGHT", new_y="LAST", align="R")
            pdf.cell(25, 10, f'{item.price} {item.currency}', 1, new_x="RIGHT", new_y="LAST", align="R")
            pdf.cell(30, 10, f'{item.total} {item.currency}', 1, new_x="LMARGIN", new_y="NEXT", align="C")
        
        # Ukupan iznos fakture
        pdf.ln(10)
        pdf.set_font('DejaVu', 'B', 12)
        pdf.cell(0, 10, f'Ukupno za uplatu: {invoice.total_amount} {invoice.currency}', 1, new_x="RIGHT", new_y="LAST", align="R")
        
        # Svrha uplate i poziv na broj
        pdf.ln(10)
        pdf.set_font('DejaVu', '', 10)
        pdf.cell(0, 6, f'Svrha uplate: 318', 1, new_x="LMARGIN", new_y="NEXT", align="L")
        pdf.cell(0, 6, f'Poziv na broj: {archive_settings.model} {archive_settings.poziv_na_broj}', 1, new_x="LMARGIN", new_y="NEXT", align="L")
        
        # Napomena
        pdf.ln(10)
        pdf.set_font('DejaVu', '', 10)
        pdf.cell(0, 6, 'Napomena: ARHIV JUGOSLAVIJE nije u sistemu PDV-a u skladu sa Zakonom o PDV-u.', 1, new_x="LMARGIN", new_y="NEXT", align="L")
        
        # Generisanje PDF-a
        if is_attachment:
            # Vraćamo BytesIO objekat sa PDF sadržajem za prilog emailu
            pdf_buffer = io.BytesIO()
            pdf.output(pdf_buffer)
            pdf_buffer.seek(0)
            return pdf_buffer
        else:
            # Vraćamo HTTP response za prikaz u pretraživaču
            pdf_bytes = io.BytesIO()
            pdf.output(pdf_bytes)
            pdf_bytes.seek(0)
            
            response = make_response(pdf_bytes.getvalue())
            response.headers.set('Content-Disposition', f'inline; filename=faktura_{invoice.invoice_number}.pdf')
            response.headers.set('Content-Type', 'application/pdf')
            
            return response
        
    except Exception as e:
        error_msg = f"Greška prilikom generisanja PDF-a: {str(e)}"
        if is_attachment:
            current_app.logger.error(error_msg)
            return None
        else:
            logging.error(error_msg)
            flash(f'Došlo je do greške prilikom generisanja PDF-a: {str(e)}.', 'danger')
            return redirect(url_for('invoices.edit_customer_invoice', invoice_id=invoice_id))