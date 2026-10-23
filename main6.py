from itertools import combinations, product

import numpy as np

from main3 import DIRECTIONS, Direction, simulate_laser
from main4 import make_board
from main5 import pattern_cells


INSTRUCTION_SYMBOLS = ("-", "F", "B", "T")
INSTRUCTIONS = tuple(product(INSTRUCTION_SYMBOLS, repeat=6))
INSTRUCTION_ARRAY = np.asarray(
    [[INSTRUCTION_SYMBOLS.index(action) for action in line] for line in INSTRUCTIONS],
    dtype=np.uint8,
)
POPCOUNT = np.asarray([value.bit_count() for value in range(256)], dtype=np.uint8)
EMITTER_BITS = np.asarray([1 << i for i in range(6)], dtype=np.uint8)
EMITTERS = np.arange(6)
PAIR_INDICES = tuple(combinations(range(6), 2))
TRIPLE_INDICES = tuple(combinations(range(6), 3))


def compare_states(first, second, ignore_mask=0):
    """Return differing board bits, excluding bits set in ignore_mask."""
    return ((first ^ second) & ~ignore_mask).bit_count()


def board_words(bitboard, word_count):
    """Split a Python bitboard into little-endian uint64 words."""
    return np.asarray(
        [(bitboard >> (64 * index)) & ((1 << 64) - 1)
         for index in range(word_count)],
        dtype=np.uint64,
    )


def build_model(radius, pattern_rows):
    """Build packed board cells and precomputed beam paths."""
    board, perimeter, starts = make_board(radius)
    cells = [
        (row, col)
        for row in range(board.height)
        for col in range(board.width)
        if board.get(row, col) in "OM"
    ]
    cell_bits = {cell: 1 << index for index, cell in enumerate(cells)}
    valid_mask = (1 << len(cells)) - 1
    target = sum(
        cell_bits[cell]
        for cell in pattern_cells(pattern_rows)
        if cell in cell_bits
    )
    adjacent = 0
    for row, col in pattern_cells(pattern_rows):
        for dr, dc in (
            DIRECTIONS[direction]
            for direction in Direction
        ):
            adjacent_cell = (row + dr, col + dc)
            adjacent |= cell_bits.get(adjacent_cell, 0)
    adjacent &= ~target

    paths = [[0] * len(perimeter) for _ in range(6)]
    for emitter in range(6):
        direction = Direction(emitter + 1)
        for position, start in enumerate(perimeter):
            path_mask = 0
            for cell in simulate_laser(board, direction, start):
                path_mask |= cell_bits.get(cell, 0)
            paths[emitter][position] = path_mask

    word_count = (len(cells) + 63) // 64
    path_words = np.asarray(
        [
            [
                [
                    (path_mask >> (64 * word)) & ((1 << 64) - 1)
                    for word in range(word_count)
                ]
                for path_mask in emitter_paths
            ]
            for emitter_paths in paths
        ],
        dtype=np.uint64,
    )

    return {
        "perimeter": perimeter,
        "paths": paths,
        "path_words": path_words,
        "word_count": word_count,
        "valid_mask": valid_mask,
        "valid_words": board_words(valid_mask, word_count),
        "target": target,
        "target_words": board_words(target, word_count),
        "adjacent": adjacent,
        "adjacent_words": board_words(adjacent, word_count),
        "starts": [starts[direction] for direction in Direction],
    }


def perform_instructions(board_state, positions, active_mask, instructions, model):
    """Apply one six-emitter instruction line to a packed board state."""
    next_positions = list(positions)
    next_active = active_mask

    for emitter, instruction in enumerate(instructions):
        if instruction == "F":
            next_positions[emitter] = (
                positions[emitter] + 1
            ) % len(model["perimeter"])
        elif instruction == "B":
            next_positions[emitter] = (
                positions[emitter] - 1
            ) % len(model["perimeter"])
        elif instruction == "T":
            next_active ^= 1 << emitter

    beam_masks = [
        model["paths"][emitter][next_positions[emitter]]
        if next_active & (1 << emitter)
        else 0
        for emitter in range(6)
    ]
    board_state = apply_beams(board_state, beam_masks, model["valid_mask"])

    submitted = (
        board_state & model["target"] == model["target"]
        and board_state & model["adjacent"] == 0
    )
    if submitted:
        board_state &= ~model["target"]

    return board_state, next_positions, next_active, submitted


def apply_beams(board_state, beam_masks, valid_mask):
    """Apply simultaneous beam effects to the packed board."""
    pair_hits = 0
    for first, second in PAIR_INDICES:
        pair_hits |= beam_masks[first] & beam_masks[second]

    triple_hits = 0
    for first, second, third in TRIPLE_INDICES:
        triple_hits |= (
            beam_masks[first] & beam_masks[second] & beam_masks[third]
        )

    return (
        (board_state | (pair_hits & ~triple_hits))
        & ~triple_hits
        & valid_mask
    )


def evaluate_instructions(board_state, positions, active_mask, model):
    """Evaluate all 4^6 instruction lines together using NumPy."""
    actions = INSTRUCTION_ARRAY
    move_forward = actions == 1
    move_backward = actions == 2
    toggle = actions == 3
    perimeter_length = len(model["perimeter"])

    next_positions = (
        np.asarray(positions, dtype=np.int16)
        + move_forward.astype(np.int16)
        - move_backward.astype(np.int16)
    ) % perimeter_length
    toggle_masks = (toggle.astype(np.uint8) * EMITTER_BITS).sum(
        axis=1, dtype=np.uint8
    )
    next_active = np.bitwise_xor(active_mask, toggle_masks)

    beams = model["path_words"][EMITTERS[None, :], next_positions]
    active = (
        next_active[:, None] >> EMITTERS[None, :]
    ) & 1
    beams *= active[:, :, None].astype(np.uint64)

    pair_hits = np.zeros(
        (len(INSTRUCTIONS), model["word_count"]), dtype=np.uint64
    )
    for first, second in PAIR_INDICES:
        np.bitwise_or(
            pair_hits,
            np.bitwise_and(beams[:, first], beams[:, second]),
            out=pair_hits,
        )

    triple_hits = np.zeros_like(pair_hits)
    for first, second, third in TRIPLE_INDICES:
        pair = np.bitwise_and(beams[:, first], beams[:, second])
        np.bitwise_or(
            triple_hits,
            np.bitwise_and(pair, beams[:, third]),
            out=triple_hits,
        )

    exactly_two = np.bitwise_and(pair_hits, np.bitwise_not(triple_hits))
    old_words = board_words(board_state, model["word_count"])
    new_boards = np.bitwise_and(
        np.bitwise_and(
            np.bitwise_or(old_words[None, :], exactly_two),
            np.bitwise_not(triple_hits),
        ),
        model["valid_words"],
    )

    has_pattern = np.all(
        np.bitwise_and(new_boards, model["target_words"])
        == model["target_words"],
        axis=1,
    )
    touches_extra = np.any(
        np.bitwise_and(new_boards, model["adjacent_words"]) != 0,
        axis=1,
    )
    submitted = has_pattern & ~touches_extra
    new_boards[submitted] = np.bitwise_and(
        new_boards[submitted],
        np.bitwise_not(model["target_words"]),
    )

    compare_words = board_words(
        model["valid_mask"], model["word_count"]
    )
    differences = np.bitwise_and(
        np.bitwise_xor(new_boards, model["target_words"]),
        compare_words,
    )
    byte_differences = differences.view(np.uint8).reshape(
        len(INSTRUCTIONS), -1
    )
    distances = POPCOUNT[byte_differences].sum(axis=1, dtype=np.uint16)

    submitted_indices = np.flatnonzero(submitted)
    if submitted_indices.size:
        best = submitted_indices[np.argmin(distances[submitted_indices])]
    else:
        best = int(np.argmin(distances))

    best_distance = int(distances[best])
    if not submitted[best] and best_distance >= compare_states(
        board_state, model["target"]
    ):
        return None

    instruction = tuple(
        INSTRUCTION_SYMBOLS[action] for action in actions[best]
    )
    return (
        instruction,
        tuple(int(position) for position in next_positions[best]),
        int(next_active[best]),
        int(best_distance),
        bool(submitted[best]),
        sum(
            int(word) << (64 * index)
            for index, word in enumerate(new_boards[best])
        ),
    )


def find_fallback_pair(model, board_state, positions, pattern):
    """Choose a safe two-beam crossing that adds missing pattern matter."""
    missing = pattern & ~board_state
    choices = []
    for first in range(6):
        for second in range(first + 1, 6):
            for first_position, first_path in enumerate(model["paths"][first]):
                for second_position, second_path in enumerate(model["paths"][second]):
                    hit_mask = first_path & second_path
                    if not hit_mask or hit_mask & ~pattern:
                        continue
                    new_matter = hit_mask & missing
                    if not new_matter:
                        continue

                    first_forward = (
                        first_position - positions[first]
                    ) % len(model["perimeter"])
                    first_backward = (
                        positions[first] - first_position
                    ) % len(model["perimeter"])
                    second_forward = (
                        second_position - positions[second]
                    ) % len(model["perimeter"])
                    second_backward = (
                        positions[second] - second_position
                    ) % len(model["perimeter"])
                    first_step, first_distance = (
                        (1, first_forward)
                        if first_forward <= first_backward
                        else (-1, first_backward)
                    )
                    second_step, second_distance = (
                        (1, second_forward)
                        if second_forward <= second_backward
                        else (-1, second_backward)
                    )
                    choices.append(
                        (
                            new_matter.bit_count(),
                            max(first_distance, second_distance),
                            first_distance + second_distance,
                            first,
                            first_position,
                            first_step,
                            second,
                            second_position,
                            second_step,
                            hit_mask,
                        )
                    )

    if not choices:
        raise RuntimeError("No safe two-emitter crossing can build the pattern")
    return min(choices)


def find_cleanup_configuration(model, board_state, positions, pattern):
    """Find a beam configuration that clears extra matter without stalling."""
    extras = board_state & ~pattern
    current_distance = compare_states(board_state, pattern)
    best = None

    while extras:
        cell_bit = extras & -extras
        extras ^= cell_bit
        choices_by_emitter = [
            [
                position
                for position, path in enumerate(emitter_paths)
                if path & cell_bit
            ]
            for emitter_paths in model["paths"]
        ]

        for active_count in range(3, 7):
            for emitters in combinations(range(6), active_count):
                position_options = [choices_by_emitter[i] for i in emitters]
                if any(not options for options in position_options):
                    continue

                for selected_positions in product(*position_options):
                    beam_masks = [0] * 6
                    movement_cost = 0
                    for emitter, destination in zip(emitters, selected_positions):
                        beam_masks[emitter] = model["paths"][emitter][destination]
                        forward = (
                            destination - positions[emitter]
                        ) % len(model["perimeter"])
                        backward = (
                            positions[emitter] - destination
                        ) % len(model["perimeter"])
                        movement_cost += min(forward, backward)

                    result = apply_beams(
                        board_state, beam_masks, model["valid_mask"]
                    )
                    submitted = (
                        result & pattern == pattern
                        and result & model["adjacent"] == 0
                    )
                    if submitted:
                        result &= ~pattern
                    distance = compare_states(result, pattern)
                    if not submitted and distance >= current_distance:
                        continue

                    score = (
                        0 if submitted else 1,
                        distance,
                        movement_cost,
                        active_count,
                        emitters,
                        selected_positions,
                    )
                    if best is None or score < best[0]:
                        best = (
                            score,
                            emitters,
                            selected_positions,
                            submitted,
                        )

    if best is None:
        raise RuntimeError("No emitter configuration can clear the extra matter")
    return best[1:]


def cleanup_fallback(
    board_state, positions, active_mask, submitted_count, required_count,
    model, pattern,
):
    """Reposition three or more beams to remove blocking extra matter."""
    emitters, destinations, expected_submission = find_cleanup_configuration(
        model, board_state, positions, pattern
    )
    instructions = []
    if active_mask:
        line = tuple(
            "T" if active_mask & (1 << emitter) else "-"
            for emitter in range(6)
        )
        instructions.append(line)
        board_state, positions, active_mask, submitted = perform_instructions(
            board_state, positions, active_mask, line, model
        )
        if submitted:
            submitted_count += 1

    distances = [0] * 6
    steps = [0] * 6
    for emitter, destination in zip(emitters, destinations):
        forward = (destination - positions[emitter]) % len(model["perimeter"])
        backward = (positions[emitter] - destination) % len(model["perimeter"])
        if forward <= backward:
            distances[emitter], steps[emitter] = forward, 1
        else:
            distances[emitter], steps[emitter] = backward, -1

    for tick in range(max(distances)):
        line = ["-"] * 6
        for emitter in emitters:
            if tick < distances[emitter]:
                line[emitter] = "F" if steps[emitter] == 1 else "B"
        line = tuple(line)
        instructions.append(line)
        board_state, positions, active_mask, submitted = perform_instructions(
            board_state, positions, active_mask, line, model
        )
        if submitted:
            submitted_count += 1

    line = tuple(
        "T" if emitter in emitters else "-"
        for emitter in range(6)
    )
    instructions.append(line)
    board_state, positions, active_mask, submitted = perform_instructions(
        board_state, positions, active_mask, line, model
    )
    if submitted:
        submitted_count += 1
    if expected_submission and submitted_count < required_count and not submitted:
        raise RuntimeError("Cleanup beams did not submit the completed pattern")

    return instructions, board_state, positions, active_mask, submitted_count


def fallback_instructions(
    board_state, positions, active_mask, submitted_count, required_count,
    model, pattern,
):
    """Reposition two inactive emitters and use their beams to build matter."""
    if pattern & ~board_state == 0:
        return cleanup_fallback(
            board_state,
            positions,
            active_mask,
            submitted_count,
            required_count,
            model,
            pattern,
        )

    instruction_lines = []
    if active_mask:
        instruction_lines.append(
            tuple(
                "T" if active_mask & (1 << emitter) else "-"
                for emitter in range(6)
            )
        )
        active_mask = 0

    (
        _,
        _,
        _,
        first,
        first_position,
        first_step,
        second,
        second_position,
        second_step,
        _,
    ) = find_fallback_pair(model, board_state, positions, pattern)

    distances = [0] * 6
    steps = [0] * 6
    for emitter, destination, step in (
        (first, first_position, first_step),
        (second, second_position, second_step),
    ):
        if step == 1:
            distances[emitter] = (
                destination - positions[emitter]
            ) % len(model["perimeter"])
        else:
            distances[emitter] = (
                positions[emitter] - destination
            ) % len(model["perimeter"])
        steps[emitter] = step

    for tick in range(max(distances)):
        line = ["-"] * 6
        for emitter in (first, second):
            if tick < distances[emitter]:
                line[emitter] = "F" if steps[emitter] == 1 else "B"
        instruction = tuple(line)
        instruction_lines.append(instruction)
        board_state, positions, active_mask, submitted = perform_instructions(
            board_state, positions, active_mask, instruction, model
        )
        if submitted:
            submitted_count += 1
            if submitted_count == required_count:
                return (
                    instruction_lines,
                    board_state,
                    positions,
                    active_mask,
                    submitted_count,
                )

    instruction = tuple(
        "T" if emitter in (first, second) else "-"
        for emitter in range(6)
    )
    instruction_lines.append(instruction)
    board_state, positions, active_mask, submitted = perform_instructions(
        board_state, positions, active_mask, instruction, model
    )
    if submitted:
        submitted_count += 1

    return (
        instruction_lines,
        board_state,
        positions,
        active_mask,
        submitted_count,
    )


def generate_program(radius, pattern_rows, required_count):
    """Greedily select the instruction that reduces masked board distance most."""
    model = build_model(radius, pattern_rows)
    pattern = model["target"]
    board_state = 0
    positions = model["starts"].copy()
    active_mask = 0
    submitted_count = 0
    program = []

    while submitted_count < required_count:
        best = evaluate_instructions(
            board_state, positions, active_mask, model
        )
        if best is None:
            (
                fallback,
                board_state,
                positions,
                active_mask,
                submitted_count,
            ) = fallback_instructions(
                board_state,
                positions,
                active_mask,
                submitted_count,
                required_count,
                model,
                pattern,
            )
            program.extend(fallback)
            continue

        (
            instruction,
            positions,
            active_mask,
            _,
            submitted,
            board_state,
        ) = best
        program.append(instruction)
        if submitted:
            submitted_count += 1

    return program


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

        programs.append(
            generate_program(radius, pattern_rows, required_count)
        )

    with open(output_filename, "w", newline="\n") as outfile:
        for program in programs:
            outfile.write(
                "\n".join(" ".join(instruction) for instruction in program)
            )
            outfile.write("\n\n")


if __name__ == "__main__":
    main("./level-6/in_level-6_2-medium.txt", "output2")
    main("./level-6/in_level-6_3-large.txt", "output3")
    main("./level-6/in_level-6_4-enormous.txt", "output4")
