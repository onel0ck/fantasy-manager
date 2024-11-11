import concurrent.futures
import os
import sys
from time import sleep
from colorama import init, Fore
from src.utils import (
    load_config, 
    read_proxies, 
    read_accounts, 
    ensure_directories, 
    countdown_timer,
    read_user_agents,
    error_log
)
from src.main import FantasyProcessor

def print_banner():
    banner = f"""
{Fore.CYAN}██╗   ██╗███╗   ██╗██╗     ██╗   ██╗ ██████╗██╗  ██╗
{Fore.CYAN}██║   ██║████╗  ██║██║     ██║   ██║██╔════╝██║ ██╔╝
{Fore.CYAN}██║   ██║██╔██╗ ██║██║     ██║   ██║██║     █████╔╝ 
{Fore.CYAN}██║   ██║██║╚██╗██║██║     ██║   ██║██║     ██╔═██╗ 
{Fore.CYAN}╚██████╔╝██║ ╚████║███████╗╚██████╔╝╚██████╗██║  ██╗
{Fore.CYAN} ╚═════╝ ╚═╝  ╚═══╝╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝

{Fore.GREEN}Created by: {Fore.CYAN}@one_lock
{Fore.GREEN}Channel: {Fore.CYAN}https://t.me/unluck_1l0ck
{Fore.RESET}"""
    print(banner)

def main():
    init()
    ensure_directories()
    print_banner()
    
    try:
        config = load_config()
        proxies_cycle = read_proxies(config['app']['proxy_file'])
        user_agents_cycle = read_user_agents()
        accounts = read_accounts(config['app']['keys_file'])
        
        total_accounts = len(accounts)
        if total_accounts == 0:
            error_log("No accounts found in the keys file")
            sys.exit(1)

        print(f"\n{Fore.YELLOW}Total accounts to process: {total_accounts}")
        print(f"{Fore.YELLOW}Number of threads: {config['app']['threads']}")
        countdown_timer(5)

        processor = FantasyProcessor(
            config=config,
            proxies_cycle=proxies_cycle,
            user_agents_cycle=user_agents_cycle
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=config['app']['threads']) as executor:
            futures = []
            for account_number, (private_key, wallet_address) in accounts:
                future = executor.submit(
                    processor.process_account,
                    account_number,
                    private_key,
                    wallet_address,
                    total_accounts
                )
                futures.append(future)
                sleep(0.1)

            concurrent.futures.wait(futures)

    except KeyboardInterrupt:
        print(f"\n{Fore.RED}Script interrupted by user")
        sys.exit(0)
    except Exception as e:
        error_log(f"Critical error in main execution: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
