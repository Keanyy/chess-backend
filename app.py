# app.py
from flask import Flask, jsonify, request
from flask_cors import CORS
import chess
import chess.engine
import os
import random
import sys

# --- CONFIGURATION ---
# PyInstaller ile paketlendiğinde doğru yolu bulmak için
def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

STOCKFISH_PATH = resource_path("stockfish.exe")

# --- ENGINE & GAME STATE ---
app = Flask(__name__)
# CORS, Flutter web veya debug modda backend'e erişim sorunlarını engeller.
CORS(app)

# Bu basit örnekte, sunucu çalıştığı süre tek bir oyun durumu bellekte tutulur.
# Daha gelişmiş sistemlerde session veya veritabanı kullanılabilir.
game_state = {}

# --- HELPER CLASSES AND FUNCTIONS (Orijinal kodunuzdan adapte edildi) ---
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

def init_engine():
    try:
        engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        return engine
    except Exception as e:
        print(f"HATA: Stockfish motoru başlatılamadı: {e}")
        return None

def configure_engine_difficulty(engine, difficulty_index):
    if engine is None:
        return
    level_name = DIFFICULTY_LEVELS[difficulty_index]
    settings = AI_SETTINGS[level_name]
    elo = settings.get("elo")
    if elo:
        engine.configure({"UCI_LimitStrength": True, "UCI_Elo": elo})
    else:
        engine.configure({"UCI_LimitStrength": False})

def analyze_player_move(board, engine, move, difficulty_index):
    if engine is None:
        return {
            'quality': 'good',
            'text': 'İyi hamle!',
            'color': 'GOOD_MOVE_COLOR',
            'best_alternative': None,
            'threat': None
        }
    
    depth = AI_SETTINGS[DIFFICULTY_LEVELS[difficulty_index]]["depth"]
    feedback = {}
    
    try:
        analysis_before = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=3)
        top_moves_before = [info['pv'][0] for info in analysis_before if 'pv' in info and info['pv']]

        is_top_move = move in top_moves_before
        
        # En iyi hamlelerden biriyse, direkt kabul et
        if is_top_move:
            quality = "excellent" if move == top_moves_before[0] else "good"
            feedback = {
                'quality': quality,
                'text': random.choice(["Mükemmel hamle!", "Harika bir görüş!"]),
                'color': 'EXCELLENT_MOVE_COLOR' if quality == 'excellent' else 'GOOD_MOVE_COLOR',
                'best_alternative': None,
                'threat': None
            }
            return feedback

        temp_board = board.copy()
        temp_board.push(move)
        analysis_after = engine.analyse(temp_board, chess.engine.Limit(depth=depth))
        
        score_before = analysis_before[0]["score"].relative.score(mate_score=10000)
        score_after = analysis_after["score"].white().score(mate_score=10000)
        score_delta = score_after - score_before if board.turn == chess.WHITE else score_before - score_after
        
        threat = engine.play(temp_board, chess.engine.Limit(time=0.4, depth=max(6, depth//2))).move
        best_alternative = top_moves_before[0] if top_moves_before else None

        if score_delta <= BLUNDER_THRESHOLD: quality = "blunder"
        elif score_delta <= MISTAKE_THRESHOLD: quality = "mistake"
        elif score_delta <= INACCURACY_THRESHOLD: quality = "inaccuracy"
        else: quality = "good" # Technically not a top move but not bad either
        
        comments = {
            'inaccuracy': "Fena değil, ama daha iyisi olabilirdi.",
            'mistake': "Dikkat! Bu hamle rakibe bir fırsat veriyor.",
            'blunder': "Eyvah! Bu çok tehlikeli bir hamle!"
        }
        
        feedback = {
            'quality': quality,
            'text': comments.get(quality, "Mantıklı bir hamle."),
            'color': f'{quality.upper()}_COLOR',
            'best_alternative': best_alternative.uci() if best_alternative else None,
            'threat': threat.uci() if threat else None
        }
        return feedback
        
    except Exception as e:
        print(f"Analiz sırasında hata: {e}")
        return {
            'quality': 'good', 
            'text': 'İyi hamle!',
            'color': 'GOOD_MOVE_COLOR',
            'best_alternative': None,
            'threat': None
        }


# --- API ENDPOINTS ---
@app.route('/new_game', methods=['POST'])
def new_game():
    """Yeni bir oyun başlatır veya mevcut oyunu sıfırlar."""
    global game_state
    
    engine = game_state.get('engine')
    if not engine:
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
        "threat_move": None,
        "pending_move": None  # Onay bekleyen hamle
    }
    if engine:
        configure_engine_difficulty(game_state['engine'], game_state['difficulty_index'])
    
    print("New game started successfully")
    return jsonify(get_game_state_json())

@app.route('/game_state', methods=['GET'])
def get_game_state():
    """Mevcut oyun durumunu döndürür."""
    if 'board' not in game_state:
        return jsonify({"error": "Oyun başlatılmadı."}), 404
    return jsonify(get_game_state_json())
    
@app.route('/make_move', methods=['POST'])
def make_move():
    """Oyuncunun hamlesini işler."""
    if 'board' not in game_state:
        return jsonify({"error": "Oyun başlatılmadı."}), 404
        
    move_uci = request.json.get('move')
    if not move_uci:
        return jsonify({"error": "Hamle bilgisi eksik."}), 400

    print(f"Received move: {move_uci}")
        
    board = game_state['board']
    engine = game_state['engine']
    
    # Onaylanmış hamle kontrolü
    if move_uci.endswith('_confirmed'):
        actual_move_uci = move_uci.replace('_confirmed', '')
        print(f"Processing confirmed move: {actual_move_uci}")
        
        if game_state.get('pending_move') == actual_move_uci:
            # Onaylanmış hamleni yap - analiz yapmadan direkt oyna
            try:
                move = chess.Move.from_uci(actual_move_uci)
                if move in board.legal_moves:
                    return execute_move(move)
                else:
                    return jsonify({"error": "Onaylanacak hamle artık yasal değil."}), 400
            except:
                return jsonify({"error": "Geçersiz onay hamlesi."}), 400
        else:
            return jsonify({"error": "Onaylanacak hamle bulunamadı."}), 400
    
    try:
        move = chess.Move.from_uci(move_uci)
    except:
        return jsonify({"error": "Geçersiz hamle formatı."}), 400

    if move not in board.legal_moves:
        print(f"Illegal move: {move_uci}")
        return jsonify({"error": "Geçersiz hamle."}), 400
    
    print(f"Move is legal: {move_uci}")
    
    # Hamle analizini yap (sadece engine varsa)
    if engine:
        analysis = analyze_player_move(board, engine, move, game_state['difficulty_index'])
        is_bad_move = analysis['quality'] in ['blunder', 'mistake']
        tutor_mode = TUTOR_MODES[game_state['tutor_mode_index']]
        
        print(f"Move analysis - Quality: {analysis['quality']}, Is bad: {is_bad_move}, Mode: {tutor_mode}")
        
        # KATI modda kötü hamleye izin verme
        if is_bad_move and tutor_mode == "KATI":
            game_state.update({
                "feedback_text": analysis['text'] + " Bu hamleye izin verilmedi. Başka bir hamle dene.",
                "feedback_color": analysis['color'],
                "best_alternative_move": analysis['best_alternative'],
                "threat_move": None,
                "pending_move": None
            })
            return jsonify({"status": "rejected", "analysis": analysis, "game_state": get_game_state_json()})
        
        # TAVSİYECİ modda kötü hamle için onaya gönder
        elif is_bad_move and tutor_mode == "TAVSİYECİ":
            game_state.update({
                "feedback_text": analysis['text'] + " Yine de oynamak istediğine emin misin?",
                "feedback_color": analysis['color'],
                "best_alternative_move": analysis['best_alternative'],
                "threat_move": analysis['threat'],
                "pending_move": move_uci
            })
            return jsonify({"status": "confirmation_required", "analysis": analysis, "game_state": get_game_state_json()})
        
        # İyi hamle - direkt kabul et ve feedback ver
        else:
            print(f"Good move accepted in {tutor_mode} mode")
            # Hamleyi yap ve feedback'i ayarla
            board.push(move)
            game_state['last_move'] = move.uci()
            game_state['best_alternative_move'] = None
            game_state['threat_move'] = None
            game_state['pending_move'] = None
            game_state['feedback_text'] = analysis['text']
            game_state['feedback_color'] = analysis['color']
            
            # AI hamlesini yap
            if not board.is_game_over():
                try:
                    settings = AI_SETTINGS[DIFFICULTY_LEVELS[game_state['difficulty_index']]]
                    result = engine.play(board, chess.engine.Limit(time=settings["time"], depth=settings["depth"]))
                    board.push(result.move)
                    game_state['last_move'] = result.move.uci()
                    game_state['feedback_text'] = analysis['text'] + " Sıra sende!"
                    print(f"AI played: {result.move.uci()}")
                except Exception as e:
                    print(f"AI move error: {e}")
            
            return jsonify({"status": "accepted", "game_state": get_game_state_json()})
    
    # Normal hamle - doğrudan yap
    return execute_move(move)

def execute_move(move):
    """Hamleyi gerçekten oynar ve AI hamlesi yapar"""
    board = game_state['board']
    engine = game_state['engine']
    
    print(f"Executing move: {move.uci()}")
    
    # Oyuncu hamlesini yap
    board.push(move)
    game_state['last_move'] = move.uci()
    game_state['best_alternative_move'] = None
    game_state['threat_move'] = None
    game_state['pending_move'] = None
    
    # Onaylanmış kötü hamle için uyarı mesajı
    is_confirmed_bad_move = game_state.get('feedback_color') in ['BLUNDER_COLOR', 'MISTAKE_COLOR']
    
    # Yapay zeka hamlesini yap
    if not board.is_game_over() and engine:
        try:
            settings = AI_SETTINGS[DIFFICULTY_LEVELS[game_state['difficulty_index']]]
            result = engine.play(board, chess.engine.Limit(time=settings["time"], depth=settings["depth"]))
            board.push(result.move)
            game_state['last_move'] = result.move.uci()
            
            if is_confirmed_bad_move:
                game_state['feedback_text'] = "Kötü hamleyi onayladın! Daha dikkatli ol. Sıra sende."
                game_state['feedback_color'] = "MISTAKE_COLOR"
            else:
                game_state['feedback_text'] = "Sıra sende. En iyi hamleni düşün!"
                game_state['feedback_color'] = "COLOR_INFO_TEXT"
                
            print(f"AI played: {result.move.uci()}")
        except Exception as e:
            print(f"AI move error: {e}")
            game_state['feedback_text'] = "Sıra sende!"
            game_state['feedback_color'] = "COLOR_INFO_TEXT"
    elif not board.is_game_over():
        game_state['feedback_text'] = "Sıra sende! (AI engine bulunamadı)"
        game_state['feedback_color'] = "COLOR_INFO_TEXT"
    
    print(f"Move executed successfully. Game over: {board.is_game_over()}")
    return jsonify({"status": "accepted", "game_state": get_game_state_json()})

@app.route('/change_settings', methods=['POST'])
def change_settings():
    """Oyun ayarlarını (zorluk, mod) değiştirir."""
    if 'board' not in game_state:
        return jsonify({"error": "Oyun başlatılmadı."}), 404
    
    new_diff = request.json.get('difficulty_index')
    new_mode = request.json.get('tutor_mode_index')
    
    if new_diff is not None:
        game_state['difficulty_index'] = new_diff
        if game_state.get('engine'):
            configure_engine_difficulty(game_state['engine'], new_diff)
        
    if new_mode is not None:
        game_state['tutor_mode_index'] = new_mode
    
    print(f"Settings changed - Difficulty: {new_diff}, Mode: {new_mode}")
    return jsonify(get_game_state_json())

def get_game_state_json():
    """Oyun durumunu Flutter'ın anlayacağı bir JSON formatına çevirir."""
    board = game_state['board']
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
        "tutor_mode": TUTOR_MODES[game_state['tutor_mode_index']],
        "difficulty": DIFFICULTY_LEVELS[game_state['difficulty_index']],
        "tutor_mode_index": game_state['tutor_mode_index'],
        "difficulty_index": game_state['difficulty_index'],
        "feedback_text": game_state['feedback_text'],
        "feedback_color": game_state['feedback_color'],
        "last_move": game_state.get('last_move'),
        "best_alternative_move": game_state.get('best_alternative_move'),
        "threat_move": game_state.get('threat_move'),
        "is_game_over": board.is_game_over(),
        "game_result": result
    }

# --- SERVER START ---
if __name__ == '__main__':
    # Sunucuyu başlat. host='0.0.0.0' ağdaki diğer cihazların (telefonunuz gibi)
    # erişmesine izin verir.
    app.run(host='0.0.0.0', port=5000, debug=True)
