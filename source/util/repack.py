import os
import sys
from io import BytesIO, BufferedReader
sys.path.append('../lib/hoyo_audio_tools')  # Add the lib directory to the sys.path
from FilePackager import Package, build_pck_file
from BNKcompiler import BNK

# Determine the script directory
script_dir = os.path.dirname(__file__)

wav_path = os.path.join(script_dir, 'wem')
input_path = os.path.join(script_dir, 'input_pck')

if not os.path.exists(wav_path):
    os.mkdir(wav_path)

if not os.path.exists(input_path):
    os.mkdir(input_path)

if not any(os.scandir(input_path)) or not any(os.scandir(wav_path)):
    print("Please place wem files in the wem folder and original pcks in the input_pck folder")
    quit()

output_path = os.path.join(script_dir, 'output_pck')

if not os.path.exists(output_path):
    os.mkdir(output_path)

languages = {
    'english(en)': 5,
    'chinese': 2,
    'english(us)': 1,
    'japanese(jp)': 3,
    'japanese': 3,
    'korean(kr)': 4,
    'korean': 4,
    'chinese(prc)': 2,
    'english': 1
}

pckFiles = list(os.scandir(wav_path))
pckCount = len(pckFiles)
print("Repacking pcks...")

for i, x in enumerate(pckFiles):

    if not os.path.exists(os.path.join(output_path, x.name + '.pck')):

        modify_pck = Package()  # init

        with open(os.path.join(input_path, x.name + '.pck'), 'rb') as pck:
            modify_pck.addfile(BufferedReader(BytesIO(pck.read())))  # load original pck

        for f in os.scandir(os.path.join(wav_path, x.name)):

            # =======================
            # LANGUAGE FOLDERS LOGIC
            # =======================
            if f.name in languages:

                for y in os.scandir(os.path.join(wav_path, x.name, f.name)):
                    hash = y.name[:-4]
                    int_hash_value = int(hash, 16) if len(hash) == 16 else int(hash)

                    if y.name.lower().endswith('.wem'):   # direct WEM
                        with open(os.path.join(wav_path, x.name, f.name, y.name), 'rb') as wemFile:
                            wem = BufferedReader(BytesIO(wemFile.read()))
                        modify_pck.add_wem(1, languages[f.name], int_hash_value, wem)

                    elif y.name.lower().endswith('.bnk'):  # direct BNK
                        with open(os.path.join(wav_path, x.name, f.name, y.name), 'rb') as bnkFile:
                            bnk = BufferedReader(BytesIO(bnkFile.read()))
                        modify_pck.add_wem(0, languages[f.name], int_hash_value, bnk)

                    elif '_bnk' in y.name:  # _bnk folder
                        bytes = modify_pck.get_file_data_by_hash(int_hash_value, languages[f.name])[0][0]
                        bnkObj = BNK(bytes=bytes)

                        bnk_folder = os.path.join(wav_path, x.name, f.name, y.name)

                        for z in os.scandir(bnk_folder):
                            if not z.is_file():
                                continue
                            if not z.name.lower().endswith(('.wem', '.wav')):
                                print(f"[WARN] Skipping non-audio file: {z.name}")
                                continue

                            id_str = z.name.split('.')[0]
                            if not id_str.isdigit():
                                print(f"[WARN] Skipping file with non-numeric ID: {z.name}")
                                continue

                            audio_path = os.path.join(bnk_folder, z.name)
                            bnkObj.replace(id_str, audio_path)

                        modify_pck.add_wem(
                            0,
                            languages[f.name],
                            int_hash_value,
                            BufferedReader(BytesIO(bnkObj.getBytes()))
                        )

            # =======================
            # GENERIC SFX HANDLING
            # =======================
            else:
                hash = f.name[:-4]
                int_hash_value = int(hash, 16) if len(hash) == 16 else int(hash)

                if f.name.lower().endswith('.wem'):  # direct WEM
                    with open(os.path.join(wav_path, x.name, f.name), 'rb') as wemFile:
                        wem = BufferedReader(BytesIO(wemFile.read()))

                    if len(f.name) == 20:
                        modify_pck.add_wem(2, 0, int_hash_value, wem)
                    else:
                        modify_pck.add_wem(1, 0, int_hash_value, wem)

                elif f.name.lower().endswith('.bnk'):  # direct BNK file
                    with open(os.path.join(wav_path, x.name, f.name), 'rb') as bnkFile:
                        bnk = BufferedReader(BytesIO(bnkFile.read()))
                    modify_pck.add_wem(0, 0, int_hash_value, bnk)

                elif '_bnk' in f.name:  # _bnk folder
                    bytes = modify_pck.get_file_data_by_hash(int_hash_value, 0)[0][0]
                    bnkObj = BNK(bytes=bytes)

                    bnk_folder = os.path.join(wav_path, x.name, f.name)

                    for y in os.scandir(bnk_folder):
                        if not y.is_file():
                            continue
                        if not y.name.lower().endswith(('.wem', '.wav')):
                            print(f"[WARN] Skipping non-audio file: {y.name}")
                            continue

                        id_str = y.name.split('.')[0]
                        if not id_str.isdigit():
                            print(f"[WARN] Skipping file with non-numeric ID: {y.name}")
                            continue

                        audio_path = os.path.join(bnk_folder, y.name)
                        bnkObj.replace(id_str, audio_path)

                    modify_pck.add_wem(
                        0,
                        0,
                        int_hash_value,
                        BufferedReader(BytesIO(bnkObj.getBytes()))
                    )

        print(f"Repacked {x.name + '.pck'} ({i+1}/{pckCount})")

        with open(os.path.join(output_path, x.name + '.pck'), 'wb') as f:
            build_pck_file(modify_pck, f, modify_pck.LANGUAGE_DEF)
