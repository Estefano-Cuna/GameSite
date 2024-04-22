from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    UserID = db.Column(db.Integer, primary_key=True)
    Username = db.Column(db.String(255), nullable=False)
    Email = db.Column(db.String(255), nullable=False)
    Password = db.Column(db.String(255), nullable=False)
    reviews = db.relationship('Review', backref='user', lazy=True)

class Game(db.Model):
    GUID = db.Column(db.String(255), primary_key=True)
    Name = db.Column(db.String(255), nullable=False)
    Description = db.Column(db.Text)
    ReleaseDate = db.Column(db.String(255))
    reviews = db.relationship('Review', backref='game', lazy=True)

class Review(db.Model):
    ReviewID = db.Column(db.Integer, primary_key=True)
    Content = db.Column(db.Text)
    Rating = db.Column(db.Integer)
    Likes = db.Column(db.Integer, default=0)
    Dislikes = db.Column(db.Integer, default=0)
    Timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    UserID = db.Column(db.Integer, db.ForeignKey('user.UserID'))
    GameGUID = db.Column(db.String(255), db.ForeignKey('game.GUID'))  # Update this line

class Genre(db.Model):
    GenreID = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(255), nullable=False)

class Tag(db.Model):
    TagID = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(255), nullable=False)

class GameGenre(db.Model):
    __tablename__ = 'game_genre'
    GameGUID = db.Column(db.String(255), db.ForeignKey('game.GUID'), primary_key=True)
    GenreID = db.Column(db.Integer, db.ForeignKey('genre.GenreID'), primary_key=True)

class GameTag(db.Model):
    __tablename__ = 'game_tag'
    GameGUID = db.Column(db.Integer, db.ForeignKey('game.GUID'), primary_key=True)
    TagID = db.Column(db.Integer, db.ForeignKey('tag.TagID'), primary_key=True)

def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()