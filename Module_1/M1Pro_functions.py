# William Beckham
# 08-24-2026
# CSC221 M1Pro-- weight average review
# Overview:
# Helper functions used by M1Pro_Review_Beckham_William.py to collect a
# list of weights from the user and calculate their trimmed average.


def getValues(n):
    """Prompt the user for n weight values and return them as a list."""
    values = []
    for i in range(n):
        value = float(input(f"Enter weight #{i + 1}: "))
        values.append(value)
    return values


def calcAverage(alist):
    """Return the average of alist, excluding the first three values."""
    trimmed = alist[3:]
    average = sum(trimmed) / len(trimmed)
    return average
