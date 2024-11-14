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

        market = request.form.get('market')  # Neues Feld für den Markt

        # Optional: Validierung für das Feld "market"
        if not market:
            flash("Market is required.")
            return redirect(url_for('trade_entry'))


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
            'unrealized_profit': unrealized_profit,
            'market': market,
        })

        flash("Trade entry recorded successfully!")
        return redirect(url_for('trade_entry'))

    trades = get_all_trades()
    return render_template('index.html', trades=trades)


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
    # Logic for the action (e.g., analyzing trades, running calculations, etc.)
    # For example, you could call a function to analyze trade data:
    trades = get_all_trades()  # Assuming you have a function to get all trades
    best_strategy, performance_results, pnl_curves = analyze_strategies(trades)  # Your strategy analysis function

    # Optionally, you can save the performance results or log them
    save_strategy_performance_to_db(best_strategy, performance_results)  # Example of saving results

    # Flash a message if you want to notify the user
    flash('Action performed successfully!')

    # After performing the action, you can render the results or redirect
    return redirect(url_for('index'))  # Redirect to the index page to display updated data


@app.route('/select_market', methods=['POST'])
def perform_action_selectmarket():
    market = request.form.get('market')  # Get the selected market from the form
    trades = get_all_trades()  # Fetch all trades

    # If a specific market is selected (not "All Markets"), filter the trades
    if market:
        filtered_trades = [trade for trade in trades if trade['market'] == market]
    else:
        filtered_trades = trades

    best_strategy, performance_results, pnl_curves = analyze_strategies(
        filtered_trades)  # Analyze strategies based on the filtered trades

    # Pass all necessary variables to the template
    return render_template('index.html',
                           trades=filtered_trades,  # Pass the filtered trades
                           performance_results=performance_results,
                           selected_market=market,
                           best_strategy=best_strategy)  # Include best_strategy if you're using it in the template



@app.route('/')
def index():
    trades = get_all_trades()  # Lädt alle Trades

    best_strategy, performance_results, pnl_curves = analyze_strategies(trades)  # Analyze strategies
    save_strategy_performance_to_db(best_strategy, performance_results)  # Save results to DB
    print(f"Performance Results: {performance_results}")  # Log for debugging

    return render_template('index.html', trades=trades, best_strategy=best_strategy,
                           performance_results=performance_results)

if __name__ == '__main__':
    app.run(port=5001, debug=True)
