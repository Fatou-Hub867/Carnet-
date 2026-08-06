FROM python:3.14-slim

# tesseract-ocr: pytesseract shells out to the `tesseract` binary at runtime
# (doctor diploma OCR verification at sign-up) — the Python package alone is not enough.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/Backend-API

COPY Backend-API/requirements-dev.txt Backend-API/requirements.text ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY Backend-API /app/Backend-API
COPY frontend /app/frontend

EXPOSE 8010

CMD ["sh", "-c", "alembic upgrade head && uvicorn app:app --host 0.0.0.0 --port 8010 --reload"]
