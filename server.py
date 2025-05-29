import os
import tempfile
import torchaudio
import torch
import json
import asyncio
import concurrent.futures
import queue
import pickle
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from zonos.model import Zonos
from zonos.conditioning import make_cond_dict
from zonos.utils import DEFAULT_DEVICE as device
from pydantic import BaseModel
from typing import AsyncGenerator, Dict, Any, Tuple, Optional
import uvicorn
import time
import logging

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# グローバル変数でモデルとデフォルトスピーカーを管理
model = None
default_speaker = None

# キャッシュ関連の設定
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
MODEL_CACHE_PATH = os.path.join(CACHE_DIR, "model_cache.pkl")
SPEAKER_CACHE_PATH = os.path.join(CACHE_DIR, "speaker_cache.pkl")
SPEAKER_EMBEDDING_CACHE: Dict[str, Tuple[torch.Tensor, float]] = {}  # {file_path: (embedding, timestamp)}
CACHE_EXPIRY_TIME = 24 * 60 * 60  # 24時間（秒）

class TTSRequest(BaseModel):
    text: str
    language: str = "ja"
    use_default_speaker: bool = True
    streaming: bool = False  # ストリーミングレスポンスを使用するかどうか
    speaking_rate: float = 15.0  # 話速（フォネーム/秒）: 10=遅い, 15=普通, 30=かなり速い

def ensure_cache_dir():
    """キャッシュディレクトリの存在を確認し、なければ作成する"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)
        logger.info(f"キャッシュディレクトリを作成しました: {CACHE_DIR}")

def save_speaker_embedding_cache():
    """スピーカーエンベディングをキャッシュに保存"""
    ensure_cache_dir()
    try:
        with open(SPEAKER_CACHE_PATH, 'wb') as f:
            pickle.dump(SPEAKER_EMBEDDING_CACHE, f)
        logger.info(f"スピーカーエンベディングをキャッシュに保存しました: {SPEAKER_CACHE_PATH}")
    except Exception as e:
        logger.error(f"スピーカーエンベディングのキャッシュ保存エラー: {e}")

def load_speaker_embedding_cache() -> Dict[str, Tuple[torch.Tensor, float]]:
    """スピーカーエンベディングをキャッシュから読み込み"""
    if os.path.exists(SPEAKER_CACHE_PATH):
        try:
            with open(SPEAKER_CACHE_PATH, 'rb') as f:
                cache = pickle.load(f)
            logger.info(f"スピーカーエンベディングをキャッシュから読み込みました: {SPEAKER_CACHE_PATH}")
            return cache
        except Exception as e:
            logger.error(f"スピーカーエンベディングのキャッシュ読み込みエラー: {e}")
    return {}

def cached_make_speaker_embedding(model, wav_path):
    """キャッシュを活用したスピーカーエンベディング生成"""
    global SPEAKER_EMBEDDING_CACHE
    
    # キャッシュが有効かチェック
    current_time = time.time()
    if wav_path in SPEAKER_EMBEDDING_CACHE:
        embedding, timestamp = SPEAKER_EMBEDDING_CACHE[wav_path]
        # キャッシュの有効期限をチェック
        if current_time - timestamp < CACHE_EXPIRY_TIME:
            logger.info(f"キャッシュからスピーカーエンベディングを使用: {wav_path}")
            return embedding
    
    # キャッシュに無いか期限切れの場合は新しく生成
    logger.info(f"新しいスピーカーエンベディングを生成: {wav_path}")
    start_time = time.time()
    wav, sampling_rate = torchaudio.load(wav_path)
    embedding = model.make_speaker_embedding(wav, sampling_rate)
    
    # キャッシュに保存
    SPEAKER_EMBEDDING_CACHE[wav_path] = (embedding, current_time)
    save_speaker_embedding_cache()
    
    logger.info(f"スピーカーエンベディング生成完了: {wav_path} ({time.time() - start_time:.2f}秒)")
    return embedding

def save_model_to_cache(model):
    """モデルをキャッシュに保存（現在は実装しないがインターフェースだけ用意）"""
    # モデルの保存は大きすぎるためここでは実装しません
    # 実際にはモデルの重みを保存する代わりに、事前にダウンロードしたファイルのパスを保存するなどの方法があります
    pass

def load_model_from_cache(repo_id, revision=None):
    """キャッシュからモデルを読み込む（HuggingFaceから再ダウンロードせずに高速化）"""
    from huggingface_hub import hf_hub_download
    import os
    
    try:
        # キャッシュディレクトリの取得（ライブラリのデフォルトキャッシュを活用）
        from huggingface_hub import constants
        cache_dir = os.getenv("HF_HOME", constants.default_cache_path)
        
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    global model, default_speaker, SPEAKER_EMBEDDING_CACHE
    
    # キャッシュディレクトリの確認
    ensure_cache_dir()
    
    # スピーカーエンベディングキャッシュの読み込み
    SPEAKER_EMBEDDING_CACHE = load_speaker_embedding_cache()
    
    # 起動時の処理
    logger.info("モデルを読み込み中...")
    start_time = time.time()
    
    # キャッシュからモデルを読み込む（なければダウンロード）
    model = load_model_from_cache("Zyphra/Zonos-v0.1-transformer")
    logger.info(f"モデル読み込み完了 ({time.time() - start_time:.2f}秒)")
    
    # デフォルトスピーカーを設定
    asset_path = "assets/anno-sample.mp3"
    if os.path.exists(asset_path):
        logger.info("デフォルトスピーカーを読み込み中...")
        start_time = time.time()
        default_speaker = cached_make_speaker_embedding(model, asset_path)
        logger.info(f"デフォルトスピーカー読み込み完了 ({time.time() - start_time:.2f}秒)")
    else:
        logger.warning("警告: デフォルトスピーカーのアセットが見つかりません。音声合成はデフォルトスピーカーなしで行われます。")
    
    logger.info("初期化完了！")
    yield
    
    # 終了時の処理
    logger.info("サーバーを終了しています...")
    # キャッシュの保存
    save_speaker_embedding_cache()

app = FastAPI(
    title="Zonos TTS API", 
    description="Text-to-Speech API using Zonos model",
    lifespan=lifespan
)

@app.post("/synthesize")
async def synthesize_speech(request: TTSRequest):
    """テキストを音声に変換して返す"""
    if model is None:
        raise HTTPException(status_code=500, detail="モデルが初期化されていません")
    
    if request.use_default_speaker and default_speaker is None:
        raise HTTPException(status_code=500, detail="デフォルトスピーカーが利用できません")
    
    if request.streaming:
        async def stream_with_cleanup():
            temp_files = []
            try:
                async for chunk in generate_speech_stream(request):
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
                        asyncio.create_task(cleanup_temp_file(temp_file))
        
        return StreamingResponse(
            stream_with_cleanup(),
            media_type="application/json"
        )
    else:
        # 従来の方式（非ストリーミング）
        return await synthesize_speech_sync(request)

async def generate_speech_stream(request: TTSRequest) -> AsyncGenerator[str, None]:
    """音声合成の進捗をストリーミングで返すジェネレータ"""
    try:
        # 進捗率を返すヘルパー関数
        def send_progress(stage: str, progress: float, message: str = ""):
            return json.dumps({
                "stage": stage,
                "progress": progress,
                "message": message,
                "completed": False
            }) + "\n"
        
        # 進捗を送信するためのスレッドセーフなキュー
        progress_queue = queue.Queue()
        
        # 前回の進捗率を記録して変化がある場合のみ送信
        last_progress = {"value": -1.0}
        
        # モデルのgenerateで使用するコールバック関数
        def progress_callback(frame, step, max_steps):
            # 生成フェーズでの進捗率を計算（0.3から0.8の範囲）
            generation_progress = 0.3 + (step / max_steps) * 0.5
            # 小数点2桁に丸める
            generation_progress = round(generation_progress, 2)
            
            # 進捗率に変化がある場合のみキューに追加
            if generation_progress != last_progress["value"]:
                last_progress["value"] = generation_progress
                try:
                    print(f"Progress: {generation_progress:.0%} (Step {step}/{max_steps})")
                    progress_queue.put({
                        "stage": "generation",
                        "progress": generation_progress,
                        "message": f"音声コードを生成中... ({step}/{max_steps}) - {generation_progress:.0%}"
                    }, block=False)
                except queue.Full:
                    # キューが満杯の場合はスキップ
                    pass
            return True  # 生成を継続
        
        # 1. 初期化
        yield send_progress("initialization", 0.0, "音声合成を開始しています...")
        await asyncio.sleep(0.1)
        
        # 2. 条件付き辞書を作成
        yield send_progress("conditioning", 0.1, "条件付き辞書を作成中...")
        cond_dict = make_cond_dict(
            text=request.text, 
            speaker=default_speaker if request.use_default_speaker else None, 
            language=request.language,
            speaking_rate=request.speaking_rate
        )
        conditioning = model.prepare_conditioning(cond_dict)
        
        # 3. 音声コード生成開始
        yield send_progress("generation", 0.3, "音声コードの生成を開始...")
        
        # 音声生成を別のタスクで実行
        async def run_generation():
            try:
                # ThreadPoolExecutorを使用してsyncのgenerate関数を実行
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    codes = await loop.run_in_executor(
                        executor,
                        lambda: model.generate(
                            conditioning, 
                            progress_bar=False,  # tqdmを無効化
                            callback=progress_callback
                        )
                    )
                return codes
            except Exception as e:
                progress_queue.put({"error": str(e)}, block=False)
                raise e
            finally:
                # 生成完了を通知
                progress_queue.put({"completed": True}, block=False)
        
        # 生成タスクを開始
        generation_task = asyncio.create_task(run_generation())
        
        # 進捗を監視してリアルタイムで送信
        codes = None
        while True:
            # 非ブロッキングでキューから進捗を取得
            try:
                progress_data = progress_queue.get(block=False)
                
                if "error" in progress_data:
                    raise Exception(progress_data["error"])
                elif "completed" in progress_data:
                    # 生成完了、結果を取得
                    codes = await generation_task
                    break
                else:
                    # 進捗情報を送信
                    yield send_progress(
                        progress_data["stage"],
                        progress_data["progress"],
                        progress_data["message"]
                    )
            except queue.Empty:
                # キューが空の場合は生成が完了しているかチェック
                if generation_task.done():
                    codes = await generation_task
                    break
                # まだ生成中の場合は少し待機
                await asyncio.sleep(0.1)
        
        # 4. 音声デコード
        yield send_progress("decoding", 0.8, "音声をデコード中...")
        wavs = model.autoencoder.decode(codes).cpu()
        
        # 5. ファイル保存
        yield send_progress("saving", 0.9, "音声ファイルを保存中...")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            torchaudio.save(temp_file.name, wavs[0], model.autoencoder.sampling_rate)
            temp_file_path = temp_file.name
        
        # 6. 完了
        yield json.dumps({
            "stage": "completed",
            "progress": 1.0,
            "message": "音声合成が完了しました",
            "completed": True,
            "file_path": temp_file_path,
            "download_url": f"/download/{os.path.basename(temp_file_path)}"
        }) + "\n"
        
    except Exception as e:
        yield json.dumps({
            "stage": "error",
            "progress": 0.0,
            "message": f"エラーが発生しました: {str(e)}",
            "completed": True,
            "error": True
        }) + "\n"
    finally:
        # ストリーミング完了後にファイルクリーンアップを遅延実行
        if 'temp_file_path' in locals() and temp_file_path and os.path.exists(temp_file_path):
            # バックグラウンドタスクとしてファイル削除を実行
            asyncio.create_task(cleanup_temp_file(temp_file_path))

async def cleanup_temp_file(file_path: str):
    """一時ファイルを遅延削除するためのヘルパー関数"""
    try:
        # 少し待ってからファイルを削除（ダウンロードの時間を確保）
        await asyncio.sleep(5)
        if os.path.exists(file_path):
            os.unlink(file_path)
    except Exception:
        pass  # ファイル削除エラーは無視

async def synthesize_speech_sync(request: TTSRequest):
    """従来の同期的な音声合成処理"""
    try:
        # 条件付き辞書を作成
        cond_dict = make_cond_dict(
            text=request.text, 
            speaker=default_speaker if request.use_default_speaker else None, 
            language=request.language,
            speaking_rate=request.speaking_rate
        )
        conditioning = model.prepare_conditioning(cond_dict)
        
        # 音声を生成
        codes = model.generate(conditioning)
        wavs = model.autoencoder.decode(codes).cpu()
        
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            torchaudio.save(temp_file.name, wavs[0], model.autoencoder.sampling_rate)
            temp_file_path = temp_file.name
        
        # 非同期的にファイル削除を行うタスクを作成
        asyncio.create_task(cleanup_temp_file(temp_file_path))
        
        return FileResponse(
            path=temp_file_path,
            media_type="audio/wav",
            filename="synthesized_speech.wav"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"音声合成エラー: {str(e)}")

# 一時ファイルダウンロード用のエンドポイント
@app.get("/download/{filename}")
async def download_file(filename: str):
    """一時ファイルをダウンロードするエンドポイント"""
    temp_file_path = os.path.join(tempfile.gettempdir(), filename)
    if not os.path.exists(temp_file_path):
        raise HTTPException(status_code=404, detail="ファイルが見つかりません")
    
    # 非同期的にファイル削除を行うタスクを作成
    asyncio.create_task(cleanup_temp_file(temp_file_path))
    
    return FileResponse(
        path=temp_file_path,
        media_type="audio/wav",
        filename="synthesized_speech.wav"
    )

@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "default_speaker_available": default_speaker is not None
    }

@app.get("/")
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

def save_model_to_cache(model):
    """モデルをキャッシュに保存（現在は実装しないがインターフェースだけ用意）"""
    # モデルの保存は大きすぎるためここでは実装しません
    # 実際にはモデルの重みを保存する代わりに、事前にダウンロードしたファイルのパスを保存するなどの方法があります
    pass

def load_model_from_cache(repo_id, revision=None):
    """キャッシュからモデルを読み込む（HuggingFaceから再ダウンロードせずに高速化）"""
    from huggingface_hub import hf_hub_download
    import os
    
    try:
        # キャッシュディレクトリの取得（ライブラリのデフォルトキャッシュを活用）
        from huggingface_hub import constants
        cache_dir = os.getenv("HF_HOME", constants.default_cache_path)
        
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
