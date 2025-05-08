from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func, and_, or_
from decimal import Decimal
from arhivjugoslavije import db
from arhivjugoslavije.models import PurchasePlan, PurchasePlanAccount, AccountLevel4, StatementItem, BankAccount, BankStatement

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
    selected_year = request.args.get('year', None)
    if not selected_year and purchase_plans:
        selected_year = purchase_plans[0].year
    
    # Inicijalizacija rezultata
    accounts = []
    totals = {
        'planned': Decimal('0.00'),
        'budget_received': Decimal('0.00'),
        'budget_spent': Decimal('0.00'),
        'budget_balance': Decimal('0.00'),
        'own_spent': Decimal('0.00'),
        'total_expense': Decimal('0.00')
    }
    
    # Dobavljanje svih konta iz plana nabavki za odabranu godinu
    if selected_year:
        # Pronađi plan nabavke za odabranu godinu
        purchase_plan = PurchasePlan.query.filter_by(year=selected_year).first()
        
        if purchase_plan:
            # Dobavi sva konta iz plana nabavke
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
            
            # Pronađi budžetski račun (pretpostavljamo da je to račun sa ID 1)
            budget_account = BankAccount.query.filter(BankAccount.account_type=='budget').first()
            
            # Pronađi sopstvene račune (pretpostavljamo da su to računi sa ID 2 i 3)
            own_accounts = BankAccount.query.filter(BankAccount.account_type.in_(['own', 'other'])).all()
            own_account_ids = [acc.id for acc in own_accounts]
            
            # Za svaki konto iz plana nabavke, izračunaj potrebne vrednosti
            for account_data in plan_accounts:
                account_number = account_data.account_level_4_number
                account_name = account_data.name
                planned_amount = account_data.planned_amount or Decimal('0.00')
                
                # Izračunaj iznose koji su doznačeni na budžetski račun sa sopstvenih računa
                budget_received = Decimal('0.00')
                if budget_account and own_account_ids:
                    # Pronađi sve uplate na budžetski račun sa sopstvenih računa
                    budget_received_items = db.session.query(
                        func.sum(StatementItem.amount)
                    ).join(
                        BankStatement, BankStatement.id == StatementItem.bank_statement_id
                    ).filter(
                        BankStatement.bank_account_id == budget_account.id,
                        StatementItem.is_debit == False,  # Uplate (prihodi)
                        StatementItem.account_level_6_number.like(f'{account_number}%')  # Konta koja počinju sa account_number
                    ).scalar() or Decimal('0.00')
                    
                    budget_received = budget_received_items
                    print(f'{budget_received=}')
                
                # Izračunaj iznose koji su potrošeni sa budžetskog računa
                budget_spent = Decimal('0.00')
                if budget_account:
                    # Pronađi sve isplate sa budžetskog računa
                    budget_spent_items = db.session.query(
                        func.sum(StatementItem.amount)
                    ).join(
                        BankStatement, BankStatement.id == StatementItem.bank_statement_id
                    ).filter(
                        BankStatement.bank_account_id == budget_account.id,
                        StatementItem.is_debit == True,  # Isplate (rashodi)
                        StatementItem.account_level_6_number.like(f'{account_number}%')  # Konta koja počinju sa account_number
                    ).scalar() or Decimal('0.00')
                    
                    budget_spent = budget_spent_items
                
                # Izračunaj iznose koji su potrošeni sa sopstvenih računa
                own_spent = Decimal('0.00')
                if own_account_ids:
                    # Pronađi sve isplate sa sopstvenih računa
                    own_spent_items = db.session.query(
                        func.sum(StatementItem.amount)
                    ).join(
                        BankStatement, BankStatement.id == StatementItem.bank_statement_id
                    ).filter(
                        BankStatement.bank_account_id.in_(own_account_ids),
                        StatementItem.is_debit == True,  # Isplate (rashodi)
                        StatementItem.account_level_6_number.like(f'{account_number}%')  # Konta koja počinju sa account_number
                    ).scalar() or Decimal('0.00')
                    
                    own_spent = own_spent_items
                
                # Izračunaj saldo budžeta i ukupan trošak
                budget_balance = budget_received - budget_spent
                total_expense = budget_spent + own_spent
                
                # Dodaj podatke u listu
                account_data = {
                    'year': selected_year,
                    'account_number': account_number,
                    'account_name': account_name,
                    'planned': planned_amount,
                    'budget_received': budget_received,
                    'budget_spent': budget_spent,
                    'budget_balance': budget_balance,
                    'own_spent': own_spent,
                    'total_expense': total_expense
                }
                accounts.append(account_data)
                
                # Ažuriraj ukupne iznose
                totals['planned'] += planned_amount
                totals['budget_received'] += budget_received
                totals['budget_spent'] += budget_spent
                totals['budget_balance'] += budget_balance
                totals['own_spent'] += own_spent
                totals['total_expense'] += total_expense
    
    return render_template('reports/report_1.html', 
                            purchase_plans=purchase_plans, 
                            accounts=accounts, 
                            totals=totals,
                            selected_year=selected_year)