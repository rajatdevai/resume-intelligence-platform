import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.resume import router as resume_router

app = FastAPI(
    title="Resume Intelligence Platform API",
    description="Backend API for Resume Customizer Web App",
    version="1.0.0"
)

# CORS Configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume_router)

@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "environment": settings.ENV,
        "llm_provider": settings.LLM_PROVIDER
    }

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True if settings.ENV == "development" else False
    )
