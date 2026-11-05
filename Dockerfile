FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# uzex_spot_data.zip ni shu papkaga qo'ying — baza build vaqtida yig'iladi (~30 s)
RUN if [ -f uzex_spot_data.zip ]; then python prepare_data.py --data uzex_spot_data.zip --out uzex.db; fi
ENV PORT=8000
CMD ["sh","-c","uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
