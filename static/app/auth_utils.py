def is_logged_in():
    return session.get("user_id") is not None

def current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None

    conn = get_conn()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ? AND archived_at IS NULL",
        (user_id,),
    ).fetchone()
    conn.close()

    return user

'''
def current_user():
    """Возвращает строку текущего пользователя (dict-like) или None."""
    uid = session.get("user_id")
    if uid is None:
        return None
    conn = get_conn()
    user = conn.execute(
        "SELECT id, username, role FROM users WHERE id = ? AND archived_at IS NULL",
        (uid,),
    ).fetchone()
    conn.close()
    return user
'''


def create_user(username, password, role):
    """
    Создать пользователя с указанным логином, паролем и ролью.
    На этом этапе пароль сохраняется как есть (будем улучшать позже).
    """
    password_hash = generate_password_hash(password)

    conn = get_conn()
    conn.execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        (username, password_hash, role),
    )
    conn.commit()
    conn.close()




def get_registration_open():
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = 'registration_open'").fetchone()
    conn.close()
    return row is not None and row["value"] == "1"



def ensure_master():
    """
    Убедиться, что в системе есть хотя бы один администратор.
    Если нет — создать пользователя master/master с ролью admin.
    """
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM users WHERE role = 'admin' AND archived_at IS NULL LIMIT 1"
    ).fetchone()

    if row is None:
        create_user("master", "master", "admin")

    conn.close()

def get_registration_open():
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = 'registration_open'").fetchone()
    conn.close()
    return row is not None and row["value"] == "1"

def is_admin():
    u = current_user()
    return u is not None and u["role"] == "admin"

def is_agent():
    user = current_user()
    return user is not None and user["role"] == "agent"

