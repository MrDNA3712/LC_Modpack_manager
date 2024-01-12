#!/bin/python

import argparse
import sys
import logging
import requests
import json
import os
import shutil
import io
import zipfile
from datetime import date


# commands
#  - mods
#       - add
#       - remove
#       - update
#       - list
#  - version
#       - add
#       - restore
#       - list


class Modpack:

    def __init__(self,modlist=[],dir = "current") -> None:
        self.modlist = modlist
        self.dir = dir

    def save_modlist(self):
        modfile = os.path.join(self.dir,"modfile.json")
        with open(modfile,"w") as f:
            json.dump(self.modlist,f)

    def has_mod(self,name):
        for mod in self.modlist:
            if mod["name"] == name or mod["full_name"] == name or mod["url"] == name:
                return mod
        return None

    def __check_dependencies(self, dep):
        for d in dep:
            index = d.rindex("-")
            version = d[index:]
            full_name = d[:index]
            mod = self.has_mod(full_name)
            if mod is None:
                self.add_mod(full_name)
            else:
                # TODO check version
                pass

    def __install_and_download(self,version_info):
        r = requests.get(version_info["download_url"])
        if r.status_code == 200:
            buffer = io.BytesIO(r.content)
            modzip = zipfile.ZipFile(buffer)
            modfiles = modzip.namelist()
            installed_files=[]
            for file in modfiles:
                if file.startswith("BepInEx"):
                    path = self.dir
                    rel_path=""
                elif file.endswith(".dll"):
                    path = os.path.join(self.dir,"BepInEx","plugins")
                    rel_path=os.path.join("BepInEx","plugins")
                else:
                    logging.debug("Datei %s übersprungen",file)
                    continue
                logging.debug("installiere %s nach %s",file,path)
                modzip.extract(file,path)
                if not file.endswith("/"):
                    installed_files.append(os.path.join(rel_path,file))
            mod_info={'name':version_info['name'],'version':version_info['version_number'],'uuid4':version_info['uuid4'],'files':installed_files}
            modzip.close()
            return mod_info
        else:
            logging.error("Mod konnte nicht heruntergeladen werden: %i",r.status_code)
            return None

    def __install_recent_version(self,mod):
        recent_version = mod["versions"][0]
        self.__check_dependencies(recent_version["dependencies"])
        modinfo = self.__install_and_download(recent_version)
        modinfo['url'] = mod['package_url']
        modinfo['full_name'] = mod['full_name']
        modinfo['uuid4'] = mod['uuid4']
        self.modlist.append(modinfo)
        logging.info("%s wurde installiert",mod["name"])

    def add_mod(self,name):
        if self.has_mod(name):
            logging.error("Dieser Mod ist bereits Teil des Packs!")
            return False
        selection=[]
        modlist = update_modlist()
        for mod in modlist:
            if mod["name"] == name or mod["full_name"] == name or mod["package_url"] == name:
                logging.debug("Gefunden %s",mod['full_name'])
                selection.append(mod)
        if len(selection)>1:
            logging.error('Es gibt mehr als ein Mod mit dem Namen "%s"',name)
            print("Folgende Mods wurden gefunden:")
            for mod in selection:
                print(f"{mod['full_name']}, URL: {mod['package_url']}")
            print("Bitte mit einem der oberen Ergebnisse erneut versuchen")
            return False
        elif len(selection)==0:
            logging.error('Es wurde kein Mod mit dem Namen "%s" gefunden. Bitte Groß-/Kleinschreibung beachten!',name)
            return False
        elif len(selection)==1:
            mod = selection[0]
            self.__install_recent_version(mod)

    def remove_mod(self,name):
        mod= self.has_mod(name)
        if mod is None:
            logging.error("Dieser Mod ist nicht Teil des Packs!")
            return False
        for file in mod["files"]:
            os.remove(os.path.join(self.dir,file))
            logging.debug("removed %s", file)
        self.modlist.remove(mod)
        logging.info("%s wurde entfernt", mod['name'])
        
    def update_mods(self):
        for mod in self.modlist:
            if mod['full_name']=='BepInEx-BepInExPack':
                continue
            r = self.update_mod(mod['full_name'])
            if r !=0:
                logging.warning("%s wurde übersprungen", mod['name'])

    def update_mod(self,name):
        mod = self.has_mod(name)
        if mod is None:
            logging.error("Dieser Mod ist nicht Teil des Packs!")
        modinfo = get_modinfo(mod['uuid4'])
        if modinfo == -1:
            logging.error("%s konnte nicht auf Updates überprüft werden",mod['name'])
            return -1
        recent_version = modinfo['versions'][0]
        if recent_version['version_number'] == mod['version']:
            logging.info("%s ist aktuell", mod['full_name'])
        else:
            logging.info("%s hat die neue Version %s", mod['full_name'],recent_version['version_number'])
            self.remove_mod(mod['full_name'])
            self.__install_recent_version(modinfo)
        return 0

    def list_mods(self):
        print("Derzeit installierte Mods:")
        for mod in self.modlist:
            print(f"{mod['name']}, Version: {mod['version']}, Link: {mod['url']}")
        print(f"Insgesamt {len(self.modlist)} Mods")


class VersionManager:

    def __init__(self, versions, config) -> None:
        self.versions = versions
        self.config=config

    def has_version(self, name):
        for v in self.versions:
            if name == v['name']:
                return v
        return None

    def release_version(self, name, current_dir):
        version  = self.has_version(name)
        if version is not None:
            logging.error("Die Version %s existiert bereits!", name)
            return -1
        filename = f"{config['prefix']}-{name}"
        filepath = os.path.join(config['release_dir'],filename)
        shutil.make_archive(filepath,"zip",current_dir)
        # for more complex things, complete the following
        # with  zipfile.ZipFile(filepath,"w",zipfile.ZIP_DEFLATED) as packzip:
        #     for root,dirs,files in os.walk(current_dir):
        #         ...
        versioninfo={"file":f"{filepath}.zip","name":name, "date":date.today().strftime("%d.%m.%Y")}
        self.versions.append(versioninfo)

    def restore_version(self,name):
        logging.error("Noch nicht implementiert")

    def list_versions(self):
        print("Versionen:")
        for v in self.versions:
            print(f"Version {v['name']}, erstellt am {v['date']}, Zip-Datei: {v['file']}")

def get_modinfo(uuid4):
    r=requests.get(f"https://thunderstore.io/c/lethal-company/api/v1/package/{uuid4}")
    if r.status_code == 200:
        return r.json()
    logging.error("error while getting modinfo: %i",r.status_code)
    return -1

def update_modlist():
    logging.debug("updating full modlist")
    r=requests.get("https://thunderstore.io/c/lethal-company/api/v1/package/")
    if r.status_code == 200:
        logging.debug("update complete")
        with open('full_modlist.json','w',encoding=r.encoding) as f:
            f.write(r.text)
        return r.json()
    logging.error("error while updating modlist: %i",r.status_code)
    return -1

if __name__ == '__main__':
    args = argparse.ArgumentParser(description="Lethal Company Modpack Manager")
    subparser = args.add_subparsers(title="command",dest="command")
    mods_parser = subparser.add_parser("mods",description="Verwalten von Mods")
    mods_subparser = mods_parser.add_subparsers(title="mods-command",dest="subcommand")
    mod_add_parser = mods_subparser.add_parser("add",help="Einen Mod hinzufügen")
    mod_add_parser.add_argument("name",help="Name der Mod oder URL",nargs=1)
    mod_rem_parser = mods_subparser.add_parser("remove",help="Einen Mod entfernen")
    mod_rem_parser.add_argument("name",help="Name der Mod oder URL",nargs=1)
    mod_upd_parser = mods_subparser.add_parser("update",help="Einen Mod oder alle Mods updaten")
    mod_upd_parser.add_argument("name",help="Name der Mod oder URL",nargs='?')
    mods_subparser.add_parser("list",help="Alle installierten Mods auflisten")
    version_parser = subparser.add_parser("version",help="Verwalten von Modpack Versionen")
    version_subparser = version_parser.add_subparsers(title="version-command",dest="subcommand")
    version_add_parser = version_subparser.add_parser("release",help="Aktuellen Stand als neue Version speichern")
    version_add_parser.add_argument("name",help="Name für die neue Version")
    version_swt_parser = version_subparser.add_parser("switch",help="Aktuellen Stand auf Version zurücksetzen") 
    version_swt_parser.add_argument("name", help="Name der Version")
    version_subparser.add_parser("list",help="Alle Versionen auflisten")

    print(sys.argv[1])
    argv = sys.argv[1:]

    args = args.parse_args(argv)

    logging.debug(args)

    if 'name' in args and type(args.name)==list:
        args.name = args.name[0]

    #logging.basicConfig(level=logging.DEBUG,filename='output.log',force=True)
    logging.basicConfig(level=logging.INFO,force=True)
    script_dir = os.path.dirname(__file__)

    config_file = os.path.join(script_dir,"config.json")
    if os.path.exists(config_file):
        with open(config_file,"r") as f:
            config = json.load(f)
    else:
        logging.error("Die config Datei konnte nicht gefunden werden!")
        sys.exit(-1)

    # create versions.json
    versions_file = os.path.join(script_dir,"versions.json")
    if not os.path.exists(versions_file):
        logging.debug("creating versions file: %s", versions_file)
        versions = []
        with open(versions_file,"w") as f:
            json.dump(versions,f)
    else:
        with open(versions_file,'r') as f:
            versions = json.load(f)
    

    version_manager = VersionManager(versions,config)

    # create dir for current modpack
    current_pack_dir = os.path.join(script_dir,"current")
    if not os.path.isdir(current_pack_dir):
        logging.debug("creating current dir: %s",current_pack_dir)
        shutil.copytree(os.path.join(script_dir,"default"),current_pack_dir)
    
    # create file containg all mods in the current pack
    current_modfile = os.path.join(current_pack_dir,"modfile.json")
    if not os.path.exists(current_modfile):
        logging.debug("creating modfile for current dir: %s",current_modfile)
        modlist = []
        with open(current_modfile,"w") as f:
            json.dump(modlist,f)
    else:
        logging.debug("reading modfile: %s",current_modfile)
        with open(current_modfile,"r") as f:
            modlist = json.load(f)

    current_modpack = Modpack(modlist,current_pack_dir)
    
    if args.command == "mods":
        if args.subcommand == "add":
            current_modpack.add_mod(args.name)
        elif args.subcommand == "remove":
            current_modpack.remove_mod(args.name)
        elif args.subcommand == "update":
            if args.name:
                current_modpack.update_mod(args.name)
            else:
                current_modpack.update_mods()
        elif args.subcommand == "list":
            current_modpack.list_mods()
        current_modpack.save_modlist()

    elif args.command == "version":
        if args.subcommand == "release":
            version_manager.release_version(args.name, current_pack_dir)
        elif args.subcommand == "restore":
            version_manager.restore_version(args.name)
        elif args.subcommand == "list":
            version_manager.list_versions()
        with open(versions_file,"w") as f:
            json.dump(version_manager.versions,f)