"""
APIルーターモジュール
FastAPIルートハンドラとエンドポイント定義
"""
import os
import logging
import asyncio
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator

from app.core import model_manager
from app.api import tts
from app.utils import audio

logger = logging.getLogger(__name__)

# APIモデル定義
class TTSRequest(BaseModel):
    text: str
    language: str = "ja"
    use_default_speaker: bool = True
    streaming: bool = False  # ストリーミングレスポンスを使用するかどうか
    speaking_rate: float = 15.0  # 話速（フォネーム/秒）: 10=遅い, 15=普通, 30=かなり速い

# ルーター作成
router = APIRouter()

@router.post("/synthesize")
async def synthesize_speech(request: TTSRequest):
    """テキストを音声に変換して返す"""
    if model_manager.get_model() is None:
        raise HTTPException(status_code=500, detail="モデルが初期化されていません")
    
    if request.use_default_speaker and model_manager.get_default_speaker() is None:
        raise HTTPException(status_code=500, detail="デフォルトスピーカーが利用できません")
    
    if request.streaming:
        async def stream_with_cleanup():
            temp_files = []
            try:
                async for chunk in tts.generate_speech_stream(
                    request.text, 
                    request.language, 
                    request.use_default_speaker, 
                    request.speaking_rate
                ):
                    # ファイルパスを記録
                    if '"file_path"' in chunk:
                        import re
                        match = re.search(r'"file_path":\s*"([^"]+)"', chunk)
                        if match:
                            temp_files.append(match.group(1))
                    yield chunk
            finally:
                # ストリーミング完了後にファイルを遅延削除
                for temp_file in temp_files:
                    if os.path.exists(temp_file):
                        asyncio.create_task(audio.cleanup_temp_file(temp_file))
        
        return StreamingResponse(
            stream_with_cleanup(),
            media_type="application/json"
        )
    else:
        # 従来の方式（非ストリーミング）
        try:
            temp_file_path = await tts.synthesize_speech_sync(
                request.text, 
                request.language, 
                request.use_default_speaker, 
                request.speaking_rate
            )
            
            return FileResponse(
                path=temp_file_path,
                media_type="audio/wav",
                filename="synthesized_speech.wav"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"音声合成エラー: {str(e)}")

# 一時ファイルダウンロード用のエンドポイント
@router.get("/download/{filename}")
async def download_file(filename: str):
    """一時ファイルをダウンロードするエンドポイント"""
    import tempfile
    temp_file_path = os.path.join(tempfile.gettempdir(), filename)
    
    if not os.path.exists(temp_file_path):
        raise HTTPException(status_code=404, detail="ファイルが見つかりません")
    
    # 非同期的にファイル削除を行うタスクを作成
    asyncio.create_task(audio.cleanup_temp_file(temp_file_path))
    
    return FileResponse(
        path=temp_file_path,
        media_type="audio/wav",
        filename="synthesized_speech.wav"
    )

@router.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "model_loaded": model_manager.get_model() is not None,
        "default_speaker_available": model_manager.get_default_speaker() is not None
    }

@router.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "message": "Zonos TTS API",
        "endpoints": {
            "/synthesize": "テキスト音声合成（streaming=trueで進捗表示可能）",
            "/download/{filename}": "一時ファイルのダウンロード",
            "/health": "ヘルスチェック",
            "/docs": "API文書"
        },
        "streaming_usage": "streaming=trueを指定すると進捗率がJSON形式でストリーミング返却されます"
    }
