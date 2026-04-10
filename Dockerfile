FROM python:3.11-slim

WORKDIR /app

COPY sandbox_requirements.txt .
RUN pip install --no-cache-dir -r sandbox_requirements.txt
COPY runner.py .

CMD ["python", "runner.py"]