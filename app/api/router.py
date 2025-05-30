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

from app import config
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
    split_text: bool = False  # 長いテキストをOpenAI APIを使って自然に分割するか

# ルーター作成
router = APIRouter()

@router.post("/synthesize")
async def synthesize_speech(request: TTSRequest):
    """テキストを音声に変換して返す"""
    if model_manager.get_model() is None:
        raise HTTPException(status_code=500, detail="モデルが初期化されていません")
    
    if request.use_default_speaker and model_manager.get_default_speaker() is None:
        raise HTTPException(status_code=500, detail="デフォルトスピーカーが利用できません")
    
    # ストリーミングリクエストの場合
    if request.streaming:
        async def stream():
            temp_files = []
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
        
        return StreamingResponse(
            stream(),
            media_type="application/json"
        )
    
    # 非ストリーミングリクエストの場合
    else:
        # 長いテキストを分割する場合
        if request.split_text:
            # ストリーミングなしでテキスト分割を使用する場合はエラーとする
            raise HTTPException(
                status_code=400, 
                detail="テキスト分割機能はストリーミングモードでのみ使用できます。streaming=trueを指定してください。"
            )
        # 従来の方式（非ストリーミング）
        else:
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
        "default_speaker_available": model_manager.get_default_speaker() is not None,
        "config": {
            "openai_api_key_set": bool(config.OPENAI_API_KEY),
            "model_repo": config.DEFAULT_MODEL_REPO,
            "openai_model": config.OPENAI_MODEL
        }
    }

@router.get("/")
async def root():
    """ルートエンドポイント"""
    # OpenAI APIキーが設定されているか確認
    openai_key_status = "設定済み" if config.OPENAI_API_KEY else "未設定"
    
    return {
        "message": "Zonos TTS API",
        "endpoints": {
            "/synthesize": "テキスト音声合成（streaming=trueで進捗表示可能）",
            "/download/{filename}": "一時ファイルのダウンロード",
            "/health": "ヘルスチェック",
            "/docs": "API文書"
        },
        "streaming_usage": "streaming=trueを指定すると進捗率がJSON形式でストリーミング返却されます",
        "split_text_usage": f"長いテキストはsplit_text=trueを指定するとOpenAI APIを使って自然な区切りで分割されます（streaming=trueが必要）。OpenAI APIキー: {openai_key_status}",
        "environment": {
            "model": config.DEFAULT_MODEL_REPO,
            "openai_model": config.OPENAI_MODEL
        }
    }
