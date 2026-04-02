config_data = {}

def save_config(data: dict):
    global config_data
    config_data = data

def get_config():
    return config_data