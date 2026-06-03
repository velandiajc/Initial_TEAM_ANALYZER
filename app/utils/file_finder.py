from pathlib import Path


class FileFinder:

    @staticmethod
    def latest_csv(folder):

        folder = Path(folder)

        files = list(folder.glob("*.csv"))

        if not files:
            raise FileNotFoundError(
                f"No CSV files found in {folder}"
            )

        return max(
            files,
            key=lambda x: x.stat().st_mtime
        )

    @staticmethod
    def latest_excel(folder):

        folder = Path(folder)

        files = (
            list(folder.glob("*.xlsx"))
            + list(folder.glob("*.xls"))
        )

        if not files:
            raise FileNotFoundError(
                f"No Excel files found in {folder}"
            )

        return max(
            files,
            key=lambda x: x.stat().st_mtime
        )
    