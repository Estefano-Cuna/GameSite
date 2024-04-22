import sqlite3
from db import get_db

def create_tables():
    db = get_db()
    c = db.cursor()

    c.execute('''
        CREATE TABLE User (
            UserID INTEGER PRIMARY KEY,
            Username TEXT NOT NULL,
            Email TEXT NOT NULL,
            Password TEXT NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE Game (
            GUID TEXT PRIMARY KEY,
            Name TEXT NOT NULL,
            Description TEXT,
            ReleaseDate TEXT
        )
    ''')

    c.execute('''
    CREATE TABLE Review (
        ReviewID INTEGER PRIMARY KEY,
        Content TEXT,
        Rating INTEGER,
        Likes INTEGER DEFAULT 0,
        Dislikes INTEGER DEFAULT 0,
        Timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        UserID INTEGER,
        GameGUID TEXT,
        FOREIGN KEY(UserID) REFERENCES User(UserID),
        FOREIGN KEY(GameGUID) REFERENCES Game(GUID)
    )
''')

    c.execute('''
        CREATE TABLE Genre (
            GenreID INTEGER PRIMARY KEY,
            Name TEXT NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE Tag (
            TagID INTEGER PRIMARY KEY,
            Name TEXT NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE Game_Genre (
            GameGUID TEXT,
            GenreID INTEGER,
            PRIMARY KEY(GameGUID, GenreID),
            FOREIGN KEY(GameGUID) REFERENCES Game(GUID),
            FOREIGN KEY(GenreID) REFERENCES Genre(GenreID)
        )
    ''')

    c.execute('''
        CREATE TABLE Game_Tag (
            GameGUID TEXT,
            TagID INTEGER,
            PRIMARY KEY(GameGUID, TagID),
            FOREIGN KEY(GameGUID) REFERENCES Game(GUID),
            FOREIGN KEY(TagID) REFERENCES Tag(TagID)
        )
    ''')

    db.commit()

create_tables()