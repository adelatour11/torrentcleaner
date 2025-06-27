import requests
import json
import logging
import logging.handlers

# Functions to load dynamically determined configuration variable values
def load_suspicious_extensions(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        # Split lines, strip whitespace, ignore empty lines
        return tuple(line.strip() for line in response.text.splitlines() if line.strip())
    except Exception as e:
        print(f"Failed to load suspicious extensions from {url}: {e}")
        # Fallback to default
        return ('.zipx', '.gz', '.lz', '.lnk', '.arj', '.lzh')

#############################################
# Configuration
#############################################
#General

#Permanent URL set below will need to be decided and changed it needed. @adelatour11 github repo for the main project is probably best, but other options are possible.
SUSPICIOUS_EXTENSIONS = load_suspicious_extensions('https://raw.githubusercontent.com/bugalou/torrentcleaner/refs/heads/dynamic-extensions-filter/extfilter-strings.txt') #Text file URL to fetch suspicious file extensions from
BLOCK_TORRENT_ON_REMOVAL = True  # If True, the torrent will be blocked from being downloaded again, otherwise it will be removed from the queue but not blocked
syslog_enabled = True #if True, messages will be sent to syslog based on logging level set in syslog_level. Syslog config below must be set up
syslog_level = 2 # 0 = no logging, 1 = send all events, 2 = send warnings and errors 3 = only send matching torrent removal events  (send to syslog if syslog_enabled=True)

# Sonarr configuration
sonarr_host = '' #hostname for sonarr server, use localhost if running on the same server
sonarr_port = '8989'
sonarr_url = f'http://{sonarr_host}:{sonarr_port}/api/v3/queue'
sonarr_api_key = 'API_KEY_HERE'

# Radarr configuration
radarr_host = '' #hostname for radarr server, use localhost if running on the same server
radarr_port = '7878'
radarr_url = f'http://{radarr_host}:{radarr_port}/api/v3/queue'
radarr_api_key = 'API_KEY_HERE'  # Replace with your actual API key

# Choose torrent client: set to either 'transmission' or 'qbittorrent'
torrent_client = 'qbittorrent'  # Change to 'qbittorrent' or 'transmission' for desired BT client

# Transmission configuration (only used if torrent_client == 'transmission')
transmission_url = 'http://XXXX:9091/transmission/rpc'
transmission_username = 'username'
transmission_password = 'password'

# qBittorrent configuration (only used if torrent_client == 'qbittorrent')
qbittorrent_url = 'http://XXXX:8080'
qb_username = 'btuser'
qb_password = 'btpass'
qb_force_direct_delete = True  # If True, files will be deleted directly from qbittorrent when the torrent is removed. Helps avoid hanging ".parts" files in the download directory thats sonarr/radarr do not remove when a torrent is canceled mid transfer.
#^ (continued from above) This may create logged errors in sonnarr/raddarr since files are removed directly from qBittorrent and are not present when Sonarr/Radarr tries to remove them. This can be ignored and sonarr/radarr will handle internally - end result is the same, the files are removed and the torrent is blocked from being downloaded again
#^ (continued from above) this behaviour is not known to occur in transmission app, but similar approach could be taken if it is down the road.

# Remote Sys Logging configuration
syslog_host = '192.168.100.100' #ip of syslog server, hostname should work too assuming python instance can resolve DNS.
syslog_port = 514 # UDP is only supported for this.
syslog_entity_id = 'torrentcleaner_python@hostname' #will show up as the syslog source versus parent host (should show up separately)

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
            print(f"Error fetching torrent files: {response.text}")
            return None
    else:
        print(f"Error fetching torrent files: {response.text}")
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
    response = qb_session.post(urld, data=params) 
    if response.status_code == 200:
        log_message(f"Removed torrent {torrent_hash} directly from qBittorrent and deleting files. [qb_force_direct_delete = True]", log_rate=3)
        print(f"Removed torrent {torrent_hash} directly from qBittorrent and deleting files. [qb_force_direct_delete = True]")
        return None
    else:
        log_message(f"Error directly deleting qBittorrent torrent files: {response.text}", log_rate=3)
        print(f"Error directly deleting qBittorrent torrent files: {response.text}")
        return None
    
#############################################
# Initialization of the torrent client session
#############################################

if torrent_client.lower() == 'transmission':
    transmission_session_id = get_transmission_session_id()
    if not transmission_session_id:
        log_message("Failed to get Transmission session ID.", log_rate=2)
elif torrent_client.lower() == 'qbittorrent':
    qbittorrent_login()

#############################################
# Main processing: Check queues and verify torrent file names
#############################################

for app_name, api_url, api_key in [
    ('Sonarr', sonarr_url, sonarr_api_key),
    ('Radarr', radarr_url, radarr_api_key)
]:
    downloads_data = fetch_queue(api_url, api_key)
    downloads = downloads_data.get('records', [])
    log_message(f"Torrent cleaner script started.", log_rate=1)
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
                            if filename.endswith(SUSPICIOUS_EXTENSIONS):
                                log_message(f"Identified suspicious file: {filename}. Marking download for removal...", log_rate=3)
                                print(f"Identified suspicious file: {filename}. Marking download for removal...")
                                remove_torrent_flag = True
                                break
                        if remove_torrent_flag:
                            break
                elif torrent_client.lower() == 'qbittorrent':
                    # For qBittorrent, the API returns a list of file objects directly.
                    for file in torrent_files:
                        filename = file.get('name', '')
                        if filename.endswith(SUSPICIOUS_EXTENSIONS):
                            log_message(f"Identified suspicious file: {filename}. Marking download for removal...", log_rate=3)
                            print(f"Identified suspicious file: {filename}. Marking download for removal...")
                            remove_torrent_flag = True
                            break
                    if remove_torrent_flag:
                        if qb_force_direct_delete:
                            del_qbittorrent_torrent_files(torrent_hash)
                        remove_and_block_download(api_url, api_key, download['id'], block_torrent=BLOCK_TORRENT_ON_REMOVAL)
            else:
                log_message(f"Failed to fetch torrent info for {title} in {app_name}", log_rate=2)
    else:
        log_message(f"Unexpected data structure from {app_name} API. Expected a list.", log_rate=2)
log_message(f"Torrent cleaner script ended.", log_rate=1)
