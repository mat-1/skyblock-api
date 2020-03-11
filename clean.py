import json
import nbt
import time
import utils
import skyblock

with open('rank_colors.json', 'r') as f:
	rank_colors = json.loads(f.read())

with open('rank_real_names.json', 'r') as f:
	rank_real_names = json.loads(f.read())

with open('inventories.json', 'r') as f:
	inventories = json.loads(f.read())

with open('collections.json', 'r') as f:
	collection_categories = json.loads(f.read())

color_symbol = '§'

def clean_profiles(data):
	output = []
	player = data['player']
	if player is None: return
	if 'stats' not in player:
		return
	if 'SkyBlock' not in player['stats']:
		return
	skyblock_profiles_raw = player['stats']['SkyBlock']['profiles']
	for profile in skyblock_profiles_raw.values():
		output.append({
			'uuid': profile['profile_id'],
			'name': profile['cute_name'],
		})
	return output

def clean_player(data):
	if not data: return
	player = data['player']
	if player is None: return
	output = {
		'uuid': player['uuid'],
		'username': player['displayname'],
		'rank': get_player_rank(player),
		'rank_display': get_formatted_rank(player),
		'rank_color_hex': get_rank_color(player),
		'discord': {
			'name': player.get('socialMedia', {}).get('links', {}).get('DISCORD'),
			'id': None
		}
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
	return 'NONE'

def get_player_rank(data):
	rank_raw = get_player_rank_raw(data)
	if rank_raw in rank_real_names:
		return rank_real_names[rank_raw]
	if rank_raw:
		rank_raw = rank_raw.replace('_PLUS', '+')
	return rank_raw

def get_formatted_rank(data):
	rank_prefix = data.get('prefix')
	if rank_prefix: return rank_prefix
	rank_name = get_player_rank(data)
	if rank_name == 'NONE': return ''

	rank_color = rank_colors.get(rank_name, '7')
	return f'{color_symbol}{rank_color}[{rank_name}]'

def get_rank_color(data):
	formatted_rank = get_formatted_rank(data)
	if formatted_rank is None: return utils.color_codes['7']
	found_symbol_position = formatted_rank.rfind(color_symbol)
	if found_symbol_position != -1:
		rank_color_char = formatted_rank[found_symbol_position + 1]
		return utils.color_codes[rank_color_char]
	return utils.color_codes['7']

def clean_color(color_raw):
	color = color_raw.split(b':')
	color = tuple(map(int, color))
	return color


def clean_item(data):
	if not data: return
	data_tag = data.get('tag', {})
	data_attributes = data_tag.get('ExtraAttributes', {})
	data_display = data_tag.get('display', {})
	showing_enchant_glint = bool(data_tag.get('ench'))
	if 'SkullOwner' in data_tag and 'Properties' in data_tag['SkullOwner']:
		skull_owner = data_tag['SkullOwner']['Properties']['textures'][0]['Value'].decode()
	else:
		skull_owner = None

	if 'color' in data_attributes:
		color = data_attributes['color']
		color = clean_color(color)
		data_attributes['color'] = color

	for item in dict(data_attributes):
		if item.endswith('_backpack_data'):
			data_attributes['backpack'] = clean_nbt(
				data_attributes[item],
				b64=False,
				multi=True
			)
			del data_attributes[item]

	output = {
		**data_attributes,
		'old_id': data['id'],
		'count': data['Count'],
		'damage': data['Damage'],
		'name_display': data_display.get('Name', '[unknown]'),
		'lore': data_display.get('Lore', ''),
		'enchant_glint': showing_enchant_glint,
		'skull_owner': skull_owner
	}
	return output

def clean_nbt(data, b64=True, multi=False):
	if b64:
		item_nbt = nbt.read_b64_nbt(data)
	else:
		item_nbt = nbt.read_nbt(data)
	items = item_nbt['']['i']
	if multi:
		return list(map(clean_item, items))
	else:
		item = items[0]
	
		return clean_item(item)

def clean_inventory(data):
	if not data: return
	inventory_data_raw = data['data']
	if not inventory_data_raw: return
	inventory_data = nbt.read_b64_nbt(inventory_data_raw)
	items = list(inventory_data['']['i'])
	return list(map(clean_item, items))

async def clean_profile(data):
	profile_raw = data.get('profile')
	if not profile_raw: return {}
	profile_id = profile_raw['profile_id']
	members_list = []
	all_minions = set()

	collection_tiers = None
	collection_contributors = {}

	for member_uuid in profile_raw['members']:
		member_data_raw = profile_raw['members'][member_uuid]
		member_data = clean_profile_member(member_data_raw, member_uuid)
		members_list.append(member_data)
		if 'crafted_generators' in member_data_raw:
			all_minions.update(member_data_raw['crafted_generators'])
		if 'unlocked_coll_tiers' in member_data_raw:
			collection_tiers = member_data_raw['unlocked_coll_tiers']
		if 'collection' in member_data_raw:
			for raw_collection in member_data_raw['collection']:
				collection_name = utils.fix_name(raw_collection)
				if collection_name not in collection_contributors:
					collection_contributors[collection_name] = {}
				collection_xp = member_data_raw['collection'][raw_collection]
				collection_contributors[collection_name][member_uuid] = collection_xp
	bank = profile_raw.get('banking', {}).get('balance')
	bank_history = profile_raw.get('banking', {}).get('transactions')
	
	output = {
		'uuid': profile_id,
		'members': members_list,
		'bank': bank,
		'bank_history': clean_bank_history(bank_history),
		'crafted_minions': clean_minions(all_minions),
		'minion_count': len(all_minions),
		'collections': await clean_collection_tiers(collection_tiers, collection_contributors),
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

def choose_collection_category(raw_collection_name):
	for category_name in collection_categories:
		if utils.fix_name(raw_collection_name) in collection_categories[category_name]:
			return category_name
	return 'other'

def clean_zone_name(zone_name_raw):
	return zone_name_raw

def clean_profile_member(data, member_uuid, player_data=None):
	output = {
		'uuid': member_uuid,
		'purse': data.get('coin_purse', 0),
		'fairy_souls': data.get('fairy_souls_collected', 0),
		'last_save': 0,
		'first_join': 0,
		'online': False,
		'inventories': {},
		'stats': {},
		'raw_stats': {},
		'objectives': [],
		'quests': [],
		'skills_xp': {},
		'visited_zones': [],
		'crafted_minions': [],
		'slayers': [],
		'collection_contributions': {}
	}
	last_save = data.get('last_save', 0) / 1000
	first_join = data.get('first_join', 0) / 1000
	output['last_save'] = last_save
	output['first_join'] = first_join
	output['online'] = time.time() - last_save < 180

	# raw stats
	for name in data.get('stats', ()):
		value = data['stats'][name]
		output['raw_stats'][name] = value

	for inventory_raw_name in inventories:
		inventory_new_name = inventories[inventory_raw_name]
		inventory_raw = data.get(inventory_raw_name)
		cleaned_inventory = clean_inventory(inventory_raw)
		if inventory_new_name == 'armor' and cleaned_inventory:
			cleaned_inventory = list(reversed(cleaned_inventory))
		output['inventories'][inventory_new_name] = cleaned_inventory

	# rename and organize stats
	for raw_stat_name in data.get('stats', ()):
		category, name = choose_category(raw_stat_name)
		stat_value = data['stats'][raw_stat_name]
		if category not in output['stats']:
			output['stats'][category] = {}
		output['stats'][category][name] = stat_value
	stats = dict(output['stats'])
	output['stats'] = {}
	stats_list = list(stats)
	if 'misc' in stats_list: # move misc to end
		stats_list.remove('misc')
		stats_list.append('misc')
	for category in stats_list:
		output['stats'][category] = stats[category]
	for category in output['stats']:
		stats = dict(output['stats'][category])
		output['stats'][category] = {}
		for stat_name in sorted(stats, key=stats.get, reverse=True):
			output['stats'][category][stat_name] = stats[stat_name]

	for raw_objective_name in data.get('objectives', ()):
		raw_objective_data = data['objectives'][raw_objective_name]
		output['objectives'].append({
			'name': raw_objective_name,
			'completed': raw_objective_data['status'] == 'COMPLETE',
		})
	for raw_quest_name in data.get('quests', ()):
		raw_quest_data = data['quests'][raw_quest_name]
		output['objectives'].append({
			'name': raw_quest_name,
			'completed': raw_quest_data['status'] == 'COMPLETE',
		})
	for data_item_key in data:
		if data_item_key.startswith('experience_skill_'):
			skill_name = data_item_key[17:]
			skill_xp = data[data_item_key]
			output['skills_xp'][skill_name] = skill_xp
	for slayer_boss_name in data.get('slayer_bosses', ()):
		raw_slayer_data = data['slayer_bosses'][slayer_boss_name]
		max_level = 0
		for level_name_raw in raw_slayer_data.get('claimed_levels', ()):
			level = int(level_name_raw.rsplit('_', 1)[1])
			if level > max_level:
				max_level = level

		output['slayers'].append({
			'name': slayer_boss_name,
			'xp': raw_slayer_data.get('xp', 0),
			'level': max_level,
			'kills_tier_1': raw_slayer_data.get('boss_kills_tier_0', 0),
			'kills_tier_2': raw_slayer_data.get('boss_kills_tier_1', 0),
			'kills_tier_3': raw_slayer_data.get('boss_kills_tier_2', 0),
			'kills_tier_4': raw_slayer_data.get('boss_kills_tier_3', 0),
		})
	for visited_zone_name_raw in data.get('visited_zones', ()):
		visited_zone_name = clean_zone_name(visited_zone_name_raw)
		output['visited_zones'].append(visited_zone_name)
	
	crafted_minions_raw = data.get('crafted_generators', ())

	output['crafted_minions'] = clean_minions(crafted_minions_raw)
	output['minion_count'] = len(crafted_minions_raw)
	if player_data:
		output['player'] = player_data
	return output

async def clean_one_member(data, member_uuid, player_data=None, profiles=None):
	profile_data = await clean_profile(data)
	member_uuids = []
	if profile_data and profile_data['members']:
		for member in profile_data['members']:
			member_uuids.append(member['uuid'])
		for member in profile_data['members']:
			if member['uuid'] == member_uuid:
				break
	else:
		return {}
	
	bank = profile_data.get('banking', {}).get('balance')
	profile_data['player'] = member
	if player_data:
		profile_data['player'].update(player_data)
		del profile_data['members']
	if profiles:
		profile_name = None
		for profile in profiles:
			if profile['uuid'] == profile_data['uuid']:
				profile_name = profile['name']
				break
		profile_data['name'] = profile_name
	profile_data['online'] = member['online']
	profile_data['members'] = {}
	for member_uuid in member_uuids:
		member = await skyblock.fetch_player(member_uuid, None, lazy=True)
		profile_data['members'][member_uuid] = member
	return profile_data

def clean_minions(data):
	minion_levels = {}
	top_minion_level = 11
	for minion_name_raw in data:
		# minions are formatted as MINION_NAME_LEVEL
		minion_name, minion_level = minion_name_raw.rsplit('_', 1)
		minion_level = int(minion_level)
		minion_name = minion_name.lower()
		if minion_name not in minion_levels:
			minion_levels[minion_name] = [False] * top_minion_level
		minion_levels[minion_name][minion_level - 1] = True
	return minion_levels

def clean_bank_history(data):
	if not data: return
	balance = 0
	previous_timestamp = 0
	previous_balance = 0
	output = []
	for transaction in data:
		action = transaction['action']
		amount = transaction['amount']
		timestamp = transaction['timestamp'] / 1000
		if action == 'DEPOSIT':
			balance += amount
		elif action == 'WITHDRAW':
			balance -= amount
			
		time_since_last_timestamp = timestamp - previous_timestamp
		if balance > previous_balance:
			previous_balance = balance
		if time_since_last_timestamp > 60 * 60 * 24:
			output.append({
				'balance': previous_balance,
				'timestamp': previous_timestamp or timestamp
			})
			previous_timestamp = timestamp
			previous_balance = balance

	return output


async def clean_collection_tiers(data, contributors):
	if not data: return

	# {category: {collection: value, ...}, ...}
	collection_categories = {}
	
	for minion_name_raw in data:
		# collections are formatted as COLLECTION_LEVEL
		collection_name, collection_level = minion_name_raw.rsplit('_', 1)
		collection_level = int(collection_level)
		collection_category = choose_collection_category(collection_name)
		collection_name = utils.fix_name(collection_name)


		# If it's not upgraded it'll be -1, so fix it to be 0
		if collection_level == -1:
			collection_level = 0

		if collection_category not in collection_categories:
			collection_categories[collection_category] = {}
		current_collection_level = collection_categories[collection_category].get(collection_name, {}).get('level', -1)
		if collection_level > current_collection_level:
			collection_data = {
				'level': collection_level,
				'contributors': {}
			}
			if collection_name in contributors:
				collection_contributors = contributors[collection_name]
				for member_uuid in collection_contributors:
					contributed = collection_contributors[member_uuid]
					collection_data['contributors'][member_uuid] = contributed
			collection_categories[collection_category][collection_name] = collection_data
	return collection_categories

def clean_auction(data):
	# only include wanted attributes
	end = data['end'] / 1000
	output = {
		'uuid': data['uuid'],
		'auctioneer': data['auctioneer'],
		'profile_id': data['profile_id'],
		'start': data['start'] / 1000,
		'end': end,
		'name': data['item_name'],
		'category': data['category'],
		'tier': data['tier'],
		'starting_bid': data['starting_bid'],
		'highest_bid_amount': data.get('highest_bid_amount', 0),
		'claimed': data['claimed'],
		'nbt': None,
		'active': time.time() < end
	}
	output['nbt'] = clean_nbt(data['item_bytes']['data'])
	return output