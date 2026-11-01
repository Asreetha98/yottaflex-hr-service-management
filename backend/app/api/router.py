from fastapi import APIRouter

from app.api import admin, analytics, auth, employees, knowledge, policies, sla, tickets

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(employees.router)
api_router.include_router(tickets.router)
api_router.include_router(policies.router)
api_router.include_router(knowledge.router)
api_router.include_router(sla.router)
api_router.include_router(analytics.router)
api_router.include_router(admin.router)
