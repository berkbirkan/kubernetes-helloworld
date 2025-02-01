FROM python:3.9-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Gereksinim dosyasını kopyala ve paketleri yükle
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyasını kopyala
COPY app.py .

# API’nin dinleyeceği portu aç
EXPOSE 5000

# Uygulamayı başlat
CMD ["python", "app.py"]
