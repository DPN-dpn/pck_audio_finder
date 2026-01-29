import os
import sys
from multiprocessing import Pool, Value

# Determine the script directory
script_dir = os.path.dirname(__file__)

sys.path.append(os.path.join(script_dir,'..','lib','hoyo_audio_tools'))  # Add the lib directory to the sys.path
from BNKcompiler import BNK
from HoyoPckExtractor import PCKextract
import ProgressBar

input_path = os.path.join(script_dir, 'input_pck')
output_path = os.path.join(script_dir, 'unpacked')

if not os.path.exists(input_path):
	os.mkdir(input_path)
if not any(os.scandir(input_path)):
	print(f'Please add pck files to {input_path}')
	quit()
if not os.path.exists(output_path):
	os.mkdir(output_path)

counter = Value('i', 0)
files = [f.name for f in os.scandir(input_path) if '.pck' in f.name]
fileCount = len(files)
def initPool(theCounter):
	global counter
	counter = theCounter

def extractFile(f):
	outFilePath = os.path.join(output_path,f[:-4])
	if not os.path.exists(outFilePath):
		os.mkdir(outFilePath)
	allFiles = PCKextract(os.path.join(input_path,f), outFilePath).extract()

	# Write files
	for file in allFiles:
		if '.bnk' in file: # handle bnks
			bnkObj = BNK(bytes=allFiles[file])
			if bnkObj.data['DATA'] is not None:
				bnkFolder = f'{file[:-4]}_bnk'
				if not os.path.exists(bnkFolder):
					os.makedirs(bnkFolder, exist_ok=True)
				bnkObj.extract('all', bnkFolder) # write bnk wems
		else: # write wems
			dir = os.path.dirname(file)
			if not os.path.exists(dir):
				os.makedirs(dir, exist_ok=True)
			with open(file, 'wb') as o:
				o.write(allFiles[file])
	with counter.get_lock():
		counter.value +=1
		# prepare components for a safe f-string (avoid nested quotes/braces)
		bar = ProgressBar.generate(counter.value/fileCount, 60)
		spaces = ' ' * (len(str(fileCount)) - len(str(counter.value)))
		print(f'\x1b[2F\x1b[KExtracted {f}\n|{bar}| {spaces}{counter.value}/{fileCount}')

if __name__ == '__main__':
	# prepare initial progress display safely
	bar0 = ProgressBar.generate(0, 60)
	spaces0 = ' ' * (len(str(fileCount)) - 1)
	print(f'Extracting pcks...\n\n|{bar0}| {spaces0}0/{fileCount}')
	with Pool(initializer=initPool, initargs=(counter,)) as p:
		p.map(extractFile, files)
	print('Done')