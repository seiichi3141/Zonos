"""
音声合成(TTS)モジュール
テキストから音声への変換処理を行う
"""
import os
import json
import queue
import asyncio
import concurrent.futures
import logging
from typing import AsyncGenerator

from zonos.conditioning import make_cond_dict

from app.core import model_manager
from app.utils import audio

logger = logging.getLogger(__name__)

async def synthesize_speech_sync(text, language="ja", use_default_speaker=True, speaking_rate=15.0):
    """同期的な音声合成処理"""
    model = model_manager.get_model()
    default_speaker = model_manager.get_default_speaker()
    
    try:
        # 条件付き辞書を作成
        cond_dict = make_cond_dict(
            text=text, 
            speaker=default_speaker if use_default_speaker else None, 
            language=language,
            speaking_rate=speaking_rate
        )
        conditioning = model.prepare_conditioning(cond_dict)
        
        # 音声を生成
        codes = model.generate(conditioning)
        wavs = model.autoencoder.decode(codes).cpu()
        
        # 一時ファイルに保存
        temp_file_path = audio.save_audio_to_temp_file(wavs[0], model.autoencoder.sampling_rate)
        
        # 非同期的にファイル削除を行うタスクを作成
        asyncio.create_task(audio.cleanup_temp_file(temp_file_path))
        
        return temp_file_path
        
    except Exception as e:
        logger.error(f"音声合成エラー: {str(e)}")
        raise e

async def generate_speech_stream(
    text, language="ja", use_default_speaker=True, speaking_rate=15.0
) -> AsyncGenerator[str, None]:
    """音声合成の進捗をストリーミングで返すジェネレータ"""
    
    model = model_manager.get_model()
    default_speaker = model_manager.get_default_speaker()
    temp_file_path = None
    
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
            text=text, 
            speaker=default_speaker if use_default_speaker else None, 
            language=language,
            speaking_rate=speaking_rate
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
        temp_file_path = audio.save_audio_to_temp_file(wavs[0], model.autoencoder.sampling_rate)
        
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
        logger.error(f"音声合成ストリーミングエラー: {str(e)}")
        yield json.dumps({
            "stage": "error",
            "progress": 0.0,
            "message": f"エラーが発生しました: {str(e)}",
            "completed": True,
            "error": True
        }) + "\n"
    finally:
        # ストリーミング完了後にファイルクリーンアップを遅延実行
        if temp_file_path and os.path.exists(temp_file_path):
            # バックグラウンドタスクとしてファイル削除を実行
            asyncio.create_task(audio.cleanup_temp_file(temp_file_path))
