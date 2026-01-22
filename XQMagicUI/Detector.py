
import time
from pathlib import Path
from typing import List, Tuple, Union


#-----------------------------------------------------#
class ChessboardDetector:
    def __init__(self, model_path: str):
        pass

    def img_to_fen(self, image_file):
        board = ChessBoard()
        return board.to_fen()        