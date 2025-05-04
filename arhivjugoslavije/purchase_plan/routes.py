from flask import Blueprint, render_template, request, redirect, url_for, flash
from arhivjugoslavije.models import PurchasePlan, PurchasePlanAccount, AccountLevel4
from arhivjugoslavije import db
from flask_login import login_required
from datetime import datetime

purchase_plan = Blueprint('purchase_plan', __name__)

@login_required
@purchase_plan.route("/purchase_plan_list", methods=["GET"])
def purchase_plan_list():
    current_year = datetime.now().year
    purchase_plans = PurchasePlan.query.all()
    plans_with_readonly = []
    for plan in purchase_plans:
        readonly = plan.year < current_year
        plans_with_readonly.append({"plan": plan, "readonly": readonly})
    return render_template("purchase_plan/purchase_plan_list.html", purchase_plans=purchase_plans, plans_with_readonly=plans_with_readonly, current_year=current_year)



@login_required
@purchase_plan.route("/create_purchase_plan", methods=["GET", "POST"])
def create_purchase_plan():
    if request.method == "POST":
        year = request.form["year"]
        purchase_plan = PurchasePlan(year=year)
        db.session.add(purchase_plan)
        db.session.commit()
        flash("Plan nabavke je uspešno kreiran.", "success")
        return redirect(url_for("purchase_plan.edit_purchase_plan", purchase_plan_id=purchase_plan.id))
    return render_template("purchase_plan/create_purchase_plan.html")


@login_required
@purchase_plan.route("/edit_purchase_plan/<int:purchase_plan_id>", methods=["GET", "POST"])
def edit_purchase_plan(purchase_plan_id):
    purchase_plan = PurchasePlan.query.get_or_404(purchase_plan_id)
    accounts_level_4 = AccountLevel4.query.all()
    current_year = datetime.now().year
    readonly = purchase_plan.year < current_year
    if readonly:
        flash(f"Plan nabavke za {purchase_plan.year}. godinu je moguće samo pregledati. Izmene nisu dozvoljene.", "warning")
    amount_for_regular_activity = sum([account.amount_1 for account in purchase_plan.purchase_plan_accounts])
    amount_for_program_activity = sum([account.amount_2 for account in purchase_plan.purchase_plan_accounts])
    return render_template("purchase_plan/edit_purchase_plan.html",
                            legend="Izmena plana nabavke",
                            title="Izmena plana nabavke",
                            purchase_plan=purchase_plan, 
                            accounts_level_4=accounts_level_4, 
                            amount_for_regular_activity=amount_for_regular_activity,
                            amount_for_program_activity=amount_for_program_activity,
                            readonly=readonly)


@login_required
@purchase_plan.route("/delete_purchase_plan/<int:purchase_plan_id>", methods=["POST"])
def delete_purchase_plan(purchase_plan_id):
    purchase_plan = PurchasePlan.query.get_or_404(purchase_plan_id)
    purchase_plan_accounts = PurchasePlanAccount.query.filter_by(purchase_plan_id=purchase_plan_id).all()
    for account in purchase_plan_accounts:
        db.session.delete(account)
    db.session.delete(purchase_plan)
    db.session.commit()
    flash("Plan nabavke je uspešno obrisan.", "success")
    return redirect(url_for("purchase_plan.purchase_plan_list"))


@login_required
@purchase_plan.route("/add_account/<int:purchase_plan_id>", methods=["POST"])
def add_account(purchase_plan_id):
    purchase_plan = PurchasePlan.query.get_or_404(purchase_plan_id)
    
    account_level_4_number = request.form["account_level_4_number"]
    amount_1 = request.form["amount_1"] or 0
    amount_2 = request.form["amount_2"] or 0
    note = request.form["note"]
    
    # Provera da li konto već postoji u planu nabavke
    existing_account = PurchasePlanAccount.query.filter_by(
        purchase_plan_id=purchase_plan_id, 
        account_level_4_number=account_level_4_number
    ).first()
    
    if existing_account:
        flash("Ovaj konto već postoji u planu nabavke.", "danger")
        return redirect(url_for("purchase_plan.edit_purchase_plan", purchase_plan_id=purchase_plan_id))
    
    # Provera da li konto postoji u bazi
    account_level_4 = AccountLevel4.query.filter_by(number=account_level_4_number).first()
    if not account_level_4:
        flash("Izabrani konto ne postoji.", "danger")
        return redirect(url_for("purchase_plan.edit_purchase_plan", purchase_plan_id=purchase_plan_id))
    
    new_account = PurchasePlanAccount(
        purchase_plan_id=purchase_plan_id,
        account_level_4_number=account_level_4_number,
        amount_1=amount_1,
        amount_2=amount_2,
        note=note
    )
    
    db.session.add(new_account)
    db.session.commit()
    flash("Konto je uspešno dodat u plan nabavke.", "success")
    return redirect(url_for("purchase_plan.edit_purchase_plan", purchase_plan_id=purchase_plan_id))


@login_required
@purchase_plan.route("/edit_account/<int:purchase_plan_id>/<int:account_id>", methods=["POST"])
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
    return redirect(url_for("purchase_plan.edit_purchase_plan", purchase_plan_id=purchase_plan_id))


@login_required
@purchase_plan.route("/delete_account/<int:purchase_plan_id>/<int:account_id>", methods=["POST"])
def delete_account(purchase_plan_id, account_id):
    account = PurchasePlanAccount.query.get_or_404(account_id)
    db.session.delete(account)
    db.session.commit()
    flash("Konto je uspešno obrisan iz plana nabavke.", "success")
    return redirect(url_for("purchase_plan.edit_purchase_plan", purchase_plan_id=purchase_plan_id))
