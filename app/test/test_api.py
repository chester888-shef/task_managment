import uuid
import httpx

BASE_URL = "http://localhost:8000"


def get_auth_headers() -> dict:
    """Допоміжна функція: реєструє нового юзера, логіниться і повертає токен."""
    unique = uuid.uuid4().hex[:6]
    email = f"user_{unique}@example.com"
    username = f"user_{unique}"
    password = "password123"

    with httpx.Client(base_url=BASE_URL) as client:
        # 1. Реєстрація
        reg_res = client.post(
            "/auth/register",
            json={"email": email, "username": username, "password": password},
        )
        assert reg_res.status_code in (200, 201)

        # 2. Логін
        login_res = client.post(
            "/auth/login",
            data={"username": email, "password": password},
        )
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}


def test_health():
    """Тест 1: Перевірка, що API працює."""
    res = httpx.get(f"{BASE_URL}/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_create_and_get_task():
    """Тест 2: Створення задачі та отримання її за ID."""
    headers = get_auth_headers()
    with httpx.Client(base_url=BASE_URL, headers=headers) as client:
        res = client.post(
            "/tasks/",
            json={"title": "Test task", "description": "Test desc", "priority": "high"},
        )
        assert res.status_code == 201
        task = res.json()
        assert task["title"] == "Test task"
        assert task["status"] == "backlog"


def test_status_transition_rules():
    """Тест 3: Перевірка переходів статусу (Backlog -> In Progress дозволено, назад - заборонено)."""
    headers = get_auth_headers()
    with httpx.Client(base_url=BASE_URL, headers=headers) as client:
        # Створюємо задачу
        task_id = client.post("/tasks/", json={"title": "Status test"}).json()["id"]

        # Переводимо в in_progress (має пройти успішно)
        res_ok = client.patch(f"/tasks/{task_id}/status", json={"status": "in_progress"})
        assert res_ok.status_code == 200
        assert res_ok.json()["status"] == "in_progress"

        # Пробуємо повернути назад у backlog (має видати помилку 400 за бізнес-логікою)
        res_err = client.patch(f"/tasks/{task_id}/status", json={"status": "backlog"})
        assert res_err.status_code == 400


def test_cannot_delete_in_progress_task():
    """Тест 4: Заборона видалення задачі у статусі In Progress."""
    headers = get_auth_headers()
    with httpx.Client(base_url=BASE_URL, headers=headers) as client:
        task_id = client.post("/tasks/", json={"title": "Delete test"}).json()["id"]
        client.patch(f"/tasks/{task_id}/status", json={"status": "in_progress"})

        # Спроба видалити активну задачу в роботі має повернути 400
        del_res = client.delete(f"/tasks/{task_id}")
        assert del_res.status_code == 400