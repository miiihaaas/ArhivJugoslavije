from fpdf import FPDF
import os
import io
import logging
from pathlib import Path
from flask import make_response, flash, redirect, url_for, current_app
from arhivjugoslavije.models import Invoice, Partner, InvoiceItem, Service, ArchiveSettings, UnitOfMeasure, BankAccount, User
from arhivjugoslavije import db, mail
from arhivjugoslavije import format_number
from flask_mail import Message


def cc_adrese_korisnika():
    """
    Adrese korisnika aplikacije koji dobijaju kopiju (CC) mejlova partnerima.
    Adrese navedene u MAIL_CC_ISKLJUCI (.env, odvojene zarezom) se preskaču.
    """
    iskljuceni = {a.strip().lower() for a in os.getenv('MAIL_CC_ISKLJUCI', '').split(',') if a.strip()}
    return [user.email for user in User.query.all() if user.email and user.email.strip().lower() not in iskljuceni]


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


def notify_partner_about_canceled_invoice(invoice_number, partner_id):
    """
    Funkcija za slanje mejla partneru o storniranoj fakturi.
    Vraća poruku sa statusom slanja.
    """
    partner = Partner.query.get_or_404(partner_id)
    message = {}
    if partner.email:
        msg = Message(
            subject=f'Faktura {invoice_number} stornirana',
            recipients=[partner.email],
            cc=cc_adrese_korisnika(),
            body=f'Faktura {invoice_number} je stornirana.'
        )
        try:
            mail.send(msg)
            message['success'] = f'Faktura {invoice_number} je uspešno stornirana.'
        except Exception as e:
            message['error'] = f'Nije moguće poslati mejl partneru o storniranoj fakturi: {str(e)}'
    else:
        message['error'] = 'Partner nema mejl adresu.'
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
        # sender = current_app.config.get('MAIL_DEFAULT_SENDER', archive_settings.email)
        sender = os.getenv('MAIL_USERNAME')
        cc = cc_adrese_korisnika()
        
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
            cc=cc,
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
        language = 'en' if partner.international else 'sr'
        
        # Dohvati stavke fakture
        invoice_items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
        if not invoice_items:
            if is_attachment:
                current_app.logger.warning('Faktura nema stavke.')
                return None
            else:
                flash('Faktura nema stavke. Molimo vas da dodate bar jednu stavku.', 'warning')
                return redirect(url_for('invoices.edit_customer_invoice', invoice_id=invoice_id))
        
        # Fontovi: PT Sans (tekst) i PT Sans Narrow (naslovi, natpisi) — isti kao u aplikaciji,
        # podržavaju čćžšđ. Traže se u static/fonts.
        base_dir = current_app.root_path
        fonts_dir = os.path.join(base_dir, 'static', 'fonts')
        font_fajlovi = {
            ('Tekst', ''): 'PTSans-Regular.ttf',
            ('Tekst', 'B'): 'PTSans-Bold.ttf',
            ('Natpis', ''): 'PTSansNarrow-Regular.ttf',
            ('Natpis', 'B'): 'PTSansNarrow-Bold.ttf',
        }
        for font_fajl in font_fajlovi.values():
            font_putanja = os.path.join(fonts_dir, font_fajl)
            if not os.path.exists(font_putanja):
                if is_attachment:
                    current_app.logger.error(f"Font nije pronađen na putanji: {font_putanja}")
                    return None
                logging.error(f"Font nije pronađen na putanji: {font_putanja}")
                flash(f'Font {font_fajl} nije pronađen. Proverite da li je font dostupan u static/fonts direktorijumu.', 'danger')
                return redirect(url_for('invoices.edit_customer_invoice', invoice_id=invoice_id))

        def putanja_slike(relativna):
            """Putanja do slike iz podešavanja arhiva (logo, pečat, faksimil) ili None ako ne postoji."""
            if not relativna:
                return None
            if 'uploads/' in relativna:
                putanja = os.path.join(base_dir, 'static', relativna)
            else:
                putanja = os.path.join(base_dir, 'static', 'uploads', relativna)
            return putanja if os.path.exists(putanja) else None

        en = language == 'en'
        predracun = invoice.status == 'nacrt'
        naslov_dokumenta = ('Proforma invoice' if en else 'Predračun') if predracun else ('Invoice' if en else 'Račun')
        tekuci_racun = '840000003112084593'  #! ovo možda treba menjati da bude promenjivo

        # Boje (iz identiteta Arhiva, kao u aplikaciji) — dovoljno svetle podloge da faktura
        # izgleda uredno i kad se štampa crno-belo
        BORDO = (119, 30, 50)
        GRAFIT = (46, 49, 50)
        SIVA = (104, 109, 110)
        LINIJA = (207, 204, 193)
        PERGAMENT = (245, 233, 207)

        LEVO = 18          # leva i desna margina (mm)
        SIRINA = 210 - 2 * LEVO

        class InvoicePDF(FPDF):
            def __init__(self):
                super().__init__(orientation='P', unit='mm', format='A4')
                for (porodica, stil), fajl in font_fajlovi.items():
                    self.add_font(porodica, stil, os.path.join(fonts_dir, fajl))
                self.set_margins(LEVO, 16, LEVO)
                self.set_auto_page_break(auto=True, margin=24)
                self.set_text_color(*GRAFIT)
                self.set_draw_color(*LINIJA)
                self.set_font('Tekst', '', 9.5)

            def header(self):
                # Od druge strane: samo kratko zaglavlje sa oznakom dokumenta
                if self.page_no() == 1:
                    return
                self.set_font('Natpis', 'B', 11)
                self.set_text_color(*BORDO)
                self.cell(0, 6, f'{naslov_dokumenta} {invoice.invoice_number}', new_x="LMARGIN", new_y="NEXT")
                self.set_text_color(*GRAFIT)
                self.set_draw_color(*BORDO)
                self.set_line_width(0.4)
                self.line(LEVO, self.get_y() + 1, LEVO + SIRINA, self.get_y() + 1)
                self.set_draw_color(*LINIJA)
                self.set_line_width(0.2)
                self.ln(6)

            def footer(self):
                self.set_y(-14)
                self.set_draw_color(*LINIJA)
                self.set_line_width(0.2)
                self.line(LEVO, self.get_y(), LEVO + SIRINA, self.get_y())
                self.ln(1.5)
                self.set_font('Tekst', '', 7.5)
                self.set_text_color(*SIVA)
                self.cell(SIRINA / 2, 4, f'{archive_settings.name}, {archive_settings.address}, {archive_settings.zip_code} {archive_settings.city}')
                self.cell(SIRINA / 2, 4, f'{"Page" if en else "Strana"} {self.page_no()} {"of" if en else "od"} {{nb}}', align='R')
                self.set_text_color(*GRAFIT)

            # --- pomoćne ---------------------------------------------------------
            def natpis(self, tekst, x, sirina):
                """Mali sivi natpis iznad podatka."""
                self.set_x(x)
                self.set_font('Natpis', '', 8.5)
                self.set_text_color(*SIVA)
                self.cell(sirina, 4.2, tekst, new_x="LMARGIN", new_y="NEXT")
                self.set_text_color(*GRAFIT)

            def red(self, tekst, x, sirina, stil='', velicina=9.5, visina=4.6):
                """Red teksta u koloni; dugačak tekst se prelama."""
                self.set_x(x)
                self.set_font('Tekst', stil, velicina)
                self.multi_cell(sirina, visina, tekst, new_x="LMARGIN", new_y="NEXT")

            def broj_redova(self, tekst, sirina):
                """Koliko redova zauzima tekst u koloni date širine (za visinu reda tabele)."""
                redovi = 0
                for pasus in str(tekst).split('\n'):
                    linija = ''
                    redovi += 1
                    for rec in pasus.split(' '):
                        proba = f'{linija} {rec}'.strip()
                        if self.get_string_width(proba) > sirina - 2 and linija:
                            redovi += 1
                            linija = rec
                        else:
                            linija = proba
                return max(redovi, 1)

        pdf = InvoicePDF()
        pdf.alias_nb_pages()
        pdf.add_page()

        # ===== ZAGLAVLJE: logo levo, vrsta i broj dokumenta desno =====
        logo_path = putanja_slike(archive_settings.logo)
        if logo_path:
            pdf.image(logo_path, x=LEVO, y=14, w=46)

        pdf.set_xy(LEVO, 15)
        pdf.set_font('Natpis', 'B', 26)
        pdf.set_text_color(*BORDO)
        pdf.cell(SIRINA, 11, naslov_dokumenta, align='R', new_x="LMARGIN", new_y="NEXT")
        pdf.set_font('Natpis', 'B', 14)
        pdf.set_text_color(*GRAFIT)
        pdf.cell(SIRINA, 7, f'{"No." if en else "Broj"} {invoice.invoice_number}', align='R', new_x="LMARGIN", new_y="NEXT")

        pdf.set_draw_color(*BORDO)
        pdf.set_line_width(0.6)
        pdf.line(LEVO, 40, LEVO + SIRINA, 40)
        pdf.set_line_width(0.2)
        pdf.set_draw_color(*LINIJA)

        # ===== IZDAVALAC (levo) i PRIMALAC (desno, u uokvirenom polju) =====
        kolona = 84
        desno_x = LEVO + SIRINA - kolona
        vrh = 45

        pdf.set_y(vrh)
        pdf.natpis('Issuer' if en else 'Izdavalac', LEVO, kolona)
        pdf.red(archive_settings.name, LEVO, kolona, stil='B', velicina=11, visina=5.4)
        pdf.red(archive_settings.address, LEVO, kolona)
        pdf.red(f'{archive_settings.zip_code} {archive_settings.city}', LEVO, kolona)
        pdf.red(f'{"CRN" if en else "MB"}: {archive_settings.mb}    {"TIN" if en else "PIB"}: {archive_settings.pib}', LEVO, kolona)
        pdf.red(f'{"Bank account" if en else "Tekući račun"}: {tekuci_racun}', LEVO, kolona)
        telefoni = ', '.join(t for t in [archive_settings.phone_1, archive_settings.phone_2] if t)
        if telefoni:
            pdf.red(f'{"Phone" if en else "Tel"}: {telefoni}', LEVO, kolona)
        if archive_settings.email:
            pdf.red(f'{"E-mail" if en else "Mejl"}: {archive_settings.email.strip()}', LEVO, kolona)
        if archive_settings.web_site:
            pdf.red(archive_settings.web_site, LEVO, kolona)
        kraj_izdavaoca = pdf.get_y()

        # Primalac: prvo se ispiše tekst, pa se ispod njega nacrta polje iste visine
        pdf.set_y(vrh + 3)
        unutra_x = desno_x + 4
        unutra_w = kolona - 8
        pdf.natpis('Recipient' if en else 'Primalac', unutra_x, unutra_w)
        pdf.red(partner.name, unutra_x, unutra_w, stil='B', velicina=11, visina=5.4)
        if partner.address:
            pdf.red(partner.address, unutra_x, unutra_w)
        mesto = ', '.join(d for d in [partner.city, partner.country if partner.international else None] if d)
        if mesto:
            pdf.red(mesto, unutra_x, unutra_w)
        if partner.pib:
            pdf.red(f'{"TIN" if en else "PIB"}: {partner.pib}', unutra_x, unutra_w)
        if partner.mb:
            pdf.red(f'{"CRN" if en else "MB"}: {partner.mb}', unutra_x, unutra_w)
        kraj_primaoca = pdf.get_y() + 3
        pdf.set_line_width(0.3)
        pdf.rect(desno_x, vrh, kolona, max(kraj_primaoca, kraj_izdavaoca) - vrh)
        pdf.set_line_width(0.2)

        # ===== PODACI O IZDAVANJU: traka sa poljima (natpis iznad vrednosti) =====
        polja = [
            ('Issue place' if en else 'Mesto izdavanja', archive_settings.city),
            ('Issue date' if en else 'Datum izdavanja', invoice.issue_date.strftime('%d.%m.%Y.')),
            ('Service date' if en else 'Datum prometa', invoice.service_date.strftime('%d.%m.%Y.')),
        ]
        if invoice.payment_due_date:
            polja.append(('Payment due date' if en else 'Rok plaćanja', invoice.payment_due_date.strftime('%d.%m.%Y.')))
        if invoice.document_number:
            polja.append(('Document number' if en else 'Broj dokumenta', invoice.document_number))

        traka_y = max(kraj_primaoca, kraj_izdavaoca) + 6
        traka_h = 12
        sirina_polja = SIRINA / len(polja)
        pdf.set_fill_color(*PERGAMENT)
        pdf.rect(LEVO, traka_y, SIRINA, traka_h, style='F')
        pdf.set_fill_color(*BORDO)
        pdf.rect(LEVO, traka_y, 0.8, traka_h, style='F')
        for i, (naziv, vrednost) in enumerate(polja):
            x = LEVO + i * sirina_polja
            if i > 0:
                pdf.set_draw_color(217, 199, 156)
                pdf.line(x, traka_y + 2, x, traka_y + traka_h - 2)
                pdf.set_draw_color(*LINIJA)
            pdf.set_xy(x + 3.5, traka_y + 1.6)
            pdf.set_font('Natpis', '', 8.5)
            pdf.set_text_color(*SIVA)
            pdf.cell(sirina_polja - 5, 4, naziv)
            pdf.set_xy(x + 3.5, traka_y + 5.6)
            pdf.set_font('Natpis', 'B', 11)
            pdf.set_text_color(*GRAFIT)
            pdf.cell(sirina_polja - 5, 5, str(vrednost))

        # ===== STAVKE =====
        kolone = [
            ('No.' if en else 'Rb', 9, 'C'),
            ('Description' if en else 'Opis', 78, 'L'),
            ('UOM' if en else 'Jed. mere', 20, 'C'),
            ('Quantity' if en else 'Kol.', 18, 'R'),
            ('Price' if en else 'Cena', 24.5, 'R'),
            ('Amount' if en else 'Iznos', 24.5, 'R'),
        ]

        def zaglavlje_tabele():
            pdf.set_font('Natpis', 'B', 9.5)
            pdf.set_fill_color(*PERGAMENT)
            pdf.set_text_color(*GRAFIT)
            for naziv, sirina, poravnanje in kolone:
                pdf.cell(sirina, 7.5, naziv, align=poravnanje, fill=True)
            pdf.ln(7.5)
            pdf.set_draw_color(*GRAFIT)
            pdf.set_line_width(0.3)
            pdf.line(LEVO, pdf.get_y(), LEVO + SIRINA, pdf.get_y())
            pdf.set_line_width(0.2)
            pdf.set_draw_color(*LINIJA)

        pdf.set_y(traka_y + traka_h + 8)
        zaglavlje_tabele()

        pdf.set_font('Tekst', '', 9.5)
        visina_linije = 4.6
        for i, item in enumerate(invoice_items):
            service = Service.query.get(item.service_id)
            unit = UnitOfMeasure.query.get(service.unit_of_measure_id)
            unit_name = unit.name_en if en else unit.name_sr

            description = service.name_en if en else service.name_sr
            if service.note not in [None, '']:
                description += f' ({service.note})'

            pdf.set_font('Tekst', '', 9.5)
            redova = pdf.broj_redova(description, kolone[1][1])
            visina = redova * visina_linije + 3.4

            # Ako red ne staje na stranu, nova strana i ponovljeno zaglavlje tabele
            if pdf.get_y() + visina > pdf.h - pdf.b_margin:
                pdf.add_page()
                zaglavlje_tabele()
                pdf.set_font('Tekst', '', 9.5)

            y = pdf.get_y()
            vrednosti = [
                str(i + 1),
                None,  # opis se ispisuje posebno (prelama se)
                unit_name,
                format_number(item.quantity),
                f'{format_number(item.price)} {item.currency}',
                f'{format_number(item.total)} {item.currency}',
            ]
            x = LEVO
            for (naziv, sirina, poravnanje), vrednost in zip(kolone, vrednosti):
                pdf.set_xy(x, y + 1.7)
                if vrednost is None:
                    pdf.multi_cell(sirina, visina_linije, description, align='L')
                else:
                    pdf.cell(sirina, visina_linije, vrednost, align=poravnanje)
                x += sirina
            pdf.set_y(y + visina)
            pdf.line(LEVO, pdf.get_y(), LEVO + SIRINA, pdf.get_y())

        # ===== UKUPNO ZA UPLATU: dvostruka linija iznad (knjigovodstvena oznaka zbira) =====
        blok_w = 92
        blok_x = LEVO + SIRINA - blok_w
        if pdf.get_y() + 22 > pdf.h - pdf.b_margin:
            pdf.add_page()
        y = pdf.get_y() + 5
        pdf.set_draw_color(*GRAFIT)
        pdf.set_line_width(0.3)
        pdf.line(blok_x, y, blok_x + blok_w, y)
        pdf.line(blok_x, y + 0.9, blok_x + blok_w, y + 0.9)
        pdf.set_line_width(0.2)
        pdf.set_draw_color(*LINIJA)
        pdf.set_fill_color(*PERGAMENT)
        pdf.rect(blok_x, y + 1.3, blok_w, 11, style='F')
        pdf.set_xy(blok_x + 3.5, y + 1.3)
        pdf.set_font('Natpis', 'B', 11)
        pdf.cell(blok_w / 2 - 3.5, 11, 'Total amount to pay' if en else 'Ukupno za uplatu')
        pdf.set_font('Natpis', 'B', 15)
        pdf.set_text_color(*BORDO)
        pdf.cell(blok_w / 2 - 3.5, 11, f'{format_number(invoice.total_amount)} {invoice.currency}', align='R')
        pdf.set_text_color(*GRAFIT)
        pdf.set_y(y + 18)

        # ===== PLAĆANJE i NAPOMENA =====
        def odeljak(naslov):
            if pdf.get_y() + 20 > pdf.h - pdf.b_margin:
                pdf.add_page()
            pdf.set_font('Natpis', 'B', 10.5)
            pdf.cell(0, 6, naslov, new_x="LMARGIN", new_y="NEXT")
            pdf.line(LEVO, pdf.get_y(), LEVO + SIRINA, pdf.get_y())
            pdf.ln(1.8)

        def stavka(naziv, vrednost):
            pdf.set_font('Tekst', '', 9.5)
            pdf.set_text_color(*SIVA)
            pdf.cell(42, 5.2, naziv)
            pdf.set_text_color(*GRAFIT)
            pdf.set_font('Tekst', 'B', 9.5)
            pdf.multi_cell(SIRINA - 42, 5.2, vrednost, new_x="LMARGIN", new_y="NEXT")

        odeljak('Payment details' if en else 'Podaci za uplatu')
        stavka('Bank account' if en else 'Tekući račun', tekuci_racun)
        stavka('Payment Reference' if en else 'Poziv na broj', f'{archive_settings.model} {archive_settings.poziv_na_broj}')
        stavka('Purpose of payment' if en else 'Svrha uplate', invoice.invoice_number)
        pdf.ln(4)

        pdv = ('ARHIV JUGOSLAVIJE is not registered for VAT in accordance with the VAT Law.' if en
               else 'ARHIV JUGOSLAVIJE nije u sistemu PDV-a u skladu sa Zakonom o PDV-u.')
        odeljak(('Notes' if en else 'Napomene') if invoice.note else ('Note' if en else 'Napomena'))
        pdf.set_font('Tekst', '', 9.5)
        pdf.multi_cell(0, 5.2, pdv, new_x="LMARGIN", new_y="NEXT")
        if invoice.note:
            pdf.multi_cell(0, 5.2, invoice.note, new_x="LMARGIN", new_y="NEXT")

        # ===== PEČAT I POTPIS: na dnu poslednje strane =====
        potpis_h = 36
        potpis_y = pdf.h - pdf.b_margin - potpis_h
        if pdf.get_y() + 6 > potpis_y:
            pdf.add_page()
        stamp_path = putanja_slike(archive_settings.stamp)
        if stamp_path:
            pdf.image(stamp_path, x=LEVO + 58, y=potpis_y + 2, w=30)

        potpis_w = 64
        potpis_x = LEVO + SIRINA - potpis_w
        facsimile_path = putanja_slike(archive_settings.facsimile)
        if facsimile_path:
            pdf.image(facsimile_path, x=potpis_x + (potpis_w - 38) / 2, y=potpis_y + 4, w=38)
        linija_y = potpis_y + 28
        pdf.set_draw_color(*GRAFIT)
        pdf.line(potpis_x, linija_y, potpis_x + potpis_w, linija_y)
        pdf.set_draw_color(*LINIJA)
        pdf.set_xy(potpis_x, linija_y + 1)
        pdf.set_font('Natpis', '', 9)
        pdf.set_text_color(*SIVA)
        pdf.cell(potpis_w, 4.5, "Authorized person's signature" if en else 'Potpis odgovornog lica', align='C')
        pdf.set_text_color(*GRAFIT)

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