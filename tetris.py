#!/usr/bin/env python3
"""A small, dependency-free Tetris game. Run with: python3 tetris.py"""

import random
import time

try:
    import tkinter as tk
    from tkinter import messagebox
    TK_AVAILABLE = True
except ModuleNotFoundError as error:
    if error.name != "_tkinter":
        raise
    # Homebrew Python may be installed without Tk. In that case, use the
    # standard-library curses version so the game still runs in a terminal.
    import curses
    tk = None
    messagebox = None
    TK_AVAILABLE = False

CELL = 30
COLS = 10
ROWS = 20
BOARD_W = CELL * COLS
BOARD_H = CELL * ROWS

# Each piece is a matrix of 0s and 1s.
SHAPES = [
    ([[1, 1, 1, 1]], "#35c9e8"),                    # I
    ([[1, 0, 0], [1, 1, 1]], "#4c78ff"),           # J
    ([[0, 0, 1], [1, 1, 1]], "#ff9f43"),           # L
    ([[1, 1], [1, 1]], "#f5d547"),                 # O
    ([[0, 1, 1], [1, 1, 0]], "#46d17a"),           # S
    ([[0, 1, 0], [1, 1, 1]], "#bd72e8"),           # T
    ([[1, 1, 0], [0, 1, 1]], "#ef5d68"),           # Z
]


class TerminalTetris:
    """Curses fallback for Python builds that don't include Tkinter."""
    def __init__(self, screen):
        self.screen = screen
        self.reset()
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        if curses.has_colors():
            curses.start_color()
            try:
                curses.use_default_colors()
            except curses.error:
                pass
            colors = [curses.COLOR_CYAN, curses.COLOR_BLUE, curses.COLOR_YELLOW,
                      curses.COLOR_GREEN, curses.COLOR_MAGENTA, curses.COLOR_RED,
                      curses.COLOR_WHITE]
            for i, color in enumerate(colors, 1):
                curses.init_pair(i, color, curses.COLOR_BLACK)
        self.color_pair = {color: i + 1 for i, (_, color) in enumerate(SHAPES)}

    def reset(self):
        self.board = [[None for _ in range(COLS)] for _ in range(ROWS)]
        self.score = self.lines = 0
        self.level = 1
        self.paused = self.game_over = False
        self.bag = []
        self.next_piece = self.pick_piece()
        self.spawn()

    def pick_piece(self):
        if not self.bag:
            self.bag = SHAPES[:]
            random.shuffle(self.bag)
        shape, color = self.bag.pop()
        return [row[:] for row in shape], color

    def spawn(self):
        self.shape, self.color = self.next_piece
        self.next_piece = self.pick_piece()
        self.x = COLS // 2 - len(self.shape[0]) // 2
        self.y = 0
        if self.collides(self.x, self.y, self.shape):
            self.game_over = True

    def collides(self, x, y, shape):
        for row, cells in enumerate(shape):
            for col, filled in enumerate(cells):
                if filled:
                    px, py = x + col, y + row
                    if px < 0 or px >= COLS or py >= ROWS:
                        return True
                    if py >= 0 and self.board[py][px] is not None:
                        return True
        return False

    def lock(self):
        for row, cells in enumerate(self.shape):
            for col, filled in enumerate(cells):
                if filled and self.y + row >= 0:
                    self.board[self.y + row][self.x + col] = self.color
        remaining = [row for row in self.board if any(cell is None for cell in row)]
        cleared = ROWS - len(remaining)
        if cleared:
            self.board = [[None] * COLS for _ in range(cleared)] + remaining
            self.lines += cleared
            self.score += (0, 100, 300, 500, 800)[cleared] * self.level
            self.level = self.lines // 10 + 1
        self.spawn()

    def drop(self, points=0):
        if self.collides(self.x, self.y + 1, self.shape):
            self.lock()
        else:
            self.y += 1
            self.score += points

    def draw(self):
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        if height < 25 or width < 44:
            self.screen.addstr(0, 0, "Enlarge terminal to at least 44 columns x 25 rows.")
            self.screen.refresh()
            return
        self.screen.addstr(0, 2, "TETRIS")
        self.screen.addstr(1, 2, "Arrows: move/rotate/drop   Space: hard drop")
        self.screen.addstr(2, 2, "P: pause   R: restart   Q: quit")
        ox, oy = 2, 4
        for y in range(ROWS):
            self.screen.addstr(oy + y, ox, "|")
            for x in range(COLS):
                color = self.board[y][x]
                if not self.game_over and any(
                    filled and self.x + col == x and self.y + row == y
                    for row, cells in enumerate(self.shape)
                    for col, filled in enumerate(cells)
                ):
                    color = self.color
                if color:
                    attr = curses.color_pair(self.color_pair[color]) if curses.has_colors() else curses.A_REVERSE
                    self.screen.addstr(oy + y, ox + 1 + x * 2, "  ", attr)
                else:
                    self.screen.addstr(oy + y, ox + 1 + x * 2, "  ")
            self.screen.addstr(oy + y, ox + 21, "|")
        self.screen.addstr(oy + ROWS, ox, "+" + "-" * 20 + "+")
        side = ox + 25
        self.screen.addstr(oy + 1, side, f"Score: {self.score}")
        self.screen.addstr(oy + 2, side, f"Lines: {self.lines}")
        self.screen.addstr(oy + 3, side, f"Level: {self.level}")
        self.screen.addstr(oy + 5, side, "NEXT")
        shape, color = self.next_piece
        attr = curses.color_pair(self.color_pair[color]) if curses.has_colors() else curses.A_REVERSE
        for row, cells in enumerate(shape):
            for col, filled in enumerate(cells):
                if filled:
                    self.screen.addstr(oy + 6 + row, side + col * 2, "  ", attr)
        if self.paused:
            self.screen.addstr(oy + 12, side, "PAUSED")
        if self.game_over:
            self.screen.addstr(oy + 12, side, "GAME OVER")
            self.screen.addstr(oy + 13, side, "Press R to restart")
        self.screen.refresh()

    def run(self):
        self.screen.timeout(50)
        last_drop = time.monotonic()
        while True:
            self.draw()
            key = self.screen.getch()
            if key in (ord('q'), ord('Q')):
                break
            if key in (ord('r'), ord('R')):
                self.reset()
                last_drop = time.monotonic()
                continue
            if key in (ord('p'), ord('P')) and not self.game_over:
                self.paused = not self.paused
            if self.paused or self.game_over:
                continue
            if key == curses.KEY_LEFT and not self.collides(self.x - 1, self.y, self.shape):
                self.x -= 1
            elif key == curses.KEY_RIGHT and not self.collides(self.x + 1, self.y, self.shape):
                self.x += 1
            elif key == curses.KEY_DOWN:
                self.drop(1)
                last_drop = time.monotonic()
            elif key == curses.KEY_UP:
                rotated = [list(row) for row in zip(*self.shape[::-1])]
                for offset in (0, -1, 1, -2, 2):
                    if not self.collides(self.x + offset, self.y, rotated):
                        self.x += offset
                        self.shape = rotated
                        break
            elif key == ord(' '):
                distance = 0
                while not self.collides(self.x, self.y + 1, self.shape):
                    self.y += 1
                    distance += 1
                self.score += distance * 2
                self.lock()
                last_drop = time.monotonic()
            interval = max(0.09, 0.65 - (self.level - 1) * 0.055)
            if time.monotonic() - last_drop >= interval:
                self.drop()
                last_drop = time.monotonic()


def run_terminal_game():
    curses.wrapper(lambda screen: TerminalTetris(screen).run())


class Tetris:
    def __init__(self, root):
        self.root = root
        root.title("Tetris")
        root.resizable(False, False)
        root.configure(bg="#171923")

        self.canvas = tk.Canvas(
            root, width=BOARD_W, height=BOARD_H,
            bg="#10131b", highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, rowspan=2, padx=(16, 12), pady=16)

        panel = tk.Frame(root, bg="#171923", padx=8, pady=16)
        panel.grid(row=0, column=1, sticky="n")
        tk.Label(panel, text="TETRIS", font=("Helvetica", 20, "bold"),
                 fg="white", bg="#171923").pack(anchor="w", pady=(0, 16))
        self.score_label = self._label(panel, "Score: 0")
        self.lines_label = self._label(panel, "Lines: 0")
        self.level_label = self._label(panel, "Level: 1")
        self._label(panel, "NEXT", bold=True).pack(anchor="w", pady=(20, 4))
        self.preview = tk.Canvas(panel, width=120, height=100, bg="#10131b",
                                 highlightthickness=0)
        self.preview.pack(anchor="w")
        self.status_label = self._label(panel, "")
        self.status_label.pack(anchor="w", pady=(8, 0))

        controls = tk.Frame(root, bg="#171923", padx=16, pady=0)
        controls.grid(row=1, column=1, sticky="sw", pady=(0, 16))
        tk.Label(controls, text="← →  Move\n↑      Rotate\n↓      Soft drop\nSpace  Hard drop\nP      Pause   R Restart",
                 justify="left", font=("Helvetica", 10), fg="#c5cad6",
                 bg="#171923").pack(anchor="w")

        self.bindings = {
            "<Left>": lambda: self.move(-1),
            "<Right>": lambda: self.move(1),
            "<Down>": self.soft_drop,
            "<Up>": self.rotate,
            "<space>": self.hard_drop,
            "p": self.toggle_pause,
            "P": self.toggle_pause,
            "r": self.restart,
            "R": self.restart,
        }
        for key, callback in self.bindings.items():
            root.bind(key, lambda event, cb=callback: cb())

        self.after_id = None
        self.restart()

    @staticmethod
    def _label(parent, text, bold=False):
        return tk.Label(parent, text=text,
                        font=("Helvetica", 12, "bold" if bold else "normal"),
                        fg="#e8eaf0", bg="#171923")

    def restart(self):
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.board = [[None for _ in range(COLS)] for _ in range(ROWS)]
        self.score = self.lines = 0
        self.level = 1
        self.paused = self.game_over = False
        self.bag = []
        self.next_piece = self.random_piece()
        self.spawn_piece()
        self.update_labels()
        self.draw()
        self.tick()

    def random_piece(self):
        if not self.bag:
            self.bag = SHAPES[:]
            random.shuffle(self.bag)
        shape, color = self.bag.pop()
        return [row[:] for row in shape], color

    def spawn_piece(self):
        self.shape, self.color = self.next_piece
        self.next_piece = self.random_piece()
        self.x = COLS // 2 - len(self.shape[0]) // 2
        self.y = 0
        if self.collides(self.x, self.y, self.shape):
            self.game_over = True

    def collides(self, x, y, shape):
        for row, cells in enumerate(shape):
            for col, occupied in enumerate(cells):
                if not occupied:
                    continue
                px, py = x + col, y + row
                if px < 0 or px >= COLS or py >= ROWS:
                    return True
                if py >= 0 and self.board[py][px] is not None:
                    return True
        return False

    def move(self, dx):
        if not self.paused and not self.game_over and not self.collides(self.x + dx, self.y, self.shape):
            self.x += dx
            self.draw()

    def rotate(self):
        if self.paused or self.game_over:
            return
        rotated = [list(row) for row in zip(*self.shape[::-1])]
        # Small wall kicks make rotations near an edge feel natural.
        for offset in (0, -1, 1, -2, 2):
            if not self.collides(self.x + offset, self.y, rotated):
                self.x += offset
                self.shape = rotated
                self.draw()
                return

    def soft_drop(self):
        if self.paused or self.game_over:
            return
        if not self.collides(self.x, self.y + 1, self.shape):
            self.y += 1
            self.score += 1
            self.update_labels()
        else:
            self.lock_piece()
        self.draw()

    def hard_drop(self):
        if self.paused or self.game_over:
            return
        distance = 0
        while not self.collides(self.x, self.y + 1, self.shape):
            self.y += 1
            distance += 1
        self.score += distance * 2
        self.lock_piece()
        self.update_labels()
        self.draw()

    def lock_piece(self):
        for row, cells in enumerate(self.shape):
            for col, occupied in enumerate(cells):
                if occupied:
                    py, px = self.y + row, self.x + col
                    if py >= 0:
                        self.board[py][px] = self.color

        remaining = [row for row in self.board if any(cell is None for cell in row)]
        cleared = ROWS - len(remaining)
        if cleared:
            self.board = [[None] * COLS for _ in range(cleared)] + remaining
            self.lines += cleared
            self.score += (0, 100, 300, 500, 800)[cleared] * self.level
            self.level = self.lines // 10 + 1
        self.spawn_piece()
        self.update_labels()

    def tick(self):
        if not self.paused and not self.game_over:
            if not self.collides(self.x, self.y + 1, self.shape):
                self.y += 1
            else:
                self.lock_piece()
            self.draw()
        self.after_id = self.root.after(max(90, 650 - (self.level - 1) * 55), self.tick)

    def toggle_pause(self):
        if not self.game_over:
            self.paused = not self.paused
            self.status_label.config(text="PAUSED" if self.paused else "")
            self.draw()

    def update_labels(self):
        self.score_label.config(text=f"Score: {self.score}")
        self.lines_label.config(text=f"Lines: {self.lines}")
        self.level_label.config(text=f"Level: {self.level}")

    def draw_cell(self, canvas, x, y, color, size=CELL):
        pad = 1
        canvas.create_rectangle(x * size + pad, y * size + pad,
                                (x + 1) * size - pad, (y + 1) * size - pad,
                                fill=color, outline="#171923", width=1)

    def draw(self):
        self.canvas.delete("all")
        # Subtle board grid.
        for x in range(COLS + 1):
            self.canvas.create_line(x * CELL, 0, x * CELL, BOARD_H, fill="#202431")
        for y in range(ROWS + 1):
            self.canvas.create_line(0, y * CELL, BOARD_W, y * CELL, fill="#202431")
        for y, row in enumerate(self.board):
            for x, color in enumerate(row):
                if color:
                    self.draw_cell(self.canvas, x, y, color)
        if not self.game_over:
            for row, cells in enumerate(self.shape):
                for col, occupied in enumerate(cells):
                    if occupied and self.y + row >= 0:
                        self.draw_cell(self.canvas, self.x + col, self.y + row, self.color)
        self.preview.delete("all")
        shape, color = self.next_piece
        size = 22
        offset_x = (120 - len(shape[0]) * size) // 2
        offset_y = (100 - len(shape) * size) // 2
        for y, row in enumerate(shape):
            for x, occupied in enumerate(row):
                if occupied:
                    self.preview.create_rectangle(
                        offset_x + x * size + 1, offset_y + y * size + 1,
                        offset_x + (x + 1) * size - 1, offset_y + (y + 1) * size - 1,
                        fill=color, outline="#171923")
        if self.game_over:
            self.canvas.create_rectangle(25, 245, BOARD_W - 25, 355,
                                         fill="#171923", outline="")
            self.canvas.create_text(BOARD_W // 2, 278, text="GAME OVER",
                                    fill="white", font=("Helvetica", 22, "bold"))
            self.canvas.create_text(BOARD_W // 2, 318, text="Press R to restart",
                                    fill="#c5cad6", font=("Helvetica", 12))


def main():
    root = tk.Tk()
    Tetris(root)
    root.mainloop()


if __name__ == "__main__":
    if TK_AVAILABLE:
        main()
    else:
        run_terminal_game()
