from flask import Flask, render_template, request, flash, redirect, url_for, session
from functools import wraps
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import numpy as np  # Add this import for NumPy

# Add these constants at the top of your file with your other imports
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"  # You should change this in production


app = Flask(__name__)
app.secret_key = 'test'  # Set a secret key for session management

# Database setup
DATABASE = 'trades.db'


def fix_users_table():
    """Fix the users table structure and data"""
    with sqlite3.connect('trades.db') as conn:
        # Create temporary table with correct structure
        conn.execute('''CREATE TABLE IF NOT EXISTS users_temp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN NOT NULL DEFAULT 0
        )''')

        try:
            # Try to copy data from old table if it exists
            conn.execute('''INSERT INTO users_temp (username, password_hash, is_admin)
                          SELECT username, password, is_admin FROM users''')
        except sqlite3.Error:
            # If old table doesn't exist or has different structure,
            # just create admin user in new table
            password_hash = generate_password_hash('admin123')
            conn.execute('''INSERT INTO users_temp (username, password_hash, is_admin)
                          VALUES (?, ?, ?)''', ('admin', password_hash, True))

        # Drop old table and rename new one
        conn.execute('DROP TABLE IF EXISTS users')
        conn.execute('ALTER TABLE users_temp RENAME TO users')
        conn.commit()



def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        # Create tables first
        conn.execute('''CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            entry INTEGER NOT NULL,
            exit INTEGER NOT NULL,
            stop_loss INTEGER NOT NULL,
            most_adverse INTEGER NOT NULL,
            unrealized_profit INTEGER NOT NULL,
            market TEXT NOT NULL
         )''')

        conn.execute('''CREATE TABLE IF NOT EXISTS strategy_config (
            id INTEGER PRIMARY KEY,
            config_name TEXT UNIQUE,
            "values" TEXT NOT NULL
        )''')

        # Create users table with explicit column definitions
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN NOT NULL DEFAULT 0
        )''')

        # Explicitly check for existing admin user
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users WHERE username = ?', (DEFAULT_ADMIN_USERNAME,))
        user_exists = cursor.fetchone()[0]

        if not user_exists:
            try:
                password_hash = generate_password_hash(DEFAULT_ADMIN_PASSWORD)
                cursor.execute('''INSERT INTO users (username, password_hash, is_admin)
                                VALUES (?, ?, ?)''', (DEFAULT_ADMIN_USERNAME, password_hash, True))
                conn.commit()
                print("Default admin user created successfully.")
            except sqlite3.Error as e:
                    print(f"Error creating admin user: {e}")
        else:
            print("Admin user already exists.")

    print("Database initialized.")




    print("Database initialized.")

def create_strategy_performance_table():
    """Create a table for storing strategy performance results."""
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS strategy_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stop_loss INTEGER,
                target INTEGER,
                total_profit REAL,
                winrate REAL,
                profit_factor REAL
            )
        ''')
    print("strategy_performance table is ready or already exists.")

def create_markets_table():
    """Create a table for storing markets."""
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS markets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        ''')
    print("Markets table is ready or already exists.")

# Initialize all tables
init_db()
fix_users_table()
create_strategy_performance_table()
create_markets_table()

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        with get_db() as conn:
            cursor = conn.execute(
                'SELECT password_hash FROM users WHERE username = ?',
                (username,)
            )
            user = cursor.fetchone()

            if user and check_password_hash(user['password_hash'], password):
                session['logged_in'] = True
                session['username'] = username
                flash('Login successful!', 'success')
                return redirect(url_for('index'))

            flash('Invalid username or password.', 'danger')

    return render_template('login.html')



@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))




def simulate_strategy(stop_loss, target, trades):
    """
    Simulates both hypothetical and actual trade performance.
    Returns both sets of results.
    """
    print("Starting strategy simulation...")
    for trade in trades:
        if trade['entry'] != 0:
            raise ValueError("All trades must have an entry price of 0.")
        print(
            f"Evaluating trade: {trade['entry']}, {trade['exit']}, {trade['stop_loss']}, {trade['most_adverse']}, {trade['unrealized_profit']}")

    # Arrays to store both hypothetical and actual profits
    hypothetical_profits = []
    actual_profits = []

    # Iterate over valid trades
    for trade in trades:
        entry = trade['entry']
        exit_value = trade['exit']
        trade_stop_loss = trade['stop_loss']  # Individual trade's stop loss
        most_adverse = trade['most_adverse']
        unrealized_profit = trade['unrealized_profit']

        # Calculate hypothetical profit
        if most_adverse <= entry + stop_loss:
            hypothetical_profit = stop_loss
        elif unrealized_profit >= entry + target:
            hypothetical_profit = target
        else:
            hypothetical_profit = stop_loss

        hypothetical_profits.append(hypothetical_profit)

        # Calculate actual profit
        if most_adverse <= entry + trade_stop_loss:
            actual_profit = trade_stop_loss
        else:
            actual_profit = exit_value

        actual_profits.append(actual_profit)

    return np.array(hypothetical_profits), np.array(actual_profits)

def analyze_strategies(trades, market=None):
    """
    Analyze various stop loss and target combinations and actual trade performance.
    Returns the best strategy, performance results, and actual performance metrics.
    """
    stop_loss_values = STOP_LOSS_VALUES
    target_values = TARGET_VALUES

    best_strategy = None
    best_performance = -np.inf
    performance_results = []

    # Filter trades by market if specified
    if market:
        trades = [trade for trade in trades if trade['market'] == market]

    queried_trade_count = len(trades)

    # Initialize actual performance metrics
    actual_performance = None

    for stop_loss in stop_loss_values:
        for target in target_values:
            hypothetical_profits, actual_profits = simulate_strategy(stop_loss, target, trades)

            # Calculate hypothetical metrics
            total_profit = hypothetical_profits.sum()
            winrate = (hypothetical_profits > 0).mean() * 100
            profit_factor = (hypothetical_profits[hypothetical_profits > 0].sum() /
                           abs(hypothetical_profits[hypothetical_profits < 0].sum())) if (
                               hypothetical_profits < 0).sum() > 0 else float('inf')

            # Store hypothetical results
            performance_results.append({
                'Stop Loss': stop_loss,
                'Target': target,
                'Total Profit': total_profit,
                'Winrate': winrate,
                'Profit Factor': profit_factor
            })

            # Update best strategy if current is better
            if total_profit > best_performance:
                best_performance = total_profit
                best_strategy = performance_results[-1].copy()

            # Calculate actual performance metrics (only need to do this once)
            if actual_performance is None:
                actual_total_profit = actual_profits.sum()
                actual_winrate = (actual_profits > 0).mean() * 100
                actual_profit_factor = (actual_profits[actual_profits > 0].sum() /
                                     abs(actual_profits[actual_profits < 0].sum())) if (
                                         actual_profits < 0).sum() > 0 else float('inf')

                actual_performance = {
                    'Total Profit': actual_total_profit,
                    'Winrate': actual_winrate,
                    'Profit Factor': actual_profit_factor
                }

    return best_strategy, performance_results, actual_performance, queried_trade_count

def validate_trade_entry(exit_value, stop_loss, most_adverse, unrealized_profit):
    try:
        exit_value = int(exit_value)
        stop_loss = int(stop_loss)
        most_adverse = int(most_adverse)
        unrealized_profit = int(unrealized_profit)

        # Check the constraints
        if stop_loss >= 0 or most_adverse > 0 or unrealized_profit < 0:
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

def save_trade_to_db(trade_data):
    """Save a trade entry to the SQLite database."""
    with get_db() as conn:
        conn.execute('''INSERT INTO trades (name, entry, exit, stop_loss, most_adverse, unrealized_profit, market)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (trade_data['name'], trade_data['entry'], trade_data['exit'],
                     trade_data['stop_loss'], trade_data['most_adverse'], trade_data['unrealized_profit'],
                     trade_data['market']))

def delete_trade_from_db(trade_id):
    """Delete a trade from the database."""
    with get_db() as conn:
        conn.execute('DELETE FROM trades WHERE id = ?', (trade_id,))
    print(f"Trade with ID {trade_id} deleted.")

def get_all_markets():
    """Retrieve all markets from the database."""
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM markets ORDER BY name')
        return cursor.fetchall()

def add_market_to_db(market_name):
    """Add a new market to the database."""
    try:
        with get_db() as conn:
            conn.execute('INSERT INTO markets (name) VALUES (?)', (market_name,))
        return True, "Market added successfully!"
    except sqlite3.IntegrityError:
        return False, "Market already exists!"
    except Exception as e:
        return False, f"Error adding market: {str(e)}"

def delete_market_from_db(market_id):
    """Delete a market from the database."""
    try:
        with get_db() as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM trades WHERE market = (SELECT name FROM markets WHERE id = ?)',
                                (market_id,))
            if cursor.fetchone()[0] > 0:
                return False, "Cannot delete market that has associated trades!"

            conn.execute('DELETE FROM markets WHERE id = ?', (market_id,))
        return True, "Market deleted successfully!"
    except Exception as e:
        return False, f"Error deleting market: {str(e)}"

def save_strategy_performance_to_db(best_strategy, performance_results):
    """Save the best strategy and all performance results to the SQLite database."""
    with get_db() as conn:
        # Save the best strategy
        conn.execute('''INSERT INTO strategy_performance (stop_loss, target, total_profit, winrate, profit_factor)
                       VALUES (?, ?, ?, ?, ?)''',
                    (best_strategy['Stop Loss'], best_strategy['Target'], best_strategy['Total Profit'],
                     best_strategy['Winrate'], best_strategy['Profit Factor']))

        # Save each performance result
        for result in performance_results:
            conn.execute('''INSERT INTO strategy_performance (stop_loss, target, total_profit, winrate, profit_factor)
                          VALUES (?, ?, ?, ?, ?)''',
                       (result['Stop Loss'], result['Target'], result['Total Profit'],
                        result['Winrate'], result['Profit Factor']))

    print("Strategy performance saved to the database.")

# Routes

@app.route('/')

@login_required
def index():
    trades = get_all_trades()
    markets = get_all_markets()

    best_strategy = None
    performance_results = None
    actual_performance = None

    if trades:
        best_strategy, performance_results, actual_performance, queried_trade_count = analyze_strategies(trades)
        save_strategy_performance_to_db(best_strategy, performance_results)
        print(f"Performance Results: {performance_results}")

    return render_template('index.html',
                         trades=trades,
                         markets=markets,
                         best_strategy=best_strategy,
                         performance_results=performance_results,
                         actual_performance=actual_performance,
                         STOP_LOSS_VALUES=STOP_LOSS_VALUES,
                         TARGET_VALUES=TARGET_VALUES,
                         queried_trade_count=queried_trade_count)


@login_required
@app.route('/trade_entry', methods=['GET', 'POST'])
def trade_entry():
    if request.method == 'POST':
        # Retrieve the form data
        name = request.form.get('name')
        exit_value = request.form.get('exit')
        stop_loss = request.form.get('stop_loss')
        most_adverse = request.form.get('most_adverse')
        unrealized_profit = request.form.get('unrealized_profit')
        market = request.form.get('market')

        # Validate market exists in database
        with get_db() as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM markets WHERE name = ?', (market,))
            if cursor.fetchone()[0] == 0:
                flash("Selected market does not exist in the database.")
                return redirect(url_for('trade_entry'))

        # Validate all required fields are present
        if not all([name, exit_value, stop_loss, most_adverse, unrealized_profit, market]):
            flash("All fields are required!")
            return redirect(url_for('trade_entry'))

        # Validate inputs
        if not validate_trade_entry(exit_value, stop_loss, most_adverse, unrealized_profit) or not name:
            flash("Invalid input values! Please ensure all fields are filled out correctly.")
            return redirect(url_for('trade_entry'))

        try:
            # Save the trade entry to the database
            save_trade_to_db({
                'name': name,
                'entry': 0,  # Entry is set to 0
                'exit': exit_value,
                'stop_loss': stop_loss,
                'most_adverse': most_adverse,
                'unrealized_profit': unrealized_profit,
                'market': market,
            })
            flash("Trade entry recorded successfully!")
        except sqlite3.Error as e:
            flash(f"Database error occurred: {str(e)}")
        except Exception as e:
            flash(f"An error occurred: {str(e)}")

        return redirect(url_for('trade_entry'))

    # For GET requests
    trades = get_all_trades()
    markets = get_all_markets()

    best_strategy = None
    performance_results = None
    actual_performance = None

    if trades:
        best_strategy, performance_results, actual_performance, queried_trade_count = analyze_strategies(trades)

    return render_template('index.html',
                         trades=trades,
                         markets=markets,
                         best_strategy=best_strategy,
                         performance_results=performance_results,
                         actual_performance=actual_performance,
                         queried_trade_count=queried_trade_count)



def load_strategy_parameters():
    """Load strategy parameters from the database."""
    global STOP_LOSS_VALUES, TARGET_VALUES
    with get_db() as conn:
        stop_loss_cursor = conn.execute(
            'SELECT "values" FROM strategy_config WHERE config_name = "stop_loss_values"'
        )
        target_cursor = conn.execute(
            'SELECT "values" FROM strategy_config WHERE config_name = "target_values"'
        )

        stop_loss_result = stop_loss_cursor.fetchone()
        target_result = target_cursor.fetchone()

        # Set default values if not found in database
        STOP_LOSS_VALUES = [
            int(x) for x in (stop_loss_result[0].split(',') if stop_loss_result else [-6, -8, -12])
        ]
        TARGET_VALUES = [
            int(x) for x in (target_result[0].split(',') if target_result else [10, 16, 20])
        ]


# Call this during app initialization
load_strategy_parameters()

@login_required
@app.route('/delete_trade/<int:trade_id>', methods=['POST'])
def delete_trade(trade_id):
    delete_trade_from_db(trade_id)
    flash("Trade was successfully deleted!")
    return redirect(url_for('index'))

@login_required
@app.route('/perform_action', methods=['POST'])
def perform_action():
    trades = get_all_trades()
    markets = get_all_markets()

    best_strategy, performance_results, actual_performance, queried_trade_count = analyze_strategies(trades)
    save_strategy_performance_to_db(best_strategy, performance_results)

    flash('Action performed successfully!')

    return render_template('index.html',
                         trades=trades,
                         markets=markets,
                         best_strategy=best_strategy,
                         performance_results=performance_results,
                         actual_performance=actual_performance,
                         queried_trade_count=queried_trade_count)

@login_required
@app.route('/select_market', methods=['POST'])
def perform_action_selectmarket():
    selected_market = request.form.get('market')
    trades = get_all_trades()
    markets = get_all_markets()

    if selected_market:
        filtered_trades = [trade for trade in trades if trade['market'] == selected_market]
    else:
        filtered_trades = trades

    best_strategy, performance_results, actual_performance, queried_trade_count = analyze_strategies(filtered_trades)

    return render_template('index.html',
                         trades=filtered_trades,
                         markets=markets,
                         selected_market=selected_market,
                         performance_results=performance_results,
                         best_strategy=best_strategy,
                         actual_performance=actual_performance,
                         queried_trade_count=queried_trade_count)


@app.route('/manage_markets', methods=['GET'])
@login_required
def manage_markets():
    markets = get_all_markets()
    return render_template('manage_markets.html', markets=markets)

@login_required
@app.route('/add_market', methods=['POST'])
def add_market():
    market_name = request.form.get('market_name')
    if not market_name:
        flash("Market name is required!")
        return redirect(url_for('manage_markets'))

    success, message = add_market_to_db(market_name)
    flash(message)

    if success:
        return redirect(url_for('index'))
    return redirect(url_for('manage_markets'))

@login_required
@app.route('/delete_market/<int:market_id>', methods=['POST'])
def delete_market(market_id):
    success, message = delete_market_from_db(market_id)
    flash(message)

    if success:
        return redirect(url_for('index'))
    return redirect(url_for('manage_markets'))


def update_strategy_parameters(stop_loss_values, target_values):
    """
    Update the stop loss and target values used in strategy analysis.

    Args:
        stop_loss_values (list): List of stop loss values to use in simulation
        target_values (list): List of target values to use in simulation
    """
    global STOP_LOSS_VALUES, TARGET_VALUES

    # Validate input
    if not (isinstance(stop_loss_values, list) and isinstance(target_values, list)):
        raise ValueError("Inputs must be lists of integers")

    if not all(isinstance(x, int) for x in stop_loss_values + target_values):
        raise ValueError("All values must be integers")

    STOP_LOSS_VALUES = stop_loss_values
    TARGET_VALUES = target_values

    print(f"Updated stop loss values: {STOP_LOSS_VALUES}")
    print(f"Updated target values: {TARGET_VALUES}")


# Global variables to store strategy parameters
STOP_LOSS_VALUES = [-6, -8, -12]
TARGET_VALUES = [10, 16, 20]

@login_required
@app.route('/update_strategy_params', methods=['POST'])
def update_strategy_params():
    try:
        # Parse comma-separated values from form
        stop_loss_values = [int(x.strip()) for x in request.form.get('stop_loss_values').split(',')]
        target_values = [int(x.strip()) for x in request.form.get('target_values').split(',')]

        # Call the update function
        update_strategy_parameters(stop_loss_values, target_values)

        flash("Strategy parameters updated successfully!")
        return redirect(url_for('index'))
    except (ValueError, AttributeError) as e:
        flash(f"Error updating parameters: Invalid input format")
        return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(port=5001, debug=True)