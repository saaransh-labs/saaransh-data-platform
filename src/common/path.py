from pathlib import Path

def get_project_root() -> Path:
    """Returns the root directory of the project."""
    return Path(__file__).resolve().parents[2]

PROJECT_ROOT = get_project_root()

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PARSED_DATA_DIR = DATA_DIR / "parsed"

CONFIG_DIR = PROJECT_ROOT / "config"

if __name__ == "__main__":
    config_path = get_project_root().parents[3] / "config" / "data_sources.yaml"
    print(f"Config path: {config_path}")
    print(f"Does config file exist? {config_path.exists()}")