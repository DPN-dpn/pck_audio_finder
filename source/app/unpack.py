import os
import sys

# Determine the script directory
script_dir = os.path.dirname(__file__)

sys.path.append(os.path.join(script_dir,'..','..','lib','HoyoAudioTools','lib'))  # Add the lib directory to the sys.path
from BNKcompiler import BNK
from HoyoPckExtractor import PCKextract


def extract_pck_file(pck_path: str) -> int:
	"""Extract a single .pck file into <pckname>_unpacked next to the PCK.

	- BNK files are extracted into a dedicated BNK folder under the output dir.
	- WEM files are written into the output dir preserving any contained paths.

	Returns exit code (0 success, non-zero failure).
	"""
	if not os.path.isfile(pck_path):
		print(f'파일이 존재하지 않습니다: {pck_path}')
		return 2
	if not pck_path.lower().endswith('.pck'):
		print(f'PCK 파일이 아닙니다: {pck_path}')
		return 3

	output_path = os.path.join(os.path.dirname(pck_path), os.path.splitext(os.path.basename(pck_path))[0] + '_unpacked')
	os.makedirs(output_path, exist_ok=True)

	try:
		allFiles = PCKextract(pck_path, output_path).extract()
	except Exception as e:
		print(f'PCK 추출 실패: {e}')
		return 4

	for filename, data in allFiles.items():
		try:
			lower = filename.lower()
			if lower.endswith('.bnk'):
				# BNK는 별도 폴더로 분리하되, 실제 DATA가 있을 때만 폴더를 만듭니다
				bnkObj = BNK(bytes=data)
				if bnkObj.data.get('DATA') is not None:
					bnk_folder_name = os.path.splitext(os.path.basename(filename))[0] + '_bnk'
					bnk_folder = os.path.join(output_path, bnk_folder_name)
					os.makedirs(bnk_folder, exist_ok=True)
					bnkObj.extract('all', bnk_folder)
					print(f'BNK 처리: {filename} -> {bnk_folder}')
				else:
					print(f'BNK에 데이터 없음: {filename}')
			else:
				# WEM 등은 출력 폴더의 루트에 평탄화하여 저장 (하위 폴더 생성하지 않음)
				base_name = os.path.basename(filename)
				target = os.path.join(output_path, base_name)
				with open(target, 'wb') as o:
					o.write(data)
				print(f'파일 작성: {target}')
		except Exception as e:
			print(f'처리 실패 {filename}: {e}')

	print('완료')
	return 0
