import os
import sys
import requests
from git import Repo
from git.exc import InvalidGitRepositoryError
import inquirer
from tqdm import tqdm
import threading
import shutil
import time
from urllib.parse import urlparse

MODULES_URL = 'https://raw.githubusercontent.com/GKGameStudio/Unity-GKModuleManager/main/modules.json'

def load_modules_from_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Failed to load modules: {e}")
        sys.exit(1)

def get_installed_modules(repo):
    return {submodule.name: submodule for submodule in repo.submodules}

def display_modules(modules, installed_modules):
    choices = []
    for module in modules:
        installed = installed_modules.get(module['moduleName'])
        status = "✔️" if installed and installed.url == module['gitUrl'] else ""
        choices.append((f"{module['moduleName']} {status}", module))
    choices.append(('Reload modules', 'reload'))
    return choices

def remove_directory_tree(path):
    if os.path.exists(path):
        shutil.rmtree(path, onerror=lambda func, path, exc_info: os.chmod(path, 0o777))

def remove_submodule(repo, module):
    submodule_dir = os.path.join(repo.working_tree_dir, module["recommendedPath"])
    remove_directory_tree(submodule_dir)
    
    git_modules_dir = os.path.join(repo.git_dir, 'modules', module["moduleName"])
    remove_directory_tree(git_modules_dir)

    repo.git.rm('--cached', module['recommendedPath'], with_exceptions=False)

def slow_progress_bar(progress_bar, delay=1, stop_event=None):
    while not stop_event.is_set():
        time.sleep(delay)
        progress_bar.update(5)  # Arbitrary increment

def submodule_action(repo, module, action):
    if action == 'install':
        remove_submodule(repo, module)
        repo.git.submodule('add', "--name", module["moduleName"], module['gitUrl'], module['recommendedPath'])
    elif action == 'pull':
        submodule = repo.submodules[module['moduleName']]
        repo.git.submodule('update', '--remote', '--', submodule.path)
    elif action == 'uninstall':
        submodule = repo.submodules[module['moduleName']]
        repo.git.submodule('deinit', '-f', submodule.path)
        repo.git.rm('--cached', submodule.path)
        remove_submodule(repo, module)

def handle_action(repo, module, action):
    with tqdm(total=100, desc=f"{action.capitalize()}ing", unit='%') as pbar:
        done_event = threading.Event()
        progress_thread = threading.Thread(target=slow_progress_bar, args=(pbar, 1, done_event))
        progress_thread.start()
        submodule_action(repo, module, action)
        done_event.set()
        progress_thread.join()
        pbar.update(100 - pbar.n)
    print(f"{action.capitalize()} complete.")

def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py <path_to_repo>")
        sys.exit(1)

    repo_path = sys.argv[1]
    try:
        repo = Repo(repo_path)
    except InvalidGitRepositoryError:
        print("Invalid Git repository.")
        return

    modules = load_modules_from_url(MODULES_URL)
    installed_modules = get_installed_modules(repo)
    choices = display_modules(modules, installed_modules)
    
    while True:
        question = [inquirer.List('module', message="Choose a module", choices=choices)]
        answers = inquirer.prompt(question)
        if not answers or answers['module'] == 'reload':
            continue

        selected_module = answers['module']
        action_choices = [('Pull updates', 'pull'), ('Uninstall', 'uninstall')] if selected_module['gitUrl'] in [m.url for m in installed_modules.values()] else [('Install', 'install')]
        action_question = [inquirer.List('action', message="Choose an action", choices=action_choices)]
        action_answer = inquirer.prompt(action_question)
        
        if action_answer:
            handle_action(repo, selected_module, action_answer['action'])
        else:
            break

if __name__ == '__main__':
    main()