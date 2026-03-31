import yaml

def load_yaml(file_path):
    """Load a YAML file and return its contents as a dictionary."""
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)