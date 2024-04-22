from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session
import requests
from gameDatabase import db, Game, init_db, User, Review
from markupsafe import Markup, escape
from bs4 import BeautifulSoup
from bleach import clean
import html5lib
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///games.db'
app.secret_key = '11118189b0d92baea740b984f70ac4c6'
init_db(app)

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
            game = Game(GUID=guid, Name=Name, Description=Description, ReleaseDate=ReleaseDate)
            db.session.add(game)
            db.session.commit()

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
    page = request.args.get('page', 1, type=int)
    games = Game.query.order_by(Game.Name).paginate(page=page, per_page=10)  # 10 games per page
    for game in games.items:
        if game.Description is not None:
            truncated_description = truncate_html(game.Description, 200)  # Truncate to 200 characters
            game.Description = Markup(clean(truncated_description))
    return render_template('index.html', games=games)

@app.route('/game/<guid>')
def game_page(guid):
    game = Game.query.filter_by(GUID=guid).first_or_404()
    reviews = Review.query.filter_by(GameGUID=guid).order_by(Review.Timestamp.desc()).all()
    user_already_reviewed = False
    average_rating = sum([review.Rating for review in reviews]) / len(reviews) if reviews else 0
    if 'user_id' in session:
        user_already_reviewed = Review.query.filter_by(UserID=session['user_id'], GameGUID=guid).first() is not None
    return render_template('game_page.html', game=game, reviews=reviews, user_already_reviewed=user_already_reviewed, average_rating=average_rating)

@app.route('/submit_review/<guid>', methods=['POST'])
def submit_review(guid):
    # Get the content and rating from the form
    content = request.form.get('content')
    rating = request.form.get('rating')

    # Get the current user's ID from the session
    user_id = session.get('user_id')

    # Check if the user has already reviewed this game
    existing_review = Review.query.filter_by(UserID=user_id, GameGUID=guid).first()
    if existing_review is not None:
        flash('You have already reviewed this game.')
        return redirect(url_for('game_page', guid=guid))

    # Create a new review
    review = Review(
        Content=content,
        Rating=rating,
        Timestamp=datetime.now(),
        UserID=user_id,
        GameGUID=guid
    )

    # Add the review to the database
    db.session.add(review)
    db.session.commit()

    # Redirect to the game page after submitting the review
    return redirect(url_for('game_page', guid=guid))

@app.route('/update_review/<int:review_id>', methods=['POST'])
def update_review(review_id):
    review = Review.query.get_or_404(review_id)
    review.Content = request.form['content']
    review.Rating = request.form['rating']
    db.session.commit()
    print('GameGUID:', review.GameGUID)  # Add this line
    return redirect(url_for('game_page', guid=review.GameGUID))

@app.route('/delete_review/<int:review_id>', methods=['POST'])
def delete_review(review_id):
    review = Review.query.get_or_404(review_id)
    if 'user_id' in session and session['user_id'] == review.UserID:
        db.session.delete(review)
        db.session.commit()
    return redirect(url_for('game_page', guid=review.GameGUID))

@app.route('/search')
def search():
    query = request.args.get('query')
    games = Game.query.filter(Game.Name.contains(query)).all()
    for game in games:
        if game.Description is not None:
            truncated_description = truncate_html(game.Description, 200)  # Truncate to 200 characters
            game.Description = Markup(clean(truncated_description))
    return render_template('search_results.html', games=games)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        hashed_password = generate_password_hash(password)
        new_user = User(Username=username, Email=email, Password=hashed_password)
        db.session.add(new_user)
        try:
            db.session.commit()
            flash('Successfully registered. You can now log in.', 'success')
            return redirect(url_for('login'))
        except IntegrityError:
            db.session.rollback()
            flash('Username or email already exists.', 'error')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(Email=email).first()
        if user and check_password_hash(user.Password, password):
            session['user_id'] = user.UserID
            session['Username'] = user.Username  # store the username in the session
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
    user = User.query.filter_by(Username=username).first_or_404()
    reviews = Review.query.filter_by(UserID=user.UserID).all()
    reviews_with_games = [(review, Game.query.get(review.GameGUID)) for review in reviews]
    return render_template('profile.html', user=user, reviews=reviews_with_games)


if __name__ == '__main__':
    app.run(debug=True)
