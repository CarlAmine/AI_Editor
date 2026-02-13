# Use a Python image that includes necessary build tools
FROM python:3.10-slim

# Install system dependencies for OpenCV and OCR
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# Start the FastAPI server (assuming you named your entry file app.py)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]
