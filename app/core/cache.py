"""
キャッシュ管理モジュール
スピーカーエンベディングやモデルのキャッシュ機能を提供
"""
import os
import pickle
import time
import torch
import logging
from typing import Dict, Tuple

from app import config

logger = logging.getLogger(__name__)

# スピーカーエンベディングのキャッシュデータ
SPEAKER_EMBEDDING_CACHE: Dict[str, Tuple[torch.Tensor, float]] = {}

def ensure_cache_dir():
    """キャッシュディレクトリの存在を確認し、なければ作成する"""
    if not os.path.exists(config.CACHE_DIR):
        os.makedirs(config.CACHE_DIR, exist_ok=True)
        logger.info(f"キャッシュディレクトリを作成しました: {config.CACHE_DIR}")

def save_speaker_embedding_cache():
    """スピーカーエンベディングをキャッシュに保存"""
    ensure_cache_dir()
    try:
        with open(config.SPEAKER_CACHE_PATH, 'wb') as f:
            pickle.dump(SPEAKER_EMBEDDING_CACHE, f)
        logger.info(f"スピーカーエンベディングをキャッシュに保存しました: {config.SPEAKER_CACHE_PATH}")
    except Exception as e:
        logger.error(f"スピーカーエンベディングのキャッシュ保存エラー: {e}")

def load_speaker_embedding_cache() -> Dict[str, Tuple[torch.Tensor, float]]:
    """スピーカーエンベディングをキャッシュから読み込み"""
    if os.path.exists(config.SPEAKER_CACHE_PATH):
        try:
            with open(config.SPEAKER_CACHE_PATH, 'rb') as f:
                cache = pickle.load(f)
            logger.info(f"スピーカーエンベディングをキャッシュから読み込みました: {config.SPEAKER_CACHE_PATH}")
            return cache
        except Exception as e:
            logger.error(f"スピーカーエンベディングのキャッシュ読み込みエラー: {e}")
    return {}

def cached_speaker_embedding(model, wav_path):
    """キャッシュを活用したスピーカーエンベディング生成"""
    global SPEAKER_EMBEDDING_CACHE
    
    # キャッシュが有効かチェック
    current_time = time.time()
    if wav_path in SPEAKER_EMBEDDING_CACHE:
        embedding, timestamp = SPEAKER_EMBEDDING_CACHE[wav_path]
        # キャッシュの有効期限をチェック
        if current_time - timestamp < config.CACHE_EXPIRY_TIME:
            logger.info(f"キャッシュからスピーカーエンベディングを使用: {wav_path}")
            return embedding
    
    # キャッシュに無いか期限切れの場合は新しく生成
    logger.info(f"新しいスピーカーエンベディングを生成: {wav_path}")
    start_time = time.time()
    
    import torchaudio
    wav, sampling_rate = torchaudio.load(wav_path)
    embedding = model.make_speaker_embedding(wav, sampling_rate)
    
    # キャッシュに保存
    SPEAKER_EMBEDDING_CACHE[wav_path] = (embedding, current_time)
    save_speaker_embedding_cache()
    
    logger.info(f"スピーカーエンベディング生成完了: {wav_path} ({time.time() - start_time:.2f}秒)")
    return embedding
