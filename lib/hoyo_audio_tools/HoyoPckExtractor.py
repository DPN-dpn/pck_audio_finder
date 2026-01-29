# Wwise AKPK packages (.PCK) extractor
# 
# v1 by Nicknine
# v2 by bnnm (old extensions, lang names, etc)
# original quickbms script from https://github.com/bnnm/wwiser-utils/blob/master/scripts/wwise_pck_extractor.bms 
# python conversion by failsafe65
import os
class PCKextract():
	def __init__(self, inFilePath, outFilePath):
		self.pckName = os.path.basename(inFilePath)
		self.outFilePath = outFilePath
		# set to generate (packname)/files
		self.writepath = 0

		# set if cannot be autodetected: 62< uses old extensions, 62>= uses new extensions
		self.bankversion = 0

		# set 1 to extract BNK/WEM only
		self.filterbnkonly = 0
		self.filterwemonly = 0

		###

		self.idstring = "AKPK"

		self.pckFile = open(inFilePath, 'rb')
		self.pckFile.seek(4)
		self.headersize = int.from_bytes(self.pckFile.read(4), 'little') # not counting padding
		self.flag = int.from_bytes(self.pckFile.read(4), 'little') # always 1?
		self.sec1size = int.from_bytes(self.pckFile.read(4), 'little') # Languages
		self.sec2size = int.from_bytes(self.pckFile.read(4), 'little') # Banks
		self.sec3size = int.from_bytes(self.pckFile.read(4), 'little') # Sounds
		self.sec4size = 0 # Externals
		self.langdict = {0: 'sfx',
						 1: 'english',
						 2: 'chinese',
						 3: 'japanese',
						 4: 'korean'}

		# Later Wwise versions (+2012) have the fourth section with "externals" (.wem set at runtime).
		sum = self.sec1size + self.sec2size + self.sec3size + 0x10 # Detect its presense.
		if sum < self.headersize:
			self.sec4size = int.from_bytes(self.pckFile.read(4), 'little')

		self.testsize = os.path.getsize(inFilePath)
		self.testsize -= 0x08

	def DETECT_BANK_VERSION(self, offset):
		current = self.pckFile.tell()
		self.pckFile.seek(offset)
		self.pckFile.seek(8,1)
		self.bankversion = int.from_bytes(self.pckFile.read(4), 'little')
		if self.bankversion > 0x1000:
			# print("wrong bank version, assuming new (set manually)")
			self.bankversion = 62

		self.pckFile.seek(current)

	def PARSE_TABLE(self, sectionsize, sounds, externals, extension):
		outfiles ={}
		if sectionsize != 0:
			files = int.from_bytes(self.pckFile.read(4), 'little')
			if files != 0:		
				entrysize = (sectionsize - 0x04) / files
				if entrysize == 0x18:
					altmode = 1
				else:
					altmode = 0
				for i in range(files):
					if altmode == 1 and externals == 1:
						id = self.pckFile.read(8)
					else:
						id = self.pckFile.read(4)
					blocksize = int.from_bytes(self.pckFile.read(4), 'little')

					if altmode == 1 and externals == 1:
						size = int.from_bytes(self.pckFile.read(4), 'little')
					elif altmode == 1:
						size = int.from_bytes(self.pckFile.read(8), 'little')
					else:
						size = int.from_bytes(self.pckFile.read(4), 'little')

					offset = int.from_bytes(self.pckFile.read(4), 'little') # START_BLOCK
					langid = int.from_bytes(self.pckFile.read(4), 'little')


					if blocksize != 0:
						offset *= blocksize

					# get version from first bnk for proper sound extensions
					if sounds == 0 and self.bankversion == 0:
						self.DETECT_BANK_VERSION(offset)

					# get codec ID to guess extension
					if sounds and self.bankversion < 62:
						current = self.pckFile.tell()

						codecoffset = offset
						codecoffset += 0x14 #maybe should find "fmt " chunk first
						self.pckFile.seek(codecoffset)
						codec = int.from_bytes(self.pckFile.read(2), 'little')

						if codec == 0x0401 or codec == 0x0166: #0x0401: old XMA (not a codec)
							extension = "xma"
						elif codec == 0xFFFF:
							extension = "ogg"
						else:
							extension = "wav" #PCM, PCMEX, ADPCM, WIIADPCM

						self.pckFile.seek(current)

					# ID 0 is "sfx" so just print in root
					if langid == 0:
						path = f'{self.outFilePath}/'
					else:
						langname = self.langdict[langid]
						path = f'{self.outFilePath}/{langname}/'
					if altmode == 1 and externals == 1:
						name = f"{path}{id[::-1].hex()}.{extension}"
					else:
						name = f"{path}{int.from_bytes(id[::-1], 'big')}.{extension}"



					if self.filterbnkonly == 1 and extension != "bnk":
						continue
					if self.filterwemonly == 1 and extension != "wem":
						continue

					if self.writepath != 0:
						name = f"{self.pckName}/{name}"
					current = self.pckFile.tell()
					self.pckFile.seek(offset)
					outfiles[name] = self.pckFile.read(size)
					self.pckFile.seek(current)
		return outfiles

	def extract(self):
		if self.headersize == self.testsize:
			return {}
		# Get languages
		stringsoffset = self.pckFile.tell()
		langs = int.from_bytes(self.pckFile.read(4), 'little')
		for i in range(langs):
			langoffset = int.from_bytes(self.pckFile.read(4), 'little')
			langid = int.from_bytes(self.pckFile.read(4), 'little')

			langoffset += stringsoffset

			current = self.pckFile.tell()

			# Language names are stored as UTF-16

			self.pckFile.seek(langoffset)
			langname = ""
			while(True):
				byte = self.pckFile.read(2)
				if byte == b'\x00\x00':
					break
				langname += byte.decode("utf-16")


			# table isn't ordered by ID, but IDs are fixed (0=sfx, 1=english, etc)
			self.langdict[langid] = langname
			self.pckFile.seek(current)

		self.pckFile.seek(stringsoffset)
		self.pckFile.seek(self.sec1size, 1)

		# Extract banks
		bnks = self.PARSE_TABLE(self.sec2size, False, False, "bnk")

		# banks section always exists but may set 0 files = can't autodetect
		if self.bankversion == 0:
			# section 4 was added after .wem
			# if self.sec4size == 0:
			# 	print("can't detect bank version, assuming new (set manually)")
			self.bankversion = 62

		# Extract sounds
		sounds = self.PARSE_TABLE(self.sec3size, True, False, "wem")

		# Extract externals
		externals = self.PARSE_TABLE(self.sec4size, True, True, "wem")

		allFiles = bnks | sounds | externals

		return allFiles

	def writeFiles(self):
		allFiles = self.extract()
		for i in allFiles:
			dir = os.path.dirname(i)
			if not os.path.exists(dir):
				os.makedirs(dir, exist_ok=True)
			with open(i, 'wb') as o:
				o.write(allFiles[i])
		# last sound may be padding