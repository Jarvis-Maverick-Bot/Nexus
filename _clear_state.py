import json
with open(r'D:\Projects\Nexus\governance\data\collab_state.json', 'w') as f:
    json.dump({}, f)
print("cleared")