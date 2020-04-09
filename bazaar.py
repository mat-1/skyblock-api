import aiohttp
import errors
import utils


base_url = 'https://hypixel-skyblock-bazaar.mat1.repl.co/'

async def request(path):
	async with aiohttp.ClientSession() as s:
		r = await s.get(base_url + path)
		return await r.json()

async def get_products():
	products = []
	for product in await request('products'):
		products.append(utils.fix_name(product, 'bazaar'))
	return products

async def get_average_prices():
	r = await request('products/averages')
	output = {}
	for product in r:
		average = r[product]
		product_name = utils.fix_name(product, 'bazaar')
		output[product_name] = round(average, 2)
	return output

async def get_current_prices():
	r = await request('products/current')
	output = []
	for product in r:
		product_name = utils.fix_name(product['productId'], 'bazaar')
		output.append({
			'id': product_name,
			'buy_price': product['buyPrice'],
			'sell_price': product['sellPrice'],
			'buy_volume': product['buyVolume'],
			'sell_volume': product['sellVolume'],
			'average': round(product['average'], 2),
		})
	return output

async def get_product(name):
	product_id = utils.unfix_name(name, 'bazaar')
	data = await request(f'product/{product_id}')
	if not data:
		raise errors.InvalidItem(name)

	buy_summary_raw = data['buy_summary']
	sell_summary_raw = data['sell_summary']
	quick_status_raw = data['quick_status']
	week_historic_raw = data['week_historic']

	top_buy_orders = []
	top_sell_orders = []
	week_historic = []

	for order in buy_summary_raw:
		top_buy_orders.append({
			'amount': order['amount'],
			'price_per_unit': order['pricePerUnit'],
			'orders': order['orders'],
		})
	for order in sell_summary_raw:
		top_sell_orders.append({
			'amount': order['amount'],
			'price_per_unit': order['pricePerUnit'],
			'orders': order['orders'],
		})
	for point in week_historic_raw:
		week_historic.append({
			'timestamp': point['timestamp'] / 1000,
			'now_buy_volume': point['nowBuyVolume'],
			'now_sell_volume': point['nowSellVolume'],
			'buy_coins': point['buyCoins'],
			'buy_volume': point['buyVolume'],
			'buys': point['buys'],
			'sell_coins': point['sellCoins'],
			'sell_volume': point['sellVolume'],
			'sells': point['sells'],

			'buy_price': (point['sellCoins'] / point['buyVolume']) if point['buyVolume'] else 0,
			'sell_price': (point['buyCoins'] / point['sellVolume']) if point['sellVolume'] else 0
		})
	

	output = {
		'name': name,
		'id': product_id,

		'sell_price': quick_status_raw['buyPrice'],
		'sell_volume': quick_status_raw['buyVolume'],
		'sell_moving_week': quick_status_raw['buyMovingWeek'],
		'sell_orders': quick_status_raw['buyOrders'],
		'buy_price': quick_status_raw['sellPrice'],
		'buy_volume': quick_status_raw['sellVolume'],
		'buy_moving_week': quick_status_raw['sellMovingWeek'],
		'buy_orders': quick_status_raw['sellOrders'],

		'top_sell_orders': top_buy_orders,
		'top_buy_orders': top_sell_orders,
		'week_historic': week_historic,
	}
	return output
