"""
Discover available PNW RAWS stations for this Synoptic token.
Run: python3 find_stations.py
"""
import requests, json

TOKEN = 'accc7bd46f1e4e98aebe794a4ab64d5c'

# Search for RAWS stations in WA and OR by bounding box
params = {
    'token': TOKEN,
    'bbox': '-125,41.5,-115,49.5',   # PNW bounding box: lon_min,lat_min,lon_max,lat_max
    'network': '2',                   # 2 = RAWS network
    'status': 'active',
    'vars': 'air_temp,relative_humidity,wind_speed',
    'output': 'json',
}

print('Searching for RAWS stations in PNW bounding box...')
r = requests.get('https://api.synopticdata.com/v2/stations/metadata', params=params, timeout=30)
data = r.json()

summary = data.get('SUMMARY', {})
print(f"Response: {summary.get('RESPONSE_MESSAGE')}")
print(f"Stations found: {summary.get('NUMBER_OF_OBJECTS', 0)}\n")

stations = data.get('STATION', [])
if stations:
    print(f"{'ID':<12} {'Name':<30} {'State':<6} {'Lat':>8} {'Lon':>10} {'Elev(ft)':>10}")
    print('-' * 80)
    for s in sorted(stations, key=lambda x: (x.get('STATE',''), x.get('NAME',''))):
        print(f"{s.get('STID',''):<12} {s.get('NAME',''):<30} {s.get('STATE',''):<6} "
              f"{float(s.get('LATITUDE',0)):>8.3f} {float(s.get('LONGITUDE',0)):>10.3f} "
              f"{s.get('ELEVATION',''):>10}")
else:
    # Try without network filter — see what's available at all
    print('No RAWS stations found. Trying without network filter...')
    params2 = {
        'token': TOKEN,
        'state': 'WA,OR',
        'status': 'active',
        'vars': 'air_temp,relative_humidity,wind_speed',
        'limit': '20',
        'output': 'json',
    }
    r2 = requests.get('https://api.synopticdata.com/v2/stations/metadata', params=params2, timeout=30)
    data2 = r2.json()
    print(f"Response: {data2.get('SUMMARY',{}).get('RESPONSE_MESSAGE')}")
    print(f"Stations found: {data2.get('SUMMARY',{}).get('NUMBER_OF_OBJECTS',0)}\n")
    for s in data2.get('STATION', [])[:20]:
        print(f"{s.get('STID',''):<12} {s.get('NAME',''):<30} {s.get('STATE',''):<6} network={s.get('MNET_ID','')}")