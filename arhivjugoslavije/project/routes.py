from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from arhivjugoslavije import db, app
from arhivjugoslavije.models import Project, ProjectAccount, AccountLevel6
from arhivjugoslavije.project.forms import ProjectRegisterForm, ProjectEditForm
from flask_login import login_required, current_user


project = Blueprint('project', __name__)


@project.route('/project_list')
@login_required
def project_list():
    projects = Project.query.all()
    create_form = ProjectRegisterForm()
    edit_form = ProjectEditForm()
    return render_template('project/project_list.html', 
                            projects=projects,
                            legend='Lista projekata',
                            title='Projekti',
                            create_form=create_form,
                            edit_form=edit_form)


@project.route('/create_project', methods=['GET', 'POST'])
@login_required
def create_project():
    endpoint = request.endpoint
    create_form = ProjectRegisterForm()
    edit_form = ProjectEditForm()
    if create_form.validate_on_submit():
        new_project = Project(
            name=create_form.name.data,
            note=create_form.note.data,
            year=create_form.year.data,
            archived=False
        )
        db.session.add(new_project)
        db.session.commit()
        flash('Projekat uspešno kreiran.', 'success')
        return redirect(url_for('project.project_list'))
    return render_template('project/project_list.html', 
                            endpoint=endpoint,
                            create_form=create_form,
                            edit_form=edit_form,
                            legend='Kreiranje projekta',
                            title='Kreiranje projekta')


@project.route('/edit_project/<int:project_id>', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    edit_form = ProjectEditForm()
    
    if edit_form.validate_on_submit():
        project.name = edit_form.name.data
        project.note = edit_form.note.data
        project.year = edit_form.year.data
        project.archived = bool(int(edit_form.archived.data))
        
        db.session.commit()
        flash('Projekat uspešno izmenjen.', 'success')
        return redirect(url_for('project.project_list'))
        
    return redirect(url_for('project.project_list'))


@project.route('/get_project/<int:project_id>')
@login_required
def get_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    project_accounts = ProjectAccount.query.filter_by(project_id=project_id).order_by(ProjectAccount.id.asc())
    sum_data_dict = sum_account_data(project_accounts)
    
    # Konvertuj sum_data_dict u format koji je kompatibilan sa JavaScript kodom
    sum_data_list = []
    for key, value in sum_data_dict.items():
        sum_data_list.append({
            'account': value['account'],
            'amount': float(value['amount'])
        })
    
    return jsonify({
        'name': project.name,
        'note': project.note,
        'amount': float(project.amount) if project.amount else None,
        'year': project.year,   
        'archived': project.archived,
        'sum_data': sum_data_list
    })

def sum_account_data(project_accounts):
    sum_data = {}
    
    for account in project_accounts:
        account_level_4_number = account.account_level_6.account_level_4.number
        
        if account_level_4_number not in sum_data:
            sum_data[account_level_4_number] = {
                'account': account_level_4_number,
                'amount': account.amount
            }
        else:
            sum_data[account_level_4_number]['amount'] += account.amount
    return sum_data

@project.route('/project_accounts/<int:project_id>')
@login_required
def project_accounts(project_id):
    project = Project.query.get_or_404(project_id)
    project_accounts = ProjectAccount.query.filter_by(project_id=project_id).order_by(ProjectAccount.id.asc())
    sum_data = sum_account_data(project_accounts)
    accounts = AccountLevel6.query.order_by(AccountLevel6.number).all()
    accounts_list = [{
        'number': account.number,
        'name': account.name,
    } for account in accounts]
    return render_template('project/project_accounts.html', 
                            project=project,
                            project_accounts=project_accounts,
                            sum_data=sum_data,
                            accounts_list=accounts_list,
                            legend='Detalji projekta',
                            title='Detalji projekta')


@project.route('/get_accounts_level6')
@login_required
def get_accounts_level6():
    accounts = AccountLevel6.query.order_by(AccountLevel6.number).all()
    accounts_list = [{
        'number': account.number,
        'name': account.name,
        'account_level_4_number': account.account_level_4_number
    } for account in accounts]
    
    return jsonify({'success': True, 'accounts': accounts_list})


@project.route('/add_project_account', methods=['POST'])
@login_required
def add_project_account():
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Nema podataka'}), 400
    
    project_id = data.get('project_id')
    account_level_6_number = data.get('account_level_6_number')
    amount = data.get('amount')
    note = data.get('note')
    
    # Validacija podataka
    if not project_id or not account_level_6_number or not amount:
        return jsonify({'success': False, 'message': 'Projekat, konto i iznos su obavezni'}), 400
    
    # Provera da li projekat postoji
    project = Project.query.get(project_id)
    if not project:
        return jsonify({'success': False, 'message': f'Projekat sa ID {project_id} ne postoji'}), 404
    
    # Provera da li konto postoji
    account = AccountLevel6.query.get(account_level_6_number)
    if not account:
        return jsonify({'success': False, 'message': f'Konto {account_level_6_number} ne postoji'}), 404
    
    try:
        # Kreiranje novog konta projekta
        new_project_account = ProjectAccount(
            project_id=project_id,
            account_level_6_number=account_level_6_number,
            amount=amount,
            note=note
        )
        db.session.add(new_project_account)
        db.session.commit()
        
        # Dodajemo flash poruku koja će biti prikazana nakon redirekcije
        flash(f'Konto uspešno dodat projektu', 'success')
        
        return jsonify({
            'success': True, 
            'message': f'Konto uspešno dodat projektu',
            'project_account': {
                'id': new_project_account.id,
                'project_id': new_project_account.project_id,
                'account_level_6_number': new_project_account.account_level_6_number,
                'amount': float(new_project_account.amount),
                'note': new_project_account.note
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Greška pri dodavanju konta projektu: {str(e)}'}), 500


@project.route('/get_project_account/<int:account_id>', methods=['GET'])
@login_required
def get_project_account(account_id):
    # Pronalazimo konto projekta po ID-u
    project_account = ProjectAccount.query.get_or_404(account_id)
    
    # Vraćamo podatke o kontu kao JSON
    return jsonify({
        'success': True,
        'project_account': {
            'id': project_account.id,
            'project_id': project_account.project_id,
            'account_level_6_number': project_account.account_level_6_number,
            'amount': float(project_account.amount) if project_account.amount else None,
            'note': project_account.note
        }
    })


@project.route('/edit_project_account/<int:account_id>', methods=['POST'])
@login_required
def edit_project_account(account_id):
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Nema podataka'}), 400
    
    account_level_6_number = data.get('account_level_6_number')
    amount = data.get('amount')
    note = data.get('note')
    
    # Validacija podataka
    if not account_level_6_number or not amount:
        return jsonify({'success': False, 'message': 'Konto i iznos su obavezni'}), 400
    
    # Pronalazimo konto projekta koji želimo da izmenimo
    project_account = ProjectAccount.query.get_or_404(account_id)
    
    # Provera da li konto postoji
    account = AccountLevel6.query.get(account_level_6_number)
    if not account:
        return jsonify({'success': False, 'message': f'Konto {account_level_6_number} ne postoji'}), 404
    
    try:
        # Ažuriranje konta projekta
        project_account.account_level_6_number = account_level_6_number
        project_account.amount = amount
        project_account.note = note
        db.session.commit()
        
        # Dodajemo flash poruku koja će biti prikazana nakon redirekcije
        flash(f'Konto uspešno izmenjen', 'success')
        
        return jsonify({
            'success': True, 
            'message': f'Konto uspešno izmenjen',
            'project_account': {
                'id': project_account.id,
                'project_id': project_account.project_id,
                'account_level_6_number': project_account.account_level_6_number,
                'amount': float(project_account.amount),
                'note': project_account.note
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Greška pri izmeni konta projekta: {str(e)}'}), 500