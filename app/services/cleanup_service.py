import shutil
from pathlib import Path


class CleanupService:
    def __init__(self, project_root="."):
        self.project_root = Path(project_root)

    def remove_pycache(self):
        for path in self.project_root.rglob("__pycache__"):
            shutil.rmtree(path, ignore_errors=True)

    def remove_reports(self):
        reports = self.project_root / "Reports"
        if reports.exists():
            shutil.rmtree(reports, ignore_errors=True)
        reports.mkdir(parents=True, exist_ok=True)

    def remove_database(self):
        database = self.project_root / "Data" / "database"
        if database.exists():
            shutil.rmtree(database, ignore_errors=True)
        database.mkdir(parents=True, exist_ok=True)

    def remove_generated_call_outputs(self):
        folders = [
            self.project_root / "Data" / "CALLS" / "ANALYZED",
            self.project_root / "Data" / "CALLS" / "TRANSCRIPTS",
            self.project_root / "Data" / "markdown",
            self.project_root / "Data" / "processed",
        ]

        for folder in folders:
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)
            folder.mkdir(parents=True, exist_ok=True)

    def run_light_cleanup(self):
        self.remove_pycache()

    def run_full_cleanup(self):
        self.remove_pycache()
        self.remove_reports()
        self.remove_database()
        self.remove_generated_call_outputs()
        