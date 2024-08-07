import re
import requests
import os
import json
import sys
import argparse
from urllib.parse import urlparse
from termcolor import colored

class CTFdBackup:
    def __init__(self, url, username, password):
        self.nonce = None
        self.url = self.format_url(url)
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.ctf_name = self.get_ctf_name()

    def format_url(self, url):
        if not url.startswith('http://') and not url.startswith('https://'):
            return 'https://' + url
        return url

    def get_ctf_name(self):
        parsed_url = urlparse(self.url)
        return parsed_url.netloc

    def login(self):
        login_page = self.session.get(f'{self.url}/login')
        matched = re.search(r'csrfNonce\'\s*:\s*"([a-f0-9A-F]+)"', login_page.text)
        if matched:
            self.nonce = matched.group(1)
        else:
            print('❌ Failed to find csrfNonce')
            sys.exit(1)

        login_url = f'{self.url}/login'
        payload = {
            'name': self.username,
            'password': self.password,
            'nonce': self.nonce
        }
        response = self.session.post(login_url, data=payload)
        if response.status_code == 200:
            print('Login successful')
        else:
            print('❌ Login failed')
            print(response.text)
            sys.exit(1)

    def get_data(self, endpoint):
        url = f'{self.url}/api/v1/{endpoint}'
        response = self.session.get(url)
        if response.status_code == 200:
            if "not found" not in response.json():
                return response.json().get('data')
            else:
                print(f'❌ Failed to fetch data from {endpoint}')
                return []
        else:
            print(f'❌ Failed to fetch data from {endpoint}')
            return []

    def get_meta(self, endpoint):
        url = f'{self.url}/api/v1/{endpoint}'
        response = self.session.get(url)
        if response.status_code == 200:
            return response.json().get('meta')
        else:
            print(f'❌ Failed to fetch meta from {endpoint}')
            return []

    def save_to_file(self, data, filename):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def download_file(self, url, filename):
        response = self.session.get(url)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)
            return True
        return False

    def backup_challenges(self):
        challenges = self.get_data('challenges')
        challenges_dir = os.path.join(self.ctf_name, 'challenges')

        categories = {}

        for challenge in challenges:
            challenge_id = challenge['id']
            name = challenge.get('name', 'unknown').replace('/', '-')
            challenge_data = self.get_data(f'challenges/{challenge_id}')
            category = challenge_data.get('category', 'uncategorized').replace('/', '-')
            if category not in categories:
                categories[category] = []
            categories[category].append(name)

            print(f"- [ ] {name}", end='\r')

            category_dir = os.path.join(challenges_dir, category)
            os.makedirs(category_dir, exist_ok=True)
            challenge_dir = os.path.join(category_dir, name)
            os.makedirs(challenge_dir, exist_ok=True)

            challenge_filename = os.path.join(challenge_dir, f'{name}.md')
            try:
                with open(challenge_filename, 'w', encoding='utf-8') as f:
                    f.write(f'# {name}\n\n')
                    f.write(f'**ID:** {challenge_id}\n\n')
                    f.write(f'**Category:** {category}\n\n')
                    f.write(f'**Description:**\n\n{challenge_data["description"]}\n\n')
                    files = challenge_data.get('files', [])
                    if files:
                        f.write('**Files:**\n\n')
                        for file_url in files:
                            filename = file_url.rsplit('/', 1)[-1].split('?')[0]
                            f.write(f'- [{filename}]({self.url}/{file_url})\n')

                # Download files and print status
                file_statuses = []
                success = True
                for file_url in files:
                    filename = file_url.rsplit('/', 1)[-1].split('?')[0]
                    file_path = os.path.join(challenge_dir, filename)
                    if self.download_file(f'{self.url}/{file_url}', file_path):
                        file_statuses.append(f"    Downloaded file: {filename}")
                    else:
                        success = False
                        file_statuses.append(f"    ❌ Failed to download file: {filename}")

                if success:
                    print(colored(f"- {colored('[✔]', 'green')} {name}", "green"))
                else:
                    print(colored(f"- {colored('[✖]', 'red')} {name}", "red"))

                for file_status in file_statuses:
                    print(file_status)

            except Exception as e:
                print(colored(f"- {colored('[✖]', 'red')} {name}", "red"))
                continue

        print("✅ Challenges backup completed.")

    def backup_teams(self):
        teams = self.get_data('teams')
        teams_dir = os.path.join(self.ctf_name, 'teams')

        os.makedirs(teams_dir, exist_ok=True)

        teams_filename = os.path.join(teams_dir, 'teams.md')

        teams_meta = self.get_meta('teams')

        if teams_meta == []:
            return

        total_pages = teams_meta['pagination']['pages']

        with open(teams_filename, 'w', encoding='utf-8') as f:
            for page in range(1, total_pages + 1):
                teams_data = self.get_data(f'teams?page={page}')
                teams = teams_data
                for team in teams:
                    name = team.get('name', 'unknown').replace('/', '-')
                    team_id = team['id']
                    f.write(f'# {name}\n\n')
                    f.write(f'**ID:** {team_id}\n\n')
                    f.write(f'**Country:** {team["country"]}\n\n')
                    f.write(f'**Affiliation:** {team.get("affiliation", "None")}\n\n')
                    f.write(f'**Website:** {team.get("website", "None")}\n\n')
                    f.write(f'**Captain ID:** {team.get("captain_id", "None")}\n\n')
                    f.write('\n\n')

        print("✅ Teams backup completed.")

    def backup_users(self):
        users_dir = os.path.join(self.ctf_name, 'users')

        os.makedirs(users_dir, exist_ok=True)

        users_filename = os.path.join(users_dir, 'users.md')

        users_meta = self.get_meta('users')
        total_pages = users_meta['pagination']['pages']

        with open(users_filename, 'w', encoding='utf-8') as f:
            for page in range(1, total_pages + 1):
                users_data = self.get_data(f'users?page={page}')
                users = users_data
                for user in users:
                    name = user.get('name', 'unknown').replace('/', '-')
                    user_id = user['id']
                    team_id = user.get('team_id', 'None')
                    f.write(f'# {name}\n\n')
                    f.write(f'**ID:** {user_id}\n\n')
                    f.write(f'**Team ID:** {team_id}\n\n')
                    f.write(f'**Country:** {user.get("country", "None")}\n\n')
                    f.write(f'**Affiliation:** {user.get("affiliation", "None")}\n\n')
                    f.write(f'**Website:** {user.get("website", "None")}\n\n')
                    f.write('\n\n')

        print("✅ Users backup completed.")

    def backup_scoreboard(self):
        scoreboard = self.get_data('scoreboard')

        scoreboard_dir = os.path.join(self.ctf_name, 'scoreboard')

        os.makedirs(scoreboard_dir, exist_ok=True)

        scoreboard_filename = os.path.join(scoreboard_dir, 'scoreboard.md')

        with open(scoreboard_filename, 'w', encoding='utf-8') as f:
            f.write("# Scoreboard\n\n")
            for entry in scoreboard:
                rank = entry['pos']
                name = entry['name']
                score = entry['score']
                f.write(f"## Rank {rank}: {name}\n\n")
                f.write(f"**Score:** {score}\n\n")
                if "members" in scoreboard:
                    f.write("### Members\n\n")
                    for member in entry['members']:
                        member_name = member['name']
                        member_score = member['score']
                        f.write(f"- **{member_name}:** {member_score}\n")
                f.write("\n\n")

        print("✅ Scoreboard backup completed.")

    def create_overview(self):
        challenges = self.get_data('challenges')
        overview_dir = self.ctf_name

        os.makedirs(overview_dir, exist_ok=True)

        overview_filename = os.path.join(overview_dir, 'overview.md')

        categories = {}

        for challenge in challenges:
            category = challenge.get('category', 'uncategorized').replace('/', '-')
            name = challenge.get('name', 'unknown').replace('/', '-')
            if category not in categories:
                categories[category] = []
            categories[category].append(name)

        with open(overview_filename, 'w', encoding='utf-8') as f:
            for category, names in categories.items():
                f.write(f"# {category}\n")
                for name in names:
                    f.write(f"## {name}\n")
                    f.write("---\n")
                    f.write("writeup\n")
                    f.write("---\n")
                    f.write("flag\n\n")

        print("✅ Overview file created.")

    def backup_all(self):
        self.login()
        self.backup_challenges()
        self.backup_teams()
        self.backup_users()
        self.backup_scoreboard()


def main():
    print("""
       _____ _______ ______  _   ____             _                
      / ____|__   __|  ____|| | |  _ \           | |               
     | |       | |  | |__ __| | | |_) | __ _  ___| | ___   _ _ __  
     | |       | |  |  __/ _` | |  _ < / _` |/ __| |/ / | | | '_ \ 
     | |____   | |  | | | (_| | | |_) | (_| | (__|   <| |_| | |_) |
      \_____|  |_|  |_|  \__,_| |____/ \__,_|\___|_|\_\\__,_| .__/ 
                                                            | |    
                                                            |_|    
    """)

    parser = argparse.ArgumentParser(description="Backup CTFd data and create overview.")
    parser.add_argument("username", help="CTFd username")
    parser.add_argument("password", help="CTFd password")
    parser.add_argument("url", help="CTFd URL example: demo.ctfd.com")

    args = parser.parse_args()

    username = args.username
    password = args.password
    url = args.url

    backup = CTFdBackup(url, username, password)
    backup.backup_all()

    backup.create_overview()


if __name__ == '__main__':
    main()
