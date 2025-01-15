from collections import defaultdict
import json

data = [
    {"enrollid": 1, "name": "", "time": "2024-12-14 10:55:37", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 1, "name": "", "time": "2024-12-14 11:11:59", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 2, "name": "Tendresse ASA", "time": "2024-12-14 11:35:07", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 1, "name": "", "time": "2024-12-14 11:49:57", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 2, "name": "Tendresse ASA", "time": "2024-12-14 11:50:52", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 2, "name": "Tendresse ASA", "time": "2024-12-14 11:54:11", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 2, "name": "Tendresse ASA", "time": "2024-12-14 11:57:26", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 1, "name": "", "time": "2024-12-14 12:03:25", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 1, "name": "", "time": "2024-12-14 12:06:10", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 1, "name": "", "time": "2024-12-14 12:18:34", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 1, "name": "", "time": "2024-12-14 12:19:53", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 3, "name": "teddy", "time": "2024-12-27 11:23:34", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 3, "name": "teddy", "time": "2024-12-27 15:16:47", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 3, "name": "teddy", "time": "2025-01-06 18:08:36", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 3, "name": "teddy", "time": "2025-01-06 18:25:49", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 3, "name": "teddy", "time": "2025-01-08 12:11:43", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 3, "name": "teddy", "time": "2025-01-08 12:31:59", "mode": 1, "inout": 0, "event": 0},
    {"enrollid": 3, "name": "teddy", "time": "2025-01-08 12:44:07", "mode": 1, "inout": 0, "event": 0},
    {"enrollid": 3, "name": "teddy", "time": "2025-01-08 12:47:32", "mode": 8, "inout": 0, "event": 0},
    {"enrollid": 3, "name": "teddy", "time": "2025-01-08 12:52:55", "mode": 8, "inout": 0, "event": 0}
]

grouped_data = defaultdict(list)
for item in data:
    grouped_data[item['enrollid']].append(item)

# Keep only min and max time for each enrollid
final_data = {}
for enrollid, items in grouped_data.items():
    times = [item['time'] for item in items]
    min_time = min(times)
    max_time = max(times)
    final_data[enrollid] = {
        "min_time": min_time,
        "max_time": max_time
    }

print(json.dumps(final_data, indent=4))
