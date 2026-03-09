from flask import Flask, session, render_template, request, url_for, redirect,abort, flash
import sqlite3

app = Flask(__name__)
app.secret_key = "dev-secret"  # в продакшене — случайная строка из переменной окружения
DB_PATH = "database.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # строки как словари: row["column_name"]
    conn.execute("PRAGMA foreign_keys = ON")  # включить внешние ключи (пригодятся позже)
    return conn

def init_db():
    """Создать таблицу users, если её ещё нет."""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'admin')),
            archived_at TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        )
    """)  # Добавлены скобки () и правильно закрыта строка
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('registration_open', '0')")
    
    conn.commit()
    conn.close()

