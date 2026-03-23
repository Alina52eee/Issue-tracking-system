from flask import render_template, redirect, url_for, request, abort, flash
from auth_utils import is_logged_in, current_user, is_admin
from project_members import (
    can_view_project,
    can_manage_members,
    get_project_role,
)
from db import get_conn

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

    conn = get_conn()

    # Проекты, где я владелец
    my_projects = conn.execute(
        """
        SELECT p.id, p.title, p.description, p.is_archived, p.created_at
        FROM projects p
        JOIN project_members pm
          ON pm.project_id = p.id
        WHERE pm.user_id = ? AND pm.role = 'owner' AND p.is_archived = 0
        ORDER BY p.created_at DESC
        """,
        (user["id"],),
    ).fetchall()

    # Проекты, где я участник (но не владелец)
    collaborating_projects = conn.execute(
        """
        SELECT p.id, p.title, p.description, p.is_archived, p.created_at, pm.role
        FROM projects p
        JOIN project_members pm
          ON pm.project_id = p.id
        WHERE pm.user_id = ?
          AND pm.role IN ('maintainer', 'reporter')
          AND p.is_archived = 0
        ORDER BY p.created_at DESC
        """,
        (user["id"],),
    ).fetchall()

    conn.close()

    return render_template(
        "project_list.html",
        my_projects=my_projects,
        collaborating_projects=collaborating_projects,
    )


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
    cursor = conn.execute(
        "INSERT INTO projects (owner_id, title, description) VALUES (?, ?, ?)",
        (user["id"], title, description),
    )
    project_id = cursor.lastrowid

    # Владелец проекта автоматически становится участником с ролью owner
    conn.execute(
        "INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, 'owner')",
        (project_id, user["id"]),
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


        conn = get_conn()

    # Заявки проекта (как в Части G)
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

    # Участники проекта
    members = conn.execute(
        """
        SELECT
            pm.user_id,
            pm.role,
            u.username,
            u.archived_at
        FROM project_members pm
        JOIN users u ON pm.user_id = u.id
        WHERE pm.project_id = ?
        ORDER BY
            CASE pm.role
                WHEN 'owner' THEN 0
                WHEN 'maintainer' THEN 1
                ELSE 2
            END,
            u.username
        """,
        (project_id,),
    ).fetchall()

    candidate_users = conn.execute(
        """
        SELECT id, username
        FROM users
        WHERE archived_at IS NULL
          AND id NOT IN (
            SELECT user_id FROM project_members WHERE project_id = ?
          )
        ORDER BY username
        """,
        (project_id,),
    ).fetchall()

    conn.close()
    return render_template(
        "project_detail.html",
        project=project,
        tickets=tickets,
        members=members,
        project_role=get_project_role(project_id),
        candidate_users=candidate_users,
    )

def project_member_add_view(project_id):
    """Добавить участника в проект (только владелец)."""
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))

    project = get_project(project_id)
    if project is None:
        abort(404)

    if not can_manage_members(project_id):
        abort(403)

    user_id = request.form.get("user_id")
    role = request.form.get("role") or ""

    if not user_id or role not in ("maintainer", "reporter"):
        flash("Некорректные данные участника.")
        return redirect(url_for("project_detail", project_id=project_id))

    try:
        user_id_int = int(user_id)
    except ValueError:
        flash("Некорректный пользователь.")
        return redirect(url_for("project_detail", project_id=project_id))

    conn = get_conn()

    # Проверим, что такой пользователь существует и не является архивированным
    u = conn.execute(
        "SELECT id, username, archived_at FROM users WHERE id = ?",
        (user_id_int,),
    ).fetchone()
    if u is None or u["archived_at"] is not None:
        conn.close()
        flash("Нельзя добавить несуществующего или архивированного пользователя.")
        return redirect(url_for("project_detail", project_id=project_id))

    # Не дублируем участников
    existing = conn.execute(
        """
        SELECT 1
        FROM project_members
        WHERE project_id = ? AND user_id = ?
        """,
        (project_id, user_id_int),
    ).fetchone()

    if existing is None:
        conn.execute(
            """
            INSERT INTO project_members (project_id, user_id, role)
            VALUES (?, ?, ?)
            """,
            (project_id, user_id_int, role),
        )
        conn.commit()
        flash(f"Пользователь {u['username']} добавлен в проект как {role}.")
    else:
        flash("Этот пользователь уже участвует в проекте.")

    conn.close()
    return redirect(url_for("project_detail", project_id=project_id))

def project_member_remove_view(project_id, user_id):
    """Удалить участника из проекта (кроме владельца)."""
    if not is_logged_in():
        return redirect(url_for("login_form", next=request.url))

    project = get_project(project_id)
    if project is None:
        abort(404)

    if not can_manage_members(project_id):
        abort(403)

    try:
        user_id_int = int(user_id)
    except ValueError:
        abort(400)

    conn = get_conn()

    # Нельзя удалить владельца проекта
    member = conn.execute(
        """
        SELECT pm.role, u.username
        FROM project_members pm
        JOIN users u ON pm.user_id = u.id
        WHERE pm.project_id = ? AND pm.user_id = ?
        """,
        (project_id, user_id_int),
    ).fetchone()

    if member is None:
        conn.close()
        flash("Участник не найден.")
        return redirect(url_for("project_detail", project_id=project_id))

    if member["role"] == "owner":
        conn.close()
        flash("Нельзя удалить владельца проекта.")
        return redirect(url_for("project_detail", project_id=project_id))

    conn.execute(
        "DELETE FROM project_members WHERE project_id = ? AND user_id = ?",
        (project_id, user_id_int),
    )
    conn.commit()
    conn.close()

    flash(f"Пользователь {member['username']} удалён из проекта.")
    return redirect(url_for("project_detail", project_id=project_id))