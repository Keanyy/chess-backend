# Gemini'nin Satranç Akademisi (Geliştirilmiş Kivy Mobil Versiyon)
# Masaüstü versiyonundaki detaylı analiz mantığını ve oyun sonu popup'ını içerir.

import os
import chess
import chess.engine
import random
from kivy.app import App
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle

# ---------- OYUN AYARLARI ----------
STOCKFISH_PATH = "./stockfish_arm" 

# --- Renk Paleti ---
COLOR_LIGHT_SQUARE = (240/255, 217/255, 181/255, 1)
COLOR_DARK_SQUARE = (181/255, 136/255, 99/255, 1)
COLOR_BACKGROUND = (49/255, 46/255, 43/255, 1)
COLOR_INFO_TEXT = (230/255, 230/255, 230/255, 1)
COLOR_TITLE = (255/255, 204/255, 102/255, 1)
EXCELLENT_MOVE_COLOR = (102/255, 255/255, 102/255, 1)
GOOD_MOVE_COLOR = (153/255, 204/255, 153/255, 1)
INACCURACY_COLOR = (255/255, 255/255, 153/255, 1)
MISTAKE_COLOR = (255/255, 153/255, 51/255, 1)
BLUNDER_COLOR = (255/255, 102/255, 102/255, 1)
HIGHLIGHT_COLOR = (1, 1, 102/255, 0.6)

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

class ChessBoardWidget(GridLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cols = 8
        self.squares = {}
        for i in range(64):
            row, col = 7 - (i // 8), i % 8
            square_widget = Button(background_normal='', background_color=COLOR_LIGHT_SQUARE if (row + col) % 2 == 0 else COLOR_DARK_SQUARE)
            square_widget.square_index = chess.square(col, row)
            square_widget.bind(on_press=self.on_square_click)
            self.squares[square_widget.square_index] = square_widget
            self.add_widget(square_widget)

    def on_square_click(self, instance):
        App.get_running_app().game_logic.handle_click(instance.square_index)

    def update_board(self, board):
        for square_index, square_widget in self.squares.items():
            square_widget.clear_widgets()
            piece = board.piece_at(square_index)
            if piece:
                symbol = ('w' if piece.color == chess.WHITE else 'b') + piece.symbol().upper()
                if piece.color == chess.BLACK: symbol = symbol.lower()
                square_widget.add_widget(Image(source=f'pieces/{symbol}.png'))
    
    def highlight_square(self, square_index, color):
        if square_index is not None:
            widget = self.squares[square_index]
            with widget.canvas.after:
                Color(*color)
                Rectangle(pos=widget.pos, size=widget.size)

    def clear_highlights(self):
        for square in self.squares.values():
            square.canvas.after.clear()

class GameLogic:
    def __init__(self, main_widget):
        self.main_widget = main_widget
        self.board = chess.Board()
        self.engine = None
        self.selected_square, self.pending_move = None, None
        self.player_turn = True
        self.tutor_mode_index, self.difficulty_index = 0, 0
        self.init_engine()

    def init_engine(self):
        try:
            # Android'de dosya yolları farklı çalışabilir. Buildozer'ın paketlediği yerden okuması için basit yol.
            if os.path.exists('stockfish_arm'):
                self.engine = chess.engine.SimpleEngine.popen_uci('stockfish_arm')
                self.configure_engine_difficulty()
            else:
                 self.main_widget.update_feedback(f"HATA: stockfish_arm bulunamadı!", BLUNDER_COLOR)
        except Exception as e:
            self.main_widget.update_feedback(f"HATA: Stockfish başlatılamadı!", BLUNDER_COLOR)

    def configure_engine_difficulty(self):
        if not self.engine: return
        settings = AI_SETTINGS[DIFFICULTY_LEVELS[self.difficulty_index]]
        elo = settings.get("elo")
        try:
            if elo: self.engine.configure({"UCI_LimitStrength": True, "UCI_Elo": elo})
            else: self.engine.configure({"UCI_LimitStrength": False})
        except Exception as e:
             self.main_widget.update_feedback(f"Motor ayarı başarısız!", BLUNDER_COLOR)

    def handle_click(self, clicked_square):
        if not self.player_turn: return
        if self.pending_move and clicked_square == self.pending_move.to_square:
            self.make_move(self.pending_move)
            return
        if self.selected_square is None:
            piece = self.board.piece_at(clicked_square)
            if piece and piece.color == self.board.turn:
                self.selected_square = clicked_square
                self.main_widget.chess_board.clear_highlights()
                self.main_widget.chess_board.highlight_square(self.selected_square, HIGHLIGHT_COLOR)
        else:
            move = chess.Move(self.selected_square, clicked_square)
            if self.board.piece_at(self.selected_square).piece_type == chess.PAWN and chess.square_rank(clicked_square) in [0, 7]:
                move.promotion = chess.QUEEN
            if move in self.board.legal_moves:
                analysis = self.analyze_player_move(move)
                is_bad_move = analysis['quality'] in ['blunder', 'mistake']
                if not is_bad_move:
                    self.make_move(move)
                else:
                    if TUTOR_MODES[self.tutor_mode_index] == "TAVSİYECİ":
                        self.pending_move = move
                    self.selected_square = None
            else:
                self.selected_square = None
            self.main_widget.chess_board.clear_highlights()
            
    def make_move(self, move):
        self.board.push(move)
        self.player_turn = False
        self.reset_turn()
        self.main_widget.chess_board.update_board(self.board)
        if self.board.is_game_over():
            self.main_widget.show_game_over_popup()
        else:
            Clock.schedule_once(self.make_ai_move, 0.5)

    def make_ai_move(self, dt):
        settings = AI_SETTINGS[DIFFICULTY_LEVELS[self.difficulty_index]]
        try:
            result = self.engine.play(self.board, chess.engine.Limit(time=settings["time"], depth=settings["depth"]))
            self.board.push(result.move)
            self.player_turn = True
            self.main_widget.update_feedback("Sıra sende. En iyi hamleni düşün!", COLOR_INFO_TEXT)
            self.main_widget.chess_board.update_board(self.board)
            if self.board.is_game_over():
                self.main_widget.show_game_over_popup()
        except Exception as e:
            self.main_widget.update_feedback(f"AI hatası!", BLUNDER_COLOR)

    def analyze_player_move(self, move):
        depth = AI_SETTINGS[DIFFICULTY_LEVELS[self.difficulty_index]]["depth"]
        try:
            analysis_before = self.engine.analyse(self.board, chess.engine.Limit(depth=depth), multipv=3)
            top_moves_before = [info['pv'][0] for info in analysis_before if 'pv' in info and info['pv']]
            if move in top_moves_before:
                quality = "excellent" if move == top_moves_before[0] else "great"
                color = EXCELLENT_MOVE_COLOR if quality == "excellent" else GOOD_MOVE_COLOR
                self.main_widget.update_feedback(self.generate_move_commentary(move, quality), color)
                return {'quality': quality}
            temp_board = self.board.copy(); temp_board.push(move)
            analysis_after = self.engine.analyse(temp_board, chess.engine.Limit(depth=depth))
            score_before = analysis_before[0]["score"].relative.score(mate_score=10000)
            score_after = analysis_after["score"].white().score(mate_score=10000)
            score_delta = score_after - score_before if self.board.turn == chess.WHITE else score_before - score_after
            best_alt = top_moves_before[0] if top_moves_before else None
            
            if score_delta <= BLUNDER_THRESHOLD: quality, color = "blunder", BLUNDER_COLOR
            elif score_delta <= MISTAKE_THRESHOLD: quality, color = "mistake", MISTAKE_COLOR
            elif score_delta <= INACCURACY_THRESHOLD: quality, color = "inaccuracy", INACCURACY_COLOR
            else: quality, color = "good", COLOR_INFO_TEXT
            
            self.main_widget.update_feedback(self.generate_move_commentary(move, quality, best_alt), color)
            return {'quality': quality}
        except Exception:
            return {'quality': 'error'}

    def generate_move_commentary(self, move, quality, best_alt=None):
        comments = {'excellent': ["Mükemmel hamle!", "Harika görüş!"], 'great': ["Harika hamle!", "Çok sağlam fikir!"],'good': ["İyi gelişim hamlesi.", "Mantıklı."],'inaccuracy': [f"Daha iyisi olabilirdi.", f"Belki {best_alt.uci() if best_alt else '...'}?"],'mistake': [f"Dikkat! Bu bir hata.", f"Daha iyi: {best_alt.uci() if best_alt else '...'}."],'blunder': [f"Eyvah! Ağır hata!", f"Öneri: {best_alt.uci() if best_alt else '...'}."]}
        return random.choice(comments.get(quality, ["..."]))

    def reset_turn(self):
        self.selected_square, self.pending_move = None, None
        self.main_widget.chess_board.clear_highlights()
        if self.player_turn:
            self.main_widget.update_feedback("Hamleni yap.", COLOR_INFO_TEXT)
    
    def new_game(self):
        self.board.reset()
        self.player_turn = True
        self.reset_turn()
        self.main_widget.chess_board.update_board(self.board)

class MainWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.game_logic = GameLogic(self)
        with self.canvas.before:
            Color(*COLOR_BACKGROUND); self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)
        self.chess_board = ChessBoardWidget(size_hint_y=None)
        self.bind(width=self.update_board_size)
        self.add_widget(self.chess_board)
        self.info_panel = BoxLayout(orientation='vertical', size_hint_y=0.2, padding=10, spacing=10)
        self.feedback_label = Label(text="Akademi'ye Hoş Geldin!", color=COLOR_TITLE, font_size='20sp')
        self.info_panel.add_widget(self.feedback_label)
        controls_layout = BoxLayout(size_hint_y=None, height=40)
        self.mode_button = Button(text=f"Mod: {TUTOR_MODES[self.game_logic.tutor_mode_index]}", on_press=self.change_mode)
        self.diff_button = Button(text=f"Zorluk: {DIFFICULTY_LEVELS[self.game_logic.difficulty_index]}", on_press=self.change_difficulty)
        controls_layout.add_widget(self.mode_button); controls_layout.add_widget(self.diff_button)
        self.info_panel.add_widget(controls_layout)
        self.add_widget(self.info_panel)
        self.chess_board.update_board(self.game_logic.board)

    def _update_rect(self, instance, value): self.rect.pos, self.rect.size = instance.pos, instance.size
    def update_board_size(self, instance, value): self.chess_board.height = value
    def update_feedback(self, text, color): self.feedback_label.text, self.feedback_label.color = text, color
    def change_mode(self, instance):
        self.game_logic.tutor_mode_index = (self.game_logic.tutor_mode_index + 1) % len(TUTOR_MODES)
        instance.text = f"Mod: {TUTOR_MODES[self.game_logic.tutor_mode_index]}"; self.game_logic.reset_turn()
    def change_difficulty(self, instance):
        self.game_logic.difficulty_index = (self.game_logic.difficulty_index + 1) % len(DIFFICULTY_LEVELS)
        instance.text = f"Zorluk: {DIFFICULTY_LEVELS[self.game_logic.difficulty_index]}"; self.game_logic.configure_engine_difficulty(); self.game_logic.reset_turn()
        
    def show_game_over_popup(self):
        result = self.game_logic.board.result()
        if self.game_logic.board.is_checkmate():
            winner = "Beyaz" if "1-0" in result else "Siyah"
            message = f"Şah Mat! {winner} kazandı."
        else:
            message = "Oyun bitti! Sonuç: Berabere."
        
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text=message, font_size='20sp'))
        new_game_button = Button(text="Yeni Oyun", size_hint_y=None, height=40)
        content.add_widget(new_game_button)
        
        popup = Popup(title='Oyun Bitti', content=content, size_hint=(0.7, 0.4), auto_dismiss=False)
        new_game_button.bind(on_press=lambda x: self.start_new_game(popup))
        popup.open()

    def start_new_game(self, popup):
        popup.dismiss()
        self.game_logic.new_game()

class ChessTutorApp(App):
    def build(self):
        return MainWidget()

if __name__ == '__main__':
    ChessTutorApp().run()

