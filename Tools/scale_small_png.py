import os
import sys
import math

from pathlib import Path
from PIL import Image

#------------------------------------------------------------------------------
def walk_folder(root_folder):
    for root, dirs, files in os.walk(root_folder, topdown=False):
        for name in files:
            if name.lower() not in ['ra.png','rb.png','rc.png', 'rk.png', 'rn.png', 'rp.png', 'rr.png', 
                                    'ba.png','bb.png','bc.png', 'bk.png', 'bn.png', 'bp.png', 'br.png']:
                continue
                
            file_name = os.path.join(root, name)
            
            img = Image.open(file_name)
            width, height = img.size
            if width >= 1000:
                new_img = img.resize((width//10, height//10), Image.LANCZOS )
                new_img.save(file_name)
            else:    
                for i in range(10):
                    ratio = int(math.pow(2, i))
                    if height / ratio >= 200:
                        continue
                    else:
                        print(height, ratio, height / ratio)    
                        new_img = img.resize((width//ratio, height//ratio), Image.LANCZOS )
                        new_img.save(file_name)
                        break
            print(file_name, img.size, new_img.size)
            
walk_folder('../skins')
            