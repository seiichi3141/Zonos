"""
アプリケーション設定モジュール
"""
import os
import logging
from dotenv import load_dotenv

# .envファイルから環境変数を読み込み
load_dotenv()

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# パス関連の設定
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
MODEL_CACHE_PATH = os.path.join(CACHE_DIR, "model_cache.pkl")
SPEAKER_CACHE_PATH = os.path.join(CACHE_DIR, "speaker_cache.pkl")
ASSET_PATH = os.path.join(BASE_DIR, "assets")
DEFAULT_SPEAKER_PATH = os.path.join(ASSET_PATH, "anno-sample.mp3")

# キャッシュ設定
CACHE_EXPIRY_TIME = 24 * 60 * 60  # 24時間（秒）

# サーバー設定
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))

# モデル設定
DEFAULT_MODEL_REPO = os.environ.get("DEFAULT_MODEL_REPO", "Zyphra/Zonos-v0.1-transformer")

# API情報
API_TITLE = "Zonos TTS API"
API_DESCRIPTION = "Text-to-Speech API using Zonos model"

# OpenAI API設定
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")  # テキスト分割に使用するモデル
