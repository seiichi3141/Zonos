# Zonos キャッシュ機能

Zonos は 2 回目以降の起動時の高速化のため、以下のキャッシュ機能を提供します。

## スピーカーエンベディングキャッシュ

スピーカーエンベディング生成は計算コストが高いため、生成されたエンベディングはディスク上とメモリ上にキャッシュされます。
これにより、同じ音声ファイルからのスピーカーエンベディング生成を高速化します。

- キャッシュの場所: `cache/speaker_cache.pkl`
- 有効期限: 24 時間（設定可能）

## Hugging Face モデルキャッシュ

`from_pretrained`メソッドを使用してモデルをロードする際、Hugging Face のキャッシュシステムを活用します。
2 回目以降は、モデルファイルを再ダウンロードせずにローカルキャッシュから読み込みます。

## メモリ内キャッシュ

`SpeakerEmbeddingLDA`クラスは、計算された埋め込みをメモリ内にキャッシュして再利用します。
サーバー稼働中に同じ音声ファイルから複数回埋め込みを生成する場合に有効です。

## キャッシュの設定

`server.py`で以下の設定を変更できます：

```python
# キャッシュ関連の設定
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
SPEAKER_CACHE_PATH = os.path.join(CACHE_DIR, "speaker_cache.pkl")
CACHE_EXPIRY_TIME = 24 * 60 * 60  # 24時間（秒）
```

## キャッシュクリア

キャッシュをクリアする場合は、以下のコマンドを実行してください：

```bash
# スピーカーエンベディングキャッシュをクリア
rm -f /path/to/Zonos/cache/speaker_cache.pkl

# Hugging Face キャッシュをクリア
rm -rf ~/.cache/huggingface/
```
