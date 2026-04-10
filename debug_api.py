"""
Quick debug: print raw Synoptic API response for ENTW1.
Run from project root: python3 debug_api.py
"""
import requests, json
from datetime import datetime, timedelta

TOKEN = 'accc7bd46f1e4e98aebe794a4ab64d5c'

end_dt = datetime(2026, 4, 9)
start_dt = end_dt - timedelta(days=30)

params = {
    'token': TOKEN,
    'stid': 'TT246',   # ENTIAT, WA — verified in Synoptic API
    'start': start_dt.strftime('%Y%m%d%H%M'),
    'end': end_dt.strftime('%Y%m%d%H%M'),
    'vars': 'air_temp,relative_humidity,wind_speed,wind_direction',
    'units': 'english',
    'obtimezone': 'local',
    'output': 'json',
}

r = requests.get('https://api.synopticdata.com/v2/stations/timeseries', params=params, timeout=30)
data = r.json()

print('=== SUMMARY ===')
print(json.dumps(data.get('SUMMARY', {}), indent=2))

stations = data.get('STATION', [])
print(f'\nSTATION objects returned: {len(stations)}')

if stations:
    stn = stations[0]
    print(f'\nStation ID: {stn.get("STID")}')
    print(f'Station Name: {stn.get("NAME")}')
    obs = stn.get('OBSERVATIONS', {})
    print(f'\nObservation keys: {list(obs.keys())}')
    times = obs.get('date_time', [])
    print(f'Timestamps: {len(times)}')
    if times:
        print(f'First: {times[0]}')
        print(f'Last:  {times[-1]}')
        # Show first row of each variable
        for key in obs:
            if key != 'date_time' and obs[key]:
                print(f'{key}: first value = {obs[key][0]}')
else:
    print('\nFull response:')
    print(json.dumps(data, indent=2)[:2000])