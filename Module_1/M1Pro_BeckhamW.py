# William Beckham
# 08-24-2026
# CSC221 M1Pro-- weight average review
# Overview:
# Prompts the user for a list of weights, then calculates and displays
# the average, excluding the first three (atypical) values. Runs on a
# sentinel loop (-1 to quit) instead of while True/break.
#
# All key inputs, calculations, and errors are written to
# M1Pro_BeckhamW.log for review/debugging.

import logging
from M1Pro_functions import getValues, calcAverage, getSampleCount

logging.basicConfig(
    filename="M1Pro_BeckhamW.log",
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MINIMUM_VALUES = 8
SENTINEL = -1

logger.info("Program started.")

print("Weight Average Calculator")
print(f"Enter the number of weights to record (minimum {MINIMUM_VALUES}),")
print(f"or enter {SENTINEL} at any time to quit.")
print("Number of values must be a whole number; weights must be zero or greater (whole numbers or decimals).\n")

# Priming read so the loop condition has something to check on the first pass
userInput = getSampleCount("Number of values (whole number): ", SENTINEL)

while userInput != SENTINEL:
    if userInput < MINIMUM_VALUES:
        logger.warning(f"User entered {userInput}, below MINIMUM_VALUES ({MINIMUM_VALUES}).")
        print(f"Please enter at least {MINIMUM_VALUES} values.\n")
        userInput = getSampleCount("Number of values (whole number, or -1 to quit): ", SENTINEL)
    else:
        weights, exitFlag = getValues(userInput, SENTINEL)
        if exitFlag:
            logger.info("User exited mid weight-entry.")
            userInput = SENTINEL
        else:
            average = calcAverage(weights)
            print(f"\nAverage weight (excluding the first three readings): {average:.2f}\n")
            userInput = getSampleCount("Number of values (whole number, or -1 to quit): ", SENTINEL)

logger.info("User entered sentinel value. Program ending normally.")
print("\nProgram ended. Goodbye!")
