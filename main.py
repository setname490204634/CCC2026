
def print_board(r):
    lines = []

    for i in range(2 * r + 1):
        d = abs(r - i)

        if d == r:
            row = "*-" * r + "*"
        else:
            k = 2 * r - 1 - d
            row = "*-" + "-".join("O" for _ in range(k)) + "-*"

        lines.append("-" * d + row + "-" * d)

    return "\n".join(lines)


def main(input_filename, output_filename="output"):
    with open(input_filename, "r") as infile:
        n = int(infile.readline())

        with open(output_filename, "w") as outfile:
            for i in range(n):
                r = int(infile.readline())

                if i > 0:
                    outfile.write("\n")

                outfile.write(print_board(r) + "\n")


if __name__ == "__main__":
    main("./level-1/in_level-1_2-large.txt")
