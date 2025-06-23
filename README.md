# TorrentCleaner

**TorrentCleaner** is a Python script that automates the process of identifying and removing torrents that contain suspicious files (like `.zipx` or `.lnk`) from your Transmission download client. This ensures that unwanted or potentially harmful files are filtered out and deleted during the download process, keeping your system clean.

## Features

- Fetches the list of torrents from **Sonarr**'s queue.
- Fetches the list of torrents from **Radarr**'s queue.
- Identifies torrents managed by **Transmission** or **qBittorent**
- Inspects torrent contents to find suspicious file extensions (user definable)
- Automatically removes torrents containing suspicious files.
- Deletes associated files on disk using Transmission's API.
- Can forward filter hit events to syslog server

## Requirements

- **Sonarr** API key and URL
- **Radarr** API key and URL
- **Transmission** URL and credentials (if required)
- Python 3.x
- Python packages: `requests`

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/bugalou/torrentcleaner.git
    cd TorrentCleaner
    ```

2. Install the required dependencies:

    ```bash
    pip install requests
    ```

3. Set up your environment variables (or hardcode the values in the script):
    - Sonarr API key
    - Radarr API key
    - Transmission username and password (if authentication is required)
    - Hostnames and ports for Sonarr, Radarr and Transmission

    ```python
    
    SUSPICIOUS_EXTENSIONS = ('.gz', '.001', '.zipx', '.lnk', '.arj') # Add or remove extensions as needed
    BLOCK_TORRENT_ON_REMOVAL = True  # If True, the torrent will be blocked from being downloaded again, otherwise it will be removed from the queue but not blocked
    syslog_enabled = True #if True, messages including filter hits will be sent to syslog. Syslog config below must be set up
    syslog_level = 2 # 0 = no logging, 1 = send all events, 2 = send warnings and errors 3 = only send matching torrent removal events  (send to syslog if syslog_enabled=True)
    
    sonarr_host = 'XXXX'  # Update with your actual Sonarr host (e.g., 'localhost', '192.168.1.10', etc.)
    sonarr_port = '8989'  # Update with the actual port where Sonarr is running
    sonarr_url = f'http://{sonarr_host}:{sonarr_port}/api/v3/queue'
    sonarr_api_key = 'XXXX'  # Replace with your actual Sonarr API key

    radarr_host = 'localhost'  # Update with your actual Radarr host
    radarr_port = '7878'  # Update with the actual port where Radarr is running
    radarr_url = f'http://{radarr_host}:{radarr_port}/api/v3/queue'
    radarr_api_key = 'XXXX'  # Replace with your actual Radarr API key

    torrent_client = 'transmission' # define torrent client ('transmission', or 'qbittorrent')

    #transmission configuration (only used if torrent_client == 'transmission')
    transmission_url = 'http://XXXX:9091/transmission/rpc'  # Replace with your Transmission host and port
    transmission_username = 'username'  # If Transmission has authentication
    transmission_password = 'password'

    #qBittorrent configuration (only used if torrent_client == 'qbittorrent')
    qbittorrent_url = 'http://XXXX:3117'
    qb_username = 'username'
    qb_password = 'password'
    qb_force_direct_delete = True  # If True, files will be deleted directly from qbittorrent when the torrent is removed.
    # (cont note) This Helps avoid hanging .parts files in the download directory thats sonarr/radarr do not remove trying to access. 
    # (cont note) This may create logged errors in sonnarr/raddarr since files are removed directly from qBittorrent and are not present when Sonarr/Radarr tries to remove them. This can be ignored as end result is the same, the files are removed and the torrent is blocked from being downloaded again

    syslog_host = '<Syslog_IP>'
    syslog_port = 514 # UDP port
    syslog_entity_id = 'torrentcleaner_python@hostname' #will show up as the syslog source versus parent host (should show up separately)
    ```

## Usage

Once configured, you can run the script to automatically check for torrents with any extension defined in SUSPICIOUS_EXTENSIONS tuple list files and remove them from Transmission.

1. Run the script:

    ```bash
    python sonarr_queue_clearner.py
    ```
    For automation either set cronjob to monitor remote host, or set torrent client to execute script upon opening torrent
   
3. The script will:
    - Fetch all torrents from Sonarr's queue.
    - Inspect the files in each torrent.
    - If any file extensions are found in torrent that match the extensions set in the tupple SUSPICIOUS_EXTENSIONS, the torrent will be removed and the files deleted.
    - Will forward any positive hit to syslog server along with errors if syslog_enabled = True
    - Will block torrent for the future if BLOCK_TORRENT_ON_REMOVAL = True

## Example Output

```bash
Checking torrent contents for: TVShow.S02E08
Identified suspicious file: TVShow.S02E08/TVShow.S02E08.zipx. Marking download for removal...
Successfully removed download XXXX from Sonarr's queue.
```

## Transmission vs qBittorent

If you want to use qBittorrent instead of transmission, you will need to change this line

```python
torrent_client = 'qbittorrent'  # Change to bittorrent client type 
```

## Only Require Sonarr or Radarr Support

If you only need radarr or sonarr support, you can replace the fetch section in the script:

From:

```python
for app_name, api_url, api_key in [
('Sonarr', sonarr_url, sonarr_api_key),
('Radarr', radarr_url, radarr_api_key)
]:
```
Sonarr:

```python
for app_name, api_url, api_key in [
('Sonarr', sonarr_url, sonarr_api_key)
]:
```

Radarr:

```python
for app_name, api_url, api_key in [
('Radarr', radarr_url, radarr_api_key)
]:
```
## Contributing

Feel free to contribute by submitting a pull request or opening an issue. All contributions and suggestions are welcome.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
