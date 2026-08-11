from fastapi import FastAPI

from app.api.routes.customers import router as customers_router
from app.api.routes.identity import router as identity_router
from app.api.routes.sanctions import router as sanctions_router

app = FastAPI(title="RegTech Platform")

app.include_router(customers_router)
app.include_router(identity_router)
app.include_router(sanctions_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
