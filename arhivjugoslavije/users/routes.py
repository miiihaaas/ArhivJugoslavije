from flask import Blueprint, render_template, flash, redirect, url_for, request
from arhivjugoslavije import db, app, bcrypt, mail
from arhivjugoslavije.users.forms import LoginForm, RequestResetForm, ResetPasswordForm
from arhivjugoslavije.models import User
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message


users = Blueprint('users', __name__)


@users.route('/user_list', methods=['GET', 'POST'])
@login_required
def user_list():
    # if current_user.user_type != 'admin':
    #     flash('Nemate prava za pristup ovom stranici.', 'danger')
    #     return redirect(url_for('main.home'))
    users = User.query.all()
    number_of_users = User.query.count()
    return render_template('users/user_list.html', 
                            users=users,
                            number_of_users=number_of_users,
                            legend='Lista korisnika',
                            title='Korisnici')


@users.route('/register_user', methods=['GET', 'POST'])
@login_required
def register_user():
    if current_user.user_type != 'admin':
        flash('Nemate prava za pristup ovom stranici.', 'danger')
        return redirect(url_for('main.home'))
    name = request.form.get('name').capitalize()
    surname = request.form.get('surname').capitalize()
    email = request.form.get('email')
    hashed_password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')

    new_user = User(
        name=name, 
        surname=surname, 
        email=email, 
        password=hashed_password
    )
    
    db.session.add(new_user)
    db.session.commit()
    flash(f'Korisnik {name} {surname} je uspešno registrovan!', 'success')
    return redirect(url_for('users.user_list'))


@users.route('/edit_user', methods=['GET', 'POST'])
@login_required
def edit_user():
    if current_user.user_type != 'admin':
        flash('Nemate prava za pristup ovom stranici.', 'danger')
        return redirect(url_for('main.home'))
    user_id = request.form.get('user_id')
    user = User.query.get_or_404(user_id)
    user.name = request.form.get('name').capitalize()
    user.surname = request.form.get('surname').capitalize()
    user.email = request.form.get('email')

    db.session.commit()

    flash(f'Profil korisnika {user.name} {user.surname} je uspešno izmenjen', 'success')
    return redirect(url_for('users.user_list'))


@users.route('/delete_user', methods=['GET', 'POST'])
@login_required
def delete_user():
    if current_user.user_type != 'admin':
        flash('Nemate prava za pristup ovom stranici.', 'danger')
        return redirect(url_for('main.home'))
    user_id = request.form.get('delete_user_id')
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f'Profil korisnika {user.name} {user.surname} je uspešno obrisan', 'success')
    return redirect(url_for('users.user_list'))


@users.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            flash(f'Uspešno ste se prijavili, {user.name}.', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.home'))
        else:
            flash('Pogrešan mejl ili lozinka.', 'danger')
    return render_template('users/login.html', 
                            legend='Prijavljivanje', 
                            title='Prijava', 
                            form=form)


@users.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('users.login'))


def send_reset_email(user, is_create):
    token = user.get_reset_token()
    if is_create:
        subject = 'Zahtev za kreiranje naloga'
        body = f'''Da biste kreirali lozinku, kliknite na sledeći link:   
    {url_for('users.reset_token', token=token, _external=True)}
    ''' 
    else:
        subject = 'Zahtev za resetovanje lozinke'
        body = f'''Da biste resetovali lozinku, kliknite na sledeći link:
    {url_for('users.reset_token', token=token, _external=True)}
    '''
    msg = Message(subject, sender='noreply@uplatnice.online', recipients=[user.email])
    msg.body = body
    mail.send(msg)


@users.route('/create_password', methods=['GET', 'POST'])
@users.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if 'create_password' in request.url:
        is_create = True
        title = 'Kreiranje lozinke'
        legend = 'Kreiranje lozinke'
    else:
        is_create = False
        title = 'Resetovanje lozinke'
        legend = 'Resetovanje lozinke'
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user, is_create)
        if is_create:
            flash('Zahtev za kreiranje naloga je poslan na mejl.', 'info')
        else:
            flash('Zahtev za resetovanje lozinke je poslan na mejl.', 'info')
        return redirect(url_for('users.login'))
    return render_template('users/reset_request.html',
                            title=title,
                            form=form,
                            is_create=is_create,
                            legend=legend)


@users.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('Ovo je nevažeći ili istekli token.', 'warning')
        return redirect(url_for('users.reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash('Lozinka je uspešno resetovana.', 'success')
        return redirect(url_for('users.login'))
    return render_template('users/reset_password.html',
                            title='Resetovanje lozinke',
                            form=form)