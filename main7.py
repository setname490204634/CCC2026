import time
from heapq import nsmallest

import numpy as np

import main6


DEFAULT_FRONTIER_SIZE = 8
MAX_DEPTH_PER_PICKUP = 100


def instruction_successors(state, model):
    """Generate unique next states for all 4^6 instruction lines."""
    board_state, positions, active_mask = state
    actions = main6.INSTRUCTION_ARRAY
    move_forward = actions == 1
    move_backward = actions == 2
    toggle = actions == 3
    perimeter_length = len(model["perimeter"])

    next_positions = (
        np.asarray(positions, dtype=np.int16)
        + move_forward.astype(np.int16)
        - move_backward.astype(np.int16)
    ) % perimeter_length
    toggle_masks = (toggle.astype(np.uint8) * main6.EMITTER_BITS).sum(
        axis=1, dtype=np.uint8
    )
    next_active = np.bitwise_xor(active_mask, toggle_masks)

    beams = model["path_words"][
        main6.EMITTERS[None, :],
        next_positions,
    ]
    active = (
        next_active[:, None] >> main6.EMITTERS[None, :]
    ) & 1
    beams *= active[:, :, None].astype(np.uint64)

    pair_hits = np.zeros(
        (len(main6.INSTRUCTIONS), model["word_count"]),
        dtype=np.uint64,
    )
    for first, second in main6.PAIR_INDICES:
        np.bitwise_or(
            pair_hits,
            np.bitwise_and(beams[:, first], beams[:, second]),
            out=pair_hits,
        )

    triple_hits = np.zeros_like(pair_hits)
    for first, second, third in main6.TRIPLE_INDICES:
        pair = np.bitwise_and(beams[:, first], beams[:, second])
        np.bitwise_or(
            triple_hits,
            np.bitwise_and(pair, beams[:, third]),
            out=triple_hits,
        )

    old_words = main6.board_words(board_state, model["word_count"])
    new_boards = np.bitwise_and(
        np.bitwise_and(
            np.bitwise_or(
                old_words[None, :],
                np.bitwise_and(pair_hits, np.bitwise_not(triple_hits)),
            ),
            np.bitwise_not(triple_hits),
        ),
        model["valid_words"],
    )

    contains_pattern = np.all(
        np.bitwise_and(new_boards, model["target_words"])
        == model["target_words"],
        axis=1,
    )
    has_adjacent_matter = np.any(
        np.bitwise_and(new_boards, model["adjacent_words"]) != 0,
        axis=1,
    )
    submitted = contains_pattern & ~has_adjacent_matter
    new_boards[submitted] = np.bitwise_and(
        new_boards[submitted],
        np.bitwise_not(model["target_words"]),
    )

    visited = set()
    for index in range(len(main6.INSTRUCTIONS)):
        next_board = sum(
            int(word) << (64 * word_index)
            for word_index, word in enumerate(new_boards[index])
        )
        next_positions_tuple = tuple(
            int(position) for position in next_positions[index]
        )
        next_active_mask = int(next_active[index])
        is_submitted = bool(submitted[index])
        next_state = (
            next_board,
            next_positions_tuple,
            next_active_mask,
        )
        if is_submitted:
            yield main6.INSTRUCTIONS[index], next_state, True
            continue

        if next_state in visited:
            continue
        visited.add(next_state)
        yield main6.INSTRUCTIONS[index], next_state, False


def reconstruct_path(goal_state, parents, final_instruction):
    """Reconstruct instructions from search parent links."""
    path = [final_instruction]
    state = goal_state
    while parents[state] is not None:
        parent_state, instruction = parents[state]
        path.append(instruction)
        state = parent_state
    path.reverse()
    return path


def beam_search_pickup(
    start_state,
    model,
    frontier_size=DEFAULT_FRONTIER_SIZE,
    max_depth=MAX_DEPTH_PER_PICKUP,
    progress_callback=None,
):
    """Find a pickup path while retaining only the best states per depth."""
    if frontier_size < 1:
        raise ValueError("frontier_size must be at least 1")
    if max_depth < 1:
        raise ValueError("max_depth must be at least 1")

    frontier = [start_state]
    parents = {start_state: None}
    closed = set()
    expanded = 0

    for depth in range(1, max_depth + 1):
        candidates = {}
        for state in frontier:
            expanded += 1
            closed.add(state)
            for instruction, next_state, submitted in instruction_successors(
                state, model
            ):
                if submitted:
                    return (
                        reconstruct_path(state, parents, instruction),
                        next_state,
                        expanded,
                    )
                if next_state in closed or next_state in candidates:
                    continue

                heuristic = main6.compare_states(
                    next_state[0], model["target"]
                )
                candidates[next_state] = (
                    heuristic,
                    state,
                    instruction,
                )

        if not candidates:
            break

        selected = nsmallest(
            frontier_size,
            candidates.items(),
            key=lambda item: (item[1][0], item[0]),
        )
        frontier = []
        for state, (_, parent, instruction) in selected:
            parents[state] = (parent, instruction)
            frontier.append(state)
        if progress_callback is not None:
            progress_callback(depth, expanded, len(frontier))

    return None, None, expanded


def generate_program(
    radius,
    pattern_rows,
    required_count,
    progress_callback=None,
    frontier_size=DEFAULT_FRONTIER_SIZE,
):
    """Generate a repeated-pattern program using beam search and fallback."""
    model = main6.build_model(radius, pattern_rows)
    state = (
        0,
        tuple(model["starts"]),
        0,
    )
    program = []

    for pickup in range(1, required_count + 1):
        search_started = time.perf_counter()

        def report_search(depth, expanded, current_frontier_size):
            if progress_callback is not None:
                progress_callback(
                    "search",
                    {
                        "depth": depth,
                        "pickup": pickup,
                        "required_count": required_count,
                        "expanded": expanded,
                        "frontier": current_frontier_size,
                        "search_seconds": time.perf_counter() - search_started,
                    },
                )

        path, next_state, expanded = beam_search_pickup(
            state,
            model,
            frontier_size=frontier_size,
            progress_callback=report_search if progress_callback else None,
        )
        if path is None:
            fallback = main6.generate_program(
                radius,
                pattern_rows,
                required_count,
            )
            if progress_callback is not None:
                progress_callback(
                    "fallback",
                    {
                        "pickup": pickup,
                        "required_count": required_count,
                        "expanded": expanded,
                        "fallback_instructions": len(fallback),
                    },
                )
            return fallback
        program.extend(path)
        state = next_state
        if progress_callback is not None:
            progress_callback(
                "pickup",
                {
                    "pickup": pickup,
                    "required_count": required_count,
                    "expanded": expanded,
                    "path_instructions": len(path),
                    "total_instructions": len(program),
                    "search_seconds": time.perf_counter() - search_started,
                },
            )

    return program


def main(
    input_filename,
    output_filename="output",
    show_progress=True,
    frontier_size=DEFAULT_FRONTIER_SIZE,
):
    with open(input_filename, "r") as infile:
        lines = [line.split() for line in infile if line.strip()]

    line_index = 0
    pattern_count = int(lines[line_index][0])
    line_index += 1
    programs = []
    overall_started = time.perf_counter()

    for i in range(pattern_count):
        pattern_started = time.perf_counter()
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

        def report_progress(event, details):
            if not show_progress:
                return

            elapsed = time.perf_counter() - overall_started
            if event == "search":
                print(
                    f"\rPattern {i + 1}/{pattern_count} | "
                    f"pickup {details['pickup']}/{details['required_count']} | "
                    f"beam depth {details['depth']} "
                    f"(retained {details['frontier']}/{frontier_size}) | "
                    f"{details['expanded'] / max(details['search_seconds'], 1e-9):.1f} "
                    f"states/s | "
                    f"{elapsed:.1f}s elapsed",
                    end="",
                    flush=True,
                )
            elif event == "pickup":
                print(
                    f"\rPattern {i + 1}/{pattern_count} | "
                    f"pickup {details['pickup']}/{details['required_count']} "
                    f"complete | beam states expanded {details['expanded']} | "
                    f"{details['expanded'] / max(details['search_seconds'], 1e-9):.1f} "
                    f"states/s | "
                    f"{details['path_instructions']} instructions | "
                    f"{elapsed:.1f}s elapsed",
                    flush=True,
                )
            elif event == "fallback":
                print(
                    f"\rPattern {i + 1}/{pattern_count} | "
                    f"Beam search reached its depth limit; using greedy fallback "
                    f"({details['fallback_instructions']} instructions) | "
                    f"{details['expanded']} states | "
                    f"{elapsed:.1f}s elapsed",
                    flush=True,
                )

        program = generate_program(
            radius,
            pattern_rows,
            required_count,
            progress_callback=report_progress if show_progress else None,
            frontier_size=frontier_size,
        )
        programs.append(program)
        completed = i + 1
        elapsed = time.perf_counter() - overall_started
        average = elapsed / completed
        eta = average * (pattern_count - completed)
        if show_progress:
            print(
                f"Pattern {completed}/{pattern_count} done | "
                f"{len(program)} instructions | "
                f"{time.perf_counter() - pattern_started:.1f}s this pattern | "
                f"{elapsed:.1f}s elapsed | ETA {eta:.1f}s",
                flush=True,
            )

    with open(output_filename, "w", newline="\n") as outfile:
        for program in programs:
            outfile.write(
                "\n".join(" ".join(line) for line in program)
            )
            outfile.write("\n\n")


if __name__ == "__main__":
    main("./level-6/in_level-6_2-medium.txt", "output2")
    main("./level-6/in_level-6_3-large.txt", "output3")
    main("./level-6/in_level-6_4-enormous.txt", "output4")
