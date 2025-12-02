
import os
import sys
import json
import requests

url_base = 'http://127.0.0.1:8000'  

ret = requests.get(f'{url_base}/querybest', params = {'fen' : 'rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w'})
print(ret.text)
