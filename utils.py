import json

class JsonEncoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, bytes): 
			try: return obj.decode()
			except UnicodeDecodeError: return(str(obj))
		return json.JSONEncoder.default(self, obj)

class hashabledict(dict):
	def __hash__(self):
		return hash(tuple(sorted(self.items())))

def json_dumps(data):
	return json.dumps(data, cls=JsonEncoder)

def is_uuid(thing):
	return len(thing) >= 32

with open('bazaar_names.json', 'r') as f:
	bazaar_names = json.loads(f.read())

with open('collection_names.json', 'r') as f:
	collection_names = json.loads(f.read())

def fix_name(thing, category='bazaar'):
	fixed_names = {
		'collection': collection_names,
		'bazaar': bazaar_names,
	}.get(category, 'bazaar')
	thing = thing.lower()
	if thing in fixed_names:
		thing = fixed_names[thing]
	else:
		if thing in fixed_names:
			thing = fixed_names[thing]
	return thing

def unfix_name(thing, category='bazaar'):
	fixed_names = {
		'collection': collection_names,
		'bazaar': bazaar_names,
	}.get(category, 'bazaar')
	thing = thing.lower()
	for unfixed_name in fixed_names:
		fixed_name = fixed_names[unfixed_name]
		if fixed_name.lower() == thing:
			return unfixed_name.upper()
	return thing.upper()

color_codes = {
	'0': '#000000',
	'1': '#0000be',
	'2': '#00be00',
	'3': '#00bebe',
	'4': '#be0000', # red
	'5': '#be00be',
	'6': '#ffaa00', # gold
	'7': '#bebebe',
	'8': '#3f3f3f',
	'9': '#3f3ffe',
	'a': '#3ffe3f',
	'b': '#3ffefe',
	'c': '#fe3f3f',
	'd': '#fe3ffe',
	'e': '#fefe3f',
	'f': '#ffffff'
}

profile_stats = {
	'unique_minions',
	'bank'
}