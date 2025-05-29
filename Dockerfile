FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel
RUN pip install uv

RUN apt update && \
    apt install -y espeak-ng && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . ./

RUN uv pip install --system -e . && uv pip install --system -e .[compile] && uv pip install --system python-dotenv

# デフォルトの.envファイルをコピー（存在しない場合）
RUN if [ ! -f .env ]; then cp -n .env.example .env || echo "No .env.example file found"; fi
