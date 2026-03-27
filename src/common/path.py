from pathlib import Path

def get_project_root() -> Path:
    """Returns the root directory of the project."""
    return Path(__file__).resolve()

CONFIG_DIR = get_project_root().parents[3] / "config"

if __name__ == "__main__":
    config_path = get_project_root().parents[3] / "config" / "data_sources.yaml"
    print(f"Config path: {config_path}")
    print(f"Does config file exist? {config_path.exists()}")