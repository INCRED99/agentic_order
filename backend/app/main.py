from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import me, menu,orders,approvals
from app.webhooks import router as webhooks_router  # webhook router

app = FastAPI(title="Order Desk API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(me.router)
app.include_router(menu.router)
app.include_router(orders.router)
app.include_router(approvals.router)
app.include_router(webhooks_router)  # mounts POST /webhooks/razorpay



@app.get("/health")
def health():
    return {"ok": True}