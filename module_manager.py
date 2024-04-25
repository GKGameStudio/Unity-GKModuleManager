import json
import os
import sys
from git import Repo
from git.exc import InvalidGitRepositoryError
from termcolor import colored

def load_modules(filename):
    with open(filename, 'r') as file:
        modules = json.load(file)
    return modules

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
    try:
        repo = Repo(repo_path)
    except InvalidGitRepositoryError:
        print("Invalid Git repository.")
        sys.exit(1)

    modules = load_modules('modules.json')
    installed_modules = get_installed_modules(repo)
    display_modules(modules, installed_modules)

if __name__ == '__main__':
    main()