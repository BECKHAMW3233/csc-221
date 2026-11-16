"""Flask web version of the M5Pro Vet Services program.

Each page matches one option from the original console menu and reuses the
VetServiceManager class and the helper functions in m5pro_functions.py.
"""

import logging
import sqlite3
from contextlib import closing

from flask import Flask, render_template, request

from app_paths import resource_path

from .m5pro_functions import (
    DB_PATH,
    breed_charge_stats,
    configure_logging,
    parse_owner_id,
    sanitize_filename_component,
    save_dataframe_to_csv,
)
from .vet_classes import VetServiceManager

APP_TITLE = "Vet Services (M5Pro)"

logger = logging.getLogger(__name__)


def dataframe_to_html(df):
    """Return a DataFrame as an HTML table (values are HTML-escaped by pandas)."""
    return df.to_html(index=False, border=0, classes="data", na_rep="—",
                      float_format=lambda value: f"{value:.2f}")


def open_database():
    """Open the vet database. Raises FileNotFoundError if it's missing."""
    return closing(VetServiceManager(str(DB_PATH)))


def create_app():
    """Build and return the Vet Services Flask app.

    Raises FileNotFoundError if vet_serv.db is missing, so the launcher can
    report the problem instead of starting a broken app.
    """
    if not logging.getLogger(__name__).handlers:
        configure_logging()
    if not DB_PATH.is_file():
        raise FileNotFoundError(f"Database file not found: {DB_PATH}")

    app = Flask(__name__, template_folder=str(resource_path("templates")))

    def show(**result):
        """Render the main page, with an optional result section."""
        return render_template("vet/index.html", app_title=APP_TITLE,
                               form=request.args, **result)

    @app.route("/")
    def index():
        return show()

    @app.route("/owners")
    def owners():
        with open_database() as db:
            df = db.get_all_owners()
        logger.info("Web: displayed OWNER table (%d rows)", len(df))
        return show(heading="OWNER Table", table=dataframe_to_html(df),
                    saved=save_dataframe_to_csv(df, "owner.csv"))

    @app.route("/pets")
    def pets():
        with open_database() as db:
            df = db.get_all_pets()
        logger.info("Web: displayed PETS table (%d rows)", len(df))
        return show(heading="PETS Table", table=dataframe_to_html(df),
                    saved=save_dataframe_to_csv(df, "pets.csv"))

    @app.route("/owner")
    def owner_lookup():
        try:
            owner_id = parse_owner_id(request.args.get("owner_id", ""))
        except ValueError as error:
            return show(heading="Owner and Pet Lookup", error=str(error))
        with open_database() as db:
            df = db.get_owner_pet_info(owner_id)
        if df.empty:
            return show(heading="Owner and Pet Lookup",
                        error=f"No owner found with OwnerId {owner_id}.")
        last_name = sanitize_filename_component(str(df.iloc[0]["OwnerLastName"]).lower())
        logger.info("Web: owner/pet lookup for OwnerId %s: %d row(s)", owner_id, len(df))
        return show(heading=f"Owner and Pet info for OwnerId {owner_id}",
                    table=dataframe_to_html(df),
                    saved=save_dataframe_to_csv(df, f"{last_name}_{owner_id}.csv"))

    @app.route("/charges")
    def owner_charges():
        try:
            owner_id = parse_owner_id(request.args.get("owner_id", ""))
        except ValueError as error:
            return show(heading="Total Charge by Owner", error=str(error))
        with open_database() as db:
            df = db.get_owner_charges(owner_id)
        if df.empty:
            return show(heading="Total Charge by Owner",
                        error=f"No owner found with OwnerId {owner_id}.")
        total = float(df["Charge"].sum())
        logger.info("Web: charge lookup for OwnerId %s: total=$%.2f", owner_id, total)
        return show(heading=f"Charge info for OwnerId {owner_id}",
                    table=dataframe_to_html(df),
                    summary=[f"Total charge for OwnerId {owner_id}: ${total:.2f}"])

    @app.route("/breed")
    def pets_by_breed():
        breed = request.args.get("breed", "")
        with open_database() as db:
            pets_df = db.get_all_pets()
        try:
            matches, total, average = breed_charge_stats(pets_df, breed)
        except ValueError as error:
            return show(heading="Pets by Breed", error=str(error))
        breed = breed.strip()
        if matches.empty:
            return show(heading="Pets by Breed", error=f"No pets found for breed '{breed}'.")
        logger.info("Web: breed search '%s': %d match(es)", breed, len(matches))
        return show(heading=f"Pets matching breed '{breed}'",
                    table=dataframe_to_html(matches),
                    summary=[f"Total charges for '{breed}': ${total:.2f}",
                             f"Average charge for '{breed}': ${average:.2f}"])

    @app.errorhandler(FileNotFoundError)
    @app.errorhandler(sqlite3.Error)
    def database_error(error):
        logger.error("Web: database error: %s", error)
        return show(heading="Database problem", error=str(error)), 500

    return app
