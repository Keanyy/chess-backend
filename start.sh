#!/bin/bash
# Stockfish binary için çalıştırma izni ver
chmod +x ./stockfish_linux/stockfish-ubuntu-x86-64-avx2 || true

# Python bağımlılıklarını yükle (Replit bazen otomatik yapmıyor)
pip install -r requirements.txt --quiet

# Flask backend’i başlat
python3 app.py
