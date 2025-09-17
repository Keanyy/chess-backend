# Satranç Akademisi
# Çocuklar için geliştirilmiş, öğretici ve eğlenceli satranç oyunu.
# Versiyon 3.0 - Geleceği Gören Öğretmen
import pygame
import chess
import chess.engine
import sys
import os
import random

# ---------- OYUN AYARLARI ----------
STOCKFISH_PATH = "stockfish.exe" 

# --- Ekran ve Tahta Boyutları ---
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 650
BOARD_SIZE = 600
SQUARE_SIZE = BOARD_SIZE // 8
INFO_PANEL_X = BOARD_SIZE + 20

# --- Renk Paleti ---
COLOR_LIGHT_SQUARE = (240, 217, 181)
COLOR_DARK_SQUARE = (181, 136, 99)
COLOR_BACKGROUND = (49, 46, 43)
COLOR_INFO_TEXT = (230, 230, 230)
COLOR_TITLE = (255, 204, 102)

HIGHLIGHT_COLOR = (255, 255, 102, 170)
LEGAL_MOVE_COLOR = (130, 151, 105, 120)
LAST_MOVE_COLOR = (212, 188, 166, 150)

# Hamle Kalitesi Renkleri
EXCELLENT_MOVE_COLOR = (102, 255, 102)
GOOD_MOVE_COLOR = (153, 204, 153)
INACCURACY_COLOR = (255, 255, 153)
MISTAKE_COLOR = (255, 153, 51)
BLUNDER_COLOR = (255, 102, 102)

SUGGESTION_ARROW_COLOR = (102, 178, 255)
THREAT_ARROW_COLOR = (255, 80, 80)

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

PIECE_NAMES = {
    chess.PAWN: "Piyon", chess.KNIGHT: "At", chess.BISHOP: "Fil",
    chess.ROOK: "Kale", chess.QUEEN: "Vezir", chess.KING: "Şah"
}

class GeminiChessTutor:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("METE'nin Geliştirilmiş Satranç Akademisi v3")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.font_small = pygame.font.SysFont("Arial", 18)
        self.font_medium = pygame.font.SysFont("Arial", 24, bold=True)
        self.font_large = pygame.font.SysFont("Arial", 32, bold=True)
        self.clock = pygame.time.Clock()

        self.tutor_mode_index = 0
        self.difficulty_index = 0
        self.mode_button_rect, self.diff_button_rect, self.cancel_button_rect = pygame.Rect(0,0,0,0), pygame.Rect(0,0,0,0), pygame.Rect(0,0,0,0)

        self.board = chess.Board()
        self.init_engine()
        self.piece_images = self.load_piece_images()

        self.selected_square, self.pending_move, self.last_move = None, None, None
        self.player_turn = True
        
        self.feedback_text = "Merhaba! Satranç Akademisi'ne hoş geldin. İlk hamleni yap."
        self.feedback_color = COLOR_INFO_TEXT
        self.best_alternative_move, self.threat_move = None, None
        
    def init_engine(self):
        if not os.path.exists(STOCKFISH_PATH):
            print(f"HATA: Stockfish motoru bulunamadı! '{STOCKFISH_PATH}' yolunu kontrol edin.")
            pygame.quit(); sys.exit(1)
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
            self.configure_engine_difficulty()
        except Exception as e:
            print(f"HATA: Stockfish motoru başlatılamadı: {e}")
            pygame.quit(); sys.exit(1)
            
    def configure_engine_difficulty(self):
        level_name = DIFFICULTY_LEVELS[self.difficulty_index]
        settings = AI_SETTINGS[level_name]
        elo = settings.get("elo")
        if elo: self.engine.configure({"UCI_LimitStrength": True, "UCI_Elo": elo})
        else: self.engine.configure({"UCI_LimitStrength": False})

    def load_piece_images(self):
        images = {}
        for piece in ['P', 'N', 'B', 'R', 'Q', 'K']:
            try:
                images[f'w{piece}'] = pygame.transform.scale(pygame.image.load(f'pieces/w{piece}.png'), (SQUARE_SIZE, SQUARE_SIZE))
                images[f'b{piece.lower()}'] = pygame.transform.scale(pygame.image.load(f'pieces/b{piece.lower()}.png'), (SQUARE_SIZE, SQUARE_SIZE))
            except Exception as e:
                print(f"HATA: Taş görselleri yüklenemedi. Hata: {e}"); pygame.quit(); sys.exit(1)
        return images

    def get_square_from_mouse(self, pos):
        x, y = pos
        if x > BOARD_SIZE or y > BOARD_SIZE: return None
        return chess.square(x // SQUARE_SIZE, 7 - (y // SQUARE_SIZE))
        
    def draw(self):
        self.screen.fill(COLOR_BACKGROUND)
        self.draw_board()
        self.draw_highlights_and_moves()
        self.draw_pieces()
        self.draw_info_panel()
        pygame.display.flip()
        
    def draw_board(self):
        for r in range(8):
            for c in range(8):
                color = COLOR_LIGHT_SQUARE if (r + c) % 2 == 0 else COLOR_DARK_SQUARE
                pygame.draw.rect(self.screen, color, (c * SQUARE_SIZE, r * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE))
        for i in range(8):
            self.draw_text(str(8 - i), 5, i * SQUARE_SIZE + 5, self.font_small, COLOR_DARK_SQUARE if i % 2 == 0 else COLOR_LIGHT_SQUARE)
            self.draw_text(chr(ord('a') + i), i * SQUARE_SIZE + SQUARE_SIZE - 15, BOARD_SIZE - 25, self.font_small, COLOR_DARK_SQUARE if (i + 7) % 2 == 0 else COLOR_LIGHT_SQUARE)
            
    def draw_highlights_and_moves(self):
        if self.selected_square is not None:
            s = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA); s.fill(HIGHLIGHT_COLOR)
            self.screen.blit(s, (chess.square_file(self.selected_square) * SQUARE_SIZE, (7 - chess.square_rank(self.selected_square)) * SQUARE_SIZE))
            for move in self.board.legal_moves:
                if move.from_square == self.selected_square:
                    center = (chess.square_file(move.to_square) * SQUARE_SIZE + SQUARE_SIZE // 2, (7 - chess.square_rank(move.to_square)) * SQUARE_SIZE + SQUARE_SIZE // 2)
                    pygame.draw.circle(self.screen, LEGAL_MOVE_COLOR, center, SQUARE_SIZE // 6)
        if self.last_move:
            s = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA); s.fill(LAST_MOVE_COLOR)
            self.screen.blit(s, (chess.square_file(self.last_move.from_square) * SQUARE_SIZE, (7 - chess.square_rank(self.last_move.from_square)) * SQUARE_SIZE))
            self.screen.blit(s, (chess.square_file(self.last_move.to_square) * SQUARE_SIZE, (7 - chess.square_rank(self.last_move.to_square)) * SQUARE_SIZE))
        if self.best_alternative_move: self.draw_arrow(self.best_alternative_move.from_square, self.best_alternative_move.to_square, SUGGESTION_ARROW_COLOR)
        if self.threat_move: self.draw_arrow(self.threat_move.from_square, self.threat_move.to_square, THREAT_ARROW_COLOR)

    def draw_arrow(self, from_sq, to_sq, color):
        start = (chess.square_file(from_sq) * SQUARE_SIZE + SQUARE_SIZE // 2, (7 - chess.square_rank(from_sq)) * SQUARE_SIZE + SQUARE_SIZE // 2)
        end = (chess.square_file(to_sq) * SQUARE_SIZE + SQUARE_SIZE // 2, (7 - chess.square_rank(to_sq)) * SQUARE_SIZE + SQUARE_SIZE // 2)
        pygame.draw.line(self.screen, color, start, end, 7)
        try:
            angle = pygame.math.Vector2(end[0] - start[0], end[1] - start[1]).angle_to((1, 0))
            points = [ (end[0] + 20 * pygame.math.Vector2(1,0).rotate(angle - 30).x, end[1] - 20 * pygame.math.Vector2(1,0).rotate(angle - 30).y),
                       (end[0] + 20 * pygame.math.Vector2(1,0).rotate(angle + 30).x, end[1] - 20 * pygame.math.Vector2(1,0).rotate(angle + 30).y), end ]
            pygame.draw.polygon(self.screen, color, points)
        except ValueError: pass

    def draw_pieces(self):
        for sq in chess.SQUARES:
            piece = self.board.piece_at(sq)
            if piece:
                key = ('w' if piece.color == chess.WHITE else 'b') + piece.symbol().upper()
                if piece.color == chess.BLACK: key = key.lower()
                self.screen.blit(self.piece_images[key], (chess.square_file(sq) * SQUARE_SIZE, (7 - chess.square_rank(sq)) * SQUARE_SIZE))
                
    def draw_info_panel(self):
        self.draw_text("METE'nin Satranç Akademisi", INFO_PANEL_X, 30, self.font_large, COLOR_TITLE)
        y_pos = 100
        self.mode_button_rect = pygame.Rect(INFO_PANEL_X, y_pos, 300, 35)
        self.draw_text(f"Mod: {TUTOR_MODES[self.tutor_mode_index]} (Değiştir)", INFO_PANEL_X + 10, y_pos + 5, self.font_medium)
        y_pos += 50
        self.diff_button_rect = pygame.Rect(INFO_PANEL_X, y_pos, 300, 35)
        self.draw_text(f"Zorluk: {DIFFICULTY_LEVELS[self.difficulty_index]} (Değiştir)", INFO_PANEL_X + 10, y_pos + 5, self.font_medium)
        y_pos += 80
        pygame.draw.line(self.screen, COLOR_TITLE, (INFO_PANEL_X, y_pos), (SCREEN_WIDTH - 40, y_pos), 2)
        y_pos += 15
        self.draw_text("Öğretmenin Yorumu:", INFO_PANEL_X, y_pos, self.font_medium, COLOR_TITLE)
        y_pos += 40
        self.draw_multiline_text(self.feedback_text, INFO_PANEL_X, y_pos, 380, self.font_small, self.feedback_color)
        if self.pending_move:
            self.cancel_button_rect = pygame.Rect(INFO_PANEL_X, SCREEN_HEIGHT - 80, 300, 40)
            pygame.draw.rect(self.screen, (180, 50, 50), self.cancel_button_rect, border_radius=5)
            self.draw_text("Hamleden Vazgeç (ESC)", self.cancel_button_rect.centerx - 120, self.cancel_button_rect.centery - 15, self.font_medium)

    def draw_text(self, text, x, y, font, color=COLOR_INFO_TEXT):
        self.screen.blit(font.render(text, True, color), (x, y))

    def draw_multiline_text(self, text, x, y, max_width, font, color):
        words = text.split(' '); lines, current_line = [], ""
        for word in words:
            if font.size(current_line + " " + word)[0] < max_width: current_line += " " + word
            else: lines.append(current_line.strip()); current_line = word
        lines.append(current_line.strip())
        for i, line in enumerate(lines):
            self.draw_text(line, x, y + i * (font.get_height() + 2), font, color)

    def format_variation_for_display(self, variation, start_board):
        """Verilen hamle listesini okunabilir satranç notasyonuna çevirir."""
        if not variation: return ""
        board = start_board.copy()
        line, move_count = [], 0
        for move in variation:
            if not board.is_legal(move): break
            if board.turn == chess.WHITE: line.append(f"{board.fullmove_number}.")
            elif not line: line.append(f"{board.fullmove_number}... ")
            line.append(board.san(move))
            board.push(move)
            move_count += 1
            if move_count >= 5: break # En fazla 5 yarım hamle (2.5 tam hamle) göster
        return " ".join(line)

    def analyze_player_move(self, move):
        depth = AI_SETTINGS[DIFFICULTY_LEVELS[self.difficulty_index]]["depth"]
        try:
            analysis_before = self.engine.analyse(self.board, chess.engine.Limit(depth=depth), multipv=3)
            top_moves_before = [info['pv'][0] for info in analysis_before if 'pv' in info and info['pv']]
            
            if move in top_moves_before:
                quality = "excellent" if move == top_moves_before[0] else "great"
                self.feedback_color = EXCELLENT_MOVE_COLOR if quality == "excellent" else GOOD_MOVE_COLOR
                self.feedback_text = self.generate_move_commentary(move, quality)
                return {'quality': quality}

            temp_board = self.board.copy(); temp_board.push(move)
            analysis_after = self.engine.analyse(temp_board, chess.engine.Limit(depth=depth))
            score_before = analysis_before[0]["score"].relative.score(mate_score=10000)
            score_after = analysis_after["score"].white().score(mate_score=10000)
            score_delta = score_after - score_before if self.board.turn == chess.WHITE else score_before - score_after
            
            threat = self.engine.play(temp_board, chess.engine.Limit(time=0.4, depth=max(6, depth//2))).move
            self.threat_move = threat
            self.best_alternative_move = top_moves_before[0] if top_moves_before else None
            
            best_variation = analysis_before[0].get('pv', [])
            variation_str = self.format_variation_for_display(best_variation, self.board)

            if score_delta <= BLUNDER_THRESHOLD: quality, self.feedback_color = "blunder", BLUNDER_COLOR
            elif score_delta <= MISTAKE_THRESHOLD: quality, self.feedback_color = "mistake", MISTAKE_COLOR
            elif score_delta <= INACCURACY_THRESHOLD: quality, self.feedback_color = "inaccuracy", INACCURACY_COLOR
            else: quality, self.feedback_color = "good", COLOR_INFO_TEXT
            
            self.feedback_text = self.generate_move_commentary(move, quality, threat, self.best_alternative_move, variation_str)
            return {'quality': quality}
        except Exception as e:
            print(f"Analiz sırasında hata: {e}"); return {'quality': 'error'}

    def generate_move_commentary(self, move, quality, threat=None, best_alt=None, variation_str=""):
        comments = {
            'excellent': ["Mükemmel hamle! Tam bir usta gibi.", "Harika bir görüş! Motorun da ilk tercihi buydu."],
            'great': ["Harika bir hamle! Çok sağlam ve akıllıca.", "Güzel fikir! Pozisyonunu güçlendiriyorsun."],
            'good': ["İyi bir gelişim hamlesi.", "Mantıklı bir hamle. Böyle devam et!"],
            'inaccuracy': [f"Fena değil, ama daha iyisi olabilirdi.", f"Bunun yerine {best_alt.uci() if best_alt else 'başka bir hamle'} daha etkili olabilirdi."],
            'mistake': [f"Dikkat! Bu hamle rakibe bir fırsat veriyor.", f"Bunun yerine şu devam yolu daha güçlüydü: {variation_str}"],
            'blunder': [f"Eyvah! Bu çok tehlikeli bir hamle!", f"Bu ağır bir hata! Tavsiye edilen devam yolu şuydu: {variation_str}"]
        }
        if quality in ['excellent', 'great', 'good']:
            if self.board.is_castling(move): return "Şahını güvende tutmak için harika bir hamle! Kalen de artık savaşa hazır."
            if self.board.is_capture(move): return "Rakibin taşını alarak materyal kazandın. Aferin!"
        selected_comment = random.choice(comments.get(quality, ["İlginç bir hamle."]))
        if quality in ['blunder', 'mistake'] and TUTOR_MODES[self.tutor_mode_index] == "KATI":
            selected_comment += " Bu hamleye izin verilmedi."
        return selected_comment

    def make_ai_move(self):
        settings = AI_SETTINGS[DIFFICULTY_LEVELS[self.difficulty_index]]
        try:
            result = self.engine.play(self.board, chess.engine.Limit(time=settings["time"], depth=settings["depth"]))
            self.board.push(result.move); self.last_move = result.move; self.player_turn = True
            self.feedback_text = "Sıra sende. En iyi hamleni düşün!"; self.feedback_color = COLOR_INFO_TEXT
        except Exception as e:
            print(f"Yapay zeka hamle yaparken hata: {e}")
            if list(self.board.legal_moves):
                self.board.push(random.choice(list(self.board.legal_moves))); self.player_turn = True

    def handle_click(self, pos):
        if self.mode_button_rect.collidepoint(pos): self.tutor_mode_index = (self.tutor_mode_index + 1) % len(TUTOR_MODES); self.reset_turn(); return
        if self.diff_button_rect.collidepoint(pos): self.difficulty_index = (self.difficulty_index + 1) % len(DIFFICULTY_LEVELS); self.configure_engine_difficulty(); self.reset_turn(); return
        if self.cancel_button_rect.collidepoint(pos) and self.pending_move: self.reset_turn(); return
        if not self.player_turn: return
        clicked_square = self.get_square_from_mouse(pos)
        if clicked_square is None: return
        if self.pending_move and clicked_square == self.pending_move.to_square: self.make_move(self.pending_move); return
        if self.selected_square is None:
            piece = self.board.piece_at(clicked_square)
            if piece and piece.color == self.board.turn: self.selected_square = clicked_square; self.reset_feedback()
        else:
            move = chess.Move(self.selected_square, clicked_square)
            if self.board.piece_at(self.selected_square).piece_type == chess.PAWN and chess.square_rank(clicked_square) in [0, 7]: move.promotion = chess.QUEEN
            if move in self.board.legal_moves:
                analysis = self.analyze_player_move(move)
                is_bad_move = analysis['quality'] in ['blunder', 'mistake']
                if not is_bad_move: self.make_move(move)
                else:
                    if TUTOR_MODES[self.tutor_mode_index] == "TAVSİYECİ": self.pending_move = move
                    self.selected_square = None
            else: self.selected_square = None

    def make_move(self, move):
        self.board.push(move); self.last_move = move; self.player_turn = False; self.reset_turn()

    def reset_turn(self):
        self.selected_square, self.pending_move, self.best_alternative_move, self.threat_move = None, None, None, None
        self.reset_feedback()

    def reset_feedback(self):
        if self.player_turn: self.feedback_text = "Hamleni yap. Taş seçmek için üzerine tıkla."
        self.feedback_color = COLOR_INFO_TEXT

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: running = False
                if event.type == pygame.MOUSEBUTTONDOWN: self.handle_click(event.pos)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: self.reset_turn()
            self.draw()
            if self.board.is_game_over():
                result = self.board.result()
                winner = "Beyaz" if "1-0" in result else "Siyah"
                self.feedback_text = f"Şah Mat! {winner} kazandı." if self.board.is_checkmate() else "Oyun bitti! Sonuç: Berabere."
                self.feedback_color = COLOR_TITLE; self.draw()
                pygame.time.wait(5000); running = False
            if not self.player_turn and not self.board.is_game_over():
                pygame.time.wait(250); self.make_ai_move()
            self.clock.tick(30)
        self.engine.quit(); pygame.quit(); sys.exit()

if __name__ == "__main__":
    game = GeminiChessTutor()
    game.run()
