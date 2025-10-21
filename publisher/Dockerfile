FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY publish.py .

# requirements.txt untuk publisher
# Cukup 'requests'
RUN echo "requests" > requirements.txt