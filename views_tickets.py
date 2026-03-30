from flask import render_template, redirect, url_for, request, abort
from project_members import can_create_ticket
from db import get_conn
from views_projects import get_project  # если нужно
from auth_utils import is_logged_in, current_user, is_admin
from project_members import can_view_project, can_edit_ticket_in_project, can_create_ticket
from views_projects import get_project
from history_utils import log_issue_event

def tickets_for_project(project_id):
    """Вернуть все заявки этого проекта с учетом роли текущего пользователя (admin/не admin)."""
    user = current_user()
    if user is None:
        return []

    conn = get_conn()
    try:
        if is_admin():
            # Админ/менеджер видит все заявки проекта
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
            # Остальные видят только заявки, где они автор или исполнитель
            # (тут логика может отличаться от требований, но это НЕ про падение — это про “какие заявки покажут”)
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
        """
        SELECT
            id,
            reporter_id,
            assignee_id,
            project_id
        FROM tickets
        WHERE id = ?
        """,
        (ticket_id,),
    ).fetchone()
    conn.close()

    if t is None:
        return False, None

    # Админ по‑прежнему видит все заявки
    if is_admin():
        return True, t

    # Остальные — только если они участники проекта
    if not can_view_project(t["project_id"]):
        return False, None

    return True, t


def can_edit_ticket(ticket_id):
    """Можно ли редактировать эту заявку (менять статус, исполнителя и т.п.)."""
    user = current_user()
    if user is None:
        return False

    if is_admin():
        return True

    conn = get_conn()
    t = conn.execute(
        """
        SELECT
            id,
            reporter_id,
            assignee_id,
            project_id
        FROM tickets
        WHERE id = ?
        """,
        (ticket_id,),
    ).fetchone()
    conn.close()

    if t is None:
        return False

    return can_edit_ticket_in_project(t)

def ticket_list_view(project_id):
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))

    tickets = tickets_for_project(project_id)
    return render_template("ticket_list.html", tickets=tickets, project_id=project_id)


def ticket_new_view(project_id):
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))

    project = get_project(project_id)
    if project is None or project["is_archived"]:
        abort(403)

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
    
    project = get_project(project_id)
    if project is None or project["is_archived"]:
        abort(403)

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
    cursor = conn.execute(
        "INSERT INTO tickets (title, description, reporter_id, project_id, status, priority) "
        "VALUES (?, ?, ?, ?, 'Open', ?)",
        (title, description, user["id"], project_id, priority),
    )
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()

    log_issue_event(
        ticket_id,
        "created",
        {
            "project_id": project_id,
            "title": title,
            "priority": priority,
        },
    )

    return redirect(url_for("ticket_list", project_id=project_id))


def ticket_detail_view(project_id: int, ticket_id: int):
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))

    can_view, _ = can_view_ticket(ticket_id)
    if not can_view:
        abort(404)

    conn = get_conn()
    t = conn.execute("""
        SELECT
            t.id,
            t.project_id,           -- ВАЖНО: нужен для проверки и отладки
            t.title,
            t.description,
            t.status,
            t.priority,
            t.created_at,
            t.updated_at,
            t.closed_at,
            t.reporter_id,
            t.assignee_id,
            ru.username AS reporter_username,
            ru.archived_at AS reporter_archived,
            au.username AS assignee_username,
            au.archived_at AS assignee_archived
        FROM tickets t
        LEFT JOIN users ru ON t.reporter_id = ru.id
        LEFT JOIN users au ON t.assignee_id = au.id
        WHERE t.id = ?
    """, (ticket_id,)).fetchone()
    conn.close()

    if t is None or t["project_id"] != project_id:
        abort(404)

    conn = get_conn()
    comments = conn.execute(
        """
        SELECT
            c.id,
            c.body,
            c.created_at,
            c.user_id,
            u.username AS author_username
        FROM comments c
        LEFT JOIN users u ON c.user_id = u.id
        WHERE c.ticket_id = ?
        ORDER BY c.created_at ASC
        """,
        (ticket_id,),
    ).fetchall()
    

    history = conn.execute(
        """
        SELECT
            h.id,
            h.action_type,
            h.data,
            h.created_at,
            h.user_id,
            u.username AS author_username
        FROM issue_history h
        LEFT JOIN users u ON h.user_id = u.id
        WHERE h.ticket_id = ?
        ORDER BY h.created_at DESC
        """,
        (ticket_id,),
    ).fetchall()

    user = current_user()
    can_comment = (
        user is not None
        and can_view_project(project_id)
    )

    conn.close()
    return render_template(
        "ticket_detail.html",
        ticket=t,
        can_edit=can_edit_ticket(ticket_id),
        project_id=project_id,
        comments=comments,
        can_comment=can_comment,
        history=history,
    )

def comment_create_view(project_id: int, ticket_id: int):
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))

    can_view, _ = can_view_ticket(ticket_id)
    if not can_view:
        abort(404)

    project = get_project(project_id)
    if project is None or project["is_archived"]:
        abort(403)

    body = (request.form.get("body") or "").strip()
    if not body:
        return redirect(url_for("ticket_detail", project_id=project_id, ticket_id=ticket_id))

    conn = get_conn()
    user = current_user()
    user_id = user["id"] if user is not None else None

    conn.execute(
        """
        INSERT INTO comments (ticket_id, user_id, body)
        VALUES (?, ?, ?)
        """,
        (ticket_id, user_id, body),
    )
    conn.commit()
    conn.close()

    log_issue_event(
        ticket_id,
        "comment_added",
        {
            "project_id": project_id,
            "snippet": body[:100],
        },
    )

    return redirect(url_for("ticket_detail", project_id=project_id, ticket_id=ticket_id))

    project = get_project(project_id)
    if project is None or project["is_archived"]:
        abort(403)