from werkzeug.security import check_password_hash, generate_password_hash
from flask import Flask, request, session, redirect, url_for, render_template, flash, abort  # укажите нужные компоненты
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
from views_admin import (
    admin_settings_view,
    admin_settings_save_view,
    admin_users_view,
    admin_user_create_view,
    admin_user_archive_view,
    admin_user_restore_view,
    admin_user_delete_view,
)
from views_tickets import (
    ticket_list_view,
    ticket_new_view,
    ticket_create_view,
    ticket_detail_view,
    comment_create_view,
)
from views_projects import (
    projects_list_view,
    project_new_view,
    project_create_view,
    project_detail_view,
    project_member_add_view,
    project_member_remove_view,
    project_archive_view,
    project_restore_view,
    project_delete_view,
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
    return admin_users_view()

@app.get("/admin/settings")
def admin_settings():
    return admin_settings_view()

@app.post("/admin/settings")
def admin_settings_save():
    return admin_settings_save_view()

@app.post("/admin/users/create")
def admin_user_create():
    return admin_user_create_view()

@app.post("/admin/users/<int:user_id>/archive")
def admin_user_archive(user_id):
    return admin_user_archive_view(user_id)

@app.post("/admin/users/<int:user_id>/restore")
def admin_user_restore(user_id):
    return admin_user_restore_view(user_id)

@app.post("/admin/users/<int:user_id>/delete")
def admin_user_delete(user_id):
    return admin_user_delete_view(user_id)

@app.get("/projects/<int:project_id>/tickets")
def ticket_list(project_id):
    return ticket_list_view(project_id)


@app.get("/projects/<int:project_id>/tickets/new")
def ticket_new(project_id):
    return ticket_new_view(project_id)


@app.post("/projects/<int:project_id>/tickets/new")
def ticket_create(project_id):
    return ticket_create_view(project_id)


@app.get("/projects/<int:project_id>/tickets/<int:ticket_id>")
def ticket_detail(project_id, ticket_id):
    return ticket_detail_view(project_id, ticket_id)

@app.post("/projects/<int:project_id>/tickets/<int:ticket_id>/comments")
def comment_create(project_id, ticket_id):
    return comment_create_view(project_id, ticket_id)

@app.context_processor
def inject():
    return {
        "current_user": current_user,
        "is_admin": is_admin,
        #"is_agent": is_agent,
        "registration_open": get_registration_open(),
    }

@app.get("/projects")
def projects_list():
    return projects_list_view()


@app.get("/projects/new")
def project_new():
    return project_new_view()


@app.post("/projects/new")
def project_create():
    return project_create_view()


@app.get("/projects/<int:project_id>")
def project_detail(project_id):
    return project_detail_view(project_id)

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

@app.post("/projects/<int:project_id>/members/add")
def project_member_add(project_id):
    return project_member_add_view(project_id)


@app.post("/projects/<int:project_id>/members/<int:user_id>/remove")
def project_member_remove(project_id, user_id):
    return project_member_remove_view(project_id, user_id)

@app.post("/projects/<int:project_id>/archive")
def project_archive(project_id):
    return project_archive_view(project_id)


@app.post("/projects/<int:project_id>/restore")
def project_restore(project_id):
    return project_restore_view(project_id)


@app.post("/projects/<int:project_id>/delete")
def project_delete(project_id):
    return project_delete_view(project_id)






if __name__ == "__main__":
    init_db()
    ensure_master()
    app.run(debug=True)