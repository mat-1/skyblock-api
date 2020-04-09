import skyblock
import asyncio
import time

queries_in_past_min = {} # per key

default_limit = 120

def add_one(key):
	if key not in queries_in_past_min:
		set_usage(key, 0)
	queries_in_past_min[key] += 1
	
def set_usage(key, amount):
	queries_in_past_min[key] = amount
	
async def find_working_key(keys):
	for key in keys:
		if key in queries_in_past_min:
			key_usage = queries_in_past_min[key]
		else:
			key_usage = await get_key_uses(key)
			queries_in_past_min[key] = key_usage
		if key_usage >= 120:
			continue
		else:
			return key
	print('no key found')
			
async def get_key_uses(key):
	if key in queries_in_past_min: return queries_in_past_min[key]
	key_usage_raw = await skyblock.make_request('key', key)
	key_usage = key_usage_raw['record'].get('queriesInPastMin', 0)
	queries_in_past_min[key] = key_usage
	return key_usage
	
async def periodically_clear_queries_in_past_min():
	global queries_in_past_min
	await asyncio.sleep(60 - time.time() % 60)
	while True:
		queries_in_past_min = {}
		await asyncio.sleep(60)

asyncio.ensure_future(periodically_clear_queries_in_past_min())