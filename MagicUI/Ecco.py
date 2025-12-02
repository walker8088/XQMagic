
import platform
from ctypes import *

import cchess

#-----------------------------------------------------------------
try:
    if platform.system() == 'Windows':
        _ecco_dll = cdll.LoadLibrary('./Engine/EccoDLL/ECCO64.DLL')
    #else:
    #    _ecco_dll = cdll.LoadLibrary('./Engine/EccoDLL/libecco64.so')
        
    _ecco_dll.EccoVersion.restype = c_char_p
    _ecco_dll.EccoOpening.restype = c_char_p
    _ecco_dll.EccoVariation.restype = c_char_p
    _ecco_dll.EccoInitOpenVar(0)
    isLoaded = True
except Exception as e:
    print(f'Load EccoDLL 错误：{e}')
    isLoaded = False
    
#-----------------------------------------------------------------
def getBookEcco(positionList):
    wxfs = []
    
    if positionList[0]['fen'] != cchess.FULL_INIT_FEN:
       return ('', )
        
    for index, position in enumerate(positionList[1:]):
        #只有标准开局才查询ECCO开局
        text = position['move'].to_text()
        wxfs.append(text2wxf(text))

    wxf_str = ''.join(wxfs)
    return getEcco(wxf_str)

#-----------------------------------------------------------------
def getEcco(wxf_move_str):
    
    if not isLoaded:
        return ('',)

    ecco = _ecco_dll.EccoIndex(wxf_move_str.encode())
    s1 = ecco.to_bytes(3, 'little').decode()
    s2 = _ecco_dll.EccoOpening(ecco).decode()
    s3 = _ecco_dll.EccoVariation(ecco).decode()
    if not s3:
        return (s1, s2)
    else:
        return (s1, s2, s3)

#-----------------------------------------------------------------
def text2wxf(txt):
    if txt[0] in ['前','后']: 
        wtf1 = _qian_hou_text2wxf(txt[:2])
        wtf = f'{wtf1}{_change_dict[txt[2]]}{_num_dict[txt[3]]}'
    else:
        wtf = f'{_name_fench_dict[txt[0]]}{_num_dict[txt[1]]}{_change_dict[txt[2]]}{_num_dict[txt[3]]}'
    
    wtf = wtf.upper()
    return wtf
    
#-----------------------------------------------------------------
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
                 
def _qian_hou_text2wxf(ch):
    return f'{_name_fench_dict[ch[1]]}{_qian_hou_dict[ch[0]]}' 
#-----------------------------------------------------------------
        
