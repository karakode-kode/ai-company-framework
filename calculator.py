import sys


def add(a, b):
    return a + b


def subtract(a, b):
    return a - b


def multiply(a, b):
    return a * b


def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


OPERATIONS = {
    "add": add,
    "subtract": subtract,
    "multiply": multiply,
    "divide": divide,
}


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <operation> <num1> <num2>")
        print(f"Operations: {', '.join(OPERATIONS)}")
        sys.exit(1)

    operation = sys.argv[1]
    if operation not in OPERATIONS:
        print(f"Unknown operation: {operation}")
        print(f"Operations: {', '.join(OPERATIONS)}")
        sys.exit(1)

    try:
        a = float(sys.argv[2])
        b = float(sys.argv[3])
    except ValueError:
        print("Error: arguments must be numbers")
        sys.exit(1)

    try:
        result = OPERATIONS[operation](a, b)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(result)


if __name__ == "__main__":
    main()
