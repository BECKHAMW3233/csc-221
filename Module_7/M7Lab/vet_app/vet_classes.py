"""Classes for connecting to and querying the vet_serv.db SQLite database."""

import sqlite3
from pathlib import Path

import pandas as pd


class DatabaseManager:
    """Base class that opens a SQLite connection and runs queries as DataFrames."""

    def __init__(self, db_path):
        """Open a connection to the existing SQLite database at db_path.

        Raises FileNotFoundError if the file doesn't exist. (Without this
        check, sqlite3.connect() silently creates a new empty database and
        the program crashes later on the first query.)
        """
        if not Path(db_path).is_file():
            raise FileNotFoundError(f"Database file not found: {db_path}")
        self.__connection = sqlite3.connect(db_path)

    def execute_query(self, query, params=None):
        """Run a SQL query and return the result as a pandas DataFrame.

        Raises sqlite3.DatabaseError if the query fails (e.g. a missing table).
        """
        try:
            return pd.read_sql_query(query, self.__connection, params=params)
        except pd.errors.DatabaseError as error:
            raise sqlite3.DatabaseError(f"Database query failed: {error}") from error

    def close(self):
        """Close the database connection."""
        self.__connection.close()


class VetServiceManager(DatabaseManager):
    """Provides the OWNER/PETS queries needed by the vet services menu program."""

    def get_all_owners(self):
        """Return a DataFrame containing every row of the OWNER table."""
        return self.execute_query("SELECT * FROM OWNER")

    def get_all_pets(self):
        """Return a DataFrame containing every row of the PETS table."""
        return self.execute_query("SELECT * FROM PETS")

    def get_owner_pet_info(self, owner_id):
        """Return owner contact info plus basic pet info for one OwnerId."""
        query = """
            SELECT O.OwnerId, O.OwnerFirstName, O.OwnerLastName,
                   O.OwnerPhone, O.OwnerEmail,
                   P.PetId, P.PetName, P.PetBreed, P.PetDOB
            FROM OWNER O
            LEFT JOIN PETS P ON O.OwnerId = P.OwnerId
            WHERE O.OwnerId = ?
        """
        return self.execute_query(query, params=(owner_id,))

    def get_owner_charges(self, owner_id):
        """Return owner info plus pet service/charge info for one OwnerId."""
        query = """
            SELECT O.OwnerId, O.OwnerFirstName, O.OwnerLastName, O.OwnerEmail,
                   P.PetId, P.PetName, P.PetBreed, P.Service, P.Date, P.Charge
            FROM OWNER O
            LEFT JOIN PETS P ON O.OwnerId = P.OwnerId
            WHERE O.OwnerId = ?
        """
        return self.execute_query(query, params=(owner_id,))
