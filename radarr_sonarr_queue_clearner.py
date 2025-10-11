import requests
import logging
import logging.handlers
import configparser
from datetime import datetime


# Functions to load dynamically determined configuration variable values
def load_suspicious_extensions(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        # Split lines, strip whitespace, ignore empty lines
        return tuple(line.strip() for line in response.text.splitlines() if line.strip())
    except Exception as e:
        # Fallback to default
        return None

# Function to parse a tuple from string, used with configparser
def parse_tuple(s: str) -> tuple:
    s = s.strip('() ')
    if not s:
        return ()
    return tuple(item.strip() for item in s.split(','))

#############################################
# Configuration
#############################################

# Rename config.ini.example to config.ini, add your configs to that file
config = configparser.ConfigParser()
config.read('config.ini')

# General
auto_fetch_extension_filter = config.getboolean('GENERAL', 'auto_fetch_extension_filter')
extension_filter_URL = config.get('GENERAL', 'extension_filter_URL')
manual_extension_filter = parse_tuple(config.get('GENERAL', 'manual_extension_filter'))
optional_extension_filter = parse_tuple(config.get('GENERAL', 'optional_extension_filter'))
block_torrent_on_removal = config.getboolean('GENERAL', 'block_torrent_on_removal')
syslog_enabled = config.getboolean('GENERAL', 'syslog_enabled')
syslog_level = config.getint('GENERAL', 'syslog_level')

# Sonarr configuration
sonarr_host = config.get('SONARR', 'host')
sonarr_port = config.get('SONARR', 'port')
sonarr_url = f'http://{sonarr_host}:{sonarr_port}/api/v3/queue'
sonarr_api_key = config.get('SONARR', 'api_key')

# Radarr configuration
radarr_host = config.get('RADARR', 'host')
radarr_port = config.get('RADARR', 'port')
radarr_url = f'http://{radarr_host}:{radarr_port}/api/v3/queue'
radarr_api_key = config.get('RADARR', 'api_key')

# Choose torrent client: set to either 'transmission' or 'qbittorrent'
torrent_client = config.get('TORRENT', 'client')

# Transmission configuration (only used if torrent_client == 'transmission')
transmission_url = config.get('TRANSMISSION', 'url')
transmission_username = config.get('TRANSMISSION', 'username')
transmission_password = config.get('TRANSMISSION', 'password')

# qBittorrent configuration (only used if torrent_client == 'qbittorrent')
qbittorrent_url = config.get('QBITTORRENT', 'url')
qb_username = config.get('QBITTORRENT', 'username')
qb_password =  config.get('QBITTORRENT', 'password')
qb_force_direct_delete =  config.getboolean('QBITTORRENT', 'force_direct_delete') 

# Remote Sys Logging configuration
syslog_host = config.get('SYSLOG', 'host')
syslog_port = config.getint('SYSLOG', 'port')
syslog_entity_id = config.get('SYSLOG', 'entity_id')

#############################################
# Functions
#############################################

#handle user feedback/logging conditions
def log_message(message: str, log_rate: int = 2):
    print(message)
    if syslog_enabled:
        if syslog_level == 0 :
            return None
        elif log_rate >= syslog_level and syslog_level != 0:
            send_syslog(message)

#handle remote sys logging
def send_syslog(message: str):
    logger = logging.getLogger(syslog_entity_id)
    logger.setLevel(logging.INFO)

    # Avoid adding multiple handlers if function is called multiple times
    if not logger.handlers:
        handler = logging.handlers.SysLogHandler(address=(syslog_host, syslog_port))
        formatter = logging.Formatter('%(asctime)s %(name)s: %(message)s', datefmt='%b %d %H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.info(message)

# Fetch the download queue from Sonarr/Radarr
def fetch_queue(api_url, api_key):
    headers = {'X-Api-Key': api_key}
    response = requests.get(api_url, headers=headers)
    return response.json()

# Remove (and block) a download via Sonarr/Radarr API
def remove_and_block_download(api_url, api_key, download_id, block_torrent=False):
    params = {
        'removeFromClient': True,
        'blocklist': block_torrent,  # Block the torrent if True
        'skipRedownload': True
    }
    if block_torrent:
        log_message(f"Blocking torrent {download_id} from being downloaded again.", log_rate=3)
    delete_url = f'{api_url}/{download_id}'
    headers = {
        'X-Api-Key': api_key,
        'Content-Type': 'application/json'
    }
    response = requests.delete(delete_url, headers=headers, params=params)
    if response.status_code == 200:
        log_message(f"Successfully removed download {download_id} from queue.", log_rate=3)
    else:
        log_message(f"Failed to remove download {download_id}. Response: {response.status_code} - {response.text}", log_rate=3)

#############################################
# Transmission-related functions
#############################################

def get_transmission_session_id():
    response = requests.post(transmission_url, auth=(transmission_username, transmission_password))
    if 'X-Transmission-Session-Id' in response.headers:
        return response.headers['X-Transmission-Session-Id']
    return None

def get_transmission_torrent_files(session_id, torrent_hash):
    payload = {
        "method": "torrent-get",
        "arguments": {
            "fields": ["files"],
            "ids": [torrent_hash]
        }
    }
    headers = {
        'X-Transmission-Session-Id': session_id,
        'Content-Type': 'application/json'
    }
    response = requests.post(transmission_url, headers=headers, json=payload,
                             auth=(transmission_username, transmission_password))
    if response.status_code == 200:
        return response.json().get('arguments', {}).get('torrents', [])
    elif response.status_code == 409:
        # If session ID expired, refresh and retry
        new_session_id = get_transmission_session_id()
        headers['X-Transmission-Session-Id'] = new_session_id
        response = requests.post(transmission_url, headers=headers, json=payload,
                                 auth=(transmission_username, transmission_password))
        if response.status_code == 200:
            return response.json().get('arguments', {}).get('torrents', [])
        else:
            log_message (f"Error fetching torrent files: {response.text}", log_rate=2)
            return None
    else:
        log_message(f"Error fetching torrent files: {response.text}", log_rate=2)
        return None

#############################################
# qBittorrent-related functions
#############################################

# We'll use a session to handle authentication cookies
qb_session = None

def qbittorrent_login():
    global qb_session
    qb_session = requests.Session()
    login_url = f'{qbittorrent_url}/api/v2/auth/login'
    payload = {'username': qb_username, 'password': qb_password}
    r = qb_session.post(login_url, data=payload)
    if r.text != "Ok.":
        log_message("Failed to log in to qBittorrent", log_rate=2)
        qb_session = None
    else:
        log_message("Successfully logged in to qBittorrent", log_rate=1)

def get_qbittorrent_torrent_files(torrent_hash):
    if qb_session is None:
        log_message("qBittorrent session is not established.", log_rate=2)
        return None
    url = f'{qbittorrent_url}/api/v2/torrents/files'
    params = {'hash': torrent_hash}
    response = qb_session.get(url, params=params)
    if response.status_code == 200:
        # qBittorrent returns a list of file objects
        return response.json()
    else:
        log_message(f"Error fetching qBittorrent torrent files: {response.text}", log_rate=2)
        return None
def del_qbittorrent_torrent_files(torrent_hash):
    if qb_session is None:
        log_message("qBittorrent session is not established.", log_rate=2)
        return None
    urld = f'{qbittorrent_url}/api/v2/torrents/delete'
    params = {'hashes': torrent_hash, 'deleteFiles': 'true'}
    response = qb_session.post(urld, data=params)  # <-- Use POST and data
    if response.status_code == 200:
        log_message(f"Removed torrent {torrent_hash} directly from qBittorrent and deleting files. [qb_force_direct_delete = True]", log_rate=3)
        return None
    else:
        log_message(f"Error directly deleting qBittorrent torrent files: {response.text}", log_rate=3)
        return None
    
#############################################
# Initialization of the torrent client session
#############################################
start_time = datetime.now()
log_message(f"Torrent cleaner script started at {start_time}", log_rate=1)
if torrent_client.lower() == 'transmission':
    transmission_session_id = get_transmission_session_id()
    if not transmission_session_id:
        log_message("Failed to get Transmission session ID.", log_rate=2)    
elif torrent_client.lower() == 'qbittorrent':
    qbittorrent_login()

#############################################
# Main processing: Check queues and verify torrent file names
#############################################

if auto_fetch_extension_filter:
    log_message (f"Downloading latest extension filter list from {extension_filter_URL}", log_rate=1)
    suspicious_extensions = load_suspicious_extensions(extension_filter_URL)
    if suspicious_extensions is None:
        log_message("Failed to download extension filter list. Falling back to manual extension filter list.", log_rate=2)
        suspicious_extensions = manual_extension_filter
    else:
        if optional_extension_filter:
            suspicious_extensions += optional_extension_filter
            log_message(f"Adding optional userdefined suspicious extensions filter: {optional_extension_filter}", log_rate=1)
    log_message(f"Suspicious extensions filter is: {suspicious_extensions}", log_rate=1)
else:
    suspicious_extensions = manual_extension_filter
    log_message(f"Using user defined suspicious extensions filter: {suspicious_extensions}", log_rate=1)

for app_name, api_url, api_key in [
    ('Sonarr', sonarr_url, sonarr_api_key),
    ('Radarr', radarr_url, radarr_api_key)
]:
    downloads_data = fetch_queue(api_url, api_key)
    downloads = downloads_data.get('records', [])
    if isinstance(downloads, list):
        for download in downloads:
            # The 'downloadId' is assumed to be the torrent hash
            torrent_hash = download['downloadId']
            title = download['title']
            
            # Get the torrent file list using the chosen client's API
            torrent_files = None
            if torrent_client.lower() == 'transmission':
                torrent_files = get_transmission_torrent_files(transmission_session_id, torrent_hash)
            elif torrent_client.lower() == 'qbittorrent':
                torrent_files = get_qbittorrent_torrent_files(torrent_hash)
            
            if torrent_files:
                log_message(f"Checking torrent contents for: {title}", log_rate=1)
                remove_torrent_flag = False

                if torrent_client.lower() == 'transmission':
                    # For Transmission, the response is a list of torrents with a "files" key.
                    for torrent in torrent_files:
                        for file in torrent.get('files', []):
                            filename = file.get('name', '')
                            if filename.endswith(suspicious_extensions):
                                log_message(f"Identified suspicious file: {filename}. Marking download for removal...", log_rate=3)
                                remove_torrent_flag = True
                                break
                        if remove_torrent_flag:
                            remove_and_block_download(api_url,api_key, download['id'], block_torrent=block_torrent_on_removal)
                            break
                elif torrent_client.lower() == 'qbittorrent':
                    # For qBittorrent, the API returns a list of file objects directly.
                    for file in torrent_files:
                        filename = file.get('name', '')
                        if filename.endswith(suspicious_extensions):
                            log_message(f"Identified suspicious file: {filename}. Marking download for removal...", log_rate=3)
                            remove_torrent_flag = True
                            break
                    if remove_torrent_flag:
                        if qb_force_direct_delete:
                            del_qbittorrent_torrent_files(torrent_hash)
                        remove_and_block_download(api_url, api_key, download['id'], block_torrent=block_torrent_on_removal)
            else:
                log_message(f"Failed to fetch torrent info for {title} in {app_name}", log_rate=2)
    else:
        log_message(f"Unexpected data structure from {app_name} API. Expected a list.", log_rate=2)
end_time = datetime.now()
log_message(f"Script completed at {end_time}, duration: {end_time - start_time}", log_rate=1)
