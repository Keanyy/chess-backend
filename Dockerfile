# Python 3.11 slim imajı
FROM python:3.11-slim

# Çalışma dizini
WORKDIR /app

# Sistem bağımlılıkları (stockfish ve flask için gerekli temel paketler)
RUN apt-get update && apt-get install -y \
    curl wget unzip \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıkları yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje dosyalarını kopyala
COPY . .

# Stockfish binary'yi kopyala ve çalıştırılabilir yap
RUN chmod +x /app/stockfish_linux

# Flask uygulaması 5000 portunu kullanıyor
EXPOSE 5000

# Container başladığında Flask uygulamasını çalıştır
CMD ["python", "app.py"]
