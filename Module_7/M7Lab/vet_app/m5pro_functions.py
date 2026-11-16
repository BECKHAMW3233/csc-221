"""Menu, input validation, and option handlers for the M5Pro vet services program."""

import logging
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from app_paths import resource_path, writable_path

from .vet_classes import VetServiceManager

DB_PATH = resource_path("vet_app", "data", "vet_serv.db")
OUTPUT_DIR = writable_path("output")
LOG_DIR = writable_path("logs")
SQLITE_INT_MAX = 2**63 - 1

logger = logging.getLogger(__name__)


def configure_logging():
    """Set up a timestamped log file for this session under LOG_DIR.

    The handler goes on the "vet_app" package logger (not Python's root
    logger), so the other programs in the launcher keep their own log files.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"session_{datetime.now():%Y%m%d_%H%M%S_%f}.log"
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    package_logger = logging.getLogger(__package__)
    package_logger.addHandler(handler)
    package_logger.setLevel(logging.INFO)
    package_logger.propagate = False
    return log_path


def display_menu_and_get_choice():
    """Display the main menu and return the user's raw menu choice."""
    print("\nVeterinary Services Menu")
    print("1) Display OWNER content and create DataFrame")
    print("2) Display PETS content and create DataFrame")
    print("3) Retrieve Owner and Pet data for specific Owner")
    print("4) Calculate Total Charge by Owner")
    print("5) Retrieve Pet information by PetBreed")
    print("6) Exit")
    return input("Enter your choice (1-6): ").strip()


def parse_owner_id(entry):
    """Convert text to a valid OwnerId int, raising ValueError if it isn't one."""
    try:
        owner_id = int(str(entry).strip())
    except ValueError:
        raise ValueError("Invalid input. OwnerId must be a whole number.") from None
    if abs(owner_id) > SQLITE_INT_MAX:
        raise ValueError("Invalid input. OwnerId is too large.")
    return owner_id


def get_valid_owner_id():
    """Prompt for OwnerId until a valid whole number is entered."""
    valid_entry = False
    owner_id = None
    while not valid_entry:
        entry = input("Enter OwnerId: ").strip()
        try:
            owner_id = parse_owner_id(entry)
            valid_entry = True
        except ValueError as error:
            print(error)
    return owner_id


def breed_charge_stats(pets_df, breed):
    """Return (matching rows, total charge, average charge) for a breed search.

    Matching is partial and case-insensitive. Raises ValueError for a blank breed.
    """
    breed = str(breed).strip()
    if not breed:
        raise ValueError("Breed cannot be blank.")
    matches = pets_df[pets_df["PetBreed"].str.contains(breed, case=False, regex=False, na=False)]
    if matches.empty:
        return matches, 0.0, 0.0
    return matches, float(matches["Charge"].sum()), float(matches["Charge"].mean())


def get_valid_breed():
    """Prompt for a PetBreed until a non-blank value is entered."""
    valid_entry = False
    breed = ""
    while not valid_entry:
        breed = input("Enter PetBreed to search: ").strip()
        if breed:
            valid_entry = True
        else:
            print("Breed cannot be blank.")
    return breed


def print_dataframe(df):
    """Print a DataFrame wrapped to fit the current terminal width."""
    terminal_width = shutil.get_terminal_size().columns
    print(df.to_string(index=False, line_width=terminal_width))


def generate_startup_csvs(db):
    """Read OWNER and PETS from the database and save owner.csv/pets.csv on startup."""
    print("\nReading OWNER and PETS tables and generating starting CSV files...")
    save_dataframe_to_csv(db.get_all_owners(), "owner.csv")
    save_dataframe_to_csv(db.get_all_pets(), "pets.csv")


def sanitize_filename_component(value):
    """Strip characters that aren't safe in a filename (e.g. path separators)."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", value)


def save_dataframe_to_csv(df, filename):
    """Write a DataFrame to a csv in OUTPUT_DIR; return the path, or None on error."""
    output_path = OUTPUT_DIR / filename
    try:
        if output_path.resolve().parent != OUTPUT_DIR.resolve():
            raise OSError(f"refusing to write outside {OUTPUT_DIR}: {filename!r}")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"Saved to {output_path}")
        logger.info("Saved %d row(s) to %s", len(df), output_path)
        return output_path
    except OSError as error:
        print(f"Could not save {output_path}: {error}")
        logger.error("Could not save %s: %s", output_path, error)
        return None


def handle_display_owners(db):
    """Handle menu option 1: display OWNER content and save it to owner.csv."""
    df = db.get_all_owners()
    print("\nOWNER Table:")
    print_dataframe(df)
    logger.info("Displayed OWNER table (%d rows)", len(df))
    save_dataframe_to_csv(df, "owner.csv")


def handle_display_pets(db):
    """Handle menu option 2: display PETS content and save it to pets.csv."""
    df = db.get_all_pets()
    print("\nPETS Table:")
    print_dataframe(df)
    logger.info("Displayed PETS table (%d rows)", len(df))
    save_dataframe_to_csv(df, "pets.csv")


def handle_owner_pet_lookup(db):
    """Handle menu option 3: look up an owner's pets and save the results."""
    owner_id = get_valid_owner_id()
    df = db.get_owner_pet_info(owner_id)
    if df.empty:
        print(f"\nNo owner found with OwnerId {owner_id}.")
        logger.info("Owner/pet lookup for OwnerId %s: no owner found", owner_id)
        return
    print(f"\nOwner and Pet info for OwnerId {owner_id}:")
    print_dataframe(df)
    logger.info("Owner/pet lookup for OwnerId %s: %d row(s)", owner_id, len(df))
    last_name = sanitize_filename_component(str(df.iloc[0]["OwnerLastName"]).lower())
    filename = f"{last_name}_{owner_id}.csv"
    save_dataframe_to_csv(df, filename)


def handle_owner_charges(db):
    """Handle menu option 4: display an owner's charges and the total charge."""
    owner_id = get_valid_owner_id()
    df = db.get_owner_charges(owner_id)
    if df.empty:
        print(f"\nNo owner found with OwnerId {owner_id}.")
        logger.info("Charge lookup for OwnerId %s: no owner found", owner_id)
        return
    print(f"\nCharge info for OwnerId {owner_id}:")
    print_dataframe(df)
    total_charge = df["Charge"].sum()
    print(f"\nTotal charge for OwnerId {owner_id}: ${total_charge:.2f}")
    logger.info("Charge lookup for OwnerId %s: total=$%.2f", owner_id, total_charge)


def handle_pets_by_breed(db):
    """Handle menu option 5: filter pets by breed (partial, case-insensitive) and report charge stats."""
    breed = get_valid_breed()
    matches, total_charge, average_charge = breed_charge_stats(db.get_all_pets(), breed)
    if matches.empty:
        print(f"\nNo pets found for breed '{breed}'.")
        logger.info("Breed search '%s': no matches", breed)
        return
    print(f"\nPets matching breed '{breed}':")
    print_dataframe(matches)
    print(f"\nTotal charges for '{breed}': ${total_charge:.2f}")
    print(f"Average charge for '{breed}': ${average_charge:.2f}")
    logger.info("Breed search '%s': %d match(es), total=$%.2f, average=$%.2f",
                breed, len(matches), total_charge, average_charge)


def run_menu(db):
    """Run the sentinel-controlled menu loop until the user chooses to exit."""
    handlers = {
        "1": handle_display_owners,
        "2": handle_display_pets,
        "3": handle_owner_pet_lookup,
        "4": handle_owner_charges,
        "5": handle_pets_by_breed,
    }
    choice = display_menu_and_get_choice()
    while choice != "6":
        if choice in handlers:
            logger.info("Menu choice selected: %s", choice)
            handlers[choice](db)
        else:
            print("Invalid option. Please enter a number from 1 to 6.")
            logger.warning("Invalid menu choice entered: %r", choice)
        choice = display_menu_and_get_choice()
    print("\nExiting the program. Goodbye!")
    logger.info("Menu choice selected: 6 (exit)")


def main():
    """Connect to vet_serv.db and run the menu-driven vet services program."""
    sys.stdout.reconfigure(errors="replace")
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    log_path = configure_logging()
    print(f"Logging this session to {log_path}")
    logger.info("Session started")
    try:
        db = VetServiceManager(str(DB_PATH))
    except (FileNotFoundError, sqlite3.Error) as error:
        print(f"Could not open {DB_PATH}: {error}")
        logger.error("Could not open %s: %s", DB_PATH, error)
        return
    try:
        generate_startup_csvs(db)
        run_menu(db)
    except sqlite3.Error as error:
        print(f"Database error: {error}")
        logger.error("Database error: %s", error)
    finally:
        db.close()
        logger.info("Session ended")
