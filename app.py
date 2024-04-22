import sqlite3
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session, g
import requests
from markupsafe import Markup, escape
from bs4 import BeautifulSoup
from bleach import clean
import html5lib
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from db import get_db

app = Flask(__name__)
app.secret_key = '11118189b0d92baea740b984f70ac4c6'

# Connect to the SQLite database
conn = sqlite3.connect('games.db')
c = conn.cursor()

@app.before_request
def before_request():
    g.db = get_db()

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store'
    return response

def truncate_html(html_content, max_length):
    soup = BeautifulSoup(html_content, 'html.parser')
    text_content = soup.get_text()
    truncated_text = text_content[:max_length] + "..."  # Append "..." to the end
    truncated_html = html5lib.parse(truncated_text, namespaceHTMLElements=False)
    return html5lib.serialize(truncated_html, tree='etree')

# Global counter
counter = 0

def fetch_details(guid):
    global counter

    # Stop fetching if we already have 100 entries
    if counter >= 100:
        return None

    try:
        api_key = '73f8f020e7235eeb2759691b13b43707f07a0519'
        url = f'http://www.giantbomb.com/api/game/{guid}/?api_key={api_key}&format=json'
        headers = {'User-Agent': 'Game Site Project'}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            game_data = response.json()['results']
            Name = game_data.get('name', '')
            Description = game_data.get('description', '')
            ReleaseDate = game_data.get('original_release_date', '')
            
            # Create a new game and add it to the database
            db = get_db()
            db.execute("INSERT INTO Game (GUID, Name, Description, ReleaseDate) VALUES (?, ?, ?, ?)",
                      (guid, Name, Description, ReleaseDate))
            db.commit()

            # Increment the counter
            counter += 1

            return {'GUID': guid, 'Name': Name, 'Description': Description, 'ReleaseDate': ReleaseDate}
        else:
            return None
    except Exception as e:
        print("Exception:", e)
        return None

# Route to return game information with associated genres in JSON format
@app.route('/games.json')
def games_json():
    try:
        api_key = '73f8f020e7235eeb2759691b13b43707f07a0519'
        url = f'http://www.giantbomb.com/api/games/?api_key={api_key}&format=json'
        headers = {'User-Agent': 'Game Site Project'}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            api_response = response.json()
            if 'results' in api_response:
                games_data = api_response['results']
                games_list = []
                for game in games_data:
                    game_guid = game['guid']
                    game_details = fetch_details(game_guid)
                    if game_details:
                        games_list.append(game_details)
                return jsonify(games_list)
            else:
                print("No 'results' in API response")
                return jsonify([])
        else:
            print("API Request Failed:", response.status_code)
            return jsonify([])
    except Exception as e:
        print("Exception:", e)
        return jsonify([])

# Route to render the index.html template
@app.route('/')
def index():
    # Fetch games from the database
    db = get_db()
    cur = db.execute("SELECT * FROM Game ORDER BY Name")
    rows = cur.fetchall()

    games = []
    for row in rows:
        game = dict(row)
        if game['Description'] is not None:
            truncated_description = truncate_html(game['Description'], 200)  # Truncate to 200 characters
            game['Description'] = Markup(clean(truncated_description))
        games.append(game)

    return render_template('index.html', games=games)

@app.route('/game/<guid>')
def game_page(guid):
    # Fetch the game from the database
    db = get_db()
    cur = db.execute("SELECT * FROM Game WHERE GUID = ?", (guid,))
    game = cur.fetchone()

    # Fetch the reviews for the game
    cur = db.execute("SELECT Review.*, User.Username FROM Review JOIN User ON Review.UserID = User.UserID WHERE Review.GameGUID = ? ORDER BY Timestamp DESC", (guid,))
    reviews = cur.fetchall()

    user_already_reviewed = False
    average_rating = sum([review[2] for review in reviews]) / len(reviews) if reviews else 0  # Assuming Rating is the 3rd column in the reviews table

    if 'user_id' in session:
        # Check if the user has already reviewed the game
        db = get_db()
        cur = db.execute("SELECT * FROM Review WHERE UserID = ? AND GameGUID = ?", (session['user_id'], guid))
        user_already_reviewed = cur.fetchone() is not None

    return render_template('game_page.html', game=game, reviews=reviews, user_already_reviewed=user_already_reviewed, average_rating=average_rating)

@app.route('/submit_review/<guid>', methods=['POST'])
def submit_review(guid):
    content = request.form['content']
    rating = request.form['rating']
    user_id = session.get('user_id')

    # Check if the user has already reviewed this game
    db = get_db()
    cur = db.execute("SELECT * FROM Review WHERE UserID = ? AND GameGUID = ?", (user_id, guid))
    existing_review = cur.fetchone()
    if existing_review is not None:
        flash('You have already reviewed this game.')
        return redirect(url_for('game_page', guid=guid))

    # Create a new review
    timestamp = datetime.now()
    db.execute("INSERT INTO Review (Content, Rating, Timestamp, UserID, GameGUID) VALUES (?, ?, ?, ?, ?)",
              (content, rating, timestamp, user_id, guid))
    db.commit()

    # Redirect to the game page after submitting the review
    return redirect(url_for('game_page', guid=guid))

@app.route('/update_review/<int:review_id>', methods=['POST'])
def update_review(review_id):
    content = request.form['content']
    rating = request.form['rating']

    # Fetch the review from the database
    db = get_db()
    cur = db.execute("SELECT * FROM Review WHERE ReviewID = ?", (review_id,))
    review = cur.fetchone()

    if review is not None:
        # Update the review
        db.execute("UPDATE Review SET Content = ?, Rating = ? WHERE ReviewID = ?", (content, rating, review_id))
        db.commit()

        print('GameGUID:', review[5])  # Assuming GameGUID is the 6th column in the reviews table
        return redirect(url_for('game_page', guid=review[7]))
    else:
        return "Review not found", 404

@app.route('/delete_review/<int:review_id>', methods=['POST'])
def delete_review(review_id):
    # Fetch the review from the database
    db = get_db()
    cur = db.execute("SELECT * FROM Review WHERE ReviewID = ?", (review_id,))
    review = cur.fetchone()

    if review is not None and 'user_id' in session and session['user_id'] == review[6]:  # Assuming UserID is the 7th column in the reviews table
        # Delete the review
        db.execute("DELETE FROM Review WHERE ReviewID = ?", (review_id,))
        db.commit()

        return redirect(url_for('game_page', guid=review[7]))  # Assuming GameGUID is the 6th column in the reviews table
    else:
        return "Review not found or user not authorized", 403

@app.route('/search', methods=['GET', 'POST'])
def search():
    search_term = request.values.get('search')
    if search_term:
        db = get_db()
        cur = db.execute("SELECT * FROM Game WHERE LOWER(Name) LIKE LOWER(?) ORDER BY Name", ('%' + search_term + '%',))
        rows = cur.fetchall()

        games = []
        for row in rows:
            game = dict(row)
            if game['Description'] is not None:
                truncated_description = truncate_html(game['Description'], 200)  # Truncate to 200 characters
                game['Description'] = Markup(clean(truncated_description))
            games.append(game)

        return render_template('search_results.html', games=games)
    else:
        return render_template('search_results.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        hashed_password = generate_password_hash(password)

        # Check if the username or email already exists
        db = get_db()
        cur = db.execute("SELECT * FROM User WHERE Username = ? OR Email = ?", (username, email))
        existing_user = cur.fetchone()
        if existing_user is not None:
            flash('Username or email already exists.', 'error')
            return render_template('register.html')

        # Create a new user
        db.execute("INSERT INTO User (Username, Email, Password) VALUES (?, ?, ?)",
                  (username, email, hashed_password))
        db.commit()

        flash('Successfully registered. You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Fetch the user from the database
        db = get_db()
        cur = db.execute("SELECT * FROM User WHERE Email = ?", (email,))
        user = cur.fetchone()

        if user and check_password_hash(user[3], password):  # Assuming Password is the 4th column in the users table
            session['user_id'] = user[0]  # Assuming UserID is the 1st column in the users table
            session['Username'] = user[1]  # Assuming Username is the 2nd column in the users table
            flash('Successfully logged in.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

@app.route('/profile/<username>')
def profile(username):
    # Fetch the user from the database
    db = get_db()
    cur = db.execute("SELECT * FROM User WHERE Username = ?", (username,))
    user = cur.fetchone()

    if user is not None:
        # Fetch the reviews and the associated games for the user
        cur = db.execute("""
            SELECT r.*, g.Name as GameName
            FROM Review r
            INNER JOIN Game g ON r.GameGUID = g.GUID
            WHERE r.UserID = ?
        """, (user[0],))  # Assuming UserID is the 1st column in the users table
        reviews = cur.fetchall()

        # Convert the sqlite3.Row objects into dictionaries
        reviews = [dict(review) for review in reviews]

        return render_template('profile.html', user=user, reviews=reviews)
    else:
        return "User not found", 404
    
@app.route('/recommendations', methods=['GET'])
def recommendations():
    # Get the logged in user's id
    user_id = session['user_id']
    db = get_db()

    # Query the database to find games and their genres that have the same genre as a game the logged in user has given a review rating of 3 or more
    cur = db.execute("""
        SELECT DISTINCT g.*, gen.Name as GenreName
        FROM Game g
        INNER JOIN Game_Genre gg ON g.GUID = gg.GameGUID
        INNER JOIN Genre gen ON gg.GenreID = gen.GenreID
        WHERE gg.GenreID IN (
            SELECT gg.GenreID
            FROM Review r
            INNER JOIN Game g ON r.GameGUID = g.GUID
            INNER JOIN Game_Genre gg ON g.GUID = gg.GameGUID
            WHERE r.UserID = ? AND r.Rating >= 3
        ) AND g.GUID NOT IN (
            SELECT GameGUID FROM Review WHERE UserID = ?
        )
    """, (user_id, user_id))
    rows = cur.fetchall()

    games = []
    for row in rows:
        game = dict(row)
        if game['Description'] is not None:
            truncated_description = truncate_html(game['Description'], 200)  # Truncate to 200 characters
            game['Description'] = Markup(clean(truncated_description))
        games.append(game)

    # Render the recommendations template with the recommended games
    return render_template('recommendations.html', games=games)



if __name__ == '__main__':
    app.run(debug=True)
