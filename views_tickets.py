from flask import render_template, redirect, url_for, request, abort

from db import get_conn
from auth_utils import is_logged_in, current_user, is_admin


def tickets_for_project(project_id, user):
    """Вернуть все заявки этого проекта с учетом роли пользователя."""
    conn = get_conn()
    try:
        if user["is_admin"]:
            # Админ / менеджер видит все заявки проекта
            rows = conn.execute(
                """
                SELECT
                    t.id,
                    t.title,
                    t.status,
                    t.priority,
                    t.created_at,
                    t.reporter_id,
                    t.assignee_id,
                    ru.username AS reporter_username,
                    au.username AS assignee_username
                FROM tickets t
                LEFT JOIN users ru ON t.reporter_id = ru.id
                LEFT JOIN users au ON t.assignee_id = au.id
                WHERE t.project_id = ?
                ORDER BY t.created_at DESC
                """,
                (project_id,),
            ).fetchall()
        else:
            # Обычный пользователь видит заявки, где он автор или исполнитель
            rows = conn.execute(
                """
                SELECT
                    t.id,
                    t.title,
                    t.status,
                    t.priority,
                    t.created_at,
                    t.reporter_id,
                    t.assignee_id,
                    ru.username AS reporter_username,
                    ru.archived_at AS reporter_archived,
                    au.username AS assignee_username,
                    au.archived_at AS assignee_archived
                FROM tickets t
                LEFT JOIN users ru ON t.reporter_id = ru.id
                LEFT JOIN users au ON t.assignee_id = au.id
                WHERE (t.reporter_id = ? OR t.assignee_id = ?)
                  AND t.project_id = ?
                ORDER BY t.created_at DESC
                """,
                (user["id"], user["id"], project_id),
            ).fetchall()

        return rows
    finally:
        conn.close()


def can_view_ticket(ticket_id):
    """Можно ли просматривать эту заявку текущему пользователю."""
    user = current_user()
    if user is None:
        return False, None

    conn = get_conn()
    t = conn.execute(
        "SELECT id, reporter_id, assignee_id FROM tickets WHERE id = ?",
        (ticket_id,),
    ).fetchone()
    conn.close()

    if t is None:
        return False, None

    if is_admin():
        return True, t

    if t["reporter_id"] == user["id"] or t["assignee_id"] == user["id"]:
        return True, t

    return False, None


def can_edit_ticket(ticket_id):
    """Можно ли редактировать эту заявку (менять статус, исполнителя и т.п.)."""
    user = current_user()
    if user is None:
        return False

    if is_admin():
        return True

    conn = get_conn()
    t = conn.execute(
        "SELECT reporter_id, assignee_id FROM tickets WHERE id = ?",
        (ticket_id,),
    ).fetchone()
    conn.close()

    if t is None:
        return False

    return t["reporter_id"] == user["id"] or t["assignee_id"] == user["id"]

def ticket_list_view(project_id):
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))

    tickets = tickets_for_project(project_id)
    return render_template("ticket_list.html", tickets=tickets, project_id=project_id)


def ticket_new_view(project_id):
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))

      # Проверяем, что проект существует и принадлежит пользователю
    project = get_project(project_id)
    if project is None:
        abort(404)
    if project["owner_id"] != current_user()["id"]:
        abort(403)

    return render_template("ticket_new.html", 
                         project_id=project_id,  # ← Обязательно передай!
                         project=project)        # ← Для удобства


def ticket_create_view(project_id):
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))

    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    priority = request.form.get("priority") or "Medium"

    if not title:
        return render_template(
            "ticket_new.html",
            error="Введите заголовок заявки.",
            project_id=project_id,
        )

    if priority not in ("Low", "Medium", "High"):
        priority = "Medium"

    user = current_user()

    conn = get_conn()
    conn.execute(
        "INSERT INTO tickets (title, description, reporter_id, project_id, status, priority) "
        "VALUES (?, ?, ?, ?, 'Open', ?)",
        (title, description, user["id"], project_id, priority),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("ticket_list", project_id=project_id))


def ticket_detail_view(project_id: int, ticket_id: int):
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))

    can_view, _ = can_view_ticket(ticket_id)
    if not can_view:
        abort(404)

    conn = get_conn()
    t = conn.execute(
        """
        SELECT
            t.id,
            t.title,
            t.description,
            t.status,
            t.priority,
            t.created_at,
            t.updated_at,
            t.closed_at,
            t.reporter_id,
            t.assignee_id,
            t.project_id,
            ru.username AS reporter_username,
            au.username AS assignee_username
        FROM tickets t
        LEFT JOIN users ru ON t.reporter_id = ru.id
        LEFT JOIN users au ON t.assignee_id = au.id
        WHERE t.id = ?
        """,
        (ticket_id,),
    ).fetchone()
    conn.close()

    if t is None or t["project_id"] != project_id:
        abort(404)

    return render_template(
        "ticket_detail.html",
        ticket=t,
        can_edit=can_edit_ticket(ticket_id),
        project_id=project_id,
    )

