import asyncio
import time
import utils
import aiohttp
import json
import os
import skyblock

dbpassword = os.getenv('dbpassword')

seconds_in_an_hour = 3600

async def get_auction_items(hours_back=24, min_count=5):
	async with aiohttp.ClientSession() as s:
		async with s.get('https://hypixel-skyblock-get-database.mat1.repl.co/averages') as r:
			return await r.json()

async def update_profile_cache(profile, key):
	bank = profile.get('bank') or 0
	# list with all the ids of the profile members
	member_uuids = [member['uuid'] for member in profile['members']]
	# uuid of the profile
	uuid = profile['uuid']
	unique_minions = profile['minion_count']

	unclaimed_auctions = await skyblock.get_unclaimed_auctions_total(uuid, key=key)

	money = bank + unclaimed_auctions

	async with aiohttp.ClientSession() as s:
		async with s.post('https://hypixel-skyblock-leaderboards.matdoes.dev/update-profile-cache', data={
			'password': dbpassword,
			'bank': money,
			'members': ','.join(member_uuids),
			'uuid': uuid,
			'unique_minions': unique_minions
		}) as r:
			await r.text()

	for member in profile['members']:
		await update_player_cache(
			uuid,
			member
		)

async def update_player_cache(profile_uuid, player):
	stats = dict(player.get('raw_stats', {}))
	total_xp = 0
	total_kills = 0
	total_kills_1 = 0
	total_kills_2 = 0
	total_kills_3 = 0
	total_kills_4 = 0
	for slayer in player['slayers']:
		xp = slayer['xp']
		# add the xp from the current boss to the total xp
		total_xp += xp
		slayer_name = slayer['name']
		stats[f'slayer_{slayer_name}_xp'] = xp


		slayer_kills_1 = slayer['kills_tier_1']
		slayer_kills_2 = slayer['kills_tier_2']
		slayer_kills_3 = slayer['kills_tier_3']
		slayer_kills_4 = slayer['kills_tier_4']

		total_slayer_kills = slayer_kills_1 + slayer_kills_2 + slayer_kills_3 + slayer_kills_4

		stats[f'slayer_{slayer_name}_total_kills'] = total_slayer_kills
		stats[f'slayer_{slayer_name}_kills_1'] = slayer_kills_1
		stats[f'slayer_{slayer_name}_kills_2'] = slayer_kills_2
		stats[f'slayer_{slayer_name}_kills_3'] = slayer_kills_3
		stats[f'slayer_{slayer_name}_kills_4'] = slayer_kills_4

		total_kills += total_slayer_kills
		total_kills_1 += slayer_kills_1
		total_kills_2 += slayer_kills_2
		total_kills_3 += slayer_kills_3
		total_kills_4 += slayer_kills_4

	stats['slayer_total_kills'] = total_kills
	stats['slayer_total_kills_1'] = total_kills_1
	stats['slayer_total_kills_2'] = total_kills_2
	stats['slayer_total_kills_3'] = total_kills_3
	stats['slayer_total_kills_4'] = total_kills_4
	stats['slayer_total_xp'] = total_xp
	for skill_name in player['skills_xp']:
		skill_xp = player['skills_xp'][skill_name]
		stats['skill_xp_' + skill_name] = skill_xp

	json_data = json.dumps({
		'password': dbpassword,
		'profile': profile_uuid,
		'uuid': player['uuid'],
		'stats': stats
	})
	async with aiohttp.ClientSession() as s:
		async with s.post('https://hypixel-skyblock-leaderboards.matdoes.dev/update_user_cache', data=json_data) as r:
			await r.text()

async def get_top_profiles_by(stat, limit=10):
	async with aiohttp.ClientSession() as s:
		async with s.get(f'https://hypixel-skyblock-leaderboards.matdoes.dev/leaderboard/profiles/{stat}?limit={limit}') as r:
			json_data = await r.json()
			return json_data

async def get_top_users_by_stat(stat, limit=10):
	async with aiohttp.ClientSession() as s:
		async with s.get(f'https://hypixel-skyblock-leaderboards.matdoes.dev/leaderboard/stat/{stat}?limit={limit}') as r:
			json_data = await r.json()
			return json_data

async def get_profile_leaderboard_position(uuid):
	async with aiohttp.ClientSession() as s:
		async with s.get(f'https://hypixel-skyblock-leaderboards.matdoes.dev/leaderboard/bank/{uuid}') as r:
			return await r.json()

async def get_profile_stat_leaderboard_position(stat, profile, uuid):
	async with aiohttp.ClientSession() as s:
		async with s.get(f'https://hypixel-skyblock-leaderboards.matdoes.dev/leaderboard/stat/{stat}/{profile}/{uuid}') as r:
			return await r.json()

# async def update_player(data):
# 	basic_player_cache