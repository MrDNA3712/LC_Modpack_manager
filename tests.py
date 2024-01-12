#!/bin/python

import requests
import io
import zipfile


def download(v):
    r = requests.get(v["download_url"])
    print(r.status_code)
    buffer = io.BytesIO(r.content)
    modzip = zipfile.ZipFile(buffer)
    names = modzip.namelist()
    for name in names:
        if name.endswith(".dll"):
            print(name)
            modzip.extract(name,"BepInEx/plugins")




r=requests.get("https://thunderstore.io/c/lethal-company/api/v1/package/")
with open('list.json','w',encoding=r.encoding) as f:
    f.write(r.text)

modlist = r.json()
for m in modlist:
    name = m['name']
    if name=="MoreCompany":
        print(m["uuid4"])
        print(m["full_name"])
        for v in m["versions"]:
            print(v)
            download(v)
            break
    