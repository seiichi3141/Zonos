"""
音声処理ユーティリティ
一時ファイル管理や音声出力処理のヘルパー関数
"""
import os
import tempfile
import torchaudio
import asyncio
import logging

logger = logging.getLogger(__name__)

async def cleanup_temp_file(file_path: str, delay: int = 5):
    """一時ファイルを遅延削除するためのヘルパー関数"""
    try:
        # 少し待ってからファイルを削除（ダウンロードの時間を確保）
        await asyncio.sleep(delay)
        if os.path.exists(file_path):
            os.unlink(file_path)
            logger.debug(f"一時ファイルを削除しました: {file_path}")
    except Exception as e:
        logger.error(f"一時ファイル削除エラー: {e}")
        pass  # ファイル削除エラーは無視

def save_audio_to_temp_file(audio_tensor, sample_rate):
    """音声テンソルを一時WAVファイルに保存"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        torchaudio.save(temp_file.name, audio_tensor, sample_rate)
        return temp_file.name
