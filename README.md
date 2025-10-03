# CTFd Backup Tool

## Introduction
CTFd Backup Tool is a Python script for backing up data from CTFd (Capture The Flag platform) instances. This tool helps users to create backups of challenges, teams, users, scoreboard, and an overview file for easy writeup creation. It allows you to maintain a local copy of your CTFd data for offline usage or disaster recovery.

## Features
- Backup challenges, teams, users, scoreboard, and an overview file.
- **🚀 Incremental backup support** - Skip unchanged files to save time and bandwidth
- Organize challenges by category in the overview file for easy writeup creation.
- Retrieve data from CTFd instances via API.
- Save challenges including descriptions and files.
- Download files associated with challenges.
- **📊 Backup statistics and progress tracking**
- User-friendly command-line interface.

## Installation
1. Clone this repository:

    ```bash
    git clone https://github.com/mlgzackfly/CTFd-Backup-Tool.git
    ```

2. Navigate to the cloned directory:

    ```bash
    cd ctfd-backup-tool
    ```

3. Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

## Usage
1. Navigate to the directory where the script is located.
2. Run the script using Python:

    **Full Backup (default):**
    ```bash
    python ctfbackup.py <username> <password> <url>
    ```

    **Incremental Backup (recommended for subsequent runs):**
    ```bash
    python ctfbackup.py <username> <password> <url> --incremental
    ```

    **Force Full Backup (ignore metadata):**
    ```bash
    python ctfbackup.py <username> <password> <url> --force-full
    ```

    Replace `<username>`, `<password>`, and `<url>` with your CTFd credentials and URL.

3. The script will start backing up your CTFd instance. Once completed, you will find the backups in the directory named after your CTFd instance.

### Command Line Options
- `--incremental` or `-i`: Enable incremental backup mode (skip unchanged files)
- `--force-full` or `-f`: Force full backup even if metadata exists

### Incremental Backup
The tool tracks file metadata in `.backup_metadata.json` to determine which files have changed. This significantly reduces backup time for subsequent runs by:
- Comparing file sizes and modification times
- Calculating SHA256 hashes to detect content changes
- Skipping files that haven't changed since the last backup

## Example
**First time backup (full):**
```bash
python ctfbackup.py admin password https://ctfd.example.com
```

**Subsequent backups (incremental):**
```bash
python ctfbackup.py admin password https://ctfd.example.com --incremental
```

**Output example:**
```
🔄 Running incremental backup...
- ✔ Web Challenge 1
    ⬇️ Downloaded file: challenge.zip
- ✔ Crypto Challenge 1  
    ⏭️ Skipped file: crypto.py (unchanged)
    ✅ Updated file: solution.txt

==================================================
📊 BACKUP STATISTICS
==================================================
🔄 Mode: Incremental Backup
📁 Total files: 25
⬇️ Downloaded: 3
✅ Updated: 2
⏭️ Skipped: 20
💾 Efficiency: 80.0% files skipped
==================================================
```

![usage](image/usage.png)
