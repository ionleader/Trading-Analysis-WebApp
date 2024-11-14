from flask import Flask, render_template, request, flash, redirect, url_for
import sqlite3
import numpy as np


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
            unrealized_profit INTEGER NOT NULL,
            market TEXT NOT NULL
        )''')
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




init_db()
create_strategy_performance_table()


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
            # Logic to save the trade entry to the database
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

    # For GET requests, fetch data needed for the page
    try:
        trades = get_all_trades()
        markets = get_all_markets()

        # If there are no markets, flash a warning
        if not markets:
            flash("No markets available. Please add markets first.")

        best_strategy = None
        performance_results = None

        # Only calculate strategies if there are trades
        if trades:
            best_strategy, performance_results, pnl_curves = analyze_strategies(trades)

        # Render template with all necessary data
        return render_template('index.html',
                               trades=trades,
                               markets=markets,
                               best_strategy=best_strategy,
                               performance_results=performance_results)

    except sqlite3.Error as e:
        flash(f"Database error occurred: {str(e)}")
        return render_template('index.html', trades=[], markets=[])
    except Exception as e:
        flash(f"An error occurred: {str(e)}")
        return render_template('index.html', trades=[], markets=[])

def save_trade_to_db(trade_data):
    """Save a trade entry to the SQLite database."""
    with get_db() as conn:
        conn.execute('''INSERT INTO trades (name, entry, exit, stop_loss, most_adverse, unrealized_profit, market)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     (trade_data['name'], trade_data['entry'], trade_data['exit'],
                      trade_data['stop_loss'], trade_data['most_adverse'], trade_data['unrealized_profit'],
                      trade_data['market']))


#trade_data daten werden in trade_entry funktion erstellt

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


def simulate_strategy(stop_loss, target, trades):
    """
    Simulates the performance of a trading strategy given stop loss and target levels.
    Only trades with an entry price of 0 are considered valid.
    Raises an error if any trade entry is not 0.
    """
    # Check if all trades have an entry price of 0
    print("Starting strategy simulation...")
    for trade in trades:
        if trade['entry'] != 0:
            raise ValueError("All trades must have an entry price of 0.")
        print(
            f"Evaluating trade: {trade['entry']}, {trade['exit']}, {trade['stop_loss']}, {trade['most_adverse']}, {trade['unrealized_profit']}")

    profits = []

    # Iterate over valid trades
    for trade in trades:
        entry = trade['entry']
        exit_value = trade['exit']
        stop_loss_value = trade['stop_loss']  # Access the correct stop_loss from the database
        most_adverse = trade['most_adverse']
        unrealized_profit = trade['unrealized_profit']

        print(
            f"Simulating trade: Entry: {entry}, Exit: {exit_value}, Stop Loss: {stop_loss_value}, Most Adverse: {most_adverse}, Unrealized Profit: {unrealized_profit}")

        # Calculate potential stop loss hit
        if most_adverse <= entry + stop_loss:
            profit = stop_loss  # Stop loss hit
            print(f"Stop loss hit. Profit: {profit}")
        # Check if the unrealized profit meets or exceeds the target
        elif unrealized_profit >= entry + target:
            profit = target  # Target hit
            print(f"Target hit. Profit: {profit}")
        else:
            profit = stop_loss  # If neither stop loss nor target hit, assume stop loss is the loss
            print(f"No target or stop loss hit. Profit: {profit}")

        profits.append(profit)

    print(f"Completed strategy simulation for stop loss: {stop_loss}, target: {target}")
    return np.array(profits)


def analyze_strategies(trades, market=None):
    """
    Analyze various stop loss and target combinations to suggest improvements.
    Returns the best strategy and performance results including P&L curves.
    """
    stop_loss_values = [-6, -8, -12]  # Example negative stop loss values
    target_values = [10, 16, 20]  # Example target values

    best_strategy = None
    best_performance = -np.inf
    performance_results = []
    pnl_curves = {}

    if market:
        trades = [trade for trade in trades if trade['market'] == market]


    for stop_loss in stop_loss_values:
        for target in target_values:
            profits = simulate_strategy(stop_loss, target, trades)
            total_profit = profits.sum()
            winrate = (profits > 0).mean() * 100
            profit_factor = (profits[profits > 0].sum() / abs(profits[profits < 0].sum())) if (profits < 0).sum() > 0 else float('inf')

            # Calculate cumulative P&L curve
            cumulative_pnl = np.cumsum(profits)
            pnl_curves[(stop_loss, target)] = cumulative_pnl

            performance_results.append({
                'Stop Loss': stop_loss,
                'Target': target,
                'Total Profit': total_profit,
                'Winrate': winrate,
                'Profit Factor': profit_factor
            })

            # Check if this strategy is better
            if total_profit > best_performance:
                best_performance = total_profit
                best_strategy = {
                    'Stop Loss': stop_loss,
                    'Target': target,
                    'Total Profit': total_profit,
                    'Winrate': winrate,
                    'Profit Factor': profit_factor
                }

    return best_strategy, performance_results, pnl_curves




def delete_trade_from_db(trade_id):
    """Löscht einen Trade aus der Datenbank."""
    with get_db() as conn:
        conn.execute('DELETE FROM trades WHERE id = ?', (trade_id,))
    print(f"Trade mit ID {trade_id} gelöscht.")

@app.route('/delete_trade/<int:trade_id>', methods=['POST'])
def delete_trade(trade_id):
        """Löscht einen Trade aus der Datenbank und leitet zurück zur Hauptseite."""
        delete_trade_from_db(trade_id)
        flash("Trade wurde erfolgreich gelöscht!")
        return redirect(url_for('index'))

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


@app.route('/perform_action', methods=['POST'])
def perform_action():
    trades = get_all_trades()
    markets = get_all_markets()  # Add this line

    best_strategy, performance_results, pnl_curves = analyze_strategies(trades)
    save_strategy_performance_to_db(best_strategy, performance_results)

    flash('Action performed successfully!')

    return render_template('index.html',
                           trades=trades,
                           markets=markets,  # Add this line
                           best_strategy=best_strategy,
                           performance_results=performance_results)

@app.route('/select_market', methods=['POST'])
def perform_action_selectmarket():
    selected_market = request.form.get('market')
    trades = get_all_trades()
    markets = get_all_markets()  # Add this line

    if selected_market:
        filtered_trades = [trade for trade in trades if trade['market'] == selected_market]
    else:
        filtered_trades = trades

    best_strategy, performance_results, pnl_curves = analyze_strategies(filtered_trades)

    return render_template('index.html',
                         trades=filtered_trades,
                         markets=markets,  # Add this line
                         selected_market=selected_market,
                         performance_results=performance_results,
                         best_strategy=best_strategy)

def debug_markets():
    """Utility function to print all markets in the database"""
    with get_db() as conn:
        cursor = conn.execute('SELECT * FROM markets')
        markets = cursor.fetchall()
        print("Current markets in database:", [market['name'] for market in markets])
        return markets



#market management
# Add this to your existing Flask application

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


# Add this after your other init functions
create_markets_table()


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
            # Check if market is being used in trades
            cursor = conn.execute('SELECT COUNT(*) FROM trades WHERE market = (SELECT name FROM markets WHERE id = ?)',
                                  (market_id,))
            if cursor.fetchone()[0] > 0:
                return False, "Cannot delete market that has associated trades!"

            conn.execute('DELETE FROM markets WHERE id = ?', (market_id,))
        return True, "Market deleted successfully!"
    except Exception as e:
        return False, f"Error deleting market: {str(e)}"


@app.route('/manage_markets', methods=['GET'])
def manage_markets():
    markets = get_all_markets()
    return render_template('manage_markets.html', markets=markets)


# Update the manage_markets route to redirect to index after adding/deleting markets
@app.route('/add_market', methods=['POST'])
def add_market():
    market_name = request.form.get('market_name')
    if not market_name:
        flash("Market name is required!")
        return redirect(url_for('manage_markets'))

    success, message = add_market_to_db(market_name)
    flash(message)

    # After adding market, redirect to the index page instead of manage_markets
    if success:
        return redirect(url_for('index'))
    return redirect(url_for('manage_markets'))


@app.route('/delete_market/<int:market_id>', methods=['POST'])
def delete_market(market_id):
    success, message = delete_market_from_db(market_id)
    flash(message)

    # After deleting market, redirect to the index page instead of manage_markets
    if success:
        return redirect(url_for('index'))
    return redirect(url_for('manage_markets'))



@app.route('/')
def index():
    trades = get_all_trades()
    markets = get_all_markets()  # Add this line

    best_strategy, performance_results, pnl_curves = analyze_strategies(trades)
    save_strategy_performance_to_db(best_strategy, performance_results)
    print(f"Performance Results: {performance_results}")

    return render_template('index.html',
                           trades=trades,
                           markets=markets,  # Add this line
                           best_strategy=best_strategy,
                           performance_results=performance_results)


if __name__ == '__main__':
    app.run(port=5001, debug=True)
