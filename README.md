# Testing Branch - Extended Filtering

See main branch readme for general info. 

This branch is to test additional filtering ased on torrent status. 

**WARNING - This is untested code and will be subject to change.**

The changes will check sonnar/radarr API and torrents that are in "warning" state for greater than XXX minutes will be removed.
**IMPORTANT** - Age is based on torrent age, not the time the torrent has been an a warning state. The API does not provide any way to query the time the torrent has been in a bad state and at current, the cleaner script does not have any non volatime storage support to store values. This should still be workable.

## Relavant new config variables:

```python
remove_warning_downloads = True  # If true, any download that has been in the queue in warned state and for X time (see below) will be removed
warning_time_threshold_minutes = 60 * 24  # Time in minutes a download must be in warned state before being removed if Remove_Warning_Downloads is True
block_error_torrent_on_removal = False  # If true, any torrent removed due to being in a warning state will be blocked from being downloaded again
```


Track testing results and discussion in the issues thread with this request.
