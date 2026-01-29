# original from https://github.com/monkeyman192/No-Man-s-Audio-Suite/blob/new_bnkcompiler_test/BNKcompiler.py
# BNK_new bytes input and output and a few fixes by failsafe65
# program to pack a number of .wem files into a .bnk file

from struct import pack, unpack
from struct import error as struct_error
from os import path as os_path
from collections import OrderedDict as Odict
from io import BytesIO, BufferedReader

def fnvhash(s):
	s = s.lower()
	hval = 0x811c9dc5 # Magic value for 32-bit fnv1 hash initialisation.
	fnvprime = 0x01000193
	fnvsize = 2**32
	if not isinstance(s, bytes):
		s = s.encode("UTF-8", "ignore")
	for byte in s:
		hval = (hval * fnvprime) % fnvsize
		hval = hval ^ byte
	return hval

"""
.bnk file structure

			Data Index:
+0x000			0x4			char		DIDX		data index tag
+0x004			0x4			int			-			size of DIDX (multiple of 0xC)
				Data Index Entry (0xC chunks):
+0x000			0x4			int			-			audio file id (hashed version of name)
+0x004			0x4			int			-			relative file offset from start of DATA, 16 bytes aligned
+0x008			0x4			int			-			file size


"""

class BNK():
	""" New BNK class
	This class can be created from a bnk file and manipulated in such a way that extraction, addition, and (soon) replacement is possible
	"""
	def __init__(self, path = None, data = None, bytes = None):
		if data is None:
			if path is not None:
				_input = open(path, 'rb')
			elif bytes is not None:
				_input = BufferedReader(BytesIO(bytes))
			self.data = Odict()
			# first, let's just make sure we have been given a BNK file:
			if unpack('4s', _input.read(4))[0] == b'BKHD':
				# yep, we *should* be good...
				_input.seek(0)      # return to start
				# we go through the rest of the data and populate self.data
				self.cont = True     # tag to check whether or not to keep going
				while self.cont == True:
					self.read_bnk_chunk(_input)
			# now that we have the data all sorted, apply a bit of processing to it...
			# first, pass the DIDX data to the DATA data so that it can split its data into individual WEM files
			try:
				self.data['DATA'].split(self.data['DIDX'])
			except:
				# in this case we have no self.data['DATA']
				self.data['DATA'] = None
		else:
			self.data = data

	def __add__(self, other):
		# we need to check for empty DIDX and DATA section (HIRC shouldn't be empty ever...)
		try:
			combined_didx = self.data['DIDX'] + other.data['DIDX']
		except:
			if self.data['DIDX'] == None and other.data['DIDX'] == None:
				combined_didx = None
			elif self.data['DIDX'] == None and other.data['DIDX'] != None:
				combined_didx = other.data['DIDX']
			else:
				combined_didx = self.data['DIDX']
		try:
			combined_data = self.data['DATA'] + other.data['DATA']
		except:
			if self.data['DATA'] == None and other.data['DATA'] == None:
				combined_data = None
			elif self.data['DATA'] == None and other.data['DATA'] != None:
				combined_data = other.data['DATA']
			else:
				combined_data = self.data['DATA']
		combined_hirc = self.data['HIRC'] + other.data['HIRC']

		new_data = Odict()
		new_data.update({'BKHD': self.data['BKHD']})
		new_data.update({'DIDX': combined_didx})
		new_data.update({'DATA': combined_data})
		new_data.update({'HIRC': combined_hirc})

		new_BNK = BNK(data = new_data)

		# the last thing we need to do it run a function on the data so that the offsets are all correct.
		# we do this now so that all the data has been combined and sorted, and we need to talk to both the DATA and DIDX classes in the BNK class to get all the offsets correctly
		new_BNK.correct_offsets()
		return new_BNK

	def extract(self, ids, dir = ''):
		# this will extract the wems specified by the ids from the DATA section
		if ids == "all":
			ids = [x for x in self.data['DATA'].wem_data]
		for wem_id in ids:
			with open(f'{dir}{wem_id}.wem', 'wb') as wem_file:
				wem_file.write(self.data['DATA'].extract(wem_id).getdata())

	def replace(self, id_, wem):
		# this will replace the specified id with the provided wem data.
		# the wem will be a file object (maybe??)

		# first, create a wem from the actual data
		with open(wem, 'rb') as data:
			new_wem = WEM(data.read())

		# now, we need to replace it in the wem_data of self.data['DATA']
		try:
			self.data['DATA'].wem_data[int(id_)] = new_wem
		except KeyError:
			raise KeyError  # is this redundant as it would just happen anyway? Might just leave it for now in case I want to change it...

		# only thing left to do is correct the offsets and redo all the data which is handled by correct_offsets()
		self.correct_offsets()

	def save(self, path_):
		# saves the current bnk files to disc (at location path)

		# the only thing we really need to be careful about here is that the name in the BKHD needs to be the hash of the name of the file.
		# let's produce it so that it is...
		name_hash = fnvhash(os_path.splitext(os_path.basename(path_))[0])
		# now we need to actually change the value in the BKHD section...
		self.data['BKHD'].sethash(name_hash)
		
		with open(path_, 'wb') as output:
			for key in self.data:
				output.write(self.data[key].getdata())

	def getBytes(self):
		bytesArr = bytearray()
		for key in self.data:
			bytesArr.extend(self.data[key].getdata())
		return bytes(bytesArr)

	def read_bnk_chunk(self, input_):
		# this will read the tag at the current location in self.input, and then return the data and tag
		try:
			tag = input_.read(4).decode()       # use this over decode to just get the data as binary for convenience when writing later...
			size = unpack('<I', input_.read(4))[0]
			cls = eval(tag)
			self.data[tag] = cls(data = BytesIO(input_.read(size)))
		except struct_error:
			# break the loop
			self.cont = False
		except NameError:
			# class not defined for the sub section of the BNK...
			# print(f"Class {tag} doesn't exist...")
			input_.seek(size, 1) #skip past the unknown section

	def correct_offsets(self):
		# this will determine the size of the BKHD and DIDX sections (+ the 4 bytes for the DATA tag),
		# and then use this offset to generate the offsets for each wem file in DATA
		if self.data is not None:
			# add all the tags and section length data to the actual lengths of the sections
			self.data['DATA'].start_pos = 8 + len(self.data['BKHD']) + 8 + len(self.data['DIDX']) + 8
			# initial 8 bytes + len of the BKHD section
			# tag and length of DIDX
			# tag and length of DATA

			# next, call the command on the DATA object to renerate a new set of wem offsets
			new_wem_offsets = self.data['DATA'].setdata()

			# and finally, correct all the offsets in the DIDX section:
			self.data['DIDX'].setdata(new_wem_offsets)

class BKHD():
	"""
	Location:		Size:		Type:		Value:		What it is:
	+0x000			0x4			char		BKHD		header tag
	+0x004			0x4			int			-			size of header, from next 4 bytes (0x008)
	+0x008			0x4			int			0x78		version maybe?
	+0x00C			0x4			int			-			sound bank ID (hashed version of name)
	+0x010			0x8			padding		empty		not used?
	+0x018			0x4			int			0x0447		unknown (everything has it)
	+0x01C			0x0-0x8		padding		empty		NMS_AUDIO_PERSISTENT has 0x0, intro music are 0x8
	"""
	def __init__(self, data):
		self.data = data
		self.tag = b'BKHD'

	def __len__(self):
		return len(self.data.getvalue())

	def sethash(self, hash_):
		self.data.seek(4)
		self.data.write(pack('<I', hash_))
		self.data.seek(0)

	def getdata(self):
		return self.tag + pack('<I', len(self)) + self.data.getvalue()

class DIDX():
	"""
	Data Index Entry (0xC chunks):
	+0x000			0x4			int			-			audio file id (hashed version of name)
	+0x004			0x4			int			-			relative file offset from start of DATA, 16 bytes aligned
	+0x008			0x4			int			-			file size
	"""
	def __init__(self, data, **kwargs):
		self.tag = b'DIDX'
		self.data = data            # this is a BytesIO object

		# the following two Odict's contain all the data here really once it is serialised back. Maybe better to just store it here and delete self.data?
		self.wem_sizes = kwargs.get('wem_sizes', Odict())        # use an ordered dict and use the id's as the keys, and the values are the sizes
		self.wem_offsets = kwargs.get('wem_offsets', Odict())

		# have a block to check if the DIDX has been created from an addition. If so we don't actually want to run the following code:
		if not kwargs.get('added', False):
			self.num_entries = int(len(self)/0xC)     # each block is 0xC long...
			for i in range(self.num_entries):
				# for each file, get the ids and sizes of each of the wems
				wem_id = int(unpack('<I', self.data.read(4))[0])
				self.wem_offsets[wem_id] = int(unpack('<I', self.data.read(4))[0])
				wem_size = int(unpack('<I', self.data.read(4))[0])
				self.wem_sizes[wem_id] = wem_size       # update the dict

		# read off the offset of the final data entry in DATA, and its size and add together
		# this is the total size of the self.data chunk in the DATA section
		self.data_size = self.wem_offsets[next(reversed(self.wem_offsets))] + self.wem_sizes[next(reversed(self.wem_sizes))] ## I don't think this is even used??? Was made redundant at some point...

	def __len__(self):
		return len(self.data.getvalue())

	def __add__(self, other):
		# we will need to adjust all the data here since it will all become re-ordered due to merging with another file
		print('self: {0}, other: {1}'.format(len(self), len(other)))
		#total_data = BytesIO(self.data.getvalue() + other.data.getvalue())
		# combine the two ordered dicts for each DIDX section
		new_wem_sizes = Odict(self.wem_sizes)
		new_wem_sizes.update(other.wem_sizes)
		new_wem_offsets = Odict(self.wem_offsets)
		new_wem_offsets.update(other.wem_offsets)

		# now we need to do some stuff...
		# first, we need to sort both ordered dicts by key
		sorted_wem_sizes = Odict(sorted(new_wem_sizes.items()))
		del new_wem_sizes       # let's delete it to save memory...
		sorted_wem_offsets = Odict(sorted(new_wem_offsets.items()))
		del new_wem_offsets
		
		return DIDX(BytesIO(b''), wem_sizes = sorted_wem_sizes, wem_offsets = sorted_wem_offsets, added = True)

	def setdata(self, new_offsets):
		# this gets an ordered dictionary of the wem offsets and writes the values to the data section.
		# we will assume that the order of entries is the same as the wem orders, as it should be because the two were created and ordered identically
		# new_offsets is a tuple of (offset, data_size)

		self.data = BytesIO()
		
		# now go through and write each one
		for wem_id in new_offsets:
			self.data.write(pack('<I', wem_id))                     # id
			self.data.write(pack('<I', new_offsets[wem_id][0]))     # offset
			self.data.write(pack('<I', new_offsets[wem_id][1]))     # wem size
		self.data.seek(0)   # just to reset it in case...

	def getdata(self):
		return self.tag + pack('<I', len(self)) + self.data.getvalue()
		

class DATA():
	def __init__(self, data, **kwargs):
		self.tag = b'DATA'
		self.data = data
		self.wem_data = kwargs.get('wem_data', Odict())
		self.start_pos = kwargs.get('start_pos', 0x0)        # this will be the location that the data starts at (after b'DATA' and the length of the section)

	def __len__(self):
		return len(self.data.getvalue())

	def __add__(self, other):
		# Need to be careful here. We cannot simply add the two data's together as we require some padding between...
		new_wem_data = Odict(self.wem_data)
		new_wem_data.update(other.wem_data)
		sorted_new_wem_data = Odict(sorted(new_wem_data.items()))
		del new_wem_data        # delete the old one so that we don't take up all that memory still.
		
		return DATA(BytesIO(b''), wem_data = sorted_new_wem_data)        # give it an empty byte string just so that things like len(~) don't spit an error...

	def split(self, didx_data):
		# this will take the didx data, and use it to split the self.data into individual WEM objects
		for key in didx_data.wem_sizes:
			# first, move to the right spot
			self.data.seek(didx_data.wem_offsets[key])
			# then read the right amount
			self.wem_data[key] = WEM(self.data.read(didx_data.wem_sizes[key]))
		# I guess we will keep the self.data, although really we don't need it, and should probably remove it from memory to save space, especially for large bnk's.
		# del self.data

	def extract(self, _id):
		# returns the WEM's with the corresponding id
		return self.wem_data[_id]

	def setdata(self):
		# this will be called on DATA objects created from the merging of two other DATA objects.
		# we want to get all the wem objects and create the self.data again from it
		# we will also need to output some info that contains all the offsets so that the DIDX section of the BNK can be set
		wem_offsets = Odict()
		wems = list(self.wem_data.keys())
		# refresh self.data
		self.data = BytesIO()
		curr_location = 0
		for wem in wems:
			# set the offset of the wem to be equal to the current length of self.data
			wem_offsets[wem] = (curr_location, len(self.wem_data[wem]))
			# now actually add on the wem's data and offset if required
			self.data.write(self.wem_data[wem].getdata())
			curr_location += len(self.wem_data[wem])
			if wems.index(wem) == 0 and wems.index(wem) != len(wems) - 1:   # make sure it isn't also the last in case there is only one element...
				# only need to add the offset to the first entry
				file_padding = align16(len(self.wem_data[wem]) + self.start_pos)
				first = False
			elif wems.index(wem) != len(wems) - 1:
				# after this, the entries will now be aligned to 0x10, so we can just call align16 on the length
				file_padding = align16(len(self.wem_data[wem]))
			else:
				file_padding = 0
			if file_padding != 0:
				self.data.write(pack('{}s'.format(file_padding), b''))
			curr_location += file_padding

		return wem_offsets

	def getdata(self):
		return self.tag + pack('<I', len(self)) + self.data.getvalue()
		

class HIRC():
	"""
	This is a class to load an HIRC file into that will allow it to be merged (and maybe in the future more...)

	HIRC section specification:
	+0x000 - length of section (int)
	+0x004 - number of objects (int)    <- this is the first value in data.
	
	"""
	def __init__(self, data, **kwargs):
		""" this will probably need to be reformatted at some point... """        
		self.tag = b'HIRC'
		self.data = data
		self.entries = kwargs.get('entries', unpack('<I', data.read(4))[0])
		if not kwargs.get('added', False):
			self.data = BytesIO(self.data.read())        # this will make the data be everything except the first 4 bytes which are the amount of HIRC entries. Not sure if there is a better way?

	def __len__(self):
		return len(self.data.getvalue()) + 4            # we need a + 4 to take into account of the number of entries field (4 byte int)

	def __add__(self, other):
		total_entries = self.entries + other.entries
		total_data = BytesIO(self.data.getvalue() + other.data.getvalue())
		return HIRC(total_data, entries = total_entries, added = True)

	def getdata(self):
		# return all the data and header of the section
		return self.tag + pack('<I', len(self)) + pack('<I', self.entries) + self.data.getvalue()       # tag, size of HIRC section, number of entries, and then data respectively
		
class WEM():
	def __init__(self, data, **kwargs):
		self.__slots__ = ['data', '__len__']
		self.data = data        # this is just the raw bytes

	def __len__(self):
		return len(self.data)

	def getdata(self):
		return self.data


def align16(x):
	# this will take any number and find the number required to be added to make it divisible by 16
	return (16 - (x % 16))%16
