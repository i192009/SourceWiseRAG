from fastapi import FastAPI

from backend.app.core.logging_config import configure_logging
from backend.app.core.settings import APP_NAME, APP_VERSION
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.files import router as files_router
from backend.app.api.routes.jobs import router as jobs_router
from backend.app.api.routes.chat import router as chat_router
from backend.app.api.routes.sources import router as sources_router
from backend.app.api.routes.web_search import router as web_search_router
from backend.app.api.routes.admin import router as admin_router
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.users import router as users_router
from backend.app.api.routes.conversations import router as conversations_router
from backend.app.storage.sqlite_store import init_sqlite

configure_logging()

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
)


@app.on_event("startup")
def on_startup():
    init_sqlite()


app.include_router(health_router)
app.include_router(files_router)
app.include_router(jobs_router)
app.include_router(chat_router)
app.include_router(sources_router)
app.include_router(web_search_router)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(conversations_router)
