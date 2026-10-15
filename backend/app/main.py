import os
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import me, menu,orders,approvals,agent_runs,emails
from app.webhooks import router as webhooks_router  # webhook router

from app import worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("RUN_WORKER") == "1":  # only on Render, not in local dev
        threading.Thread(target=worker.main, daemon=True).start()
    yield
app = FastAPI(title="Order Desk API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://agentic-order.vercel.app", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(me.router)
app.include_router(menu.router)
app.include_router(orders.router)
app.include_router(approvals.router)
app.include_router(agent_runs.router)
app.include_router(webhooks_router)  # mounts POST /webhooks/razorpay
app.include_router(emails.router)   # D1: routes for incoming and outbound mail


@app.get("/health")
def health():
    return {"ok": True}