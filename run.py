"""
アプリケーション実行スクリプト
リファクタリングされたアプリケーションを起動
"""
import uvicorn
from app.main import app
from app import config

if __name__ == "__main__":
    print("Zonos TTS APIサーバーを起動中...")
    print(f"サーバーはhttp://{config.HOST}:{config.PORT}で起動します")
    print("APIドキュメントは http://localhost:8000/docs で確認できます")
    uvicorn.run(app, host=config.HOST, port=config.PORT)
