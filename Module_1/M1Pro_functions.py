# William Beckham
# 08-24-2026
# CSC221 M1Pro-- weight average review
# Overview:
# Helper functions used by M1Pro_Review_Beckham_William.py to collect a
# list of weights from the user and calculate their trimmed average.

import logging

logger = logging.getLogger(__name__)


def getInt(prompt):
    """Prompt until the user enters a valid whole number, then return it."""
    while True:
        userInput = input(prompt)
        try:
            value = int(userInput)
            logger.info(f"getInt('{prompt.strip()}') received valid input: {value}")
            return value
        except ValueError:
            logger.error(f"getInt('{prompt.strip()}') received invalid input: '{userInput}'")
            print(f'"{userInput}" is not a valid whole number. Please try again.\n')


def getSampleCount(prompt, sentinel):
    """Prompt for the number of samples, confirming before treating sentinel as exit."""
    while True:
        n = getInt(prompt)
        if n == sentinel:
            confirm = input(f"You entered {sentinel}. Do you want to exit? (y/n): ").strip().lower()
            if confirm == "y":
                logger.info(f"User confirmed exit after entering sentinel value {sentinel}.")
                return n
            else:
                logger.info(f"User entered sentinel value {sentinel} but chose not to exit.")
                print("Okay, let's continue.\n")
        else:
            return n


def getFloat(prompt, sentinel=None):
    """Prompt until the user enters a valid, non-negative number, then return (value, exit_flag).

    If sentinel is given and the parsed value equals it, confirm with the
    user whether they meant to exit or really intended that value as data.
    exit_flag is True only if the user confirms they meant to exit.
    Any other value that is negative triggers a warning and a re-prompt,
    since weights are expected to be zero or positive. Zero is allowed.
    """
    while True:
        userInput = input(prompt)
        try:
            value = float(userInput)
            if sentinel is not None and value == sentinel:
                confirm = input(
                    f"You entered {sentinel}. Did you mean to exit the program? (y/n): "
                ).strip().lower()
                if confirm == "y":
                    logger.info(f"User confirmed exit while entering a weight ({sentinel}).")
                    return value, True
                else:
                    logger.info(f"User entered {sentinel} as a real weight value, not exiting.")
                    logger.warning(f"getFloat('{prompt.strip()}') negative weight entered: {value}")
                    print(f'"{value}" is negative. Weights should be zero or greater. Please try again.\n')
            elif value < 0:
                logger.warning(f"getFloat('{prompt.strip()}') negative weight entered: {value}")
                print(f'"{value}" is negative. Weights should be zero or greater. Please try again.\n')
            else:
                logger.info(f"getFloat('{prompt.strip()}') received valid input: {value}")
                return value, False
        except ValueError:
            logger.error(f"getFloat('{prompt.strip()}') received invalid input: '{userInput}'")
            print(f'"{userInput}" is not a valid number. Please try again.\n')


def getValues(n, sentinel=None):
    """Prompt the user for n weight values and return (list, exit_flag).

    If sentinel is given and the user confirms they meant to exit while
    entering a weight, exit_flag is True and the partial list is returned.
    """
    values = []
    for i in range(n):
        value, exitFlag = getFloat(f"Enter weight #{i + 1} (number): ", sentinel)
        if exitFlag:
            logger.info(f"getValues({n}) exited early after weight #{i + 1} confirmed as exit.")
            return values, True
        values.append(value)
    logger.info(f"getValues({n}) collected weights: {values}")
    return values, False


def calcAverage(alist):
    """Return the average of alist, excluding the first three values."""
    trimmed = alist[3:]
    average = sum(trimmed) / len(trimmed)
    logger.info(f"calcAverage() dropped first three of {alist} -> trimmed {trimmed} -> average {average:.2f}")
    return average
