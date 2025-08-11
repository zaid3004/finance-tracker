from flask import Flask, render_template, redirect, url_for, request, flash, send_file, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from dotenv import load_dotenv
import pandas as pd
import os
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///instance/finance.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    transactions = db.relationship('Transaction', backref='user', lazy=True)

# Transaction model
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10), nullable=False)  # "income" or "expense"
    category = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(10), nullable=False)  # DD-MM-YYYY
    account = db.Column(db.String(100), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        flash("Registered successfully. Please log in.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and bcrypt.check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash("Invalid username or password", "danger")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        t = Transaction(
            type=request.form['type'],
            category=request.form['category'],
            amount=float(request.form['amount'].replace(",", "")),
            date=request.form['date'],
            account=request.form['account'],
            user_id=current_user.id
        )
        db.session.add(t)
        db.session.commit()
        flash("Transaction added", "success")
        return redirect(url_for('dashboard'))

    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    balance = sum(t.amount if t.type == 'income' else -t.amount for t in transactions)
    return render_template('dashboard.html', transactions=transactions, balance=balance)

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    t = Transaction.query.get_or_404(id)
    if t.user_id != current_user.id:
        flash("Unauthorized", "danger")
        return redirect(url_for('dashboard'))
    db.session.delete(t)
    db.session.commit()
    flash("Transaction deleted", "success")
    return redirect(url_for('dashboard'))

@app.route('/export')
@login_required
def export():
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    data = [{
        'Type': t.type,
        'Category': t.category,
        'Amount': t.amount,
        'Date': t.date,
        'Account': t.account
    } for t in transactions]
    df = pd.DataFrame(data)
    file_path = "transactions_export.csv"
    df.to_csv(file_path, index=False)
    return send_file(file_path, as_attachment=True)

# Create DB tables if they don't exist
@app.before_first_request
def create_tables():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
