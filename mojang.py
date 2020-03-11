import aiohttp
import time
import asyncio
import errors

cache = {}

async def get_username_from_uuid(uuid):
	if uuid in cache:
		if cache[uuid] is None:
			raise errors.InvalidUUID(uuid)
		return cache[uuid]['value']
	async with aiohttp.ClientSession() as s:
		r = await s.get(
			f'https://sessionserver.mojang.com/session/minecraft/profile/{uuid}'
		)
		content = await r.text()
		if not content:
			cache[uuid] = None
			raise errors.InvalidUUID(uuid)
		data = await r.json()
		if 'error' in data:
			return
		username = data['name']
		cache[uuid] = {
			'value': username,
			'time': time.time()
		}
	return username


async def get_uuid_from_username(username):
	username = username.lower()
	try:
		uuid = next(key for key, value in cache.items() if value['value'].lower() == username)
		return uuid
	except: pass
	async with aiohttp.ClientSession() as s:
		r = await s.get(
			f'https://api.mojang.com/users/profiles/minecraft/{username}'
		)
		content = await r.text()
		if not content:
			raise errors.InvalidUser(username)
		data = await r.json()
		if 'error' in data:
			return
		username = data['name']
		uuid = data['id']
		cache[uuid] = {
			'value': username,
			'time': time.time()
		}
	return uuid


async def clear_cache_periodically():
	while True:
		t = time.time()
		for uuid in dict(cache):
			if cache[uuid] is None or cache[uuid]['time'] < t - 120:
				del cache[uuid]
		await asyncio.sleep(120)
	
asyncio.ensure_future(clear_cache_periodically())