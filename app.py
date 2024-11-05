from flask import Flask, render_template, request, flash, redirect, url_for
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Set a secret key for session management

# Database setup
DATABASE = 'trades.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            entry INTEGER NOT NULL,
            exit INTEGER NOT NULL,
            stop_loss INTEGER NOT NULL,
            most_adverse INTEGER NOT NULL,
            unrealized_profit INTEGER NOT NULL
        )''')
    print("Database initialized.")

init_db()

@app.route('/trade_entry', methods=['GET', 'POST'])
def trade_entry():
    if request.method == 'POST':
        # Retrieve the form data
        name = request.form.get('name')
        exit_value = request.form.get('exit')
        stop_loss = request.form.get('stop_loss')
        most_adverse = request.form.get('most_adverse')
        unrealized_profit = request.form.get('unrealized_profit')

        # Validate inputs
        if not validate_trade_entry(exit_value, stop_loss, most_adverse, unrealized_profit) or not name:
            flash("Invalid input values! Please ensure all fields are filled out correctly.")
            return redirect(url_for('trade_entry'))     #wenn nutzer speichern klickt wírd GET Request ausgelöst unse Seite erneut geladen, so dass Formular nicht doppelt gespeichert

        # Logic to save the trade entry to the database
        save_trade_to_db({
            'name': name,
            'entry': 0,  # Entry is set to 0
            'exit': exit_value,
            'stop_loss': stop_loss,
            'most_adverse': most_adverse,
            'unrealized_profit': unrealized_profit
        })

        flash("Trade entry recorded successfully!")
        return redirect(url_for('trade_entry'))

    trades = get_all_trades()
    return render_template('index.html', trades=trades)

def save_trade_to_db(trade_data):
    """Save a trade entry to the SQLite database."""
    with get_db() as conn:
        conn.execute('''INSERT INTO trades (name, entry, exit, stop_loss, most_adverse, unrealized_profit)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (trade_data['name'], trade_data['entry'], trade_data['exit'],
                      trade_data['stop_loss'], trade_data['most_adverse'], trade_data['unrealized_profit'])) #trade_data daten werden in trade_entry funktion erstellt

def validate_trade_entry(exit_value, stop_loss, most_adverse, unrealized_profit):
    try:
        exit_value = int(exit_value)
        stop_loss = int(stop_loss)
        most_adverse = int(most_adverse)
        unrealized_profit = int(unrealized_profit)

        # Check the constraints
        if exit_value < 0 or stop_loss >= 0 or most_adverse > 0 or unrealized_profit < 0:
            return False
    except (ValueError, TypeError):
        return False

    return True

def get_all_trades():
    """Retrieve all trade entries from the database."""
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM trades')
        trades = cursor.fetchall()
    return trades

@app.route('/')
def index():
    trades = get_all_trades()  # Lädt alle Trades
    return render_template('index.html', trades=trades)  # Übergibt die Daten an die Vorlage

if __name__ == '__main__':
    app.run(port=5001, debug=True)
