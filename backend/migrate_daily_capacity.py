import sqlite3
from pathlib import Path


# Project root is one level above the backend directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "aplo.db"


def migrate():
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        cursor = connection.cursor()

        # Check whether the available_hours column already exists.
        cursor.execute("PRAGMA table_info(daily_states)")
        columns = [row[1] for row in cursor.fetchall()]

        if "available_hours" in columns:
            print(
                "available_hours column already exists. "
                "No schema change needed."
            )
            return

        # Add the new column without deleting existing data.
        cursor.execute(
            "ALTER TABLE daily_states "
            "ADD COLUMN available_hours REAL"
        )

        connection.commit()

        print("Added available_hours column to daily_states.")

        # Give existing records the default capacity.
        cursor.execute(
            """
            UPDATE daily_states
            SET available_hours = 8.0
            WHERE available_hours IS NULL
            """
        )

        updated_rows = cursor.rowcount

        connection.commit()

        print(
            f"Initialized available_hours = 8.0 "
            f"for {updated_rows} existing DailyState record(s)."
        )

    finally:
        connection.close()


if __name__ == "__main__":
    migrate()