import gzip
import base64
import struct

def TAG_End(b):
	return None, b

def TAG_byte(b):
	return b[0], b[1:]

def TAG_Short(b): # signed
	return struct.unpack('>h', b[:2])[0], b[2:]

def TAG_Short_unsigned(b): # unsigned
	return struct.unpack('>H', b[:2])[0], b[2:]

def TAG_Int(b): # signed
	return struct.unpack('>i', b[:4])[0], b[4:]

def TAG_Long(b): # signed
	return struct.unpack('>q', b[:8])[0], b[8:]

def TAG_Float(b): # signed
	return struct.unpack('>f', b[:4])[0], b[4:]

def TAG_Double(b): # signed
	return struct.unpack('>d', b[:8])[0], b[8:]

def TAG_Byte_Array(b):
	length, b = TAG_Int(b)
	
	items = []
	for _ in range(length):
		item, b = TAG_byte(b)
		items.append(item)
	return bytes(items), b

def TAG_String(b):
	length, b = TAG_Short_unsigned(b)
	value = b[:length]
	b = b[length:]
	return value, b

def TAG_List(b, use_binary=False): # nameless
	tag_type, b = b[0], b[1:]
	length, b = TAG_Int(b)
	values = []
	for _ in range(length):
		if tag_type in {9, 10}:
			value, b = tags[tag_type](b, use_binary=use_binary)
		else:
			value, b = tags[tag_type](b)
		values.append(value)
	return values, b

def TAG_Compound(b, use_binary=False): # named list (basically a dict)
	output = {}
	value = True
	while b:
		tag_type, b = TAG_byte(b)
		if tag_type == 0:
			break
		else:
			tag_name, b = TAG_String(b)
			if tag_type in {9, 10}:
				value, b = tags[tag_type](b, use_binary=use_binary)
			else:
				value, b = tags[tag_type](b)
			if not use_binary:
				tag_name = tag_name.decode()
			output[tag_name] = value
	return output, b

def TAG_Int_Array(b):
	print('int array')

def TAG_Long_Array(b):
	print('long array')

tags = ( # ordered
	TAG_End, # 0
	TAG_byte, # 1
	TAG_Short, # 2
	TAG_Int, # 3
	TAG_Long, # 4
	TAG_Float, # 4
	TAG_Double, # 6
	TAG_Byte_Array, # 7
	TAG_String, # 8
	TAG_List, # 9
	TAG_Compound, # 10
	TAG_Int_Array, # TODO
	TAG_Long_Array, # TODO
)


def read_nbt(nbt, binary=False):
	nbt = gzip.decompress(nbt)
	output = TAG_Compound(nbt, use_binary=binary)[0]
	return output

def read_b64_nbt(b64_nbt):
	return read_nbt(base64.b64decode(b64_nbt))
