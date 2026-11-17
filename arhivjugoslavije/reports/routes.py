from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func, case
from decimal import Decimal
from datetime import date
from arhivjugoslavije import db
from arhivjugoslavije.models import (PurchasePlan, PurchasePlanAccount, AccountLevel4, AccountLevel6, StatementItem,
                                     BankAccount, BankStatement, Partner, FUNDING_SOURCES, FUNDING_SOURCE_CODES,
                                     SOURCE_BY_ACCOUNT_TYPE)

reports = Blueprint('reports', __name__)

ZERO = Decimal('0.00')


@reports.route('/report_list', methods=['GET', 'POST'])
@login_required
def report_list():
    return render_template('reports/report_list.html')


@reports.route('/report_1', methods=['GET', 'POST'])
@login_required
def report_1():
    """Realizacija po kontima: plan i potrošnja za izvore 01, 04 i 13 jedan pored drugog.

    Konto nivoa 4 se otvara u konta nivoa 6, a konto nivoa 6 u dobavljače (primaoce) sa iznosima.
    Potrošnja izvora = isplate sa bankovnog računa tog izvora (SOURCE_BY_ACCOUNT_TYPE).
    """
    # Dobavljanje svih planova nabavki za filter po godinama
    purchase_plans = PurchasePlan.query.order_by(PurchasePlan.year.desc()).all()

    # Ako je odabrana godina, filtriraj po njoj, inače uzmi najnoviju godinu
    selected_year = request.args.get('year', type=int)
    if not selected_year and purchase_plans:
        selected_year = purchase_plans[0].year

    accounts = []
    unassigned = []
    totals = _empty_row()

    if selected_year:
        # Promet se računa samo iz izvoda odabrane godine
        year_start = date(selected_year, 1, 1)
        year_end = date(selected_year, 12, 31)

        # Planirani iznosi po kontu nivoa 4 i izvoru (redovna + programska delatnost)
        purchase_plan = next((plan for plan in purchase_plans if plan.year == selected_year), None)
        plan_by_account = {}
        if purchase_plan:
            plan_rows = db.session.query(
                PurchasePlanAccount.account_level_4_number,
                PurchasePlanAccount.source,
                func.sum(func.coalesce(PurchasePlanAccount.amount_1, 0) + func.coalesce(PurchasePlanAccount.amount_2, 0)).label('planned_amount')
            ).filter(
                PurchasePlanAccount.purchase_plan_id == purchase_plan.id
            ).group_by(
                PurchasePlanAccount.account_level_4_number,
                PurchasePlanAccount.source
            ).all()
            for row in plan_rows:
                if row.source in FUNDING_SOURCE_CODES:
                    plan_by_account.setdefault(row.account_level_4_number, {})[row.source] = row.planned_amount or ZERO

        # Jedan zbirni upit: promet po kontu nivoa 6, tipu računa, smeru i primaocu.
        # Primalac je partner ako je dodeljen, inače naziv primaoca sa izvoda.
        payee_text = case((StatementItem.partner_id.is_(None), StatementItem.recipient), else_=None)
        movements = db.session.query(
            StatementItem.account_level_6_number,
            AccountLevel6.name,
            BankAccount.account_type,
            StatementItem.is_debit,
            StatementItem.partner_id,
            Partner.name.label('partner_name'),
            payee_text.label('recipient'),
            func.count(StatementItem.id).label('item_count'),
            func.sum(StatementItem.amount).label('amount')
        ).join(
            BankStatement, BankStatement.id == StatementItem.bank_statement_id
        ).join(
            BankAccount, BankAccount.id == BankStatement.bank_account_id
        ).outerjoin(
            AccountLevel6, AccountLevel6.number == StatementItem.account_level_6_number
        ).outerjoin(
            Partner, Partner.id == StatementItem.partner_id
        ).filter(
            BankStatement.date.between(year_start, year_end),
            BankAccount.account_type.in_(list(SOURCE_BY_ACCOUNT_TYPE.keys()))
        ).group_by(
            StatementItem.account_level_6_number,
            AccountLevel6.name,
            BankAccount.account_type,
            StatementItem.is_debit,
            StatementItem.partner_id,
            Partner.name,
            payee_text
        ).all()

        level_6 = {}
        unassigned_by_source = {}
        for row in movements:
            amount = row.amount or ZERO
            source = SOURCE_BY_ACCOUNT_TYPE[row.account_type]

            # Stavke bez konta ne ulaze u izveštaj - samo se broje isplate radi napomene ispod tabele
            if not row.account_level_6_number:
                if row.is_debit:
                    entry = unassigned_by_source.setdefault(source, {'count': 0, 'amount': ZERO})
                    entry['count'] += row.item_count
                    entry['amount'] += amount
                continue

            # Uplate: prati se samo doznaka na budžetski račun (izvor 01); ostale uplate nisu deo izveštaja
            if not row.is_debit and source != '01':
                continue

            child = level_6.get(row.account_level_6_number)
            if child is None:
                child = dict(_empty_row(), account_number=row.account_level_6_number,
                             account_name=row.name or '', payees={})
                level_6[row.account_level_6_number] = child

            if not row.is_debit:
                child['budget_received'] += amount
                continue

            # Isplata: potrošnja izvora i raspodela po primaocu
            child['spent_' + source] += amount
            if row.partner_id:
                key, name = ('p', row.partner_id), row.partner_name or ''
            else:
                name = (row.recipient or '').strip()
                key = ('r', name.lower())
            payee = child['payees'].get(key)
            if payee is None:
                payee = dict(_empty_row(), name=name or 'Bez naziva primaoca', is_partner=bool(row.partner_id), count=0)
                child['payees'][key] = payee
            payee['spent_' + source] += amount
            payee['count'] += row.item_count

        # Zbirovi konta nivoa 6 i njihovih primalaca; primaoci sortirani po iznosu (najveći prvi)
        for child in level_6.values():
            _finish_row(child)
            for payee in child['payees'].values():
                _finish_row(payee)
            child['payees'] = sorted(child['payees'].values(), key=lambda payee: (-payee['spent_total'], payee['name'].lower()))

        # Konta nivoa 4 iz plana (bilo kog izvora); konta nivoa 6 se vezuju po prefiksu broja
        names_level_4 = dict(db.session.query(AccountLevel4.number, AccountLevel4.name).all())
        used_children = set()
        for account_number, planned in plan_by_account.items():
            children = [level_6[number] for number in sorted(level_6) if number.startswith(account_number)]
            used_children.update(child['account_number'] for child in children)
            accounts.append(_build_level_4_row(account_number, names_level_4.get(account_number, ''),
                                               planned, children, selected_year, in_plan=True))

        # Konta rashoda (4xxx, 5xxx) sa prometom u godini kojih nema u planu - "van plana",
        # da potrošnja nikada ne nestane iz izveštaja. Konta prihoda (7xxx...) se ne prikazuju.
        off_plan = {}
        for number in sorted(level_6):
            if number not in used_children and number[:1] in ('4', '5'):
                off_plan.setdefault(number[:4], []).append(level_6[number])
        for account_number, children in off_plan.items():
            accounts.append(_build_level_4_row(account_number, names_level_4.get(account_number, ''),
                                               {}, children, selected_year, in_plan=False))

        # Redovi sortirani po broju konta
        accounts.sort(key=lambda account: account['account_number'])

        # Ukupni iznosi
        for account in accounts:
            for key in totals:
                totals[key] += account[key]

        # Napomena o isplatama bez konta, po izvoru
        for source in FUNDING_SOURCES:
            if source['code'] in unassigned_by_source:
                unassigned.append(dict(unassigned_by_source[source['code']], label=source['label']))

    return render_template('reports/report_1.html',
                            purchase_plans=purchase_plans,
                            funding_sources=FUNDING_SOURCES,
                            accounts=accounts,
                            totals=totals,
                            unassigned=unassigned,
                            selected_year=selected_year)


def _empty_row():
    """Novčane kolone izveštaja: po izvoru plan/potrošeno/saldo, doznaka budžeta i ukupno."""
    row = {'budget_received': ZERO}
    for code in FUNDING_SOURCE_CODES + ['total']:
        row['planned_' + code] = ZERO
        row['spent_' + code] = ZERO
        row['balance_' + code] = ZERO
    return row


def _finish_row(row):
    """Ukupno preko izvora i saldo (planirano - potrošeno) za svaki izvor i ukupno."""
    row['planned_total'] = sum((row['planned_' + code] for code in FUNDING_SOURCE_CODES), ZERO)
    row['spent_total'] = sum((row['spent_' + code] for code in FUNDING_SOURCE_CODES), ZERO)
    for code in FUNDING_SOURCE_CODES + ['total']:
        row['balance_' + code] = row['planned_' + code] - row['spent_' + code]


def _build_level_4_row(account_number, account_name, planned, children, year, in_plan):
    """Red konta nivoa 4: potrošnja je zbir konta nivoa 6 ispod njega, plan je iz plana nabavke po izvoru."""
    row = _empty_row()
    for child in children:
        row['budget_received'] += child['budget_received']
        for code in FUNDING_SOURCE_CODES:
            row['spent_' + code] += child['spent_' + code]
    for code in FUNDING_SOURCE_CODES:
        row['planned_' + code] = planned.get(code, ZERO)
    _finish_row(row)
    row.update({
        'year': year,
        'account_number': account_number,
        'account_name': account_name,
        'in_plan': in_plan,
        'children': children
    })
    return row
