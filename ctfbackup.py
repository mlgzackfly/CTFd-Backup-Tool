import re
import requests
import os
import json
import sys
import argparse
import hashlib
import time
from datetime import datetime
from urllib.parse import urlparse
from termcolor import colored
from tqdm import tqdm

class CTFdBackup:
    def __init__(self, url, username, password, incremental=False):
        self.nonce = None
        self.url = self.format_url(url)
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.ctf_name = self.get_ctf_name()
        self.incremental = incremental
        self.metadata_file = os.path.join(self.ctf_name, '.backup_metadata.json')
        self.backup_stats = {
            'files_skipped': 0,
            'files_downloaded': 0,
            'files_updated': 0,
            'total_files': 0
        }

    def format_url(self, url):
        if not url.startswith('http://') and not url.startswith('https://'):
            return 'https://' + url
        return url

    def get_ctf_name(self):
        parsed_url = urlparse(self.url)
        return parsed_url.netloc

    def load_backup_metadata(self):
        """載入備份元數據"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return {}
        return {}

    def save_backup_metadata(self, metadata):
        """保存備份元數據"""
        os.makedirs(os.path.dirname(self.metadata_file), exist_ok=True)
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)

    def get_file_hash(self, file_path):
        """計算檔案的SHA256雜湊值"""
        if not os.path.exists(file_path):
            return None
        
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def should_download_file(self, file_url, local_file_path, metadata):
        """檢查是否需要下載檔案"""
        if not self.incremental:
            return True
            
        filename = os.path.basename(local_file_path)
        
        # 如果本地檔案不存在，需要下載
        if not os.path.exists(local_file_path):
            return True
            
        # 檢查元數據中是否有記錄
        if file_url not in metadata:
            return True
            
        # 獲取遠端檔案資訊
        try:
            response = self.session.head(f'{self.url}/{file_url}')
            if response.status_code != 200:
                return True
                
            remote_size = response.headers.get('content-length')
            remote_modified = response.headers.get('last-modified')
            
            # 比較檔案大小
            local_size = os.path.getsize(local_file_path)
            if remote_size and int(remote_size) != local_size:
                return True
                
            # 比較本地檔案雜湊值
            stored_hash = metadata[file_url].get('hash')
            current_hash = self.get_file_hash(local_file_path)
            
            if stored_hash != current_hash:
                return True
                
            return False
            
        except Exception:
            # 如果檢查失敗，選擇下載
            return True

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

    def download_file(self, url, filename, metadata=None, file_url=None, show_progress=True):
        """下載檔案並更新元數據，顯示下載進度"""
        try:
            # 先發送 HEAD 請求獲取檔案大小
            head_response = self.session.head(url)
            if head_response.status_code != 200:
                # 如果 HEAD 請求失敗，回退到普通下載
                response = self.session.get(url)
            else:
                total_size = int(head_response.headers.get('content-length', 0))
                
                # 開始下載
                response = self.session.get(url, stream=True)
            
            if response.status_code == 200:
                file_basename = os.path.basename(filename)
                
                # 確保目錄存在
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                
                if show_progress and 'content-length' in response.headers:
                    total_size = int(response.headers.get('content-length', 0))
                    
                    # 創建進度條
                    with tqdm(
                        total=total_size,
                        unit='B',
                        unit_scale=True,
                        unit_divisor=1024,
                        desc=f"📥 {file_basename}",
                        ncols=80,
                        leave=False
                    ) as pbar:
                        with open(filename, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    pbar.update(len(chunk))
                else:
                    # 無法獲取檔案大小或禁用進度條時
                    with open(filename, 'wb') as f:
                        if show_progress:
                            # 顯示簡單的脈衝進度條
                            with tqdm(
                                desc=f"📥 {file_basename}",
                                unit='B',
                                unit_scale=True,
                                unit_divisor=1024,
                                ncols=80,
                                leave=False
                            ) as pbar:
                                downloaded = 0
                                for chunk in response.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                                        downloaded += len(chunk)
                                        pbar.update(len(chunk))
                        else:
                            f.write(response.content)
                
                # 更新元數據
                if metadata is not None and file_url is not None:
                    file_info = {
                        'local_path': filename,
                        'size': os.path.getsize(filename),
                        'hash': self.get_file_hash(filename),
                        'downloaded_at': datetime.now().isoformat(),
                        'url': url
                    }
                    metadata[file_url] = file_info
                
                return True
                
        except Exception as e:
            print(f"❌ Error downloading {filename}: {str(e)}")
            return False
            
        return False

    def backup_challenges(self):
        challenges = self.get_data('challenges')
        challenges_dir = os.path.join(self.ctf_name, 'challenges')

        # 載入元數據
        metadata = self.load_backup_metadata()

        categories = {}
        
        print("🔍 Processing challenges...")
        
        # 使用進度條處理所有題目
        with tqdm(challenges, desc="📚 Challenges", unit="challenge", ncols=80) as pbar:
            for challenge in pbar:
                challenge_id = challenge['id']
                name = challenge.get('name', 'unknown').replace('/', '-')
                
                # 更新進度條描述
                pbar.set_description(f"📚 Processing: {name[:30]}...")
                
                challenge_data = self.get_data(f'challenges/{challenge_id}')
                category = challenge_data.get('category', 'uncategorized').replace('/', '-')
                if category not in categories:
                    categories[category] = []
                categories[category].append(name)

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
                    files = challenge_data.get('files', [])
                    self.backup_stats['total_files'] += len(files)
                    
                    for file_url in files:
                        filename = file_url.rsplit('/', 1)[-1].split('?')[0]
                        file_path = os.path.join(challenge_dir, filename)
                        
                        # 檢查是否需要下載
                        if self.should_download_file(file_url, file_path, metadata):
                            if self.download_file(f'{self.url}/{file_url}', file_path, metadata, file_url):
                                if os.path.exists(file_path) and file_url in metadata:
                                    # 檢查是否為更新
                                    if 'downloaded_at' in metadata[file_url]:
                                        file_statuses.append(f"    ✅ Updated file: {filename}")
                                        self.backup_stats['files_updated'] += 1
                                    else:
                                        file_statuses.append(f"    ⬇️ Downloaded file: {filename}")
                                        self.backup_stats['files_downloaded'] += 1
                                else:
                                    file_statuses.append(f"    ⬇️ Downloaded file: {filename}")
                                    self.backup_stats['files_downloaded'] += 1
                            else:
                                success = False
                                file_statuses.append(f"    ❌ Failed to download file: {filename}")
                        else:
                            file_statuses.append(f"    ⏭️ Skipped file: {filename} (unchanged)")
                            self.backup_stats['files_skipped'] += 1

                    if success:
                        tqdm.write(colored(f"- {colored('[✔]', 'green')} {name}", "green"))
                    else:
                        tqdm.write(colored(f"- {colored('[✖]', 'red')} {name}", "red"))

                    for file_status in file_statuses:
                        tqdm.write(file_status)

                except Exception as e:
                    tqdm.write(colored(f"- {colored('[✖]', 'red')} {name}", "red"))
                    continue

        # 保存更新的元數據
        self.save_backup_metadata(metadata)
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
            with tqdm(range(1, total_pages + 1), desc="👥 Teams", unit="page", ncols=80) as pbar:
                for page in pbar:
                    pbar.set_description(f"👥 Teams (page {page}/{total_pages})")
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
            with tqdm(range(1, total_pages + 1), desc="👤 Users", unit="page", ncols=80) as pbar:
                for page in pbar:
                    pbar.set_description(f"👤 Users (page {page}/{total_pages})")
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

    def print_backup_stats(self):
        """印出備份統計資訊"""
        print("\n" + "="*50)
        print("📊 BACKUP STATISTICS")
        print("="*50)
        
        if self.incremental:
            print(f"🔄 Mode: Incremental Backup")
        else:
            print(f"🔄 Mode: Full Backup")
            
        print(f"📁 Total files: {self.backup_stats['total_files']}")
        print(f"⬇️ Downloaded: {self.backup_stats['files_downloaded']}")
        print(f"✅ Updated: {self.backup_stats['files_updated']}")
        print(f"⏭️ Skipped: {self.backup_stats['files_skipped']}")
        
        if self.backup_stats['total_files'] > 0:
            skip_percentage = (self.backup_stats['files_skipped'] / self.backup_stats['total_files']) * 100
            print(f"💾 Efficiency: {skip_percentage:.1f}% files skipped")
        
        print("="*50)

    def backup_all(self):
        self.login()
        
        if self.incremental:
            print("🔄 Running incremental backup...")
        else:
            print("🔄 Running full backup...")
            
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
    parser.add_argument("--incremental", "-i", action="store_true", 
                       help="Enable incremental backup (skip unchanged files)")
    parser.add_argument("--force-full", "-f", action="store_true",
                       help="Force full backup (ignore metadata)")

    args = parser.parse_args()

    username = args.username
    password = args.password
    url = args.url
    incremental = args.incremental and not args.force_full

    if args.incremental and args.force_full:
        print("⚠️ Warning: --force-full overrides --incremental")

    backup = CTFdBackup(url, username, password, incremental)
    backup.backup_all()

    backup.create_overview()
    backup.print_backup_stats()


if __name__ == '__main__':
    main()
