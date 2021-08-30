import sys
import requests
import platform
from PyQt5.QtWidgets import * 
from PyQt5.QtGui import * 
from PyQt5.QtCore import *
from pathlib import Path
import os
import stat
import time
import math
import zipfile
from tqdm import tqdm
import subprocess

app = QApplication(sys.argv)
window = QWidget()
window.setGeometry(0, 0, 500, 250)
window.setWindowTitle("Basebane! Launcher")

errwindow = QWidget()
errwindow.setGeometry(0, 0, 500, 250)
errwindow.setWindowTitle("Error - Basebane! Launcher")

status = QLabel("Ready.", window)
status.setFont(QFont("Arial", 12))
status.setWordWrap(True)
status.setStyleSheet("background-color:black;font-family:monospace;color:white;padding:5px;")
status.resize(480,75)
status.move(10,155)
status.setAlignment(Qt.AlignTop)

title = QLabel("Basebane! Launcher", window)
title.setStyleSheet("font-weight:bold")
title.setFont(QFont("Arial", 30))
title.move(10,10)

sel_release = QLabel("Release:", window)
sel_release.setFont(QFont("Arial", 18))
sel_release.move(10,75)

releases = QComboBox(window)
releases.resize(150,28)
releases.move(110,75)

manage_releases = QPushButton("Manage releases", window)
manage_releases.setFont(QFont("Arial", 12))
manage_releases.resize(150,28)
manage_releases.move(270,75)

play_btn = QPushButton("Play!", window)
play_btn.setFont(QFont("Arial", 12))
play_btn.resize(480,40)
play_btn.move(10,110)

footer = QLabel("Basebane! Launcher v0.01. Your operating system: " + str(platform.system()), window)
footer.move(10,230)

supported_os = ["Windows", "Linux"]

def error(msg):
    window.hide()
    errorlbl = QLabel(msg, errwindow)
    errorlbl.setFont(QFont("Arial", 16))
    errorlbl.move(10,10)
    errorlbl.setStyleSheet("color:tomato")
    errorlbl.setWordWrap(True)
    footer = QLabel("Basebane! Launcher v0.01. Your operating system: " + str(platform.system()), errwindow)
    footer.move(10,220)
    errwindow.show()

#----#
program_path = str(Path.home()) + "/.basebane"
program_path = str(os.path.abspath(program_path))
local_installs_file = str(os.path.abspath(program_path + "/local"))
installs_dir = str(os.path.abspath(program_path + "/installs"))
dont_show_window = False
no_internet = False
releases_dict = {}
status_text = ""
#----#

class PlayWorker(QObject):
    finished = pyqtSignal()

    def _play(self):
        print("PlayWorker Thread:\tStarting ...")
        play_btn.setEnabled(False)
        manage_releases.setEnabled(False)
        releases.setEnabled(False)
        global status_text

        if (platform.system() not in supported_os):
            print("PlayWorker Thread:\tError: Refusing to launch game. Unsupported platform")
            return
        installation_selected = releases.currentText()
        print("PlayWorker Thread:\tInstallSelected="+str(installation_selected))
        # make sure it isn't installed somewhere else
        exists = False
        entryExists = False
        game_install_path = os.path.abspath(installs_dir + "/" + releases.currentText() + "/" + releases.currentText())
        with open(local_installs_file, "r") as f:
            contents = f.read()
            local_releases = contents.split("\n")
            if (len(local_releases) == 0 or local_releases[0].strip()==""):
                exists = False
            else:
                for release in local_releases:
                    if (release.strip()==""):
                        continue
                    release_name = release.split("=")[0]
                    release_loc = release.split("=")[1]
                    if (release_name == installation_selected):
                        print("PlayWorker Thread:\tRelease exists in local db")
                        if (os.path.exists(release_loc)):
                            game_install_path = release_loc
                            exists = True
                        else:
                            status.setText("Error: An entry for this release exists on the Local Releases Database, but it points to a non-existent file.")
                            exists = True
                            self.finished.emit()
                            return
        game_install_dir = os.path.dirname(game_install_path)
        rel_inf = os.path.abspath(game_install_dir + "/relinf")
        if (exists == False):
            if (os.path.exists(game_install_dir) == False):
                try:
                    os.mkdir(game_install_dir)
                except Exception as e:
                    status.setText("Cannot start game: " + str(e))
                    self.finished.emit()
                    return
            game_install_path = os.path.abspath(game_install_dir + "/" + installation_selected + ".zip")

        if (exists == True):
            print("PlayWorker Thread:\tInstall exists")
        else:
            if (os.path.exists(rel_inf)):
                status.setText("Error: Release binary does not exist, but release info file exists.")
                self.finished.emit()
                return
            print("PlayWorker Thread:\tDownloading release ...")
            link = releases_dict[installation_selected]
            try:
                header = requests.head(link)
            except Exception as e:
                status.setText("Error: Couldn't download metadata for release: the connection was interrupted")
                self.finished.emit()
                return
            total_length = 0
            chunks_dl = 0
            if (header.headers['content-length'] != None):
                total_length = header.headers['content-length']
            total_length_mb = int(total_length) / 1048576
            status.setText("Downloading release ... (0 MB / " + str(round(total_length_mb, 2)) + " MB)")
            if (os.path.exists(game_install_path)):
                status.setText("Error: Game install path exists but it's not listed in Local Install DB")
                self.finished.emit()
                return
            print("PlayWorker Thread:\tcontent_length-->"+header.headers['content-length'])
            try:
                with requests.get(link, stream=True) as r:
                    r.raise_for_status()
                    with open(game_install_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=4096): 
                            chunks_dl += len(chunk)
                            chunks_dl_mb = (int(chunks_dl) / 1048576)
                            status.setText("Downloading release ... ("+ str(round(chunks_dl_mb, 2)) +" MB / " + str(round(total_length_mb, 2)) + " MB)")
                            f.write(chunk)
                    print("PlayWorker Thread:\tFinished download")
            except Exception as e:
                status.setText("Error: cannot download release: the connection was interrupted")
                self.finished.emit()
                return
            
            status.setText("Extracting release ... 0 %%")

            zf = zipfile.ZipFile(game_install_path)

            uncompress_size = sum((file.file_size for file in zf.infolist()))
            extractdir = os.path.abspath(game_install_dir + "/")
            extracted_size = 0

            for file in zf.infolist():
                extracted_size += file.file_size
                status.setText("Extracting release ... %s %%" % (extracted_size * 100/uncompress_size))
                game_install_path = os.path.abspath(extractdir + "/" + str(file.filename))
                if (os.path.exists(game_install_path)):
                    status.setText("Error: Game install path exists but it's not listed in Local Install DB")
                    self.finished.emit()
                    return
                else:
                    zf.extract(file, extractdir)

            print("PlayWorker Thread:\tGAME_INSTALL_PATH="+str(game_install_path))
            print("PlayWorker Thread:\tGAME_INSTALL_DIR="+str(game_install_dir))

            status.setText("Registering release ...")
            with open(local_installs_file, "a") as f:
                f.write(str(installation_selected) + "=" + game_install_path + "\n")
                f.close()
            with open(rel_inf, "w") as f:
                f.write("sha1=\ngamedir=\nstartupArgs=\n")
                f.close()
        time.sleep(1)

        status.setText("Launching game ...")

        if (platform.system() == "Linux"):
            st = os.stat(game_install_path)
            os.chmod(game_install_path, st.st_mode | stat.S_IEXEC)

        with open(os.path.abspath(installs_dir + "/lockfile"), "w") as f:
            f.write(str(game_install_path) + ";" + str(time.time()) + ";" + str(installation_selected))
            f.close()

        status.setText("Busy. (game running)")
        subprocess.call(game_install_path)

        print("PlayWorker Thread:\tMy job here is done. Have a nice day!")
        os.remove(os.path.abspath(installs_dir + "/lockfile"))
        status.setText("Ready.")
        self.finished.emit()

class ReleaseWorker(QObject):
    finished = pyqtSignal()

    class ChildDlg(QWidget):
        closed = pyqtSignal()
        def closeEvent(self, event):
            self.closed.emit()
            self.hide()

    def _hide_edit_gui(self):
        self.mr_local_releases.setEnabled(True)
        self.mr_edit_rel.setEnabled(True)
        self.mr_rm_rel.setEnabled(True)
        self.mr_edit_attribute.hide()
        self.mr_lw.hide()
        self.mr_textbox.hide()
        self.mr_chval.hide()
        self.mr_warnings.hide()
        self.mr_save_changes.hide()
        self.mr_discard_changes.hide()

    def _show_edit_gui(self):
        self.mr_local_releases.setEnabled(False)
        self.mr_edit_rel.setEnabled(False)
        self.mr_rm_rel.setEnabled(False)
        self.mr_edit_attribute.show()
        self.mr_lw.show()
        self.mr_textbox.show()
        self.mr_chval.show()
        self.mr_warnings.show()
        self.mr_save_changes.show()
        self.mr_discard_changes.show()

    def _open_edit_gui(self):
        self.protected_values = ["sha1"]
        print("ReleaseWorker Thread:\tOpening EDIT GUI ...")
        releaseToEdit = self.mr_local_releases.currentText()
        self.tmp_attr = {}
        self.mr_edit_attribute.setText("Editing attributes for release " + str(releaseToEdit))
        rel_dirname = os.path.dirname(self.lcl_install_dict[releaseToEdit])
        print("ReleaseWorker Thread:\tREL_DRNM="+str(rel_dirname))
        relinf_loc = os.path.abspath(rel_dirname + "/relinf")
        if (os.path.exists(relinf_loc)==False):
            self.mr_messages.setText("Error: cannot edit release: relinf missing.")
            return
        with open(relinf_loc) as f:
            relinf_contents = f.read().split("\n")
            f.close()
        for attr in relinf_contents:
            print("ReleaseWorker Thread:\tParsing " + attr)
            if (attr.strip()==""):
                continue
            attrNm = attr.split("=")[0]
            attrVal = attr.split("=")[1]
            self.tmp_attr[attrNm] = attrVal
            self.mr_lw.addItem(attrNm)
        self._show_edit_gui()

    def _lw_select(self):
        selectedVar = self.mr_lw.currentItem().text()
        self.mr_textbox.setText(self.tmp_attr[selectedVar])
        if (selectedVar in self.protected_values):
            self.mr_warnings.setText("Warning: Changing this value may cause the game to not run")
        else:
            self.mr_warnings.setText("")

    def _create_children(self):
        self.mr_win_title = QLabel("Manage Releases", self.mr_win)
        self.mr_win_title.setFont(QFont("Arial", 18))
        self.mr_win_title.setStyleSheet("font-weight:bold")
        self.mr_win_title.move(10,10)

        self.mr_lcl_rel_text = QLabel("Release: ", self.mr_win)
        self.mr_lcl_rel_text.setFont(QFont("Arial", 14))
        self.mr_lcl_rel_text.move(10,45)

        self.mr_local_releases = QComboBox(self.mr_win)
        self.mr_local_releases.resize(100,35)
        self.mr_local_releases.move(90,40)

        self.mr_edit_rel = QPushButton("Edit release", self.mr_win)
        self.mr_edit_rel.move(200,45)
        self.mr_rm_rel = QPushButton("Remove release", self.mr_win)
        self.mr_rm_rel.move(290,45)

        self.mr_messages = QLabel("", self.mr_win)
        self.mr_messages.setFont(QFont("Arial", 16))
        self.mr_messages.move(10,80)
        self.mr_messages.resize(480,60)
        self.mr_messages.setWordWrap(True)
        self.mr_messages.setStyleSheet("border:3px solid black")

        self.mr_edit_attribute = QLabel("Edit attributes for None", self.mr_win)
        self.mr_edit_attribute.setFont(QFont("Arial", 18))
        self.mr_edit_attribute.move(10,160)

        self.mr_lw = QListWidget(self.mr_win)
        self.mr_lw.resize(300,200)
        self.mr_lw.move(10,190)

        self.mr_chval = QLabel("Value:",self.mr_win)
        self.mr_chval.setFont(QFont("Arial", 14))
        self.mr_chval.move(320,195)

        self.mr_textbox = QLineEdit(self.mr_win)
        self.mr_textbox.resize(170,25)
        self.mr_textbox.move(320,225)

        self.mr_warnings = QLabel("", self.mr_win)
        self.mr_warnings.resize(170,75)
        self.mr_warnings.setFont(QFont("Arial", 12))
        self.mr_warnings.move(320,255)
        self.mr_warnings.setAlignment(Qt.AlignTop)
        self.mr_warnings.setWordWrap(True)
        self.mr_warnings.setStyleSheet("border:1px solid black")

        self.mr_save_changes = QPushButton("Save changes", self.mr_win)
        self.mr_save_changes.resize(170,25)
        self.mr_save_changes.move(320,335)

        self.mr_discard_changes = QPushButton("Discard changes", self.mr_win)
        self.mr_discard_changes.resize(170,25)
        self.mr_discard_changes.move(320,365)

    def _mng_rel(self):
        status.setText("Busy. (Release manager open)")
        manage_releases.setEnabled(False)
        play_btn.setEnabled(False)
        print("ReleaseWorker Thread:\tStarted")
        self.mr_win = self.ChildDlg(window)
        self.mr_win.setWindowTitle("mrwin")

        self._create_children()
        self._hide_edit_gui()
        self.lcl_install_dict = {}

        f = open(local_installs_file, "r")
        contents = f.read()
        install_file = contents.split("\n")
        f.close()

        if (len(install_file) == 0 or install_file[0].strip() == ""):
            self.mr_edit_rel.setEnabled(False)
            self.mr_rm_rel.setEnabled(False)
            self.mr_local_releases.setEnabled(False)
            self.mr_messages.setText("You don't have any local releases to manage.")
        else:
            for installs in install_file:
                if installs.strip()=="":
                    continue
                install_name = installs.split("=")[0]
                install_loc = installs.split("=")[1]
                self.mr_local_releases.addItem(install_name)
                self.lcl_install_dict[install_name] = install_loc

        self.mr_edit_rel.clicked.connect(self._open_edit_gui)
        self.mr_discard_changes.clicked.connect(self._hide_edit_gui)
        self.mr_lw.clicked.connect(self._lw_select)

        self.mr_win.resize(500, 400)
        self.mr_win.closed.connect(self._finish)
        self.mr_win.show()
                
    def _finish(self):
        print("ReleaseWorker Thread:\tGoodbye!")
        status.setText("Ready.")
        #del self.mr_win
        self.finished.emit()

thread = QThread()
worker = PlayWorker()

rel_thread = QThread()
rel_worker = ReleaseWorker()

def _play_worker_quit():
    play_btn.setEnabled(True)
    manage_releases.setEnabled(True)
    releases.setEnabled(True)
    thread.quit()

def _play_worker():
    global worker
    global thread
    worker.moveToThread(thread)
    thread.started.connect(worker._play)
    worker.finished.connect(_play_worker_quit)
    thread.start()

def _mng_rel_worker_quit():
    global rel_worker
    manage_releases.setEnabled(True)
    play_btn.setEnabled(True)
    rel_thread.quit()
    rel_worker.deleteLater()
    rel_worker = ReleaseWorker()

def _mng_rel_worker():
    global rel_thread
    global rel_worker
    rel_worker.moveToThread(rel_thread)
    rel_thread.started.connect(rel_worker._mng_rel)
    rel_worker.finished.connect(_mng_rel_worker_quit)
    rel_thread.start()

def main_win():
    global dont_show_window
    global no_internet
    global releases_dict
    global status_text

    install_file = []
    print("Debug:\tProgram Path: " + str(program_path))

    if (platform.system() not in supported_os):
        error("Error: your OS (" + str(platform.system()) + ") is not supported by 'Basebane!'.")
        dont_show_window = True
    
    if (os.path.exists(program_path) == False):
        try:
            os.mkdir(program_path)
        except Exception as e:
            error("Error: Cannot create program path '" + str(program_path) + "' and it's subpaths: " + str(e))
            dont_show_window = True
    else:
        print("Debug:\tProgram path exists")

    if (os.path.exists(installs_dir) == False):
        try:
            os.mkdir(installs_dir)
        except Exception as e:
            error("Error: Cannot create installs dir '" + str(installs_dir) + "': " + str(e))
            dont_show_window = True

    if (os.path.exists(local_installs_file) == False):
        try:
            f = open(local_installs_file, "w")
            f.write("")
            f.close()
        except Exception as e:
            error("Error: Cannot create installs file '" + str(local_installs_file) + "': " + str(e))
            dont_show_window = True

    url = "http://www.google.com"
    timeout = 5

    try:
        request = requests.get(url, timeout=timeout)
    except:
        status.setText("You don't have an internet connection, you can only play versions of Basebane you have downloaded before")
        no_internet = True

    if (dont_show_window == False):
        window.show()

    remote_install_loc = "http://bbexports.glitch.me/install_.txt"

    if (no_internet):
        f = open(local_installs_file, "r")
        contents = f.read()
        install_file = contents.split("\n")
        f.close()
    else:
        if (platform.system() == "Windows"):
            remote_install_loc = "http://bbexports.glitch.me/install_win.txt"
        elif (platform.system() == "Linux"):
            remote_install_loc = "http://bbexports.glitch.me/install_linux.txt"
        try:
            remote_install_file = requests.get(remote_install_loc)
            contents = remote_install_file.text
            install_file = contents.split("\n")
        except:
            status.setText("Error whilst downloading and/or parsing remote install file. Using local one instead.")
            f = open(local_installs_file, "r")
            contents = f.read()
            install_file = contents.split("\n")
            f.close()

    if (len(install_file) == 0 or install_file[0].strip() == ""):
        releases.addItem("None")
        play_btn.setText("No local releases found")
        play_btn.setEnabled(False)
        manage_releases.setEnabled(False)
        releases.setEnabled(False)
    else:
        for release in install_file:
            release_name = release.split("=")[0]
            release_url = release.split("=")[1]
            releases_dict[release_name] = release_url
            releases.addItem(release_name)

    if (os.path.exists(os.path.abspath(installs_dir + "/lockfile"))):
        contents = ""
        with open(os.path.abspath(installs_dir + "/lockfile"), "r") as f:
            contents = f.read()
            f.close()
        contents = contents.split(";")
        status.setText("Busy. (game running)\nA " + str(contents[2]) + " instance is running. Please close that instance before starting another one.")
        play_btn.setEnabled(False)
        manage_releases.setEnabled(False)
        releases.setEnabled(False)

    play_btn.clicked.connect(_play_worker)
    manage_releases.clicked.connect(_mng_rel_worker)
    sys.exit(app.exec_())

if __name__ == "__main__":
    main_win()