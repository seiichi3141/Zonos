"""
メインアプリケーションエントリポイント
FastAPIアプリケーションの初期化と実行
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
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

# ルーターを登録
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host=config.HOST, port=config.PORT)
