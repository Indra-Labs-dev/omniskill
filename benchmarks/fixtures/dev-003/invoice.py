import csv
import sys


def total(path):
    with open(path, newline="") as f:
        return sum(float(r["qty"]) * float(r["unit_price"]) for r in csv.DictReader(f))


if __name__ == "__main__":
    print(f"{total(sys.argv[1]):.2f}")
