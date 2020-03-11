from utils import json_dumps
from aiohttp import web
import skyblock
import database
import mojang
import errors
import asyncio
import utils
import time
import json

print('bruh')

routes = web.RouteTableDef()

def json_response(data):
	return web.Response(
		text=json_dumps(data),
		content_type='application/json'
	)

def requires_key(func):
	def wrapper(*args, **kwargs):
		request = args[0]
		args = args[1:]

		if request.key is None:
			raise web.HTTPForbidden(
				text='Please provide API key'
			)
		return func(request, *args, **kwargs)
	return wrapper


@routes.get('/')
async def index(request):
	return {
		'ok': True
	}

@routes.get('/player/{user}')
@requires_key
async def fetch_player(request):
	user = request.match_info['user']
	show_profiles = request.query.get('profiles', 'true').lower() == 'true'
	lazy = request.query.get('lazy', 'false').lower() == 'true'
	show_profile_members = request.query.get('profile_members', 'true').lower() == 'true'
	if show_profiles:
		player_data = await skyblock.fetch_player_and_profiles(
			user,
			request.key,
			show_profile_members=show_profile_members,
			lazy=lazy
		)
	else:
		player_data = await skyblock.fetch_player(
			user,
			request.key,
			lazy=lazy
		)
	return player_data


@routes.get('/player/{user}/{profile}')
@requires_key
async def fetch_player_profile(request):
	user = request.match_info['user']
	profile = request.match_info['profile']
	return await skyblock.fetch_profile_member(user, profile, request.key)

@routes.get('/player/{user}/{profile}/auctions')
@requires_key
async def fetch_player_auctions(request):
	user = request.match_info['user']
	profile = request.match_info['profile']
	active_only = request.query.get('active_only', 'false') == 'true'
	return await skyblock.fetch_player_auctions(user, profile, request.key, active_only=active_only)

@routes.get('/player/{player_uuid}/auctions')
@requires_key
async def fetch_player_auctions_from_uuid(request):
	player_uuid = request.match_info['player_uuid']
	active_only = request.query.get('active_only', 'false') == 'true'

	return await skyblock.fetch_player_auctions_from_uuid(
		player_uuid,
		request.key,
		active_only=active_only
	)

@routes.get('/profile/{profile_uuid}/auctions')
@requires_key
async def fetch_player_auctions_from_uuid(request):
	profile_uuid = request.match_info['profile_uuid']
	active_only = request.query.get('active_only', 'false') == 'true'

	return await skyblock.fetch_player_auctions_from_uuid(
		profile_uuid,
		request.key,
		active_only=active_only
	)


@routes.get('/profile/{uuid}')
@requires_key
async def fetch_full_profile(request):
	uuid = request.match_info['uuid']
	return await skyblock.fetch_full_profile(uuid, request.key)


@routes.get('/username/{uuid}')
async def fetch_username(request):
	uuid = request.match_info['uuid']
	if len(uuid) != 32:
		raise errors.InvalidUUID()
	username = await mojang.get_username_from_uuid(uuid)
	return {
		'username': username
	}

@routes.get('/uuid/{username}')
async def fetch_uuid(request):
	username = request.match_info['username']
	uuid = await mojang.get_uuid_from_username(username)
	return {
		'uuid': uuid
	}

@routes.get('/leaderboard/{stat}')
async def fetch_uuid(request):
	stat_name = request.match_info['stat']
	limit = request.query.get('limit', 10)
	is_profile_stat = stat_name in utils.profile_stats
	players = []
	if is_profile_stat:
		raw_leaderboards = await database.get_top_profiles_by(stat_name, limit)
	else:
		raw_leaderboards = await database.get_top_users_by_stat(stat_name, limit)

	# {uuid: task, ...}
	player_data_tasks = {}
	for player in raw_leaderboards:
		if is_profile_stat:
			for user in player['members']:
				player_data_tasks[user] = skyblock.fetch_player(
					user,
					request.key,
					lazy=True
				)
		else:
			uuid = player['uuid']
			player_data_tasks[uuid] = skyblock.fetch_player(
				uuid,
				request.key,
				lazy=True
			)

	# {uuid: {data}, ...}
	player_datas = {}
	results = await asyncio.gather(*list(player_data_tasks.values()))
	for player_data in results:
		uuid = player_data['uuid']
		player_datas[uuid] = player_data

	for player in raw_leaderboards:
		if is_profile_stat:
			profile = player['_id']
			stat_value = player.get(stat_name)
			profile_members = []
			for user in player['members']:
				player_data = player_datas.get(user)
				profile_members.append(player_data)
			
			players.append({
				'profile': profile,
				'value': stat_value,
				'members': profile_members
			})

		else:
			uuid = player['uuid']
			stat_value = player['value']
			player_data = player_datas.get(uuid)

			players.append({
				'uuid': uuid,
				'profile': player['profile'],
				'value': stat_value,
				**player_data
			})
	return players


@web.middleware
async def middleware(request, handler):
	key = request.query.get('key')
	if not key:
		key = request.headers.get('key')
	request.key = key
	try:
		resp = await handler(request)
	except errors.SkyBlockError as e:
		resp = {
			'error': str(e.__class__.__name__)
		}
	if isinstance(resp, (dict, list)) or resp is None:
		resp = json_response(resp)
	return resp

app = web.Application(
	middlewares=[middleware],
)
app.add_routes(routes)
print('running app')
web.run_app(app, port=6969)
