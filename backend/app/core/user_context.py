from fastapi import Request


def get_current_user_context(request: Request):
    user_id = request.headers.get("X-User-Id")
    username = request.headers.get("X-Username")
    name = request.headers.get("X-Name")

    if user_id and username:
        return {
            "user_id": user_id,
            "username": username,
            "name": name or username,
        }

    return {
        "user_id": "demo-user-001",
        "username": "demo_user",
        "name": "Demo User",
    }
