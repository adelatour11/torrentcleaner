# TorrentCleaner

**TorrentCleaner** is a Python script that automates the process of identifying and removing torrents that contain suspicious files (like `.zipx` or `.lnk`) from your Transmission download client. This ensures that unwanted or potentially harmful files are filtered out and deleted during the download process, keeping your system clean.

## Features

- Fetches the list of torrents from **Sonarr**'s queue.
- Identifies torrents managed by **Transmission**.
- Inspects torrent contents to find suspicious file extensions (`.zipx` or `.lnk`).
- Automatically removes torrents containing suspicious files.
- Deletes associated files on disk using Transmission's API.

## Requirements

- **Sonarr** API key and URL
- **Transmission** URL and credentials (if required)
- Python 3.x
- Python packages: `requests`

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/adelatour11/torrentcleaner.git
    cd TorrentCleaner
    ```

2. Install the required dependencies:

    ```bash
    pip install requests
    ```

3. Set up your environment variables (or hardcode the values in the script):
    - Sonarr API key
    - Transmission username and password (if authentication is required)
    - Hostnames and ports for Sonarr and Transmission

    ```python
    sonarr_host = 'XXXX'  # Update with your actual Sonarr host (e.g., 'localhost', '192.168.1.10', etc.)
    sonarr_port = '8989'  # Update with the actual port where Sonarr is running
    sonarr_url = f'http://{sonarr_host}:{sonarr_port}/api/v3/queue'
    sonarr_api_key = 'XXXX'  # Replace with your actual Sonarr API key

    transmission_url = 'http://XXXX:9091/transmission/rpc'  # Replace with your Transmission host and port
    transmission_username = 'username'  # If Transmission has authentication
    transmission_password = 'password'
    ```

## Usage

Once configured, you can run the script to automatically check for torrents with `.zipx` or `.lnk` files and remove them from Transmission.

1. Run the script:

    ```bash
    python sonarr_queue_clearner.py
    ```

2. The script will:
    - Fetch all torrents from Sonarr's queue.
    - Inspect the files in each torrent.
    - If any `.zipx` or `.lnk` files are found, the torrent will be removed and the files deleted.

## Example Output

```bash
Checking torrent contents for: TVShow.S02E08
Identified suspicious file: TVShow.S02E08/TVShow.S02E08.zipx. Marking download for removal...
Successfully removed download XXXX from Sonarr's queue.
```

## Customization

You can modify the file types that trigger removal by editing the `filename.endswith()` checks in the script:

```python
if filename.endswith('.zipx') or filename.endswith('.lnk'):
```

## Contributing

Feel free to contribute by submitting a pull request or opening an issue. All contributions and suggestions are welcome.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
