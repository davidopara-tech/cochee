import requests
import json

URL = "https://fantasy.premierleague.com/api/bootstrap-static/"

response = requests.get(URL)

print("Status", response.status_code)

data = response.json()

print("Players:" , len(data["elements"]))
print("Teams:", len(data["teams"]))
print("Gameweeks:" , len(data["events"]))

#Show one player so we can see the shape
p = data["elements"][0]
print("\nSample player:")
print(json.dumps({
    "id": p["id"],
    "name": p["web_name"],
    "position": p["element_type"],
    "price": p["now_cost"],
    "form": p["form"],
    "ict_index": p["ict_index"],
    "expected_goals": p["expected_goals"],
    "yellow_cards": p["yellow_cards"],
    "chance_of_playing_this_round": p["chance_of_playing_this_round"],
    "penalties_order": p["penalties_order"],
}, indent=2))