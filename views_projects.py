from flask import render_template, redirect, url_for, request, abort

from db import get_conn
from auth_utils import is_logged_in, current_user


def get_project(project_id):
    """Вернуть проект по id или None, если не найден."""
    conn = get_conn()
    project = conn.execute(
        "SELECT * FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    conn.close()
    return project


def user_owns_project(project_id):
    """Проверить, что текущий пользователь — владелец проекта."""
    user = current_user()
    if user is None:
        return False

    project = get_project(project_id)
    if project is None:
        return False

    return project["owner_id"] == user["id"]

def projects_list_view():
    """Список проектов текущего пользователя (как владелец)."""
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))

    user = current_user()
    if user is None:
        return redirect(url_for("login_form"))

    conn = get_conn()
    projects = conn.execute(
        """
        SELECT id, title, description, is_archived, created_at
        FROM projects
        WHERE owner_id = ?
        ORDER BY created_at DESC
        """,
        (user["id"],),
    ).fetchall()
    conn.close()

    return render_template("project_list.html", projects=projects)

def project_new_view():
    """Показать форму создания проекта."""
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))

    return render_template("project_new.html", error=None)


def project_create_view():
    """Обработать создание проекта."""
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))

    user = current_user()
    if user is None:
        return redirect(url_for("login_form"))

    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()

    if not title:
        return render_template(
            "project_new.html",
            error="Введите название проекта.",
        )

    conn = get_conn()
    conn.execute(
        "INSERT INTO projects (owner_id, title, description) VALUES (?, ?, ?)",
        (user["id"], title, description),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("projects_list"))

def project_detail_view(project_id):
    """Страница одного проекта с его заявками."""
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))

    user = current_user()
    if user is None:
        return redirect(url_for("login_form"))

    project = get_project(project_id)
    if project is None:
        abort(404)

    # На этом шаге даём доступ только владельцу проекта
    if project["owner_id"] != user["id"]:
        abort(403)

    conn = get_conn()
    tickets = conn.execute(
        """
        SELECT
            t.id,
            t.title,
            t.status,
            t.priority,
            t.created_at,
            ru.username AS reporter_username
        FROM tickets t
        LEFT JOIN users ru ON t.reporter_id = ru.id
        WHERE t.project_id = ?
        ORDER BY t.created_at DESC
        """,
        (project_id,),
    ).fetchall()
    conn.close()

    return render_template(
        "project_detail.html",
        project=project,
        tickets=tickets,
    )