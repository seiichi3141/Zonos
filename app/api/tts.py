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
from typing import AsyncGenerator, List
from openai import OpenAI

from zonos.conditioning import make_cond_dict

from app.core import model_manager
from app.utils import audio
from app import config

logger = logging.getLogger(__name__)

async def split_text_with_openai(text: str) -> List[str]:
    """
    OpenAIのAPIを使用してテキストを自然な区切りで分割する
    長いテキストを音声合成しやすい複数のセグメントに分割する
    """
    if not config.OPENAI_API_KEY:
        logger.warning("OpenAI APIキーが設定されていません。テキストは分割せずそのまま返します。")
        return [text]
    
    try:
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        
        # プロンプトの作成
        prompt = f"""
        以下の日本語テキストを音声合成のために自然な区切りで分割してください。
        各セグメントは読み上げに適した長さ（ワンセンテンス）で、
        文の途中で切れないようにしてください。
        セグメントはJSON形式の配列として返してください。
        
        テキスト:
        {text}
        """
        
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "あなたは文章を自然な区切りで分割するアシスタントです。"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=1,
        )
        
        # レスポンスからセグメントを抽出
        try:
            content = response.choices[0].message.content
            segments = json.loads(content).get("segments", [])
            
            # 空の配列が返された場合は元のテキストをそのまま返す
            if not segments:
                logger.warning("OpenAI APIが空の配列を返しました。テキストは分割せずそのまま返します。")
                return [text]
                
            return segments
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            logger.error(f"OpenAI APIのレスポンスの解析に失敗しました: {str(e)}")
            # 分割に失敗した場合は元のテキストをそのまま返す
            return [text]
            
    except Exception as e:
        logger.error(f"OpenAI APIでテキスト分割中にエラーが発生しました: {str(e)}")
        # エラーが発生した場合は元のテキストをそのまま返す
        return [text]

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
        
        # 同期版では即座にファイル削除タスクを作成（単発使用のため）
        # ストリーミング版とは異なり、すぐに使用されてダウンロードされることを想定
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
    temp_file_paths = []
    
    try:
        # 進捗率を返すヘルパー関数
        def send_progress(stage: str, progress: float, message: str = "", segment_index=None, total_segments=None):
            data = {
                "stage": stage,
                "progress": progress,
                "message": message,
                "completed": False
            }
            if segment_index is not None and total_segments is not None:
                data["segment_index"] = segment_index
                data["total_segments"] = total_segments
            return json.dumps(data) + "\n"
        
        # 1. 初期化
        yield send_progress("initialization", 0.0, "音声合成を開始しています...")
        await asyncio.sleep(0.1)
        
        # 2. テキストの分割
        # yield send_progress("text_splitting", 0.05, "テキストを適切な長さに分割中...")
        # text_segments = await split_text_with_openai(text)
        # logger.info(f"分割されたテキストセグメント数: {len(text_segments)}")
        text_segments = [text]  # OpenAI APIを使用せず、テキストをそのまま使用
        total_segments = len(text_segments)
        
        # 3. 各セグメントを順番に処理
        for i, segment_text in enumerate(text_segments):
            segment_index = i + 1
            segment_progress_base = i / total_segments
            segment_progress_range = 1 / total_segments
            
            # セグメント処理開始
            yield send_progress(
                "segment_processing", 
                segment_progress_base,
                f"セグメント {segment_index}/{total_segments} の処理を開始...",
                segment_index, total_segments
            )
            
            # 進捗を送信するためのスレッドセーフなキュー
            progress_queue = queue.Queue()
            
            # 前回の進捗率を記録して変化がある場合のみ送信
            last_progress = {"value": -1.0}
            
            # モデルのgenerateで使用するコールバック関数
            def progress_callback(frame, step, max_steps):
                # セグメント内での生成フェーズでの進捗率を計算
                generation_progress = segment_progress_base + (step / max_steps) * segment_progress_range * 0.7
                # 小数点2桁に丸める
                generation_progress = round(generation_progress, 2)
                
                # 進捗率に変化がある場合のみキューに追加
                if generation_progress != last_progress["value"]:
                    last_progress["value"] = generation_progress
                    try:
                        print(f"Segment {segment_index}/{total_segments}: {generation_progress:.0%} (Step {step}/{max_steps})")
                        progress_queue.put({
                            "stage": "generation",
                            "progress": generation_progress,
                            "message": f"セグメント {segment_index}/{total_segments} の音声コードを生成中... ({step}/{max_steps})",
                            "segment_index": segment_index,
                            "total_segments": total_segments
                        }, block=False)
                    except queue.Full:
                        # キューが満杯の場合はスキップ
                        pass
                return True  # 生成を継続
            
            # 条件付き辞書を作成
            yield send_progress(
                "conditioning", 
                segment_progress_base + segment_progress_range * 0.1, 
                f"セグメント {segment_index}/{total_segments} の条件付き辞書を作成中...",
                segment_index, total_segments
            )
            cond_dict = make_cond_dict(
                text=segment_text, 
                speaker=default_speaker if use_default_speaker else None, 
                language=language,
                speaking_rate=speaking_rate
            )
            conditioning = model.prepare_conditioning(cond_dict)
            
            # 音声コード生成開始
            yield send_progress(
                "generation", 
                segment_progress_base + segment_progress_range * 0.2, 
                f"セグメント {segment_index}/{total_segments} の音声コード生成を開始...",
                segment_index, total_segments
            )
            
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
                        yield json.dumps(progress_data) + "\n"
                except queue.Empty:
                    # キューが空の場合は生成が完了しているかチェック
                    if generation_task.done():
                        codes = await generation_task
                        break
                    # まだ生成中の場合は少し待機
                    await asyncio.sleep(0.1)
            
            # 音声デコード
            yield send_progress(
                "decoding", 
                segment_progress_base + segment_progress_range * 0.9, 
                f"セグメント {segment_index}/{total_segments} をデコード中...",
                segment_index, total_segments
            )
            wavs = model.autoencoder.decode(codes).cpu()
            
            # ファイル保存
            yield send_progress(
                "saving", 
                segment_progress_base + segment_progress_range * 0.95, 
                f"セグメント {segment_index}/{total_segments} を保存中...",
                segment_index, total_segments
            )
            temp_file_path = audio.save_audio_to_temp_file(wavs[0], model.autoencoder.sampling_rate)
            temp_file_paths.append(temp_file_path)
            
            # セグメント完了通知
            yield json.dumps({
                "stage": "segment_completed",
                "text": segment_text,
                "progress": segment_progress_base + segment_progress_range,
                "message": f"セグメント {segment_index}/{total_segments} の処理が完了しました",
                "completed": False,
                "segment_index": segment_index,
                "total_segments": total_segments,
                "file_path": temp_file_path,
                "download_url": f"/download/{os.path.basename(temp_file_path)}"
            }) + "\n"
        
        # 全セグメント処理完了
        yield json.dumps({
            "stage": "completed",
            "text": segment_text,
            "progress": 1.0,
            "message": f"全 {total_segments} セグメントの音声合成が完了しました",
            "completed": True,
            "segments": [{
                "segment_index": i + 1,
                "file_path": path,
                "download_url": f"/download/{os.path.basename(path)}"
            } for i, path in enumerate(temp_file_paths)]
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
        # ストリーミングレスポンスの音声ファイルはダウンロード用に保持するため削除しない
        # 必要に応じて別途手動でクリーンアップするか、定期的なクリーンアップ処理を実装する
        logger.info(f"ストリーミング音声合成が完了しました。生成されたファイル数: {len(temp_file_paths)}")
