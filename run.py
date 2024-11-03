from concurrent.futures import ThreadPoolExecutor, as_completed
from src.utils import (
    load_config, read_proxies, read_accounts, 
    countdown_timer, ensure_directories, info_log, error_log
)
from src.main import FantasyProcessor
from time import sleep
import random
from colorama import Fore, init
import signal
import sys

init(autoreset=True)

def signal_handler(signum, frame):
    print(f"\n{Fore.YELLOW}Exiting gracefully... Please wait.{Fore.RESET}")
    sys.exit(0)

def print_banner():
    banner = f"""
{Fore.CYAN}██╗   ██╗███╗   ██╗██╗     ██╗   ██╗ ██████╗██╗  ██╗
{Fore.CYAN}██║   ██║████╗  ██║██║     ██║   ██║██╔════╝██║ ██╔╝
{Fore.CYAN}██║   ██║██╔██╗ ██║██║     ██║   ██║██║     █████╔╝ 
{Fore.CYAN}██║   ██║██║╚██╗██║██║     ██║   ██║██║     ██╔═██╗ 
{Fore.CYAN}╚██████╔╝██║ ╚████║███████╗╚██████╔╝╚██████╗██║  ██╗
{Fore.CYAN} ╚═════╝ ╚═╝  ╚═══╝╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝
{Fore.LIGHTBLACK_EX} Created by: {Fore.CYAN}1LOCK{Fore.LIGHTBLACK_EX}
  Channel: {Fore.CYAN}https://t.me/unluck_1l0ck{Fore.RESET}
"""
    print(banner)

def main():
    signal.signal(signal.SIGINT, signal_handler)

    ensure_directories()
    config = load_config()
    
    print_banner()
    
    delay_start = int(input(f"{Fore.YELLOW}Enter start delay in seconds: {Fore.RESET}"))
    countdown_timer(delay_start)
    
    proxies = read_proxies(config['app']['proxy_file'])
    accounts = read_accounts(config['app']['keys_file'])
    total_accounts = len(accounts)
    
    processor = FantasyProcessor(config, proxies)
    info_log(f"Processing {total_accounts} accounts...")
    
    try:
        with ThreadPoolExecutor(max_workers=config['app']['threads']) as executor:
            futures = [
                executor.submit(
                    processor.process_account,
                    account_number,
                    private_key,
                    wallet_address,
                    total_accounts
                )
                for account_number, (private_key, wallet_address) in accounts
            ]
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    error_log(f'Thread execution failed: {str(e)}')

        info_log("Main processing completed.")
        
        failed_accounts = read_accounts(config['app']['failure_file'])
        if failed_accounts:
            info_log(f"Processing {len(failed_accounts)} failed accounts...")
            for account_number, (private_key, wallet_address) in failed_accounts:
                try:
                    processor.process_account(account_number, private_key, wallet_address, total_accounts)
                    sleep(random.uniform(2, 4))
                except Exception as e:
                    error_log(f'Failed account processing error: {str(e)}')

        info_log("All processing completed.")

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Interrupted by user. Cleaning up...{Fore.RESET}")
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_log(f"Unexpected error: {str(e)}")
        sys.exit(1)