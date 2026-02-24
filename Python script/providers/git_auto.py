import os
import requests
import stat
from git import Repo
from providers.YamlHelper import load_github_repo_folder, load_github_config_file_name, load_enable_github_autodetect_config


def get_autodetected_config_files_from_github(github_pat, resource_folder, config_file_name='run-config.yaml'):
    """
        Experimental feature.
        Controlled by the EnableGitHubAutoDetectConfig flag in run-config.yaml
        System will fetch all repositories from GitHub which github_pat has access to. 
        After that, system will try to find files named as configured in 'ConfigFileName' property
        and include them in the processing.
        System will also take a note of all repositories that the PAT has access to but don't have that config file available.
    """
    config_files = []
    if not load_enable_github_autodetect_config(resource_folder, config_file_name):
        print("GitHub config autodetection disabled!")
        return config_files
    
    print("Started autodetection of config files in GitHub repos")
    if not github_pat:
        print("GitHub Personal Access token not provided via CLI, unable to use Automatic Github configuration detection")
        return []
    
    gh_config_file_name = load_github_config_file_name(resource_folder, config_file_name)
    local_gh_repo_folder = load_github_repo_folder(resource_folder, config_file_name)
    
    try:
        github_repos = _get_github_repos_for_pat(github_pat)
        for github_repo in github_repos:
            print("")
            print("------")
            github_repo_name = github_repo.get('full_name')
            print(f"Repository: {github_repo_name}")
            git_url = github_repo.get('html_url')
            print(f"Git URL: {git_url}")
        
            try:
                local_folder = git_url.rsplit("/")[4]
                local_folder_path = os.path.join(local_gh_repo_folder, local_folder)
                repo, remote = _setup_repo_and_remote(local_folder_path, git_url)
                
                config_file = _find_config_file(repo, remote, gh_config_file_name, github_repo_name, local_folder_path)
                
                if not config_file:
                    print(f"{gh_config_file_name} not found in {github_repo_name}")
                    continue

                config_files.append(config_file)
            except Exception as e:
                print(f'Error occurred while searching config file from {github_repo_name}', e)
            print("------")
        return config_files
    except Exception as e:
        print("Unexpected error occurred while running git autodetection of config files", e)

    return []


def _get_github_repos_for_pat(github_pat):
    headers = {
        "Authorization": f"Bearer {github_pat}",
        "Content-Type": "application/json"
    }
    try:
        result = []
        github_repos_resp = requests.get("https://api.github.com/user/repos", headers=headers)
        github_repos_resp.raise_for_status()
        result.extend(github_repos_resp.json())
        while github_repos_resp.links and github_repos_resp.links.get('next', None):
            github_repos_resp = requests.get(github_repos_resp.links.get('next').get('url'), headers=headers)
            github_repos_resp.raise_for_status()
            result.extend(github_repos_resp.json())
        return result
    except Exception as e:
        print("Github API: Get repositories failed")
        print(e)

    return []


def _setup_repo_and_remote(local_folder_path, git_url):
    if not os.path.exists(local_folder_path):
        os.mkdir(local_folder_path)
        os.chmod(local_folder_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        repo = Repo.init(local_folder_path)
        remote = repo.create_remote('origin', git_url)
    else:
        repo = Repo.init(local_folder_path)
        remote = repo.remote()
    
    return (repo, remote)


def _find_config_file(repo, remote, gh_config_file_name, github_repo_name, local_folder_path):
    try:
        remote.fetch()
        main_branch = _find_main_branch(repo)
        if not main_branch:
            print(f'Unable to detect main branch in repo {github_repo_name}, using origin/main as fallback')
            main_branch = "main"
        repo_tree = repo.git.execute(["git", "ls-tree", "-r", "--name-only", f"origin/{main_branch}"])
        for git_file in repo_tree.split('\n'):
            if git_file.endswith(gh_config_file_name):
                print(f"Found {gh_config_file_name} in {github_repo_name}")
                repo.git.execute(["git", "checkout", f"origin/{main_branch}", "--", git_file])
                return os.path.join(local_folder_path, git_file)
    except Exception as e:
        print(f"Error occurred while searching for config file for {github_repo_name}", e)
        
    return None


def _find_main_branch(repo):
    origin_info_raw = repo.git.execute(["git", "remote", "show", "origin"])

    for origin_info in origin_info_raw.split("\n"):
        if "HEAD branch: (unknown)" in origin_info:
            print("Main branch not defined for repo, got HEAD branch: (unknown)")
            return None
        if ("HEAD branch:" in origin_info):
            return origin_info[15:]
    
    return None

