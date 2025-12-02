# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

from cchess import *

#result_dict = {'红胜': RED_WIN, '黑胜': BLACK_WIN, '和棋': PEACE}
result_dict = {'红胜': '1-0', '黑胜': '0-1', '和棋': '1/2-1/2'}

'''
def load_move_txt(txt_file):
    with open(txt_file, "rb") as f:
        lines = f.readlines()
    fen = lines[0].strip().decode('utf-8')
    moves = [it.strip().decode('utf-8') for it in lines[1:-1]]
    result = result_dict[lines[-1].strip().decode('utf-8')]
    return (fen, moves, result)


        game = read_from_xqf(Path("data", "WildHouse.xqf"))
        moves = game.dump_moves()

        #assert moves == ''

    def test_k1(self):
        fen, moves, result = load_move_txt(Path("data", "test1_move.txt"))
        game = read_from_xqf(Path("data", "test1.xqf"))
        assert game.init_board.to_fen() == fen
        assert game.info['result'] == result

        #game.print_init_board()
        m = game.dump_text_moves()[0]
        assert len(m) == len(moves)
        for i in range(len(m)):
            assert m[i] == moves[i]
'''
#-----------------------------------------------------#

def dump_game(game):
    line = game.dump_moves_line()
    move_text = [f'{it.to_text(detailed = True) }' for it in line]
    print(move_text)    
    #for move in line:
    #    print(it.to_text(detailed = True))
    moves = game.dump_moves()
    for i, line in enumerate(moves):
        new_index = ".".join([str(x) for x in line[0]])
        line[0] = new_index
    #moves.sort(key = lambda x : x[0])
    
    for i, line in enumerate(moves):
        print(line[0])
        it = [f'{it.to_text(detailed = True) }' for it in line[1:]]
        print(it)
                
if __name__ == '__main__':

    if len(sys.argv) != 2:
        print(f'Usage {sys.argv[0]} xqf_file')
        sys.exit(-1)
        
    f_path = Path(sys.argv[1])
    if f_path.is_dir():
        for file in f_path.glob('*.XQF'):
            print(file)
            game = read_from_xqf(file)
            dump_game(game)         
            #input()
    else:
       file = f_path
       print(file)
       game = read_from_xqf(file)
       dump_game(game)         
