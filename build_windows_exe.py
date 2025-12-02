import os
import sys
import shutil
from pathlib import Path
from ChessUI.Version import release_version

#cmd = "pyinstaller.exe -F .\\Evolution.py -i images\\app.ico --noconsole --exclude-module PyQt5"
cmd = "pyinstaller.exe .\\Evolution.py -i ImgRes\\app.ico --clean --noconsole --exclude-module=PySide6 \
            --exclude-module=nacl --exclude-module=psycopg2"

ret = os.system(cmd)

if ret != 0:
    sys.exit(ret)

need_removes = Path('dist', 'Evolution', '_internal').glob(".//mkl_*.dll")
for file in need_removes:
    os.remove(file)
    print(f'Deleted:{file}')

'''
#shutil.rmtree('dist/Evolution/_internal/psycopg2')
for file in [
    'opengl32sw.dll',
    'Qt6Quick.dll',
    'Qt6Pdf.dll',
    'Qt6Qml.dll',
    'Qt6OpenGL.dll',
    ]:
    #os.remove(F'dist/Evolution/_internal/PySide6/{file}')
    pass
'''    

for file in [    
    'tcl86t.dll',
    'tk86t.dll',
    'libiomp5md.dll',
    'omptarget.rtl.level0.dll',
    '_brotli.cp311-win_amd64.pyd',
    'omptarget.rtl.opencl.dll',
    ]:
    os.remove(F'dist/Evolution/_internal/{file}')
 
need_removes = Path('dist', 'Evolution', '_internal', 'cv2').glob(".//opencv_videoio_ffmpeg*.dll")
for file in need_removes:
    os.remove(file)
    print(f'Deleted:{file}')

for file in [    
    'opengl32sw.dll',
    'libGLESv2.dll',
    'Qt5Quick.dll',
    'Qt5Qml.dll',
    'd3dcompiler_47.dll',
    ]:
    os.remove(F'dist/Evolution/_internal/PyQt5/Qt5/bin/{file}')


folders = ['Books', 'Game', 'Engine', 'Sound', 'Skins']
for folder in folders:
    src_folder = f".\\{folder}"
    dest_folder = f".\\dist\\Evolution\\{folder}"
    #os.mkdir(dest_folder) 
    print("*** Copying Folder:", src_folder,"-->", dest_folder)
    shutil.copytree(src_folder, dest_folder)

shutil.rmtree('build')

#os.rename('.\\dist', '.\\Evolution')
for file in [
    "Evolution.ini",
    'ReadMe.txt',
    'ReleaseNote.txt'
    ]:
    shutil.copy(file, '.\\dist\\Evolution\\')

for file in [    
    'openbook.pfBook',
    ]:
    os.remove(F'dist/Evolution/Game/{file}')
    
final_folder = f'D:\\Evolution-{release_version}'    
shutil.move('.\\dist\\Evolution', final_folder)
print(f'请到 {final_folder} 目录下查看exe文件。')
print("Done.")      