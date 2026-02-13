# 1. Use Python 3.10 specifically (Slim version to save space)
FROM python:3.10-slim

# 2. Install system-level dependencies for OpenCV and Paddle
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# 3. Upgrade pip and install from Paddle's specific mirror
RUN pip install --upgrade pip
RUN pip install paddlepaddle==3.0.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
RUN pip install -r requirements.txt

# 4. Your Start Command
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]
