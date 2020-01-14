from aiohttp import web
import skyblock
import json

routes = web.RouteTableDef()

class JsonEncoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, bytes): 
			return obj.decode()
		return json.JSONEncoder.default(self, obj)

def json_dumps(data):
	return json.dumps(data, cls=JsonEncoder)

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

		print('bruh')
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
	show_profiles = request.query.get('profiles', True)
	show_profile_members = request.query.get('profile_members', True)
	if show_profiles:
		player_data = await skyblock.fetch_player_and_profiles(user, request.key, show_profile_members=show_profile_members)
	else:
		player_data = await skyblock.fetch_player(user, request.key)
	return player_data

@routes.get('/player/{user}/{profile}')
@requires_key
async def fetch_user_profiles(request):
	user = request.match_info['user']
	profile = request.match_info['profile']
	return await skyblock.fetch_profile_member(user, profile, request.key)

@routes.get('/full_profile/{uuid}')
@requires_key
async def fetch_full_profile(request):
	uuid = request.match_info['uuid']
	return await skyblock.fetch_full_profile(uuid, request.key)


@web.middleware
async def middleware(request, handler):
	request.key = request.query.get('key')
	resp = await handler(request)
	if isinstance(resp, (dict, list)) or resp is None:
		resp = json_response(resp)
	return resp

app = web.Application(
	middlewares=[middleware]
)
app.add_routes(routes)
web.run_app(app)
