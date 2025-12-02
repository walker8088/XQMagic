# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
import platform
from ctypes import *

import cchess

if platform.system() == 'Windows':
    ecco_dll = cdll.LoadLibrary('..\\EccoDLL\\ECCO64.DLL')
else:
    ecco_dll = cdll.LoadLibrary('./libecco64.so')
    
ecco_dll.EccoVersion.restype = c_char_p
ecco_dll.EccoOpening.restype = c_char_p
ecco_dll.EccoVariation.restype = c_char_p
ecco_dll.EccoInitOpenVar(0)

def fen_mirror(fen):
    b = cchess.ChessBoard(fen)
    return b.mirror().to_fen()
    
def iccs_list_mirror(iccs_list):
    return [cchess.iccs_mirror(x) for x in iccs_list]
    
_name_fench_dict = {
    "帅": 'K',
    "将": 'k',
    "仕": 'A',
    "士": 'a',
    "相": 'B',
    "象": 'b',
    "马": 'n',
    "车": 'r',
    "炮": 'c',
    "兵": 'P',
    "卒": 'p',
}

_qian_hou_dict = {
    '前':'+',
    '后':'-',
}

_change_dict = { 
    '进': '+',
    '退': '-',
    '平': '.',
}

_num_dict = {    
    "一": '1', 
    "二": '2', 
    "三": '3', 
    "四": '4', 
    "五": '5', 
    "六": '6', 
    "七": '7', 
    "八": '8', 
    "九": '9',
    '１': '1',
    '２': '2',
    '３': '3',
    '４': '4',
    '５': '5',
    '６': '6',
    '７': '7',
    '８': '8',
    '９': '9',
}
                 
def qian_hou_text2wxf(ch):
    return f'{_name_fench_dict[ch[1]]}{_qian_hou_dict[ch[0]]}' 
        
def text2wxf(txt):
    if txt[0] in ['前','后']: 
        wtf1 = qian_hou_text2wxf(txt[:2])
        wtf = f'{wtf1}{_change_dict[txt[2]]}{_num_dict[txt[3]]}'
    else:
        wtf = f'{_name_fench_dict[txt[0]]}{_num_dict[txt[1]]}{_change_dict[txt[2]]}{_num_dict[txt[3]]}'
    
    wtf = wtf.upper()
    return wtf
   
def get_ecco(wtf):
    ecco = ecco_dll.EccoIndex(wtfs.encode())
    s1 = ecco.to_bytes(3, 'little').decode()
    s2 = ecco_dll.EccoOpening(ecco).decode()
    s3 = ecco_dll.EccoVariation(ecco).decode()
    if not s3:
        return (s1, s2)
    else:
        return (s1, s2, s3)
    
bad_files = []
#root_folder = 'D:\\01_MyRepos\\开局库制作\\现代对局谱'
root_folder = 'D:\\01_MyRepos\\开局库制作\\1_布局'

iccs_dict = {}
open_dict = {}
count = 0
done = False
for root, dirs, files in os.walk(root_folder, topdown=False):
    for name in files:
        ext = os.path.splitext(name)[1]
        if ext.lower() != '.xqf':
            continue
            
        file_name = os.path.join(root, name)
        game = cchess.read_from_xqf(file_name)
        if game.init_board.to_fen() != cchess.FULL_INIT_FEN:
            print('棋局非正常开局', file_name)
            bad_files.append(file_name)
            break        
        try:
            game.verify_moves()
        except Exception as e:
            print('棋局有错招', file_name)
            print(str(e))
            bad_files.append(file_name)
            break
        moves = game.dump_moves()
        if len(moves) < 1:
            print("棋谱为空:", file_name)
            break
        
        print(name)    
            
        for action in moves:
            wtfs = ''
            iccs_list = []
            if len(action) < 24:
                continue
            for steps, m in enumerate(action[1:25]):
                iccs = m.to_iccs()
                txt = m.to_text()
                color = m.board.get_move_color()
                wtf = text2wxf(txt)
                wtfs += wtf
                iccs_list.append(iccs)
                if steps >= 10:
                    ecco_info = get_ecco(wtfs)
                    result = '-'.join(ecco_info)
                    if len(ecco_info) == 3:
                        print(steps)
                        break
                        
            result = '-'.join(ecco_info[:])
            print(result)
            if len(ecco_info) <= 2:
                iccs_list = iccs_list[:10]
            
            if result not in open_dict:
                open_dict[result] = ','.join(iccs_list)
                    
            count += 1
            #if count >= 10:
            #    done = True
            #    break
    if done:
        break
        
print("文件写入中。。。。")
with open('open_book.txt', 'w') as f:
    for key in sorted(open_dict.keys()):
        f.write(f"{key}:{open_dict[key]}\n")
        