from main3 import DIRECTIONS, Direction, HexBoard, simulate_laser


INSTRUCTIONS = {"F", "B", "T", "-"}


def make_board(radius):
    """Create an empty hex board with its border emitters' rail positions."""
    rows = []
    for row in range(2 * radius + 1):
        distance = abs(radius - row)
        cell_count = 2 * radius + 1 - distance
        cells = ["O"] * cell_count
        if distance == radius:
            cells = ["*"] * cell_count
        else:
            cells[0] = "*"
            cells[-1] = "*"

        rows.append(
            "-" * distance + "-".join(cells) + "-" * distance
        )

    board = HexBoard(rows)
    perimeter = []
    row, col = 0, radius
    for direction in (
        Direction.E,
        Direction.SE,
        Direction.SW,
        Direction.W,
        Direction.NE,
        Direction.NW,
    ):
        dr, dc = DIRECTIONS[direction]
        for _ in range(radius):
            perimeter.append((row, col))
            row += dr
            col += dc

    starts = {
        Direction.E: 5 * radius,
        Direction.SE: 0,
        Direction.SW: radius,
        Direction.W: 2 * radius,
        Direction.NE: 3 * radius,
        Direction.NW: 4 * radius,
    }
    return board, perimeter, starts


def process_program(radius, instructions):
    """Run a program from a fresh board and six inactive emitters."""
    board, perimeter, starts = make_board(radius)
    positions = [starts[direction] for direction in Direction]
    active = [False] * 6

    for line in instructions:
        next_positions = positions.copy()
        next_active = active.copy()

        for i, instruction in enumerate(line):
            if instruction == "F":
                next_positions[i] = (positions[i] + 1) % len(perimeter)
            elif instruction == "B":
                next_positions[i] = (positions[i] - 1) % len(perimeter)
            elif instruction == "T":
                next_active[i] = not active[i]

        positions = next_positions
        active = next_active

        hits = {}
        for i, is_active in enumerate(active):
            if not is_active:
                continue

            direction = Direction(i + 1)
            start = perimeter[positions[i]]
            for cell in simulate_laser(board, direction, start):
                hits[cell] = hits.get(cell, 0) + 1

        for (row, col), count in hits.items():
            if count == 2:
                board.set(row, col, "M")
            elif count >= 3:
                board.set(row, col, "O")

    return board


def main(input_filename, output_filename="output"):
    with open(input_filename, "r") as infile:
        lines = [line.split() for line in infile if line.strip()]

    line_index = 0
    program_count = int(lines[line_index][0])
    line_index += 1

    results = []
    for _ in range(program_count):
        radius = int(lines[line_index][0])
        line_count = int(lines[line_index + 1][0])
        line_index += 2

        instructions = []
        for _ in range(line_count):
            instruction_line = lines[line_index]
            line_index += 1
            if len(instruction_line) != 6 or any(
                instruction not in INSTRUCTIONS
                for instruction in instruction_line
            ):
                raise ValueError("Each instruction line must contain six valid instructions")
            instructions.append(instruction_line)

        results.append("\n".join(process_program(radius, instructions).to_rows()))

    with open(output_filename, "w", newline="\n") as outfile:
        outfile.write("\n\n".join(results) + "\n\n")


if __name__ == "__main__":
    main("./level-4/in_level-4_2-large.txt")
