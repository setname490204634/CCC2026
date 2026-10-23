from enum import IntEnum


class Direction(IntEnum):
    E = 1
    SE = 2
    SW = 3
    W = 4
    NE = 5
    NW = 6


# Offsets in the printed character matrix.
DIRECTIONS = {
    Direction.E:  (0, 2),
    Direction.SE: (1, 1),
    Direction.SW: (1, -1),
    Direction.W:  (0, -2),
    Direction.NE: (-1, -1),
    Direction.NW: (-1, 1),
}


class HexBoard:
    """Hexagonal board stored as a contiguous one-byte-per-character matrix."""

    VALID_CELLS = set("OMPLNQWERTYUIOPASDFGHJKLZXCVBNM123456")

    def __init__(self, rows):
        self.height = len(rows)
        self.width = len(rows[0]) if rows else 0

        if any(len(row) != self.width for row in rows):
            raise ValueError("All rows must have the same width")

        self.cells = bytearray("".join(rows), "ascii")

    def index(self, r, c):
        if 0 <= r < self.height and 0 <= c < self.width:
            return r * self.width + c
        return None

    def get(self, r, c):
        i = self.index(r, c)
        return chr(self.cells[i]) if i is not None else None

    def set(self, r, c, value):
        if len(value) != 1 or ord(value) > 127:
            raise ValueError("Each cell must be one ASCII character")

        i = self.index(r, c)
        if i is None:
            raise IndexError("Cell is outside the board")

        self.cells[i] = ord(value)

    def move(self, r, c, direction):
        """Move one step; return coordinates or None if no valid neighbor."""
        dr, dc = DIRECTIONS[Direction(direction)]
        nr, nc = r + dr, c + dc

        if self.get(nr, nc) not in self.VALID_CELLS:
            return None

        return nr, nc

    def emitters(self):
        """Return all emitters as (row, column, direction)."""
        result = []

        for r in range(self.height):
            for c in range(self.width):
                ch = self.get(r, c)
                if ch in "123456":
                    result.append((r, c, Direction(int(ch))))

        return result

    def to_rows(self):
        return [
            self.cells[r * self.width:(r + 1) * self.width].decode("ascii")
            for r in range(self.height)
        ]

    def print_board(self):
        print("\n".join(self.to_rows()))


def simulate_laser(board, direction, start):
    """Return the cells reached by one laser."""
    r, c = start
    cells = []

    while True:
        next_cell = board.move(r, c, direction)

        if next_cell is None:
            break

        r, c = next_cell
        cells.append((r, c))

    return cells


def process_board(board):
    """Apply matter creation and destruction where beams intersect."""
    hits = {}

    for r, c, direction in board.emitters():
        for cell in simulate_laser(board, direction, (r, c)):
            hits[cell] = hits.get(cell, 0) + 1

    for (r, c), count in hits.items():
        if board.get(r, c) in "123456":
            continue

        if count == 2:
            board.set(r, c, "M")
        elif count >= 3:
            board.set(r, c, "O")

    return board


def main(input_filename, output_filename="output"):
    with open(input_filename, "r") as infile:
        lines = iter(infile)

        def next_nonempty_line():
            for line in lines:
                if line.strip():
                    return line.strip()
            raise ValueError("Unexpected end of input")

        n = int(next_nonempty_line())

        with open(output_filename, "w", newline="\n") as outfile:
            for i in range(n):
                radius, rows, cols = map(
                    int, next_nonempty_line().split()
                )

                board_rows = [
                    next(lines).rstrip("\r\n")
                    for _ in range(rows)
                ]

                if any(len(row) != cols for row in board_rows):
                    raise ValueError("Input row width does not match cols")

                board = HexBoard(board_rows)
                result = process_board(board)

                if i > 0:
                    outfile.write("\n")

                outfile.write("\n".join(result.to_rows()) + "\n")

            outfile.write("\n")


if __name__ == "__main__":
    main("./level-3/in_level-3_2-large.txt")
