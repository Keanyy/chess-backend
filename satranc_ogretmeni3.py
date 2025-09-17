# Satranç Akademisi
# Çocuklar için geliştirilmiş, öğretici ve eğlenceli satranç oyunu.
import pygame
import chess
import chess.engine
import sys
import os

# ---------- OYUN AYARLARI ----------
# Stockfish motorunun bulunduğu tam yolu buraya yazın.
# Windows için: "stockfish.exe", Linux/Mac için: "./stockfish" gibi olabilir.
# Eğer bu kodla aynı klasördeyse, sadece ismini yazmak yeterlidir.
STOCKFISH_PATH = "stockfish.exe" 

# --- Ekran ve Tahta Boyutları ---
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 650
BOARD_SIZE = 600
SQUARE_SIZE = BOARD_SIZE // 8
INFO_PANEL_X = BOARD_SIZE + 20

# --- Renk Paleti (Daha sıcak ve davetkar) ---
COLOR_LIGHT_SQUARE = (240, 217, 181)
COLOR_DARK_SQUARE = (181, 136, 99)
COLOR_BACKGROUND = (49, 46, 43)
COLOR_INFO_TEXT = (230, 230, 230)
COLOR_TITLE = (255, 204, 102)

HIGHLIGHT_COLOR = (255, 255, 102, 170)  # Seçili kare
LEGAL_MOVE_COLOR = (130, 151, 105, 120) # Yasal hamle dairesi
LAST_MOVE_COLOR = (212, 188, 166, 150) # Son yapılan hamle

GOOD_MOVE_COLOR = (153, 204, 153)
BLUNDER_COLOR = (255, 102, 102)
SUGGESTION_ARROW_COLOR = (102, 178, 255)
THREAT_ARROW_COLOR = (255, 80, 80)

# --- Oyun Modları ve Seviyeleri ---
TUTOR_MODES = ["TAVSİYECİ", "KATI"] # Tavsiyeci: Hatalı hamlede uyarır, KATI: Hatalı hamleye izin vermez.
DIFFICULTY_LEVELS = ["Çok Kolay", "Kolay", "Orta", "Zor"]

# Yapay Zeka Düşünme Ayarları
# Her seviye için (zaman, derinlik, ELO) ayarları.
AI_SETTINGS = {
    "Çok Kolay": {"time": 0.3, "depth": 5, "elo": 1320}, # Stockfish'in bu sürümü min 1320 ELO kabul ediyor.
    "Kolay":      {"time": 0.5, "depth": 8, "elo": 1400},
    "Orta":       {"time": 0.8, "depth": 12, "elo": 1600},
    "Zor":        {"time": 1.2, "depth": 18, "elo": 2200}
}

# --- Taş İsimleri (Türkçe) ---
PIECE_NAMES = {
    chess.PAWN: "Piyon", chess.KNIGHT: "At", chess.BISHOP: "Fil",
    chess.ROOK: "Kale", chess.QUEEN: "Vezir", chess.KING: "Şah"
}

# ---------- OYUN SINIFI: GeminiChessTutor ----------
class GeminiChessTutor:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("METE'nin Satranç Akademisi")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.font_small = pygame.font.SysFont("Arial", 18)
        self.font_medium = pygame.font.SysFont("Arial", 24, bold=True)
        self.font_large = pygame.font.SysFont("Arial", 32, bold=True)
        self.clock = pygame.time.Clock()

        # --- UI (Kullanıcı Arayüzü) Ayarları ---
        self.tutor_mode_index = 0
        self.difficulty_index = 0  # Başlangıç seviyesi: Çok Kolay
        self.mode_button_rect = pygame.Rect(0, 0, 0, 0)
        self.diff_button_rect = pygame.Rect(0, 0, 0, 0)
        self.cancel_button_rect = pygame.Rect(0, 0, 0, 0)

        self.board = chess.Board()
        self.init_engine()
        self.piece_images = self.load_piece_images()

        # --- Oyun Durumu Değişkenleri ---
        self.selected_square = None
        self.player_turn = True
        self.pending_move = None
        self.last_move = None
        
        # --- Öğretmen Geri Bildirimleri ---
        self.feedback_text = "Merhaba! Satranç Akademisi'ne hoş geldin. İlk hamleni yap."
        self.feedback_color = COLOR_INFO_TEXT
        self.best_alternative_move = None
        self.threat_move = None
        
    def init_engine(self):
        """Stockfish motorunu başlatır ve 'Çok Kolay' seviyesi için ayarlar."""
        if not os.path.exists(STOCKFISH_PATH):
            print(f"HATA: Stockfish motoru bulunamadı! '{STOCKFISH_PATH}' yolunu kontrol edin.")
            pygame.quit()
            sys.exit(1)
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
            self.configure_engine_difficulty() # Başlangıç zorluğunu ayarla
        except Exception as e:
            print(f"HATA: Stockfish motoru başlatılamadı: {e}")
            pygame.quit()
            sys.exit(1)
            
    def configure_engine_difficulty(self):
        """Seçilen zorluk seviyesine göre motoru yapılandırır."""
        level_name = DIFFICULTY_LEVELS[self.difficulty_index]
        settings = AI_SETTINGS[level_name]
        elo = settings.get("elo")
        if elo:
            self.engine.configure({"UCI_LimitStrength": True, "UCI_Elo": elo})
        else:
            self.engine.configure({"UCI_LimitStrength": False})

    def load_piece_images(self):
        """Taş görsellerini 'pieces' klasöründen yükler."""
        images = {}
        pieces = ['P', 'N', 'B', 'R', 'Q', 'K']
        for piece in pieces:
            try:
                # Beyaz taşlar için 'wP.png', siyahlar için 'bP.png' formatında
                images[f'w{piece}'] = pygame.transform.scale(pygame.image.load(f'pieces/w{piece}.png'), (SQUARE_SIZE, SQUARE_SIZE))
                images[f'b{piece.lower()}'] = pygame.transform.scale(pygame.image.load(f'pieces/b{piece.lower()}.png'), (SQUARE_SIZE, SQUARE_SIZE))
            except Exception as e:
                print(f"HATA: Taş görselleri yüklenemedi. 'pieces' klasörünü ve içindeki dosyaları kontrol edin. Hata: {e}")
                pygame.quit()
                sys.exit(1)
        return images

    def get_square_from_mouse(self, pos):
        """Mouse pozisyonuna göre tahtadaki kareyi döndürür."""
        x, y = pos
        if x > BOARD_SIZE or y > BOARD_SIZE:
            return None
        col = x // SQUARE_SIZE
        row = 7 - (y // SQUARE_SIZE)
        return chess.square(col, row)
        
    # ---------- ÇİZİM FONKSİYONLARI ----------
    
    def draw(self):
        """Tüm oyun ekranını çizer."""
        self.screen.fill(COLOR_BACKGROUND)
        self.draw_board()
        self.draw_highlights_and_moves()
        self.draw_pieces()
        self.draw_info_panel()
        pygame.display.flip()
        
    def draw_board(self):
        """Satranç tahtasını ve koordinatları çizer."""
        for row in range(8):
            for col in range(8):
                color = COLOR_LIGHT_SQUARE if (row + col) % 2 == 0 else COLOR_DARK_SQUARE
                pygame.draw.rect(self.screen, color, (col * SQUARE_SIZE, row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE))
        # Koordinatlar
        for i in range(8):
            # Dikey (1-8)
            label = self.font_small.render(str(8 - i), True, COLOR_DARK_SQUARE if i % 2 == 0 else COLOR_LIGHT_SQUARE)
            self.screen.blit(label, (5, i * SQUARE_SIZE + 5))
            # Yatay (a-h)
            label = self.font_small.render(chr(ord('a') + i), True, COLOR_DARK_SQUARE if (i + 7) % 2 == 0 else COLOR_LIGHT_SQUARE)
            self.screen.blit(label, (i * SQUARE_SIZE + SQUARE_SIZE - 15, BOARD_SIZE - 25))
            
    def draw_highlights_and_moves(self):
        """Seçili kareyi, yasal hamleleri ve son hamleyi vurgular."""
        # Seçili kareyi vurgula
        if self.selected_square is not None:
            s = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
            s.fill(HIGHLIGHT_COLOR)
            col = chess.square_file(self.selected_square)
            row = 7 - chess.square_rank(self.selected_square)
            self.screen.blit(s, (col * SQUARE_SIZE, row * SQUARE_SIZE))
            
            # Seçili taşın yasal hamlelerini daire ile göster
            for move in self.board.legal_moves:
                if move.from_square == self.selected_square:
                    center_x = chess.square_file(move.to_square) * SQUARE_SIZE + SQUARE_SIZE // 2
                    center_y = (7 - chess.square_rank(move.to_square)) * SQUARE_SIZE + SQUARE_SIZE // 2
                    pygame.draw.circle(self.screen, LEGAL_MOVE_COLOR, (center_x, center_y), SQUARE_SIZE // 6)

        # Son yapılan hamleyi göster
        if self.last_move:
            from_col, from_row = chess.square_file(self.last_move.from_square), 7 - chess.square_rank(self.last_move.from_square)
            to_col, to_row = chess.square_file(self.last_move.to_square), 7 - chess.square_rank(self.last_move.to_square)
            s = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
            s.fill(LAST_MOVE_COLOR)
            self.screen.blit(s, (from_col * SQUARE_SIZE, from_row * SQUARE_SIZE))
            self.screen.blit(s, (to_col * SQUARE_SIZE, to_row * SQUARE_SIZE))
        
        # Öneri ve tehdit oklarını çiz
        if self.best_alternative_move:
            self.draw_arrow(self.best_alternative_move.from_square, self.best_alternative_move.to_square, SUGGESTION_ARROW_COLOR)
        if self.threat_move:
            self.draw_arrow(self.threat_move.from_square, self.threat_move.to_square, THREAT_ARROW_COLOR)

    def draw_arrow(self, from_sq, to_sq, color):
        """İki kare arasında bir ok çizer."""
        start_pos = (chess.square_file(from_sq) * SQUARE_SIZE + SQUARE_SIZE // 2, (7 - chess.square_rank(from_sq)) * SQUARE_SIZE + SQUARE_SIZE // 2)
        end_pos = (chess.square_file(to_sq) * SQUARE_SIZE + SQUARE_SIZE // 2, (7 - chess.square_rank(to_sq)) * SQUARE_SIZE + SQUARE_SIZE // 2)
        pygame.draw.line(self.screen, color, start_pos, end_pos, 7)
        # Ok ucu
        angle = - ( (180 / 3.14159) * pygame.math.Vector2(end_pos[0] - start_pos[0], end_pos[1] - start_pos[1]).angle_to((1, 0)) )
        triangle_points = [
            (end_pos[0] + 20 * pygame.math.Vector2(1,0).rotate(angle - 30).x, end_pos[1] - 20 * pygame.math.Vector2(1,0).rotate(angle - 30).y),
            (end_pos[0] + 20 * pygame.math.Vector2(1,0).rotate(angle + 30).x, end_pos[1] - 20 * pygame.math.Vector2(1,0).rotate(angle + 30).y),
            end_pos
        ]
        pygame.draw.polygon(self.screen, color, triangle_points)

    def draw_pieces(self):
        """Taşları tahtaya çizer."""
        for sq in chess.SQUARES:
            piece = self.board.piece_at(sq)
            if piece:
                symbol = piece.symbol()
                if piece.color == chess.WHITE:
                    key = 'w' + symbol
                else:
                    key = 'b' + symbol.lower()
                col = chess.square_file(sq)
                row = 7 - chess.square_rank(sq)
                self.screen.blit(self.piece_images[key], (col * SQUARE_SIZE, row * SQUARE_SIZE))
                
    def draw_info_panel(self):
        """Sağdaki bilgi ve kontrol panelini çizer."""
        # Başlık
        self.draw_text("METE'nin Satranç Akademisi", INFO_PANEL_X, 30, self.font_large, COLOR_TITLE)

        # Butonlar
        y_pos = 100
        self.mode_button_rect = pygame.Rect(INFO_PANEL_X, y_pos, 300, 35)
        self.draw_text(f"Mod: {TUTOR_MODES[self.tutor_mode_index]} (Değiştir)", INFO_PANEL_X + 10, y_pos + 5, self.font_medium)
        y_pos += 50
        self.diff_button_rect = pygame.Rect(INFO_PANEL_X, y_pos, 300, 35)
        self.draw_text(f"Zorluk: {DIFFICULTY_LEVELS[self.difficulty_index]} (Değiştir)", INFO_PANEL_X + 10, y_pos + 5, self.font_medium)
        
        # Geri Bildirim Bölümü
        y_pos += 80
        pygame.draw.line(self.screen, COLOR_TITLE, (INFO_PANEL_X, y_pos), (SCREEN_WIDTH - 40, y_pos), 2)
        y_pos += 15
        self.draw_text("Tavsiye:", INFO_PANEL_X, y_pos, self.font_medium, COLOR_TITLE)
        y_pos += 40
        self.draw_multiline_text(self.feedback_text, INFO_PANEL_X, y_pos, 380, self.font_small, self.feedback_color)

        # Hamleden Vazgeç Butonu
        if self.pending_move:
            self.cancel_button_rect = pygame.Rect(INFO_PANEL_X, SCREEN_HEIGHT - 80, 300, 40)
            pygame.draw.rect(self.screen, (180, 50, 50), self.cancel_button_rect, border_radius=5)
            self.draw_text("Hamleden Vazgeç (ESC)", self.cancel_button_rect.x + 45, self.cancel_button_rect.y + 8, self.font_medium)

    def draw_text(self, text, x, y, font, color=COLOR_INFO_TEXT):
        """Ekrana metin yazar."""
        surface = font.render(text, True, color)
        self.screen.blit(surface, (x, y))

    def draw_multiline_text(self, text, x, y, max_width, font, color):
        """Verilen genişliğe göre metni bölerek yazar."""
        words = text.split(' ')
        lines = []
        current_line = ""
        for word in words:
            if font.size(current_line + " " + word)[0] < max_width:
                current_line += " " + word
            else:
                lines.append(current_line.strip())
                current_line = word
        lines.append(current_line.strip())
        
        for i, line in enumerate(lines):
            self.draw_text(line, x, y + i * (font.get_height() + 2), font, color)

    # ---------- OYUN MANTIĞI ----------

    def analyze_player_move(self, move):
        """Oyuncunun hamlesini analiz eder ve pedagojik geri bildirim oluşturur."""
        level_name = DIFFICULTY_LEVELS[self.difficulty_index]
        depth = AI_SETTINGS[level_name]["depth"]

        try:
            # Oyuncunun hamlesinden önceki en iyi hamleyi bul
            info_before = self.engine.analyse(self.board, chess.engine.Limit(depth=depth))
            best_move_before = info_before['pv'][0] if 'pv' in info_before and info_before['pv'] else None

            # Oyuncunun hamlesi en iyi hamlelerden biri mi?
            if move == best_move_before:
                 self.feedback_text = f"Harika hamle! {self.generate_move_commentary(move, 'good')}"
                 self.feedback_color = GOOD_MOVE_COLOR
                 return {'is_blunder': False}

            # Hamle yapıldıktan sonraki durumu analiz et
            temp_board = self.board.copy()
            temp_board.push(move)
            
            # Rakibin en iyi cevabını (tehdidi) bul
            threat_analysis = self.engine.play(temp_board, chess.engine.Limit(time=0.5, depth=max(6, depth//2)))
            threat = threat_analysis.move if threat_analysis else None
            self.threat_move = threat

            # Skor düşüşünü kontrol et (Blunder tespiti)
            score_before = info_before["score"].relative.score(mate_score=10000)
            info_after = self.engine.analyse(temp_board, chess.engine.Limit(depth=depth))
            score_after = info_after["score"].white().score(mate_score=10000)
            
            # Skor beyazın perspektifinden olduğu için, sırası siyahtaysa delta'yı ters çevir
            score_delta = score_after - score_before if self.board.turn == chess.WHITE else score_before - score_after
            
            # Büyük bir dezavantaj yaratıyorsa veya bir taşı bedavaya veriyorsa bu bir hatadır.
            is_blunder = score_delta < -150 or (threat and temp_board.is_capture(threat) and not self.board.is_protected_by(self.board.turn, move.to_square))
            
            if is_blunder:
                self.best_alternative_move = best_move_before
                self.feedback_text = f"Dikkat! Bu hamle tehlikeli olabilir. {self.generate_move_commentary(move, 'blunder', threat)}. Belki de bunun yerine {self.best_alternative_move.uci()} oynamak daha iyidir. Ne dersin?"
                self.feedback_color = BLUNDER_COLOR
                return {'is_blunder': True}
            else:
                self.feedback_text = f"Güzel hamle! {self.generate_move_commentary(move, 'normal')}"
                self.feedback_color = COLOR_INFO_TEXT
                return {'is_blunder': False}

        except Exception as e:
            print(f"Analiz sırasında hata: {e}")
            self.feedback_text = "Analiz sırasında bir sorun oluştu."
            self.feedback_color = BLUNDER_COLOR
            return {'is_blunder': False} # Analiz başarısızsa oyunu durdurma

    def generate_move_commentary(self, move, move_type, threat=None):
        """Hamlenin stratejik amacını basit bir dille açıklar."""
        piece = self.board.piece_at(move.from_square)
        piece_name = PIECE_NAMES.get(piece.piece_type, "taş").lower()
        to_sq_name = chess.square_name(move.to_square)

        # Hatalı Hamle Yorumları
        if move_type == 'blunder':
            if threat:
                threat_piece = self.board.copy().piece_at(threat.from_square)
                threat_piece_name = PIECE_NAMES.get(threat_piece.piece_type, "Rakip").lower() if threat_piece else "rakip"
                if self.board.is_capture(threat):
                    return f"Rakibin {threat_piece_name} ile senin {piece_name}ını ({to_sq_name}) almasına izin veriyorsun."
                else:
                    return f"Rakip {to_sq_name} karesine gelerek büyük bir tehlike yaratabilir."
            return "Bu hamle pozisyonunu zayıflatıyor ve rakibe avantaj veriyor."

        # İyi Hamle Yorumları
        # Gelişim
        is_development = piece.piece_type in [chess.KNIGHT, chess.BISHOP] and chess.square_rank(move.from_square) in [0, 7]
        if is_development:
            return f"Taşlarını oyuna sokmak harika bir fikir! Bu {piece_name} artık daha etkili."
        # Merkez Kontrolü
        if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
            return f"Merkezdeki önemli kareleri kontrol etmek çok akıllıca! Oyunun kontrolü sende."
        # Rok
        if self.board.is_castling(move):
            return "Şahını güvende tutmak için harika bir hamle! Kalen de artık savaşa hazır."
        # Taş Alma
        if self.board.is_capture(move):
            captured_piece = self.board.piece_at(move.to_square)
            captured_name = PIECE_NAMES.get(captured_piece.piece_type, "taş").lower() if captured_piece else "bir taşı"
            return f"Rakibin {captured_name}ını alarak materyal kazandın. Aferin!"

        return f"{piece_name.capitalize()}ını {to_sq_name} karesine oynamak iyi bir fikir gibi duruyor."

    def make_ai_move(self):
        """Yapay zekanın hamle yapmasını sağlar."""
        level_name = DIFFICULTY_LEVELS[self.difficulty_index]
        settings = AI_SETTINGS[level_name]
        try:
            limit = chess.engine.Limit(time=settings["time"], depth=settings["depth"])
            result = self.engine.play(self.board, limit)
            self.board.push(result.move)
            self.last_move = result.move
            self.player_turn = True
            self.feedback_text = "Sıra sende. En iyi hamleni düşün!"
            self.feedback_color = COLOR_INFO_TEXT
        except Exception as e:
            print(f"Yapay zeka hamle yaparken hata: {e}")
            # Motor çökerse rastgele bir yasal hamle yap
            if list(self.board.legal_moves):
                self.board.push(list(self.board.legal_moves)[0])
                self.player_turn = True


    def handle_click(self, pos):
        """Mouse tıklamalarını yönetir."""
        # UI Butonlarına tıklama
        if self.mode_button_rect.collidepoint(pos):
            self.tutor_mode_index = (self.tutor_mode_index + 1) % len(TUTOR_MODES)
            self.reset_turn()
            return
        if self.diff_button_rect.collidepoint(pos):
            self.difficulty_index = (self.difficulty_index + 1) % len(DIFFICULTY_LEVELS)
            self.configure_engine_difficulty() # Zorluğu motor üzerinde anında güncelle
            self.reset_turn()
            return
        if self.cancel_button_rect.collidepoint(pos) and self.pending_move:
            self.reset_turn()
            return
            
        # Tahtaya tıklama
        if not self.player_turn: return
        
        clicked_square = self.get_square_from_mouse(pos)
        if clicked_square is None: return

        # Bekleyen hamleyi onaylama (TAVSİYECİ modunda)
        if self.pending_move and clicked_square == self.pending_move.to_square and TUTOR_MODES[self.tutor_mode_index] == "TAVSİYECİ":
            self.make_move(self.pending_move)
            return

        # Yeni bir taş seçme
        if self.selected_square is None:
            piece = self.board.piece_at(clicked_square)
            if piece and piece.color == self.board.turn:
                self.selected_square = clicked_square
                self.reset_feedback()
        # Bir hamle yapma
        else:
            move = chess.Move(self.selected_square, clicked_square)
            # Piyon terfisi (otomatik olarak Vezir)
            if self.board.piece_at(self.selected_square).piece_type == chess.PAWN and chess.square_rank(clicked_square) in [0, 7]:
                move.promotion = chess.QUEEN
            
            if move in self.board.legal_moves:
                analysis = self.analyze_player_move(move)
                if not analysis['is_blunder']:
                    self.make_move(move)
                else:
                    if TUTOR_MODES[self.tutor_mode_index] == "TAVSİYECİ":
                        self.pending_move = move
                    else: # KATI modda hatalı hamleye izin verme
                        self.pending_move = None
                    self.selected_square = None
            else:
                self.selected_square = None # Geçersiz hamle, seçimi iptal et

    def make_move(self, move):
        """Verilen hamleyi tahtada uygular ve sırayı rakibe verir."""
        self.board.push(move)
        self.last_move = move
        self.player_turn = False
        self.reset_turn()

    def reset_turn(self):
        """Bir hamleden vazgeçildiğinde veya yeni bir hamle öncesinde durumu sıfırlar."""
        self.selected_square = None
        self.pending_move = None
        self.best_alternative_move = None
        self.threat_move = None
        self.reset_feedback()

    def reset_feedback(self):
        """Geri bildirim metnini varsayılana döndürür."""
        if self.player_turn:
            self.feedback_text = "Hamleni yap. Taş seçmek için üzerine tıkla."
        self.feedback_color = COLOR_INFO_TEXT

    def run(self):
        """Ana oyun döngüsü."""
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_click(event.pos)
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.reset_turn()

            self.draw()

            if self.board.is_game_over():
                result = self.board.result()
                if self.board.is_checkmate():
                    winner = "Beyaz" if "1-0" in result else "Siyah"
                    self.feedback_text = f"Şah Mat! {winner} kazandı. Tebrikler!"
                else:
                    self.feedback_text = "Oyun bitti! Sonuç: Berabere."
                self.feedback_color = COLOR_TITLE
                self.draw()
                pygame.time.wait(4000)
                running = False

            if not self.player_turn and not self.board.is_game_over():
                pygame.time.wait(500) # Yapay zeka düşünüyormuş gibi kısa bir bekleme
                self.make_ai_move()

            self.clock.tick(30)

        self.engine.quit()
        pygame.quit()
        sys.exit()


# ---------- OYUNU BAŞLAT ----------
if __name__ == "__main__":
    game = GeminiChessTutor()
    game.run()
