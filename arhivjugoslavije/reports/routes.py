from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func, and_, or_
from decimal import Decimal
from datetime import date
from arhivjugoslavije import db
from arhivjugoslavije.models import PurchasePlan, PurchasePlanAccount, AccountLevel4, AccountLevel6, StatementItem, BankAccount, BankStatement

reports = Blueprint('reports', __name__)

@reports.route('/report_list', methods=['GET', 'POST'])
@login_required
def report_list():
    return render_template('reports/report_list.html')


@reports.route('/report_1', methods=['GET', 'POST'])
@login_required
def report_1():
    # Dobavljanje svih planova nabavki za filter po godinama
    purchase_plans = PurchasePlan.query.order_by(PurchasePlan.year.desc()).all()

    # Ako je odabrana godina, filtriraj po njoj, inače uzmi najnoviju godinu
    selected_year = request.args.get('year', type=int)
    if not selected_year and purchase_plans:
        selected_year = purchase_plans[0].year

    # Inicijalizacija rezultata
    accounts = []
    unassigned = []
    totals = _empty_amounts()
    totals['planned'] = Decimal('0.00')
    totals['budget_balance'] = Decimal('0.00')

    if selected_year:
        # Promet se računa samo iz izvoda odabrane godine
        year_start = date(selected_year, 1, 1)
        year_end = date(selected_year, 12, 31)

        # Planirani iznosi po kontima nivoa 4 iz plana nabavke odabrane godine
        purchase_plan = next((plan for plan in purchase_plans if plan.year == selected_year), None)
        plan_accounts = []
        if purchase_plan:
            plan_accounts = db.session.query(
                PurchasePlanAccount.account_level_4_number,
                AccountLevel4.name,
                func.sum(PurchasePlanAccount.amount_1 + func.coalesce(PurchasePlanAccount.amount_2, 0)).label('planned_amount')
            ).join(
                AccountLevel4, AccountLevel4.number == PurchasePlanAccount.account_level_4_number
            ).filter(
                PurchasePlanAccount.purchase_plan_id == purchase_plan.id
            ).group_by(
                PurchasePlanAccount.account_level_4_number,
                AccountLevel4.name
            ).all()

        # Jedan zbirni upit: promet po kontu nivoa 6, tipu bankovnog računa i smeru stavke.
        # Uzimaju se svi budžetski računi (ne samo prvi) i svi sopstveni računi (own, other).
        movements = db.session.query(
            StatementItem.account_level_6_number,
            AccountLevel6.name,
            BankAccount.account_type,
            StatementItem.is_debit,
            func.count(StatementItem.id).label('item_count'),
            func.sum(StatementItem.amount).label('amount')
        ).join(
            BankStatement, BankStatement.id == StatementItem.bank_statement_id
        ).join(
            BankAccount, BankAccount.id == BankStatement.bank_account_id
        ).outerjoin(
            AccountLevel6, AccountLevel6.number == StatementItem.account_level_6_number
        ).filter(
            BankStatement.date.between(year_start, year_end),
            BankAccount.account_type.in_(['budget', 'own', 'other'])
        ).group_by(
            StatementItem.account_level_6_number,
            AccountLevel6.name,
            BankAccount.account_type,
            StatementItem.is_debit
        ).all()

        # Raspoređivanje prometa u kolone izveštaja po kontima nivoa 6 (u Python-u, Decimal)
        level_6 = {}
        unassigned_by_type = {}
        for row in movements:
            amount = row.amount or Decimal('0.00')
            is_budget = row.account_type == 'budget'

            # Stavke bez konta ne ulaze u izveštaj - samo se broje isplate radi napomene ispod tabele
            if not row.account_level_6_number:
                if row.is_debit:
                    group = 'budget' if is_budget else 'own'
                    entry = unassigned_by_type.setdefault(group, {'count': 0, 'amount': Decimal('0.00')})
                    entry['count'] += row.item_count
                    entry['amount'] += amount
                continue

            # Kolona u koju ide promet (ista semantika kao ranije)
            if is_budget and not row.is_debit:
                column = 'budget_received'   # uplate na budžetski račun
            elif is_budget:
                column = 'budget_spent'      # isplate sa budžetskog računa
            elif row.is_debit:
                column = 'own_spent'         # isplate sa sopstvenih računa
            else:
                continue                     # uplate na sopstvene račune nisu deo izveštaja

            child = level_6.setdefault(row.account_level_6_number, dict(
                _empty_amounts(),
                account_number=row.account_level_6_number,
                account_name=row.name or ''
            ))
            child[column] += amount

        for child in level_6.values():
            child['total_expense'] = child['budget_spent'] + child['own_spent']

        # Konta nivoa 4 iz plana; konta nivoa 6 se vezuju po prefiksu broja (kao ranije LIKE 'xxxx%')
        used_children = set()
        for account_data in plan_accounts:
            account_number = account_data.account_level_4_number
            children = [level_6[number] for number in sorted(level_6) if number.startswith(account_number)]
            used_children.update(child['account_number'] for child in children)
            accounts.append(_build_level_4_row(
                account_number, account_data.name,
                account_data.planned_amount or Decimal('0.00'),
                children, selected_year, in_plan=True
            ))

        # Konta rashoda (4xxx, 5xxx) sa prometom u godini kojih nema u planu - "van plana",
        # da potrošnja nikada ne nestane iz izveštaja. Konta prihoda (7xxx...) se ne prikazuju.
        off_plan = {}
        for number in sorted(level_6):
            if number not in used_children and number[:1] in ('4', '5'):
                off_plan.setdefault(number[:4], []).append(level_6[number])
        if off_plan:
            off_plan_names = dict(db.session.query(AccountLevel4.number, AccountLevel4.name).filter(
                AccountLevel4.number.in_(list(off_plan.keys()))
            ).all())
            for account_number, children in off_plan.items():
                accounts.append(_build_level_4_row(
                    account_number, off_plan_names.get(account_number, ''),
                    Decimal('0.00'), children, selected_year, in_plan=False
                ))

        # Redovi sortirani po broju konta
        accounts.sort(key=lambda account: account['account_number'])

        # Ažuriraj ukupne iznose
        for account in accounts:
            for key in totals:
                totals[key] += account[key]

        # Napomena o isplatama bez konta, po tipu računa
        type_labels = {'budget': 'sa budžetskog računa', 'own': 'sa sopstvenih računa'}
        for group in ('budget', 'own'):
            if group in unassigned_by_type:
                unassigned.append(dict(unassigned_by_type[group], label=type_labels[group]))

    return render_template('reports/report_1.html',
                            purchase_plans=purchase_plans,
                            accounts=accounts,
                            totals=totals,
                            unassigned=unassigned,
                            selected_year=selected_year)


def _empty_amounts():
    """Prazne novčane kolone izveštaja (bez plana i salda, koji postoje samo na nivou 4)."""
    return {
        'budget_received': Decimal('0.00'),
        'budget_spent': Decimal('0.00'),
        'own_spent': Decimal('0.00'),
        'total_expense': Decimal('0.00')
    }


def _build_level_4_row(account_number, account_name, planned_amount, children, year, in_plan):
    """Red konta nivoa 4: iznosi su zbir konta nivoa 6 ispod njega, saldo = planirano - budžet potrošeno."""
    row = _empty_amounts()
    for child in children:
        for key in row:
            row[key] += child[key]
    row.update({
        'year': year,
        'account_number': account_number,
        'account_name': account_name,
        'planned': planned_amount,
        'budget_balance': planned_amount - row['budget_spent'],
        'in_plan': in_plan,
        'children': children
    })
    return row
