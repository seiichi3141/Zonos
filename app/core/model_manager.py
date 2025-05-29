"""
モデル管理モジュール
モデルのロード、キャッシュ、初期化を管理
"""
import os
import logging
import time
from zonos.model import Zonos
from zonos.utils import DEFAULT_DEVICE as device

from app import config
from app.core import cache

logger = logging.getLogger(__name__)

# グローバル変数でモデルとデフォルトスピーカーを管理
model = None
default_speaker = None

def load_model_from_cache(repo_id, revision=None):
    """キャッシュからモデルを読み込む（HuggingFaceから再ダウンロードせずに高速化）"""
    from huggingface_hub import hf_hub_download
    
    try:
        # キャッシュディレクトリの取得（ライブラリのデフォルトキャッシュを活用）
        from huggingface_hub import constants
        hf_cache_dir = os.getenv("HF_HOME", constants.default_cache_path)
        
        # キャッシュが既にあるかどうかを確認するために、キャッシュされたパスを計算せずに
        # 存在確認のためにダウンロードを試みる（キャッシュがあれば再ダウンロードしない）
        logger.info(f"モデルファイルのキャッシュを確認中: {repo_id}")
        config_path = hf_hub_download(repo_id=repo_id, filename="config.json", revision=revision)
        model_path = hf_hub_download(repo_id=repo_id, filename="model.safetensors", revision=revision)
        
        if os.path.exists(config_path) and os.path.exists(model_path):
            logger.info(f"キャッシュされたモデルファイルを使用します: {model_path}")
            return Zonos.from_local(config_path, model_path, device=device)
        
    except Exception as e:
        logger.error(f"キャッシュからのモデル読み込みエラー: {e}")
        
    # キャッシュがない場合や読み込みエラーの場合はデフォルトのロード方式に戻る
    logger.info(f"モデルを通常方式で読み込みます: {repo_id}")
    return Zonos.from_pretrained(repo_id, revision=revision, device=device)

async def initialize_model():
    """モデルと必要なリソースを初期化する"""
    global model, default_speaker
    
    # キャッシュディレクトリの確認
    cache.ensure_cache_dir()
    
    # スピーカーエンベディングキャッシュの読み込み
    cache.SPEAKER_EMBEDDING_CACHE = cache.load_speaker_embedding_cache()
    
    # 起動時の処理
    logger.info("モデルを読み込み中...")
    start_time = time.time()
    
    # キャッシュからモデルを読み込む（なければダウンロード）
    model = load_model_from_cache(config.DEFAULT_MODEL_REPO)
    logger.info(f"モデル読み込み完了 ({time.time() - start_time:.2f}秒)")
    
    # デフォルトスピーカーを設定
    if os.path.exists(config.DEFAULT_SPEAKER_PATH):
        logger.info("デフォルトスピーカーを読み込み中...")
        start_time = time.time()
        default_speaker = cache.cached_speaker_embedding(model, config.DEFAULT_SPEAKER_PATH)
        logger.info(f"デフォルトスピーカー読み込み完了 ({time.time() - start_time:.2f}秒)")
    else:
        logger.warning("警告: デフォルトスピーカーのアセットが見つかりません。音声合成はデフォルトスピーカーなしで行われます。")
    
    logger.info("モデル初期化完了！")
    return model, default_speaker

def cleanup_resources():
    """リソースのクリーンアップ処理"""
    # キャッシュの保存
    cache.save_speaker_embedding_cache()
    logger.info("リソースのクリーンアップ完了")
    
def get_model():
    """現在のモデルインスタンスを取得"""
    return model

def get_default_speaker():
    """デフォルトスピーカーエンベディングを取得"""
    return default_speaker
