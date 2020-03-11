import clean
import aiohttp
import apikeys
from utils import hashabledict
import asyncio
import time
import mojang
import errors
import database as db
import utils

skyblock_epoch = 1560275700

queue = []

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

async def profile_name_to_uuid(player, profile_name, key):
	if check_is_uuid(player):
		player_uuid = player
	else:
		player_uuid = await username_to_uuid(player, key)
	profile_name = profile_name.title()
	if (player_uuid, profile_name) in Caches.profile_name_to_uuid_cache:
		return Caches.profile_name_to_uuid_cache[(player_uuid, profile_name)]
	profiles_data = await fetch_profiles(player_uuid, key)
	for profile in profiles_data:
		if profile['name'] == profile_name:
			return profile['uuid']
	return

cache_paths = {
	'player': 600,
	'skyblock/profile': 180,
	'skyblock/auction': 60
}
caches = {}
# example: caches.180.skyblock/profile.{uuid:123} = {'asdf': 'asdf'}

async def add_to_cache(path, kwargs, data):
	cache_time_seconds = cache_paths[path]
	if cache_time_seconds not in caches:
		caches[cache_time_seconds] = {}
	if path not in caches[cache_time_seconds]:
		caches[cache_time_seconds][path] = {}
	caches[cache_time_seconds][path][hashabledict(kwargs)] = data
	if path == 'player' and 'name' in kwargs:
		uuid = data['player']['uuid']
		await add_to_cache('player', {'uuid': uuid}, data)

async def make_request(path, key, fast=False, only_cached=False, lazy=False, **kwargs):
	global caches
	original_kwargs = kwargs
	for cache_time_seconds in caches:
		for cache_path in caches[cache_time_seconds]:
			if hashabledict(original_kwargs) in caches[cache_time_seconds][cache_path]:
				if cache_path == path:
					return caches[cache_time_seconds][cache_path][hashabledict(original_kwargs)]
	if lazy: return

	keys_joined = key
	keys = keys_joined.split(',')
	if len(keys) > 1:
		key = await apikeys.find_working_key(keys)
	if key:
		kwargs = {'key': key, **kwargs}
	async with aiohttp.ClientSession() as s:
		async with s.get(
			f'https://api.hypixel.net/{path}',
			params=kwargs
		) as r:
			data = await r.json()
			if data.get('throttle'):
				key_usage = float('inf')
				apikeys.set_usage(key, key_usage)
				if 'key' in kwargs: del kwargs['key']
				return await make_request(path, keys_joined, **kwargs)
			else:
				apikeys.add_one(key)
	if path == 'player' and data['player'] is None:
		raise errors.InvalidUser()
	if path in cache_paths:
		await add_to_cache(path, original_kwargs, data)
	return data

async def fetch_player_raw(user, key, lazy=False):
	if check_is_uuid(user):
		r = await make_request('player', uuid=user, key=key, lazy=lazy)
	else:
		r = await make_request('player', name=user, key=key, lazy=lazy)
	return r

async def fetch_profile_raw(uuid, key):
	r = await make_request('skyblock/profile', profile=uuid, key=key)
	return r

async def fetch_players_auctions_raw(uuid, key):
	r = await make_request('skyblock/auction', profile=uuid, key=key)
	return r


async def fetch_player(user, key, lazy=False):
	user_data_raw = await fetch_player_raw(user, key, lazy=lazy)
	user_data = clean.clean_player(user_data_raw)
	if user_data:
		username = user_data['username']
		uuid = user_data['uuid']
		Caches.username_to_uuid_cache[username] = uuid
	else:
		if utils.is_uuid(user):
			username = await mojang.get_username_from_uuid(user)
			uuid = user
		else:
			uuid = await mojang.get_uuid_from_username(user)
			username = user
		user_data = {
			'uuid': uuid,
			'username': username,
			'rank': None,
			'rank_display': None,
			'rank_color_hex': None,
		}

	return user_data

def add_profiles_to_cache(player_uuid, profile_data):
	for profile in profile_data:
		profile_uuid = profile['uuid']
		profile_name = profile['name']
		Caches.profile_name_to_uuid_cache[(player_uuid, profile_name)] = profile_uuid

async def fetch_profile_members(
	uuid, key,
	lazy=True
):
	profile_data = await fetch_full_profile(uuid, key)
	if not profile_data: return ()
	profile_members = []
	for profile_member in profile_data['members']:
		member_uuid = profile_member['uuid']
		member_player_data = await fetch_player(member_uuid, key, lazy=lazy)
		shorter_data = {
			'uuid': member_uuid,
			'online': profile_member['online'],
			'last_save': profile_member['last_save']
		}
		if member_player_data:
			shorter_data.update(member_player_data)
		else:
			username = await mojang.get_username_from_uuid(member_uuid)
			shorter_data['username'] = username
		profile_members.append(shorter_data)
	return profile_members

async def fetch_profiles(
	user,
	key,
	show_profile_members=True,
):
	user_data_raw = await fetch_player_raw(user, key)
	player_uuid = user_data_raw['player']['uuid']
	profiles_data = clean.clean_profiles(user_data_raw)
	if not profiles_data: return []
	if show_profile_members:
		last_save_profile_time = 0
		last_save_profile_pos = None
		for i, profile in enumerate(profiles_data):
			is_online = False
			profile_members = await fetch_profile_members(profile['uuid'], key)
			for member in profile_members or ():
				if member['uuid'] == player_uuid:
					is_online = member['online']
					if member['last_save'] >= last_save_profile_time:
						last_save_profile_time = member['last_save']
						last_save_profile_pos = i
			profiles_data[i]['online'] = is_online
			profiles_data[i]['members'] = profile_members
			profiles_data[i]['active'] = False
		profiles_data[last_save_profile_pos]['active'] = True
	add_profiles_to_cache(player_uuid, profiles_data)
	return profiles_data

async def fetch_player_and_profiles(user, key, show_profile_members=True, lazy=False):
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
	profile = await clean.clean_profile(data)
	if uuid == 'cb7608d414134bb3812bc0566664c771':
		print('BRUH')
	queue.append(db.update_profile_cache(profile, key))
	return profile

async def fetch_profile_member(user, profile, key):
	if check_is_uuid(user):
		user_uuid = user
	else:
		user_uuid = await username_to_uuid(user, key)

	if check_is_uuid(profile):
		profile_uuid = profile
	else:
		profile_uuid = await profile_name_to_uuid(user_uuid, profile, key)
		
	player_data = await fetch_player(user_uuid, key)

	data = await fetch_profile_raw(profile_uuid, key)
	if data['profile'] is None:
		members = {}
	else:
		members = data['profile']['members']
	if user_uuid in members:
		profile_member = members[user_uuid]
	else:
		profile_member = None
	
	profiles = await fetch_profiles(user_uuid, key, show_profile_members=False)
	return await clean.clean_one_member(data, user_uuid, player_data=player_data, profiles=profiles)

async def fetch_player_auctions_from_uuid(player_uuid, key, active_only=False):
	auctions_data_raw = await fetch_players_auctions_raw(player_uuid, key)
	auctions = []
	for auction_data_raw in auctions_data_raw['auctions']:
		auction = clean.clean_auction(auction_data_raw)
		if not active_only or auction['active']:
			auctions.append(auction)
	return auctions

async def fetch_profile_auctions_from_uuid(profile_uuid, key, active_only=False):
	profile_members = await fetch_profile_members(
		profile_uuid, key
	)
	all_auctions = []
	for member in profile_members:
		player_uuid = member['uuid']
		player_auctions = await fetch_player_auctions_from_uuid(player_uuid, key, active_only=active_only)
		all_auctions.extend(player_auctions)
	return all_auctions


async def fetch_player_auctions(player, profile, key, active_only=False):
	profile_uuid = await profile_name_to_uuid(player, profile, key)
	return await fetch_player_auctions_from_uuid(profile_uuid, key, active_only=active_only)
	

async def clear_caches():
	await asyncio.sleep(1 - time.time() % 1)
	while True:
		await asyncio.sleep(1)
		current_time = int(time.time())
		for cached_time in dict(caches):
			if current_time % cached_time == 0:
				del caches[cached_time]

async def get_unclaimed_auctions_total(profile_id_or_username, profile_name=None, *, key):
	if profile_name is None:
		profile_id = profile_id_or_username
		auctions = await fetch_profile_auctions_from_uuid(profile_id, key)
	else:
		username = profile_id_or_username
		auctions = await fetch_profile_auctions_from_uuid(username, profile_name, key)
	total_unclaimed_coins = 0
	for auction in auctions:
		if not auction['claimed']:
			total_unclaimed_coins += auction['highest_bid_amount']
	return total_unclaimed_coins

async def queue_forever():
	global queue
	while True:
		if queue:
			try:
				await queue.pop()
			except Exception as e:
				print('queue error', type(e), e)
		# await asyncio.sleep(2)

asyncio.ensure_future(clear_caches())
asyncio.ensure_future(queue_forever())