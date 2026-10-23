from main3 import DIRECTIONS, Direction, HexBoard, simulate_laser
from main4 import make_board


INSTRUCTIONS = {"F", "B", "T", "-"}


def pattern_cells(pattern_rows):
    """Return matter coordinates in the pattern."""
    return {
        (row, col)
        for row, line in enumerate(pattern_rows)
        for col, cell in enumerate(line)
        if cell == "M"
    }


def submit_pattern(board, pattern):
    """Remove the pattern if it is present and has no adjacent extra matter."""
    if not pattern:
        return False

    if any(board.get(row, col) != "M" for row, col in pattern):
        return False

    for row, col in pattern:
        for dr, dc in DIRECTIONS.values():
            neighbor = (row + dr, col + dc)
            if neighbor not in pattern and board.get(*neighbor) == "M":
                return False

    for row, col in pattern:
        board.set(row, col, "O")
    return True


def process_program(radius, pattern, instructions):
    """Run a level-4 emitter program and count successful pattern pickups."""
    board, perimeter, starts = make_board(radius)
    positions = [starts[direction] for direction in Direction]
    active = [False] * 6
    submitted = 0

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

        if submit_pattern(board, pattern):
            submitted += 1

    return submitted


def main(input_filename, output_filename="output"):
    with open(input_filename, "r") as infile:
        lines = [line.split() for line in infile if line.strip()]

    line_index = 0
    program_count = int(lines[line_index][0])
    line_index += 1
    results = []

    for _ in range(program_count):
        radius, rows, cols = map(int, lines[line_index])
        line_index += 1
        pattern_rows = [
            lines[line_index + row][0]
            for row in range(rows)
        ]
        line_index += rows

        if any(len(row) != cols for row in pattern_rows):
            raise ValueError("Pattern row width does not match cols")

        line_count = int(lines[line_index][0])
        line_index += 1
        instructions = []

        for _ in range(line_count):
            instruction_line = lines[line_index]
            line_index += 1
            if len(instruction_line) != 6 or any(
                instruction not in INSTRUCTIONS
                for instruction in instruction_line
            ):
                raise ValueError(
                    "Each instruction line must contain six valid instructions"
                )
            instructions.append(instruction_line)

        results.append(
            str(process_program(radius, pattern_cells(pattern_rows), instructions))
        )

    with open(output_filename, "w", newline="\n") as outfile:
        outfile.write("\n".join(results) + "\n")


if __name__ == "__main__":
    main("./level-5/in_level-5_2-large.txt")
