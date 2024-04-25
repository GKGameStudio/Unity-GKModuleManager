import os
import sys
import json
import git
from git import Repo
from git.exc import InvalidGitRepositoryError, GitCommandError
import requests
from tqdm import tqdm
import time
import inquirer
import shutil
import threading

def load_modules_from_url(url):
    response = requests.get(url)
    response.raise_for_status()  # Raises an HTTPError for bad responses
    return response.json()

def get_installed_modules(repo):
    installed = {}
    for submodule in repo.submodules:
        installed[submodule.name] = submodule
    return installed

def display_modules(all_modules, installed_modules):
    choices = []
    for module in all_modules:
        submodule = installed_modules.get(module['moduleName'], None)
        print(submodule)
        if submodule and submodule.url == module['gitUrl']:
            status = "[Added]"  # Up-to-date
        else:
            status = ""
        choice_label = f"{module['moduleName']} {status}"
        choices.append((choice_label, module))
    return choices

def onerror(func, path, exc_info):
    import stat
    if not os.access(path, os.W_OK):
        # Change the file to be writable (if it's a permission issue)
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        # If it's a permission error, retry a few times before giving up
        if isinstance(exc_info[1], PermissionError):
            max_retries = 5
            for _ in range(max_retries):
                time.sleep(1)  # Wait a bit to see if the file gets unlocked
                try:
                    func(path)
                    break
                except PermissionError:
                    continue
            else:
                print(f"Failed to delete: {path}. File may be locked by another process.")
def remove_submodule(repo, module):
    # Path in the working directory
    submodule_dir = os.path.join(repo.working_tree_dir, module["recommendedPath"])
    if os.path.exists(submodule_dir):
        shutil.rmtree(submodule_dir, onerror=onerror)
    
    # Path in the .git/modules directory
    git_modules_dir = os.path.join(repo.git_dir, 'modules', module["moduleName"])
    if os.path.exists(git_modules_dir):
        shutil.rmtree(git_modules_dir, onerror=onerror)

    
    try:
        repo.git.execute(
                ['git', 'rm', '--cached', module['recommendedPath']],
        )
    except:
        pass

    print(f"Removed directories: {submodule_dir} and {git_modules_dir}")


def slow_progress(progress_bar, delay=1, stop_event=None):
    progress = 0
    while not stop_event.is_set():
        time.sleep(delay)
        progressIncrease = min((99-progress)/20, 5)  # Increase the progress by 20% each time
        progress += progressIncrease
        progress_bar.update(progressIncrease)

def handle_action(module, action, repo):
    if action == 'install':
            
        print("Starting installation...")
        with tqdm(total=100, desc="Installing", unit='%') as pbar:

            # Create and start the thread
            done_event = threading.Event()
            progress_thread = threading.Thread(target=slow_progress, args=(pbar, 1.0, done_event))
            progress_thread.start()
            try:
                remove_submodule(repo, module)
                repo.git.execute(
                        ['git', 'submodule', 'add', "--name", module["moduleName"], "-f", module['gitUrl'], module['recommendedPath']],
                )
            finally:
                done_event.set()
                progress_thread.join()
                pbar.update(pbar.total - pbar.n)
        print("Installation completed.")
    elif action == 'pull':
        print("Updating submodule...")
        submodule = next((sub for sub in repo.submodules if sub.url == module['gitUrl']), None)
        if submodule is not None:
            with tqdm(total=100, desc="Pulling", unit='%') as pbar:
                done_event = threading.Event()
                progress_thread = threading.Thread(target=slow_progress, args=(pbar, 1.0, done_event))
                progress_thread.start()
                try:
                    repo.git.execute(
                        ['git', 'submodule', 'update', '--remote', '--', submodule.path],
                    )
                finally:
                    done_event.set()
                    progress_thread.join()
                    pbar.update(100 - pbar.n)
            print("Update completed.")
        else:
            print(f"Error: Submodule {module['moduleName']} not found.")
    elif action == 'uninstall':
        # Locate the submodule using the provided `gitUrl`
        submodule = next((sub for sub in repo.submodules if sub.url == module['gitUrl']), None)
        if submodule is not None:
            with tqdm(total=100, desc="Uninstalling", unit='%') as pbar:
                done_event = threading.Event()
                progress_thread = threading.Thread(target=slow_progress, args=(pbar, 1.0, done_event))
                progress_thread.start()

                try:
                    # Deinitialize the submodule
                    repo.git.submodule('deinit', '-f', submodule.path)

                    # Remove the submodule entry from .gitmodules and config
                    repo.git.rm('--cached', submodule.path)
                    config_path = os.path.join(repo.git_dir, 'config')
                    repo.git.config('--file', config_path, '--remove-section', f'submodule.{submodule.name}', with_exceptions=False)
                    gitmodules_path = os.path.join(repo.working_tree_dir, '.gitmodules')
                    if os.path.exists(gitmodules_path):
                        repo.git.config('--file', gitmodules_path, '--remove-section', f'submodule.{submodule.name}')

                    
                    remove_submodule(repo, module)

                    #stage the changes to .gitmodules and the submodule path
                    repo.git.add('.gitmodules')

                finally:
                    # Ensure the progress bar completes and the thread is cleaned up properly
                    done_event.set()
                    progress_thread.join()
                    pbar.update(100 - pbar.n)
                    
                print("Uninstallation completed.")
        else:
            print(f"Error: Submodule {module['moduleName']} not found.")

def main():
    repo_path = "."
    modules_url = 'https://raw.githubusercontent.com/GKGameStudio/Unity-GKModuleManager/main/modules.json'

    try:
        repo = Repo(repo_path)
    except InvalidGitRepositoryError:
        print("Invalid Git repository. Please place this exe in the root of a git repository. (same level as .git folder)")
        #wait for user input before exiting
        input("Press Enter to exit...")
        sys.exit(1)

    try:
        modules = load_modules_from_url(modules_url)
    except requests.HTTPError as e:
        print(f"Failed to load modules from URL: {e}")
        sys.exit(1)
    while True:
        installed_modules = get_installed_modules(repo)
        choices = display_modules(modules, installed_modules)

        questions = [inquirer.List('module', message="Choose a module", choices=choices)]
        answers = inquirer.prompt(questions)
        if not answers:
            print("No module selected. Exiting.")
            break
        selected_module = answers['module']  # Adjust based on how you structure the choice tuple
        installed = selected_module['gitUrl'] in [m.url for m in installed_modules.values()]
        actions = [('Pull updates', 'pull'), ('Uninstall', 'uninstall')] if installed else [('Install', 'install')]
        actions.append(('Cancel', 'cancel'))
        action_question = [inquirer.List('action', message="Choose an action", choices=actions)]
        action_answer = inquirer.prompt(action_question)
        if not action_answer:
            print("No action selected. Exiting.")
            continue
        if action_answer['action'] == 'cancel':
            print("Action cancelled.")
            continue

        handle_action(selected_module, action_answer['action'], repo)
    input("Press Enter to exit...")
if __name__ == '__main__':
    main()