import clean
import aiohttp

skyblock_epoch = 1560275700

queries_in_past_min = {}

def check_is_uuid(data):
	data = data.replace('-', '')
	if len(data) == 32:
		return True
	return False

class Caches:
	username_to_uuid_cache = {}
	profile_name_to_uuid_cache = {}

async def username_to_uuid(username, key):
	if username in Caches.username_to_uuid_cache:
		return Caches.username_to_uuid_cache[username]
	player_data = await fetch_player(username, key)
	return player_data['uuid']

async def profile_name_to_uuid(player_uuid, profile_name, key):
	profile_name = profile_name.title()
	if (player_uuid, profile_name) in Caches.profile_name_to_uuid_cache:
		return Caches.profile_name_to_uuid_cache[(player_uuid, profile_name)]
	profiles_data = await fetch_profiles(player_uuid, key)
	for profile in profiles_data:
		if profile['name'] == profile_name:
			return profile['uuid']
	return

async def make_request(path, key, **kwargs):
	if key:
		kwargs = {'key': key, **kwargs}
	async with aiohttp.ClientSession() as s:
		if key not in queries_in_past_min:
			queries_in_past_min[key] = 0
		queries_in_past_min[key] += 1
		async with s.get(
			f'https://api.hypixel.net/{path}',
			params=kwargs
		) as r:
			data = await r.json()
			if data.get('throttle'):
				queries_in_past_min[key] = 120
				return await make_request(path, **kwargs)
			return data

async def fetch_player_raw(user, key):
	if check_is_uuid(user):
		r = await make_request('player', uuid=user, key=key)
	else:
		r = await make_request('player', name=user, key=key)
	return r

async def fetch_profile_raw(uuid, key):
	r = await make_request('skyblock/profile', profile=uuid, key=key)
	return r


async def fetch_player(user, key):
	user_data_raw = await fetch_player_raw(user, key)
	user_data = clean.clean_player(user_data_raw)
	if user_data:
		username = user_data['username']
		uuid = user_data['uuid']
		Caches.username_to_uuid_cache[username] = uuid
	return user_data

def add_profiles_to_cache(player_uuid, profile_data):
	for profile in profile_data:
		profile_uuid = profile['uuid']
		profile_name = profile['name']
		Caches.profile_name_to_uuid_cache[(player_uuid, profile_name)] = profile_uuid

async def fetch_profile_members(uuid, key):
	profile_data = await fetch_full_profile(uuid, key)
	profile_members = []
	for profile_member in profile_data['members']:
		profile_members.append(profile_member['uuid'])
	return profile_members

async def fetch_profiles(user, key, show_profile_members=True):
	user_data_raw = await fetch_player_raw(user, key)
	player_uuid = user_data_raw['player']['uuid']
	profiles_data = clean.clean_profiles(user_data_raw)
	if show_profile_members:
		for i, profile in enumerate(profiles_data):
			profile_members = await fetch_profile_members(profile['uuid'], key)
			profiles_data[i]['members'] = profile_members
	add_profiles_to_cache(player_uuid, profiles_data)
	return profiles_data

async def fetch_player_and_profiles(user, key, show_profile_members=True):
	user_data = await fetch_player(user, key)
	if user_data:
		profile_data = await fetch_profiles(
			user, key,
			show_profile_members=show_profile_members
		)
		user_data['profiles'] = profile_data
	return user_data


async def fetch_full_profile(uuid, key):
	data = await fetch_profile_raw(uuid, key)
	return clean.clean_profile(data)

async def fetch_profile_member(user, profile, key):
	if check_is_uuid(user):
		user_uuid = user
	else:
		user_uuid = await username_to_uuid(user, key)

	if check_is_uuid(profile):
		profile_uuid = profile
	else:
		profile_uuid = await profile_name_to_uuid(user_uuid, profile, key)

	data = await fetch_profile_raw(profile_uuid, key)
	members = data['profile']['members']
	profile_member = members[user_uuid]
	return clean.clean_one_member(data, user_uuid)
