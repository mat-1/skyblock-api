import json
import nbt

with open('rank_colors.json', 'r') as f:
	rank_colors = json.loads(f.read())

with open('rank_real_names.json', 'r') as f:
	rank_real_names = json.loads(f.read())

with open('inventories.json', 'r') as f:
	inventories = json.loads(f.read())

def clean_profiles(data):
	output = []
	player = data['player']
	if player is None: return
	skyblock_profiles_raw = player['stats']['SkyBlock']['profiles']
	for profile in skyblock_profiles_raw.values():
		output.append({
			'uuid': profile['profile_id'],
			'name': profile['cute_name'],
		})
	return output

def clean_player(data):
	player = data['player']
	if player is None: return
	output = {
		'uuid': player['uuid'],
		'username': player['displayname'],
		'rank': get_player_rank(player),
		'rank_display': get_formatted_rank(player)
	}
	return output

def get_player_rank_raw(data):
	rank_name = None

	package_rank = data.get('packageRank')
	new_package_rank = data.get('newPackageRank')
	monthly_package_rank = data.get('monthlyPackageRank')
	rank = data.get('rank')

	if rank not in {None, 'NORMAL'}:
		return rank
	elif monthly_package_rank not in {None, 'NONE'}:
		return monthly_package_rank
	elif new_package_rank not in {None, 'NONE'}:
		return new_package_rank
	elif package_rank not in {None, 'NONE'}:
		return package_rank

def get_player_rank(data):
	rank_raw = get_player_rank_raw(data)
	if rank_raw in rank_real_names:
		return rank_real_names[rank_raw]
	rank_raw = rank_raw.replace('_PLUS', '+')
	return rank_raw

def get_formatted_rank(data):
	rank_prefix = data.get('prefix')
	if rank_prefix: return rank_prefix
	rank_name = get_player_rank(data)
	if not rank_name: return
	rank_color = rank_colors.get(rank_name, '7')
	return f'§{rank_color}[{rank_name}]'

def clean_item(data):
	if not data: return
	data_tag = data['tag']
	data_attributes = data_tag['ExtraAttributes']
	data_display = data_tag['display']
	showing_enchant_glint = bool(data_tag.get('ench'))
	
	output = {
		**data_attributes,
		'old_id': data['id'],
		'count': data['Count'],
		'name_display': data_display['Name'],
		'lore': data_display['Lore'],
		'enchant_glint': showing_enchant_glint
	}
	return output

def clean_inventory(data):
	if not data: return
	inventory_data_raw = data['data']
	if not inventory_data_raw: return
	inventory_data = nbt.read_b64_nbt(inventory_data_raw)
	items = inventory_data['']['i']
	return list(map(clean_item, items))

def clean_profile(data):
	profile = data['profile']
	members_list = []
	for member_uuid in profile['members']:
		member_data = profile['members'][member_uuid]
		members_list.append(clean_profile_member(member_data, member_uuid))
	bank = profile.get('banking', {}).get('balance')
	output = {
		'uuid': profile['profile_id'],
		'members': members_list,
		'bank': bank
	}
	return output

def choose_category(raw_stat_name):
	categories = {
		'kills': 'kills',
		'deaths': 'deaths',
		'items_fished': 'fishing',
		'auctions': 'auctions',
	}
	for category in categories:
		if raw_stat_name.startswith(f'{category}_') or raw_stat_name == category:
			if raw_stat_name == category:
				stat_name = 'total'
			else:
				stat_name = raw_stat_name[len(category) + 1:]
			return categories[category], stat_name
	return 'misc', raw_stat_name

def clean_profile_member(data, member_uuid):
	output = {
		'uuid': member_uuid,
		'purse': data['coin_purse'],
		'fairy_souls': data['fairy_souls_collected'],
		'inventories': {},
		'stats': {},
		'objectives': [],
		'quests': [],
	}
	for inventory_raw_name in inventories:
		inventory_new_name = inventories[inventory_raw_name]
		inventory_raw = data.get(inventory_raw_name)
		output['inventories'][inventory_new_name] = clean_inventory(inventory_raw)
	for raw_stat_name in data['stats']:
		category, name = choose_category(raw_stat_name)
		stat_value = data['stats'][raw_stat_name]
		if category not in output['stats']:
			output['stats'][category] = {}
		output['stats'][category][name] = stat_value
	for raw_objective_name in data['objectives']:
		raw_objective_data = data['objectives'][raw_objective_name]
		output['objectives'].append({
			'name': raw_objective_name,
			'completed': raw_objective_data['status'] == 'COMPLETE',
		})
	for raw_quest_name in data['quests']:
		raw_quest_data = data['quests'][raw_quest_name]
		output['objectives'].append({
			'name': raw_quest_name,
			'completed': raw_quest_data['status'] == 'COMPLETE',
		})

	return output

def clean_one_member(data, member_uuid):
	profile = data['profile']
	members = profile['members']
	member_data_raw = members[member_uuid]
	member_data = clean_profile_member(member_data_raw, member_uuid)
	bank = profile.get('banking', {}).get('balance')
	output = {
		'player': member_data,
		'bank': bank
	}
	return output