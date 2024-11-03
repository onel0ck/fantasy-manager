import json
import os
from datetime import datetime
from colorama import Fore, init
from itertools import cycle
from time import sleep

init(autoreset=True)

def get_current_time():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def write_to_log_file(log_message: str):
    with open("logs/app.log", "a") as log_file:
        log_file.write(log_message + "\n")

def error_log(message: str):
    current_time = get_current_time()
    log_message = f">> ERROR | {current_time} | {message}"
    print(Fore.RED + log_message)
    write_to_log_file(log_message)

def success_log(message: str):
    current_time = get_current_time()
    log_message = f">> SUCCESS | {current_time} | {message}"
    print(Fore.GREEN + log_message)
    write_to_log_file(log_message)

def info_log(message: str):
    current_time = get_current_time()
    log_message = f">> INFO | {current_time} | {message}"
    print(Fore.LIGHTBLACK_EX + log_message)
    write_to_log_file(log_message)

def ensure_directories():
    directories = ['data', 'logs']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def load_config():
    config_path = 'data/config.json'
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Config file not found at {config_path}")

def read_proxies(proxy_file):
    with open(proxy_file, 'r') as f:
        proxies = [line.strip() for line in f if line.strip()]
        return cycle(proxies)

def read_accounts(file_path):
    with open(file_path, 'r') as f:
        return [(i, line.strip().split(':')) 
                for i, line in enumerate(f.readlines(), 1) 
                if line.strip()]

def countdown_timer(seconds):
    for i in range(seconds, 0, -1):
        print(f"\r{Fore.YELLOW}Starting in: {i} seconds", end="")
        sleep(1)
    print(f"\r{Fore.GREEN}Starting now!" + " " * 20)