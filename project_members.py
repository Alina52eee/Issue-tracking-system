from db import get_conn
from auth_utils import current_user, is_admin
#from project_members import (can_view_project, can_manage_members, get_project_role, can_create_ticket)



def get_project_role(project_id):
    """Вернуть роль текущего пользователя в проекте или None, если он не участник.

    Администратор (master) считается владельцем всех проектов.
    """
    user = current_user()
    if user is None:
        return None

    if is_admin():
        # Глобальный администратор обладает максимальными правами
        return "owner"

    conn = get_conn()
    row = conn.execute(
        """
        SELECT role
        FROM project_members
        WHERE project_id = ? AND user_id = ?
        """,
        (project_id, user["id"]),
    ).fetchone()
    conn.close()

    if row is None:
        return None

    return row["role"]

def can_view_project(project_id):
    """Можно ли текущему пользователю видеть этот проект."""
    role = get_project_role(project_id)
    return role is not None


def can_manage_members(project_id):
    """Можно ли управлять участниками проекта (добавлять/удалять, менять роли)."""
    role = get_project_role(project_id)
    return role == "owner"

def can_create_ticket(project_id):
    """Можно ли создавать заявки в этом проекте."""
    role = get_project_role(project_id)
    return role in ("owner", "maintainer", "reporter")


def can_edit_ticket_in_project(ticket_row):
    """Можно ли редактировать конкретную заявку."""
    # ticket_row должен содержать как минимум поля:
    # project_id, reporter_id
    user = current_user()
    if user is None:
        return False

    if is_admin():
        return True

    role = get_project_role(ticket_row["project_id"])

    if role in ("owner", "maintainer"):
        return True

    if role == "reporter" and ticket_row["reporter_id"] == user["id"]:
        return True

    return False

