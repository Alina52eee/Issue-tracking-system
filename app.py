from werkzeug.security import check_password_hash, generate_password_hash
from flask import Flask, request, session, redirect, url_for, render_template, flash  # укажите нужные компоненты
import sqlite3
from datetime import datetime
from db import get_conn, init_db, insert_test_user, show_table
from auth_utils import (create_user, ensure_master, is_logged_in, current_user, is_admin, get_registration_open
)
from views_auth import (
    login_form_view,
    login_view,
    logout_view,
    register_form_view,
    register_view,
    dashboard_view,
)

app = Flask(__name__)
app.secret_key = "dev-secret"  


@app.route("/")
def home():
    if not is_logged_in():
        return redirect(url_for("login_form"))

    conn = get_conn()
    row = conn.execute("SELECT 1 AS ok").fetchone()
    conn.close()

    db_ok = row is not None and row["ok"] == 1
    return render_template("home.html", db_ok=db_ok)



@app.get("/admin/users")
def admin_users():
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))
    if not is_admin():
        abort(403)

    conn = get_conn()
    users = conn.execute(
        """
        SELECT id, username, role, archived_at, created_at
        FROM users
        ORDER BY archived_at IS NULL DESC, username
        """
    ).fetchall()
    conn.close()

    return render_template("admin_users.html", users=users)

@app.get("/admin/settings")
def admin_settings():
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))
    if not is_admin():
        abort(403)
    return render_template("admin_settings.html", registration_open=get_registration_open())

@app.post("/admin/settings")
def admin_settings_save():
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))
    if not is_admin():
        abort(403)
    open_val = "1" if request.form.get("registration_open") == "on" else "0"
    conn = get_conn()
    conn.execute("REPLACE INTO settings (key, value) VALUES ('registration_open', ?)", (open_val,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_settings"))

@app.post("/admin/users/create")
def admin_user_create():
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))
    if not is_admin():
        abort(403)

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not username or not password:
        flash("Введите логин и пароль.")
        return redirect(url_for("admin_users"))

    if len(username) < 2:
        flash("Логин слишком короткий.")
        return redirect(url_for("admin_users"))

    try:
        # В универсальном варианте создаём пользователей с ролью 'user'
        create_user(username, password, "user")
        flash(f"Пользователь {username} создан.")
    except sqlite3.IntegrityError:
        flash("Такой логин уже занят.")

    return redirect(url_for("admin_users"))

@app.post("/admin/users/<int:user_id>/archive")
def admin_user_archive(user_id):
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))
    if not is_admin():
        abort(403)

    conn = get_conn()
    u = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if u is None:
        conn.close()
        abort(404)

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute("UPDATE users SET archived_at = ? WHERE id = ?", (now, user_id))
    conn.commit()
    conn.close()

    flash("Пользователь заархивирован. Он больше не сможет войти.")
    return redirect(url_for("admin_users"))

@app.post("/admin/users/<int:user_id>/restore")
def admin_user_restore(user_id):
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))
    if not is_admin():
        abort(403)

    conn = get_conn()
    u = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if u is None:
        conn.close()
        abort(404)

    conn.execute("UPDATE users SET archived_at = NULL WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    flash("Пользователь восстановлен.")
    return redirect(url_for("admin_users"))

@app.post("/admin/users/<int:user_id>/delete")
def admin_user_delete(user_id):
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))
    if not is_admin():
        abort(403)

    conn = get_conn()
    u = conn.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,)).fetchone()
    if u is None:
        conn.close()
        abort(404)

    if u["role"] == "admin":
        # Мастер‑аккаунт удалять нельзя
        conn.close()
        flash("Нельзя удалить мастер‑аккаунт.")
        return redirect(url_for("admin_users"))

    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    flash(f"Пользователь {u['username']} удалён безвозвратно.")
    return redirect(url_for("admin_users"))

@app.context_processor
def inject():
    return {
        "current_user": current_user,
        "is_admin": is_admin,
        #"is_agent": is_agent,
        "registration_open": get_registration_open(),
    }


@app.get("/login")
def login_form():
    return login_form_view()

@app.post("/login")
def login():
    return login_view()

@app.get("/logout")
def logout():
    return logout_view()

@app.get("/register")
def register_form():
    return register_form_view()

@app.post("/register")
def register():
    return register_view()

@app.get("/dashboard")
def dashboard():
    return dashboard_view()







if __name__ == "__main__":
    init_db()
    insert_test_user() # временно: добавим одного пользователя для проверки
    # По желанию: посмотреть содержимое таблицы в консоли
    print(show_table())
    ensure_master()
    app.run(debug=True)