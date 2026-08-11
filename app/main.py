from fastapi import FastAPI

from app.api.routes.customers import router as customers_router

app = FastAPI(title="RegTech Platform")

app.include_router(customers_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
