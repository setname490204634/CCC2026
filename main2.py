
def simulate_laser(board, direction):
    board = [list(row) for row in board]

    # Find the emitter
    emitter_row = emitter_col = None

    for i, row in enumerate(board):
        for j, char in enumerate(row):
            if char in "123456":
                emitter_row, emitter_col = i, j
                break
        if emitter_row is not None:
            break

    if emitter_row is None:
        return ["".join(row) for row in board]

    r, c = emitter_row, emitter_col

    # Direction: row change, column change
    directions = {
        1: (0, 1),    # Right
        2: (1, 1),    # Down-right
        3: (1, -1),   # Down-left
        4: (0, -1),   # Left
        5: (-1, -1),   # Up-right
        6: (-1, 1)   # Up-left
    }

    dr, dc = directions[direction]

    # Follow the beam until it leaves the board
    while True:
        r += dr
        c += dc

        if not (0 <= r < len(board) and
                0 <= c < len(board[r])):
            break

        if board[r][c] == "O":
            board[r][c] = "M"

    return ["".join(row) for row in board]


def main(input_filename, output_filename="output"):
    with open(input_filename, "r") as infile:
        lines = iter(infile)

        def next_nonempty_line():
            for line in lines:
                if line.strip():
                    return line.strip()
            raise ValueError("Unexpected end of input")

        n = int(next_nonempty_line())

        with open(output_filename, "w") as outfile:
            for i in range(n):
                radius, rows, cols = map(
                    int, next_nonempty_line().split()
                )

                board = [next(lines).rstrip("\n\r") for _ in range(rows)]

                # Determine the emitter direction
                direction = next(
                    int(ch)
                    for row in board
                    for ch in row
                    if ch in "123456"
                )

                result = simulate_laser(board, direction)

                if i > 0:
                    outfile.write("\n")

                outfile.write("\n".join(result) + "\n")


if __name__ == "__main__":
    main("./level-2/in_level-2_2-large.txt")
