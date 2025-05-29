"""
メインアプリケーションエントリポイント
FastAPIアプリケーションの初期化と実行
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app import config
from app.core import model_manager
from app.api.router import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    # 起動時の処理
    await model_manager.initialize_model()
    
    yield
    
    # 終了時の処理
    model_manager.cleanup_resources()

app = FastAPI(
    title=config.API_TITLE, 
    description=config.API_DESCRIPTION,
    lifespan=lifespan
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Next.jsの開発サーバー
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターを登録
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host=config.HOST, port=config.PORT)
