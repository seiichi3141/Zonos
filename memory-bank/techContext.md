# 技術コンテキスト

## 使用技術スタック

### Core AI/ML Technologies

#### Zonos Model (Zyphra)

- **バージョン**: v0.1
- **モデル種別**:
  - `Zyphra/Zonos-v0.1-transformer` (メイン)
  - `Zyphra/Zonos-v0.1-hybrid` (高性能版)
- **特徴**: 200k時間多言語学習、44kHzネイティブ出力
- **ライセンス**: オープンウェイト

#### PyTorch Ecosystem

- **PyTorch**: 2.5.1+
- **torchaudio**: 2.5.1+
- **CUDA**: 12.4対応
- **メモリ要件**: 6GB+ VRAM

#### Speech Processing

- **eSpeak-ng**: 音素化ライブラリ
- **phonemizer**: 3.3.0+ (eSpeak-ngラッパー)
- **DACAutoencoder**: 音声符号化/復号化

### Backend Technologies

#### Python Framework

- **Python**: 3.10+
- **FastAPI**: 非同期WebAPI
- **uvicorn**: ASGIサーバー
- **pydantic**: データ検証

#### Package Management

- **uv**: 高速パッケージマネージャー
- **pyproject.toml**: プロジェクト設定

#### External APIs

- **OpenAI API**: テキスト分割機能
- **Hugging Face Hub**: モデル配信・キャッシュ

### Frontend Technologies

#### React Ecosystem

- **Next.js**: 15.3.3 (App Router)
- **React**: 19.0.0
- **TypeScript**: 5+

#### UI Framework

- **Material-UI (MUI)**: 7.1.0
  - @mui/material
  - @mui/icons-material
  - @mui/material-nextjs (Next.js統合)
- **Emotion**: CSS-in-JS
  - @emotion/react
  - @emotion/styled
  - @emotion/cache

### Infrastructure & DevOps

#### Containerization

- **Docker**: pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel ベース
- **docker-compose**: サービス編成

#### Development Tools

- **ESLint**: コード品質
- **TypeScript**: 型安全性

## 開発環境セットアップ

### システム要件

#### 推奨環境

- **OS**: Ubuntu 22.04/24.04, macOS
- **GPU**: RTX 4090 (6GB+ VRAM)
- **RAM**: 16GB+
- **Storage**: 50GB+ (モデルキャッシュ含む)

#### 必須システム依存関係

```bash
# Ubuntu
apt install -y espeak-ng

# macOS
brew install espeak-ng
```

### セットアップ手順

#### 1. 基本環境構築

```bash
# uvインストール
pip install -U uv

# プロジェクトクローン
git clone <repository>
cd Zonos

# 依存関係インストール
uv sync
uv sync --extra compile  # Hybrid model用
```

#### 2. 環境設定

```bash
# 環境変数設定
cp .env.example .env
# .envファイルを適切に編集
```

#### 3. 動作確認

```bash
# 基本テスト
uv run sample.py

# Gradio UI起動
uv run gradio_interface.py

# API サーバー起動
uv run run.py
```

### Docker環境

#### Development

```bash
docker build -t zonos .
docker run -it --gpus=all --net=host -v $(pwd):/Zonos zonos
```

#### Production

```bash
docker-compose up
```

## 技術的制約と考慮事項

### ハードウェア制約

#### GPU要件

- **Transformer Model**: 6GB+ VRAM
- **Hybrid Model**: RTX 3000シリーズ以降
- **CPU fallback**: 可能だが非実用的

#### メモリ使用パターン

- **モデル読み込み**: 約4GB GPU メモリ
- **推論時**: 追加2GB（バッチサイズ依存）
- **キャッシュ**: 数百MB（話者エンベディング）

### ソフトウェア制約

#### Python依存関係

```toml
# 主要依存関係
torch = ">=2.5.1"
transformers = ">=4.48.1"
phonemizer = ">=3.3.0"
gradio = ">=5.15.0"

# オプション（Hybrid model用）
flash-attn = ">=2.7.3"
mamba-ssm = ">=2.2.4"
causal-conv1d = ">=1.5.0.post8"
```

#### 実行時制約

- **eSpeak-ng**: システムレベルインストール必須
- **CUDA**: バージョン互換性
- **OpenAI API**: テキスト分割機能用（オプション）

### パフォーマンス特性

#### 処理速度

- **Real-time factor**: ~2.0x (RTX 4090)
- **生成時間**: 30文字 → 約2-3秒
- **初期化時間**: モデル読み込み20-30秒

#### メモリ使用量

- **ベースライン**: 4GB GPU
- **キャッシュ**: 話者あたり数KB
- **一時ファイル**: 音声長に比例

## アーキテクチャ決定記録

### ADR-001: モデル管理方式

**決定**: シングルトンパターンでグローバル管理
**理由**: GPU メモリ効率化、起動時間短縮
**トレードオフ**: スケーラビリティの制限

### ADR-002: キャッシュ戦略

**決定**: 3層キャッシュ（メモリ→ディスク→HF）
**理由**: パフォーマンス最適化
**実装**: pickle + Hugging Face標準キャッシュ

### ADR-003: API設計

**決定**: FastAPI + AsyncIO
**理由**: 非同期処理、ストリーミング対応
**考慮**: 長時間処理への対応

### ADR-004: Frontend Framework

**決定**: Next.js App Router + Material-UI
**理由**: モダンな開発体験、コンポーネントの豊富さ
**考慮**: SSR対応、パフォーマンス

## セキュリティ考慮事項

### API セキュリティ

- 入力検証（Pydantic）
- ファイルサイズ制限
- Rate limiting（要実装）

### データ保護

- 一時ファイルの自動削除
- ログの機密情報マスキング
- 環境変数による設定分離

### 音声合成倫理

- 悪用防止の仕組み
- 話者同意の確認
- 生成音声の透明性

## モニタリングと観測性

### ログ戦略

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

### メトリクス収集

- 処理時間測定
- GPU使用率監視
- キャッシュヒット率
- エラー率追跡

### ヘルスチェック

```json
{
  "status": "healthy",
  "model_loaded": true,
  "default_speaker_available": true
}
```

## 今後の技術的改善案

### 短期改善

- バッチ処理対応
- WebSocket対応
- メトリクス詳細化

### 中期改善

- モデル並列化
- 分散キャッシュ
- ストリーミング最適化

### 長期検討

- 新モデル対応
- マルチGPU対応
- クラウドデプロイ
