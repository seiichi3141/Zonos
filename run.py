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
    
    # 環境変数の設定状況を出力
    print(f"\n環境変数の設定状況:")
    print(f"- ホスト: {config.HOST}")
    print(f"- ポート: {config.PORT}")
    print(f"- モデル: {config.DEFAULT_MODEL_REPO}")
    print(f"- OpenAI APIキー: {'設定済み' if config.OPENAI_API_KEY else '未設定'}")
    print(f"- OpenAI モデル: {config.OPENAI_MODEL}")
    
    uvicorn.run(app, host=config.HOST, port=config.PORT)
