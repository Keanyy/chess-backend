from flask import Flask, jsonify, request
from flask_cors import CORS
import chess
import chess.engine
import sys
import os
import random

def resource_path(relative_path):
    """PyInstaller ile paketlenmiş dosyalar için doğru yolu bulur"""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

# ---------- BACKEND AYARLARI ----------
STOCKFISH_PATH = resource_path("stockfish.exe")

app = Flask(__name__)
CORS(app)  # Tüm origin'lere izin ver

# --- Oyun Modları ve Seviyeleri ---
TUTOR_MODES = ["TAVSİYECİ", "KATI"]
DIFFICULTY_LEVELS = ["Çok Kolay", "Kolay", "Orta", "Zor"]

AI_SETTINGS = {
    "Çok Kolay": {"time": 0.3, "depth": 5, "elo": 1320},
    "Kolay":      {"time": 0.5, "depth": 8, "elo": 1400},
    "Orta":       {"time": 0.8, "depth": 12, "elo": 1600},
    "Zor":        {"time": 1.2, "depth": 18, "elo": 2200}
}

BLUNDER_THRESHOLD = -200
MISTAKE_THRESHOLD = -90
INACCURACY_THRESHOLD = -40

# Global oyun durumu (Production'da veritabanı kullanılmalı)
game_state = {}

def init_engine():
    """Stockfish motorunu başlat"""
    if not os.path.exists(STOCKFISH_PATH):
        raise Exception(f"Stockfish motoru bulunamadı! '{STOCKFISH_PATH}' yolunu kontrol edin.")
    
    try:
        engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        return engine
    except Exception as e:
        raise Exception(f"Stockfish motoru başlatılamadı: {e}")

def configure_engine_difficulty(engine, difficulty_index):
    """Motor zorluğunu ayarla"""
    level_name = DIFFICULTY_LEVELS[difficulty_index]
    settings = AI_SETTINGS[level_name]
    elo = settings.get("elo")
    if elo:
        engine.configure({"UCI_LimitStrength": True, "UCI_Elo": elo})
    else:
        engine.configure({"UCI_LimitStrength": False})

def analyze_player_move(board, engine, move, difficulty_index):
    """Oyuncu hamlesini analiz et"""
    depth = AI_SETTINGS[DIFFICULTY_LEVELS[difficulty_index]]["depth"]
    
    try:
        analysis_before = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=3)
        top_moves_before = [info['pv'][0] for info in analysis_before if 'pv' in info and info['pv']]
        
        if move in top_moves_before:
            quality = "excellent" if move == top_moves_before[0] else "great"
            return {
                'quality': quality,
                'text': "Mükemmel hamle! Tam bir usta gibi." if quality == "excellent" else "Harika bir hamle!",
                'color': 'EXCELLENT_MOVE_COLOR' if quality == "excellent" else 'GOOD_MOVE_COLOR',
                'best_alternative': None,
                'threat': None
            }

        temp_board = board.copy()
        temp_board.push(move)
        analysis_after = engine.analyse(temp_board, chess.engine.Limit(depth=depth))
        
        score_before = analysis_before[0]["score"].relative.score(mate_score=10000)
        score_after = analysis_after["score"].white().score(mate_score=10000)
        score_delta = score_after - score_before if board.turn == chess.WHITE else score_before - score_after
        
        threat = engine.play(temp_board, chess.engine.Limit(time=0.4, depth=max(6, depth//2))).move
        best_alternative = top_moves_before[0] if top_moves_before else None
        
        if score_delta <= BLUNDER_THRESHOLD:
            quality, color = "blunder", "BLUNDER_COLOR"
        elif score_delta <= MISTAKE_THRESHOLD:
            quality, color = "mistake", "MISTAKE_COLOR"
        elif score_delta <= INACCURACY_THRESHOLD:
            quality, color = "inaccuracy", "INACCURACY_COLOR"
        else:
            quality, color = "good", "COLOR_INFO_TEXT"
        
        comments = {
            'inaccuracy': "Fena değil, ama daha iyisi olabilirdi.",
            'mistake': "Dikkat! Bu hamle rakibe bir fırsat veriyor.",
            'blunder': "Eyvah! Bu çok tehlikeli bir hamle!"
        }
        
        return {
            'quality': quality,
            'text': comments.get(quality, "Mantıklı bir hamle."),
            'color': color,
            'best_alternative': best_alternative.uci() if best_alternative else None,
            'threat': threat.uci() if threat else None
        }
        
    except Exception as e:
        print(f"Analiz sırasında hata: {e}")
        return {'quality': 'error', 'text': 'Analiz sırasında bir hata oluştu.'}

def format_game_state(board, game_data):
    """Oyun durumunu API response'u için formatla"""
    result = "Oyun devam ediyor"
    if board.is_game_over():
        res = board.result()
        if board.is_checkmate():
            winner = "Beyaz" if res == "1-0" else "Siyah"
            result = f"Şah Mat! {winner} kazandı."
        else:
            result = "Oyun bitti! Sonuç: Berabere."
            
    return {
        "fen": board.fen(),
        "turn": "white" if board.turn == chess.WHITE else "black",
        "tutor_mode": TUTOR_MODES[game_data['tutor_mode_index']],
        "difficulty": DIFFICULTY_LEVELS[game_data['difficulty_index']],
        "tutor_mode_index": game_data['tutor_mode_index'],
        "difficulty_index": game_data['difficulty_index'],
        "feedback_text": game_data['feedback_text'],
        "feedback_color": game_data['feedback_color'],
        "last_move": game_data.get('last_move'),
        "best_alternative_move": game_data.get('best_alternative_move'),
        "threat_move": game_data.get('threat_move'),
        "is_game_over": board.is_game_over(),
        "game_result": result
    }

# ---------- API ENDPOINT'LERİ ----------
@app.route('/new_game', methods=['POST'])
def new_game():
    """Yeni bir oyun başlat"""
    global game_state
    
    try:
        engine = init_engine()
        
        game_state = {
            "board": chess.Board(),
            "engine": engine,
            "tutor_mode_index": 0,
            "difficulty_index": 0,
            "feedback_text": "Merhaba! Satranç Akademisi'ne hoş geldin. İlk hamleni yap.",
            "feedback_color": "COLOR_INFO_TEXT",
            "last_move": None,
            "best_alternative_move": None,
            "threat_move": None
        }
        
        configure_engine_difficulty(game_state['engine'], game_state['difficulty_index'])
        return jsonify(format_game_state(game_state['board'], game_state))
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/make_move', methods=['POST'])
def make_move():
    """Oyuncu hamlesini işle"""
    global game_state
    
    if 'board' not in game_state:
        return jsonify({"error": "Oyun başlatılmadı. Önce /new_game endpoint'ini çağırın."}), 400
        
    data = request.get_json()
    if not data or 'move' not in data:
        return jsonify({"error": "Hamle bilgisi eksik."}), 400
        
    move_uci = data['move']
    board = game_state['board']
    engine = game_state['engine']
    
    try:
        move = chess.Move.from_uci(move_uci)
        
        if move not in board.legal_moves:
            return jsonify({"error": "Geçersiz hamle."}), 400
        
        # Hamle analizini yap
        analysis = analyze_player_move(board, engine, move, game_state['difficulty_index'])
        
        is_bad_move = analysis['quality'] in ['blunder', 'mistake']
        tutor_mode = TUTOR_MODES[game_state['tutor_mode_index']]
        
        # KATI modda kötü hamleye izin verme
        if is_bad_move and tutor_mode == "KATI":
            game_state.update({
                "feedback_text": analysis['text'] + " Bu hamleye izin verilmedi. Başka bir hamle dene.",
                "feedback_color": analysis['color'],
                "best_alternative_move": analysis['best_alternative'],
                "threat_move": None
            })
            return jsonify({
                "status": "rejected", 
                "analysis": analysis, 
                "game_state": format_game_state(board, game_state)
            })
        
        # TAVSİYECİ modda kötü hamle için onaya gönder
        if is_bad_move and tutor_mode == "TAVSİYECİ":
            game_state.update({
                "feedback_text": analysis['text'] + " Yine de oynamak istediğine emin misin?",
                "feedback_color": analysis['color'],
                "best_alternative_move": analysis['best_alternative'],
                "threat_move": analysis['threat']
            })
            return jsonify({
                "status": "confirmation_required", 
                "analysis": analysis, 
                "game_state": format_game_state(board, game_state)
            })

        # Hamleyi yap
        board.push(move)
        game_state['last_move'] = move.uci()
        game_state['best_alternative_move'] = None
        game_state['threat_move'] = None
        
        # Yapay zeka hamlesini yap
        if not board.is_game_over():
            settings = AI_SETTINGS[DIFFICULTY_LEVELS[game_state['difficulty_index']]]
            result = engine.play(board, chess.engine.Limit(time=settings["time"], depth=settings["depth"]))
            board.push(result.move)
            game_state['last_move'] = result.move.uci()
            game_state['feedback_text'] = "Sıra sende. En iyi hamleni düşün!"
            game_state['feedback_color'] = "COLOR_INFO_TEXT"
        
        return jsonify({
            "status": "accepted", 
            "game_state": format_game_state(board, game_state)
        })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/change_settings', methods=['POST'])
def change_settings():
    """Oyun ayarlarını değiştir"""
    global game_state
    
    if 'board' not in game_state:
        return jsonify({"error": "Oyun başlatılmadı. Önce /new_game endpoint'ini çağırın."}), 400
        
    data = request.get_json()
    if not data:
        return jsonify({"error": "Geçersiz istek."}), 400
        
    new_diff = data.get('difficulty_index')
    new_mode = data.get('tutor_mode_index')
    
    if new_diff is not None:
        if 0 <= new_diff < len(DIFFICULTY_LEVELS):
            game_state['difficulty_index'] = new_diff
            configure_engine_difficulty(game_state['engine'], new_diff)
        else:
            return jsonify({"error": "Geçersiz zorluk seviyesi."}), 400
            
    if new_mode is not None:
        if 0 <= new_mode < len(TUTOR_MODES):
            game_state['tutor_mode_index'] = new_mode
        else:
            return jsonify({"error": "Geçersiz mod."}), 400
    
    game_state['feedback_text'] = "Ayarlar güncellendi. Hamleni yap."
    game_state['feedback_color'] = "COLOR_INFO_TEXT"
    
    return jsonify(format_game_state(game_state['board'], game_state))

@app.route('/game_state', methods=['GET'])
def get_game_state():
    """Mevcut oyun durumunu döndür"""
    if 'board' not in game_state:
        return jsonify({"error": "Oyun başlatılmadı. Önce /new_game endpoint'ini çağırın."}), 400
        
    return jsonify(format_game_state(game_state['board'], game_state))

# ---------- SERVER BAŞLATMA ----------
if __name__ == '__main__':
    # Yeni bir oyun başlat
    try:
        with app.app_context():
            new_game()
        print("Backend başlatıldı. http://0.0.0.0:5000 adresinde çalışıyor.")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        print(f"Backend başlatılamadı: {e}")
