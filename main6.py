from functools import lru_cache

from main3 import Direction, simulate_laser
from main4 import make_board
from main5 import pattern_cells, submit_pattern


@lru_cache(maxsize=None)
def build_intersections(radius):
    """Return emitter pairs and all cells where their beams intersect."""
    board, perimeter, _ = make_board(radius)
    paths = {
        direction: [
            set(simulate_laser(board, direction, start))
            for start in perimeter
        ]
        for direction in Direction
    }
    intersections = []

    for first in Direction:
        for second in Direction:
            if second <= first:
                continue

            for first_position, first_path in enumerate(paths[first]):
                for second_position, second_path in enumerate(paths[second]):
                    shared = frozenset(
                        cell
                        for cell in first_path & second_path
                        if board.get(*cell) == "O"
                    )
                    if shared:
                        intersections.append(
                            (
                                first.value - 1,
                                first_position,
                                second.value - 1,
                                second_position,
                                shared,
                            )
                        )

    return perimeter, intersections


def shortest_move(start, end, perimeter_length):
    forward = (end - start) % perimeter_length
    backward = (start - end) % perimeter_length
    if forward <= backward:
        return 1, forward
    return -1, backward


def generate_program(radius, pattern, required_count):
    """Generate instructions that build and submit the target repeatedly."""
    perimeter, intersections = build_intersections(radius)
    perimeter_length = len(perimeter)
    _, _, starts = make_board(radius)
    positions = [starts[direction] for direction in Direction]
    active_emitters = set()
    instructions = []
    cells = sorted(pattern)
    usable_intersections = [
        (first, first_position, second, second_position, hit_cells)
        for first, first_position, second, second_position, hit_cells in intersections
        if not hit_cells - pattern
    ]

    for _ in range(required_count):
        remaining = set(cells)
        while remaining:
            choices = []
            for first, first_position, second, second_position, hit_cells in usable_intersections:
                new_cells = hit_cells & remaining
                if not new_cells:
                    continue
                first_step, first_distance = shortest_move(
                    positions[first], first_position, perimeter_length
                )
                second_step, second_distance = shortest_move(
                    positions[second], second_position, perimeter_length
                )
                choices.append((
                    -len(new_cells),
                    max(first_distance, second_distance),
                    first_distance + second_distance,
                    first,
                    first_position,
                    second,
                    second_position,
                    hit_cells,
                    first_step,
                    second_step,
                ))
            if not choices:
                raise ValueError(
                    f"No safe emitter pair can create remaining cells: {sorted(remaining)}"
                )

            (
                _,
                _,
                _,
                first,
                first_position,
                second,
                second_position,
                hit_cells,
                first_step,
                second_step,
            ) = min(choices)

            distances = [0] * 6
            steps = [0] * 6
            distances[first] = (
                first_position - positions[first]
            ) % perimeter_length if first_step == 1 else (
                positions[first] - first_position
            ) % perimeter_length
            steps[first] = first_step
            distances[second] = (
                second_position - positions[second]
            ) % perimeter_length if second_step == 1 else (
                positions[second] - second_position
            ) % perimeter_length
            steps[second] = second_step

            move_ticks = max(distances)
            if active_emitters:
                line = ["-"] * 6
                for emitter in active_emitters:
                    line[emitter] = "T"
                instructions.append(line)
                active_emitters.clear()

            for tick in range(move_ticks):
                line = ["-"] * 6
                for emitter in (first, second):
                    if tick < distances[emitter]:
                        line[emitter] = "F" if steps[emitter] == 1 else "B"
                        positions[emitter] = (
                            positions[emitter] + steps[emitter]
                        ) % perimeter_length
                instructions.append(line)

            if positions[first] != first_position or positions[second] != second_position:
                raise RuntimeError("Emitter movement did not reach the selected positions")

            line = ["-"] * 6
            line[first] = "T"
            line[second] = "T"
            instructions.append(line)
            active_emitters = {first, second}
            remaining.difference_update(hit_cells)

    return instructions


def simulate_program(radius, pattern, instructions):
    """Return the number of times a generated program submits its pattern."""
    board, perimeter, starts = make_board(radius)
    positions = [starts[direction] for direction in Direction]
    active = [False] * 6
    submitted = 0

    for line in instructions:
        next_positions = positions.copy()
        next_active = active.copy()
        for emitter, instruction in enumerate(line):
            if instruction == "F":
                next_positions[emitter] = (
                    positions[emitter] + 1
                ) % len(perimeter)
            elif instruction == "B":
                next_positions[emitter] = (
                    positions[emitter] - 1
                ) % len(perimeter)
            elif instruction == "T":
                next_active[emitter] = not active[emitter]

        positions, active = next_positions, next_active
        hits = {}
        for emitter, is_active in enumerate(active):
            if not is_active:
                continue
            direction = Direction(emitter + 1)
            for cell in simulate_laser(
                board, direction, perimeter[positions[emitter]]
            ):
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
    pattern_count = int(lines[line_index][0])
    line_index += 1
    programs = []

    for _ in range(pattern_count):
        radius, rows, cols, required_count = map(
            int, lines[line_index]
        )
        line_index += 1
        pattern_rows = [
            lines[line_index + row][0]
            for row in range(rows)
        ]
        line_index += rows

        if any(len(row) != cols for row in pattern_rows):
            raise ValueError("Pattern row width does not match cols")

        pattern = pattern_cells(pattern_rows)
        program = generate_program(radius, pattern, required_count)
        submitted = simulate_program(radius, pattern, program)
        if submitted != required_count:
            raise RuntimeError(
                f"Generated program submitted the pattern {submitted} times; "
                f"expected {required_count}"
            )

        programs.append("\n".join(" ".join(line) for line in program))

    with open(output_filename, "w", newline="\n") as outfile:
        outfile.write("\n\n".join(programs) + "\n\n")


if __name__ == "__main__":
    main("./level-6/in_level-6_4-enormous.txt")
