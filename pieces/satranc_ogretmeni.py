import pygame
import chess
import chess.engine
import os
import math

# --- Ayarlar ve Sabitler ---
STOCKFISH_PATH = "./stockfish.exe" # Windows için. Mac/Linux için: "./stockfish"

SCREEN_WIDTH = 950 # Metin alanı için genişliği artırdık
SCREEN_HEIGHT = 600
BOARD_SIZE = 512
SQUARE_SIZE = BOARD_SIZE // 8
INFO_PANEL_X = BOARD_SIZE + 20

# Renkler
WHITE = (238, 238, 210)
GREEN = (118, 150, 86)
HIGHLIGHT_COLOR = (255, 255, 51, 150)
SUGGESTION_COLOR = (135, 206, 250, 180)
THREAT_COLOR = (255, 50, 50) # Kırmızı

# Öğretmen Modları
TUTOR_MODES = ["ADVISOR", "STRICT"]

class ChessTutorGame:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Satranç Öğretmeni")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.font_small = pygame.font.SysFont("Arial", 18)
        self.font_medium = pygame.font.SysFont("Arial", 24, bold=True)
        self.board = chess.Board()
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        except FileNotFoundError:
            print(f"HATA: Stockfish motoru '{STOCKFISH_PATH}' yolunda bulunamadı.")
            print("Lütfen STOCKFISH_PATH değişkenini doğru ayarlayın.")
            exit()
            
        self.piece_images = self.load_piece_images()
        self.selected_square = None
        self.player_turn = True
        self.pending_move = None
        self.last_analysis = None
        
        self.tutor_mode_index = 0 # 0: ADVISOR, 1: STRICT

    def load_piece_images(self):
        images = {}
        pieces = ['P', 'R', 'N', 'B', 'Q', 'K']
        for piece in pieces:
            images[f'w{piece}'] = pygame.transform.scale(pygame.image.load(f'pieces/w{piece.upper()}.png'), (SQUARE_SIZE, SQUARE_SIZE))
            images[f'b{piece}'] = pygame.transform.scale(pygame.image.load(f'pieces/b{piece.lower()}.png'), (SQUARE_SIZE, SQUARE_SIZE))
        return images

    def get_square_from_mouse(self, pos):
        x, y = pos
        if x > BOARD_SIZE or y > BOARD_SIZE:
            return None
        col = x // SQUARE_SIZE
        row = y // SQUARE_SIZE
        return chess.square(col, 7 - row)

    def draw_text(self, text, x, y, font, color=(255, 255, 255)):
        text_surface = font.render(text, True, color)
        self.screen.blit(text_surface, (x, y))

    def draw_arrow(self, start_sq, end_sq, color):
        start_center = ((chess.square_file(start_sq) + 0.5) * SQUARE_SIZE, (7 - chess.square_rank(start_sq) + 0.5) * SQUARE_SIZE)
        end_center = ((chess.square_file(end_sq) + 0.5) * SQUARE_SIZE, (7 - chess.square_rank(end_sq) + 0.5) * SQUARE_SIZE)
        pygame.draw.line(self.screen, color, start_center, end_center, 5)
        
        # Ok ucu çizimi
        rotation = math.degrees(math.atan2(start_center[1]-end_center[1], end_center[0]-start_center[0]))+90
        pygame.draw.polygon(self.screen, color, ((end_center[0]+20*math.sin(math.radians(rotation)), end_center[1]+20*math.cos(math.radians(rotation))), (end_center[0]+20*math.sin(math.radians(rotation-120)), end_center[1]+20*math.cos(math.radians(rotation-120))), (end_center[0]+20*math.sin(math.radians(rotation+120)), end_center[1]+20*math.cos(math.radians(rotation+120)))))

    def draw_game_state(self):
        # Bilgi Paneli
        self.draw_text("SATRANÇ ÖĞRETMENİ", INFO_PANEL_X, 20, self.font_medium)
        
        # Mod değiştirme butonu
        mode_text = f"Mod: {TUTOR_MODES[self.tutor_mode_index]} (Değiştirmek için tıkla)"
        self.mode_button_rect = pygame.Rect(INFO_PANEL_X, 70, 300, 40)
        self.draw_text(mode_text, INFO_PANEL_X, 80, self.font_small)

        if self.last_analysis and self.last_analysis['is_blunder']:
            analysis = self.last_analysis
            self.draw_text("DİKKAT! Bu hamle hatalı olabilir.", INFO_PANEL_X, 150, self.font_small, THREAT_COLOR)
            
            # Neden kötü olduğunu açıkla
            threat_move = analysis['threat']
            captured_piece = self.board.piece_at(threat_move.to_square)
            explanation = f"Rakibin cevabı: {threat_move.uci()}"
            if captured_piece:
                explanation += f" ({captured_piece.symbol()} taşını alır!)"
            self.draw_text(explanation, INFO_PANEL_X, 180, self.font_small, (255, 200, 200))

            # Daha iyi hamleler öner
            self.draw_text("Daha iyi alternatifler:", INFO_PANEL_X, 230, self.font_small)
            for i, move in enumerate(analysis['best_moves']):
                self.draw_text(f"{i+1}. {move.uci()}", INFO_PANEL_X, 260 + i * 30, self.font_small, (200, 255, 200))
            
            if TUTOR_MODES[self.tutor_mode_index] == "ADVISOR":
                self.draw_text("Hamleyi onaylamak için tekrar tıkla", INFO_PANEL_X, 400, self.font_small)
                self.draw_text("Veya başka bir hamle yap.", INFO_PANEL_X, 430, self.font_small)
            else: # STRICT
                self.draw_text("Bu hamle engellendi.", INFO_PANEL_X, 400, self.font_small, THREAT_COLOR)
                self.draw_text("Lütfen başka bir hamle yapın.", INFO_PANEL_X, 430, self.font_small)

    def draw_board_elements(self):
        # Tahta ve Taşlar
        for row in range(8):
            for col in range(8):
                pygame.draw.rect(self.screen, WHITE if (row + col) % 2 == 0 else GREEN, (col * SQUARE_SIZE, row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE))
        
        # Vurgular ve Öneriler
        if self.last_analysis and self.last_analysis['is_blunder']:
            # Önerilen hamlelerin hedef karelerini çiz
            for move in self.last_analysis['best_moves']:
                surface = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
                surface.fill(SUGGESTION_COLOR)
                self.screen.blit(surface, (chess.square_file(move.to_square) * SQUARE_SIZE, (7 - chess.square_rank(move.to_square)) * SQUARE_SIZE))
            
            # Tehdit okunu çiz
            threat = self.last_analysis['threat']
            self.draw_arrow(threat.from_square, threat.to_square, THREAT_COLOR)

        if self.selected_square is not None:
             surface = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
             surface.fill(HIGHLIGHT_COLOR)
             self.screen.blit(surface, (chess.square_file(self.selected_square) * SQUARE_SIZE, (7-chess.square_rank(self.selected_square)) * SQUARE_SIZE))
        
        # Taşları çiz
        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece:
                piece_symbol = piece.symbol()
                image_key = ('w' if piece_symbol.isupper() else 'b') + piece_symbol.upper()
                col, row = chess.square_file(square), 7 - chess.square_rank(square)
                self.screen.blit(self.piece_images[image_key], (col * SQUARE_SIZE, row * SQUARE_SIZE))

    def analyze_player_move(self, move):
        # Oyuncunun hamlesinden önceki pozisyonu analiz et
        info_before = self.engine.analyse(self.board, chess.engine.Limit(time=0.3, depth=15))
        score_before = info_before["score"].relative.score(mate_score=10000)

        # Hamleden sonraki pozisyonu geçici olarak analiz et
        temp_board = self.board.copy()
        temp_board.push(move)
        info_after = self.engine.analyse(temp_board, chess.engine.Limit(time=0.3, depth=15))
        score_after = info_after["score"].white().score(mate_score=10000)
        
        # Puan düşüşünü hesapla (Beyaz'ın perspektifinden)
        score_delta = score_after - score_before

        # Eğer büyük bir puan düşüşü varsa (100 cp = 1 piyon)
        if score_delta < -100:
            # En iyi 3 hamleyi bul
            best_moves_info = self.engine.analyse(self.board, chess.engine.Limit(time=0.5), multipv=3)
            best_moves = [item['pv'][0] for item in best_moves_info]
            
            # Rakibin en iyi cevabını (tehdidi) bul
            threat_info = self.engine.play(temp_board, chess.engine.Limit(time=0.2))
            
            return {
                'is_blunder': True,
                'score_delta': score_delta,
                'best_moves': best_moves,
                'threat': threat_info.move
            }
        
        return {'is_blunder': False}

    def make_ai_move(self):
        pygame.time.wait(500)
        result = self.engine.play(self.board, chess.engine.Limit(time=0.5))
        self.board.push(result.move)
        self.player_turn = True

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    
                    # Mod değiştirme butonuna tıklandı mı?
                    if self.mode_button_rect.collidepoint(pos):
                        self.tutor_mode_index = (self.tutor_mode_index + 1) % len(TUTOR_MODES)
                        self.last_analysis = None # Analizi temizle
                        continue

                    if not self.player_turn: continue
                    
                    clicked_square = self.get_square_from_mouse(pos)
                    if clicked_square is None: continue

                    # Bekleyen kötü bir hamle varken onayla
                    if self.pending_move and clicked_square == self.pending_move.to_square and TUTOR_MODES[self.tutor_mode_index] == "ADVISOR":
                        self.board.push(self.pending_move)
                        self.player_turn = False
                        self.pending_move = None
                        self.last_analysis = None
                        self.selected_square = None
                        continue
                    
                    # Yeni hamle yapma mantığı
                    if self.selected_square is None:
                        piece = self.board.piece_at(clicked_square)
                        if piece and piece.color == self.board.turn:
                            self.selected_square = clicked_square
                            self.last_analysis = None # Yeni seçimde eski analizi temizle
                            self.pending_move = None
                    else:
                        move = chess.Move(self.selected_square, clicked_square)
                        # Piyon terfisi
                        if self.board.piece_at(self.selected_square).piece_type == chess.PAWN and chess.square_rank(clicked_square) in [0, 7]:
                            move.promotion = chess.QUEEN
                        
                        if move in self.board.legal_moves:
                            analysis_result = self.analyze_player_move(move)
                            self.last_analysis = analysis_result

                            if not analysis_result['is_blunder']:
                                self.board.push(move)
                                self.player_turn = False
                                self.selected_square = None
                                self.last_analysis = None
                            else: # Hamle hatalı
                                if TUTOR_MODES[self.tutor_mode_index] == "ADVISOR":
                                    self.pending_move = move # Hamleyi onaya beklet
                                # STRICT modda hiçbir şey yapma, hamle otomatik engellenmiş olur
                                self.selected_square = None
                        else:
                            self.selected_square = None # Geçersiz hamle, seçimi kaldır

            # --- EKRANI ÇİZ ---
            self.screen.fill((40, 40, 40))
            self.draw_board_elements()
            self.draw_game_state()
            pygame.display.flip()

            if self.board.is_game_over():
                result = self.board.result()
                print(f"Oyun Bitti! Sonuç: {result}")
                pygame.time.wait(5000)
                running = False

            if not self.player_turn and not self.board.is_game_over():
                self.make_ai_move()

        self.engine.quit()
        pygame.quit()

if __name__ == '__main__':
    game = ChessTutorGame()
    game.run()
