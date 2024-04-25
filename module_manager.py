import os
import sys
import json
from git import Repo
from git.exc import InvalidGitRepositoryError
from termcolor import colored
import requests

def load_modules_from_url(url):
    response = requests.get(url)
    response.raise_for_status()  # Raises an HTTPError for bad responses
    return response.json()

def get_installed_modules(repo):
    installed = {}
    for submodule in repo.submodules:
        installed[submodule.name] = submodule.url
    return installed

def display_modules(all_modules, installed_modules):
    print("Available Modules:")
    for module in all_modules:
        if module['gitUrl'] in installed_modules.values():
            print(colored(f"{module['moduleName']} - Already Installed", 'green'))
        else:
            print(colored(f"{module['moduleName']} - Can be installed", 'white'))

def main():
    if len(sys.argv) < 2:
        print("Usage: python manage_submodules.py /path/to/your/repo")
        sys.exit(1)

    repo_path = sys.argv[1]
    modules_url = 'https://raw.githubusercontent.com/GKGameStudio/Unity-GKModuleManager/main/modules.json'  # Change this URL to where your modules.json is hosted

    try:
        repo = Repo(repo_path)
    except InvalidGitRepositoryError:
        print("Invalid Git repository.")
        sys.exit(1)

    try:
        modules = load_modules_from_url(modules_url)
    except requests.HTTPError as e:
        print(f"Failed to load modules from URL: {e}")
        sys.exit(1)

    installed_modules = get_installed_modules(repo)
    display_modules(modules, installed_modules)

if __name__ == '__main__':
    main()