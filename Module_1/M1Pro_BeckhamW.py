# William Beckham
# 08-24-2026
# CSC221 M1Pro-- weight average review
# Overview:
# Prompts the user for a list of weights, then calculates and displays
# the average, excluding the first three (atypical) values. Runs on a
# sentinel loop (-1 to quit) instead of while True/break.

from M1Pro_functions import getValues, calcAverage

MINIMUM_VALUES = 8
SENTINEL = -1

print("Weight Average Calculator")
print(f"Enter the number of weights to record (minimum {MINIMUM_VALUES}),")
print(f"or enter {SENTINEL} at any time to quit.\n")

# Priming read so the loop condition has something to check on the first pass
userInput = int(input("Number of values: "))

while userInput != SENTINEL:
    if userInput < MINIMUM_VALUES:
        print(f"Please enter at least {MINIMUM_VALUES} values.\n")
    else:
        weights = getValues(userInput)
        average = calcAverage(weights)
        print(f"\nAverage weight (excluding the first three readings): {average:.2f}\n")

    userInput = int(input("Number of values (or -1 to quit): "))

print("\nProgram ended. Goodbye!")
