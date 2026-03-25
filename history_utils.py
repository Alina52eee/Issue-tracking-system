import json

from db import get_conn
from auth_utils import current_user


def log_issue_event(ticket_id, action_type, data_dict=None):
    """Записать событие в таблицу issue_history."""
    user = current_user()
    user_id = user["id"] if user is not None else None
    data_str = json.dumps(data_dict or {}, ensure_ascii=False)

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO issue_history (ticket_id, user_id, action_type, data)
        VALUES (?, ?, ?, ?)
        """,
        (ticket_id, user_id, action_type, data_str),
    )
    conn.commit()
    conn.close()