# Simple progress bar generator by failsafe65
import math
def generate(progress, length):
	solid = math.floor(length * progress)
	mid = (progress - (solid / length))*length
	subChar = ''
	
	if 0 < mid < 0.125:
		subChar = ' '
	elif 0.125 <= mid < 0.25:
		subChar = '▏'
	elif 0.25 <= mid < 0.375:
		subChar = '▎'
	elif 0.375 <= mid < 0.5:
		subChar = '▍'
	elif 0.5 <= mid < 0.625:
		subChar = '▌'
	elif 0.625 <= mid < 0.75:
		subChar = '▋'
	elif 0.75 <= mid < 0.875:
		subChar = '▊'
	elif 0.875 <= mid < 1:
		subChar = '▉'

	block_char = '\u2588'  # '█' 문자, 이스케이프 사용으로 인코딩 문제 방지
	solid_part = block_char * solid
	tail_spaces = ' ' * max(0, length - solid - len(subChar))
	bar = f"{solid_part}{subChar}{tail_spaces}"