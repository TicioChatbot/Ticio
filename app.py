from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, EmailField
from wtforms.validators import InputRequired, Length, Email
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from time import sleep
from inference import inference

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)
socketio = SocketIO(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    active = db.Column(db.Boolean, default=False)
    pending = db.Column(db.Boolean, default=True)
    def get_link(self):
        return f"https://treli.co/payment-plan/?username=Ticio&product_id=751739&quantity=1&plan_id=0&plan_currency=COP&user_id={self.id}"

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(5000))
    answer = db.Column(db.String(5000))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=20)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=80)])
    submit = SubmitField('Login')

class SignupForm(FlaskForm):
    username = StringField('Nombre de usuario', validators=[InputRequired(), Length(min=4, max=20)])
    email = EmailField('Correo electrónico', validators=[InputRequired(), Email()])
    password = PasswordField('Contraseña', validators=[InputRequired(), Length(min=8, max=80)])
    submit = SubmitField('Registrarse')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('chat'))
        else:
            return 'Invalid username or password', 401
    return render_template('login.html', form=form)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data
        if User.query.filter_by(username=username).first():
            return 'Nombre de usuario ya existe', 400
        if User.query.filter_by(email=email).first():
            return 'Correo electrónico ya existe', 400
        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password_hash=password_hash)
        db.session.add(new_user)
        db.session.commit()
        user = User.query.filter_by(email=email).first()
        url = user.get_link()
        return redirect(url)
    return render_template('signup.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def chat():
    if not current_user.active:
        if current_user.pending:
            current_user.pending = False
            db.session.commit()
            return render_template('research.html')
        else:
            return redirect(url_for('subscription')) 
    else:
        return render_template('research.html')
    

@app.route('/subscription')
@login_required
def subscription():
    return render_template('subscription.html', user = current_user)

@app.post('/webhook')
def webhook(): 
    data = request.json
    if data.get('event_type') == 'payment_approved':
        id = data.get('content').get('meta_data')[0].get('value')
        user = User.query.filter_by(id =id).first()
        user.pending = False
        user.active = True 
        db.session.commit()
        return jsonify({'status': 'success'}), 200
    else: 
        id = data.get('content').get('meta_data')[0].get('value')
        user = User.query.filter_by(id =id).first()
        user.active = False
        db.session.commit()
        return jsonify({'status': 'success'}), 200

@socketio.on('message', namespace='/research')
def handle_research_message(message):
    response = inference(message)
    emit('response', response, namespace='/research')
    new = Message(question = message, answer = response)
    db.session.add(new)
    db.session.commit()

@app.route('/health', methods=['GET'])
def health_check():
    return 'OK', 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, host='0.0.0.0', port=8080, allow_unsafe_werkzeug= True)
