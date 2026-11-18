from flask import Blueprint, render_template, request, redirect, url_for, flash
from arhivjugoslavije.models import PurchasePlan, PurchasePlanAccount, AccountLevel4, FUNDING_SOURCES, FUNDING_SOURCE_CODES
from arhivjugoslavije import db
from flask_login import login_required
from datetime import datetime

purchase_plan = Blueprint('purchase_plan', __name__)


def _selected_source(value):
    """Izvor finansiranja iz zahteva; nepoznata vrednost vraća izvor 01."""
    return value if value in FUNDING_SOURCE_CODES else FUNDING_SOURCE_CODES[0]


def _back_to_plan(purchase_plan_id, source):
    return redirect(url_for("purchase_plan.edit_purchase_plan", purchase_plan_id=purchase_plan_id, izvor=source))

@purchase_plan.route("/purchase_plan_list", methods=["GET"])
@login_required
def purchase_plan_list():
    current_year = datetime.now().year
    purchase_plans = PurchasePlan.query.order_by(PurchasePlan.year.desc()).all()
    return render_template("purchase_plan/purchase_plan_list.html",
                           purchase_plans=purchase_plans,
                           funding_sources=FUNDING_SOURCES,
                           current_year=current_year)


@purchase_plan.route("/create_purchase_plan", methods=["GET", "POST"])
@login_required
def create_purchase_plan():
    """Plan nabavke je jedan po godini, a izvori 01, 04 i 13 su kartice unutar njega.
    Ako plan za godinu već postoji, otvara se na kartici izabranog izvora umesto da se pravi novi."""
    if request.method == "POST":
        source = _selected_source(request.form.get("source"))
        try:
            year = int(request.form["year"])
        except (KeyError, ValueError):
            flash("Unesite ispravnu godinu.", "danger")
            return redirect(url_for("purchase_plan.purchase_plan_list"))
        existing_plan = PurchasePlan.query.filter_by(year=year).first()
        if existing_plan:
            flash(f"Plan nabavke za {year}. godinu već postoji. Otvoren je izvor {source} - konta za ovaj izvor unesite dugmetom „Dodaj konto“.", "info")
            return _back_to_plan(existing_plan.id, source)
        purchase_plan = PurchasePlan(year=year)
        db.session.add(purchase_plan)
        db.session.commit()
        flash(f"Plan nabavke za {year}. godinu je kreiran. Otvoren je izvor {source} - konta unesite dugmetom „Dodaj konto“.", "success")
        return _back_to_plan(purchase_plan.id, source)
    return redirect(url_for("purchase_plan.purchase_plan_list"))


@purchase_plan.route("/edit_purchase_plan/<int:purchase_plan_id>", methods=["GET", "POST"])
@login_required
def edit_purchase_plan(purchase_plan_id):
    purchase_plan = PurchasePlan.query.get_or_404(purchase_plan_id)
    accounts_level_4 = AccountLevel4.query.all()
    current_year = datetime.now().year
    readonly = purchase_plan.year < current_year
    if readonly:
        flash(f"Plan nabavke za {purchase_plan.year}. godinu je moguće samo pregledati. Izmene nisu dozvoljene.", "warning")
    selected_source = _selected_source(request.args.get("izvor"))
    # Konta izabranog izvora, sortirana po broju konta
    plan_accounts = sorted(
        [account for account in purchase_plan.purchase_plan_accounts if account.source == selected_source],
        key=lambda account: account.account_level_4_number
    )
    amount_for_regular_activity = sum([account.amount_1 or 0 for account in plan_accounts])
    amount_for_program_activity = sum([account.amount_2 or 0 for account in plan_accounts])
    # Ukupno po izvorima, za natpise na karticama
    source_totals = {source["code"]: 0 for source in FUNDING_SOURCES}
    for account in purchase_plan.purchase_plan_accounts:
        if account.source in source_totals:
            source_totals[account.source] += (account.amount_1 or 0) + (account.amount_2 or 0)
    return render_template("purchase_plan/edit_purchase_plan.html",
                            legend="Izmena plana nabavke",
                            title="Izmena plana nabavke",
                            purchase_plan=purchase_plan, 
                            plan_accounts=plan_accounts,
                            funding_sources=FUNDING_SOURCES,
                            selected_source=selected_source,
                            source_totals=source_totals,
                            accounts_level_4=accounts_level_4, 
                            amount_for_regular_activity=amount_for_regular_activity,
                            amount_for_program_activity=amount_for_program_activity,
                            readonly=readonly)


@purchase_plan.route("/delete_purchase_plan/<int:purchase_plan_id>", methods=["POST"])
@login_required
def delete_purchase_plan(purchase_plan_id):
    purchase_plan = PurchasePlan.query.get_or_404(purchase_plan_id)
    purchase_plan_accounts = PurchasePlanAccount.query.filter_by(purchase_plan_id=purchase_plan_id).all()
    for account in purchase_plan_accounts:
        db.session.delete(account)
    db.session.delete(purchase_plan)
    db.session.commit()
    flash("Plan nabavke je uspešno obrisan.", "success")
    return redirect(url_for("purchase_plan.purchase_plan_list"))


@purchase_plan.route("/add_account/<int:purchase_plan_id>", methods=["POST"])
@login_required
def add_account(purchase_plan_id):
    purchase_plan = PurchasePlan.query.get_or_404(purchase_plan_id)
    
    account_level_4_number = request.form["account_level_4_number"]
    source = _selected_source(request.form.get("source"))
    amount_1 = request.form["amount_1"] or 0
    amount_2 = request.form["amount_2"] or 0
    note = request.form["note"]
    
    # Provera da li konto već postoji u planu nabavke za isti izvor
    existing_account = PurchasePlanAccount.query.filter_by(
        purchase_plan_id=purchase_plan_id, 
        account_level_4_number=account_level_4_number,
        source=source
    ).first()
    
    if existing_account:
        flash(f"Ovaj konto već postoji u planu nabavke za izvor {source}.", "danger")
        return _back_to_plan(purchase_plan_id, source)
    
    # Provera da li konto postoji u bazi
    account_level_4 = AccountLevel4.query.filter_by(number=account_level_4_number).first()
    if not account_level_4:
        flash("Izabrani konto ne postoji.", "danger")
        return _back_to_plan(purchase_plan_id, source)
    
    new_account = PurchasePlanAccount(
        purchase_plan_id=purchase_plan_id,
        account_level_4_number=account_level_4_number,
        source=source,
        amount_1=amount_1,
        amount_2=amount_2,
        note=note
    )
    
    db.session.add(new_account)
    db.session.commit()
    flash("Konto je uspešno dodat u plan nabavke.", "success")
    return _back_to_plan(purchase_plan_id, source)


@purchase_plan.route("/edit_account/<int:purchase_plan_id>/<int:account_id>", methods=["POST"])
@login_required
def edit_account(purchase_plan_id, account_id):
    account = PurchasePlanAccount.query.get_or_404(account_id)
    
    amount_1 = request.form["amount_1"] or 0
    amount_2 = request.form["amount_2"] or 0
    note = request.form["note"]
    
    account.amount_1 = amount_1
    account.amount_2 = amount_2
    account.note = note
    
    db.session.commit()
    flash("Konto je uspešno ažuriran.", "success")
    return _back_to_plan(purchase_plan_id, account.source)


@purchase_plan.route("/delete_account/<int:purchase_plan_id>/<int:account_id>", methods=["POST"])
@login_required
def delete_account(purchase_plan_id, account_id):
    account = PurchasePlanAccount.query.get_or_404(account_id)
    source = account.source
    db.session.delete(account)
    db.session.commit()
    flash("Konto je uspešno obrisan iz plana nabavke.", "success")
    return _back_to_plan(purchase_plan_id, source)
