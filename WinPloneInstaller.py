import os
import platform
import io
import subprocess as sp
import time
from winreg import *
from tkinter import *
from tkinter.ttk import *
import tkinter.filedialog as filedialog
from PIL import Image, ImageTk
import winsound
import threading

class WindowsPloneInstaller:

    def __init__(self):

        try:
            self.base_path = sys._MEIPASS  # PyInstaller creates a temp folder and stores path in _MEIPASS environment variable
        except Exception:
            self.base_path = os.path.abspath(".")

        self.plone_key = r'SOFTWARE\PloneInstaller' #our Windows registry key under HKEY_CURRENT_USER

        self.required_build = 15063 #this build number required for WSL installation

        try: #Grab installation state from registry if it exists
            self.reg_key = OpenKey(HKEY_CURRENT_USER, self.plone_key, 0, KEY_ALL_ACCESS)
            self.install_status = QueryValueEx(self.reg_key, "install_status")[0]
            self.installer_path = QueryValueEx(self.reg_key, "installer_path")[0]
            self.log_path = QueryValueEx(self.reg_key, "log_path")[0]

        except: #Otherwise create it with ititial "begin" value
            self.reg_key = CreateKey(HKEY_CURRENT_USER, self.plone_key)
            self.install_status = "begin"
            SetValueEx(self.reg_key, "install_status", 1, REG_SZ, self.install_status)
            self.installer_path = os.path.realpath(__file__).split(".")[0]+".exe"
            self.log_path = os.path.dirname(self.installer_path) + "\install.log"

        SetValueEx(self.reg_key, "base_path", 1, REG_SZ, self.base_path) #This ensures powershell and bash can find this path.
        SetValueEx(self.reg_key, "installer_path", 1, REG_SZ, self.installer_path)
        SetValueEx(self.reg_key, "log_path", 1, REG_SZ, self.log_path)

        if self.install_status == "begin":
            self.play_sound("loading.wav")
            self.install_status = "elevated"
            SetValueEx(self.reg_key, "install_status", 1, REG_SZ, self.install_status)
            self.run_PS("elevate.ps1", pipe=False, hide=False)
            CloseKey(self.reg_key)
            self.kill_app()
        elif self.install_status == "elevated":
            self.get_build_number()
        elif self.install_status == "enabling_wsl":
            self.build_number = int(QueryValueEx(self.reg_key, "build_number")[0])

        self.init_GUI()

    def get_build_number(self):
        self.run_PS("get_build_number.ps1", pipe=False)
        self.build_number = int(QueryValueEx(self.reg_key, "build_number")[0])

    def play_sound(self, sound_name):
        t = threading.Thread(target=self.play_sound_helper, args=(sound_name,))
        t.start()

    def play_sound_helper(self, sound_name):
        winsound.PlaySound(self.base_path+"\\resources\\"+sound_name, winsound.SND_FILENAME)

    def init_GUI(self):
        self.gui = Tk()
        self.gui.title("Windows Plone Installer")
        window_width = 500
        window_height = 330
        self.fr1 = Frame(self.gui, width=window_width, height=window_height)
        self.fr1.pack(side="top")

        self.make_shortcut = IntVar(value=1)
        self.default_password = IntVar(value=1)
        self.default_directory = IntVar(value=1)
        self.auto_restart = IntVar(value=1)

        #GUI Row 0
        self.log_text = Text(self.fr1, borderwidth=3, relief="sunken",spacing1=1, height=8, width=50, bg="black", fg="white")
        self.log_text.config(font=("consolas", 12), undo=True, wrap='word')
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=2, pady=2) 

        scrollb = Scrollbar(self.fr1, command=self.log_text.yview)
        scrollb.grid(row=0, column=1, sticky='nsew')
        self.log_text['yscrollcommand'] = scrollb.set

        #GUI Row 1
        self.progress = Progressbar(self.fr1, orient="horizontal", length=200, mode="determinate")
        self.progress.grid(row=1, sticky="EW")

        #GUI Row 2
        Checkbutton(self.fr1, text="Create Plone Desktop shortcut", variable=self.make_shortcut).grid(row=2,sticky="EW")

        #GUI Row 3
        default_pass_button = Checkbutton(self.fr1, text="Use username:admin password:admin for Plone (otherwise be prompted)", variable=self.default_password)
        default_pass_button.grid(row=3,sticky="EW")

         #GUI Row 4
        default_dir_button = Checkbutton(self.fr1, text="Install to default directory (otherwise be prompted)", variable=self.default_directory)
        default_dir_button.grid(row=4, sticky="EW")

         #GUI Row 5
        self.auto_restart_checkbutton = Checkbutton(self.fr1, text="Reboot automatically (otherwise be prompted)", variable=self.auto_restart)
        self.auto_restart_checkbutton.grid(row=5,stick="EW")

        #GUI Row 6
        button_frame = Frame(self.fr1)

        load_logo = Image.open(self.base_path + '\\resources\\plone.png')
        logo = ImageTk.PhotoImage(load_logo.resize((40, 40), Image.ANTIALIAS))
        img = Label(button_frame, image=logo)
        img.grid(row=0, column=0, sticky="E")

        self.okaybutton = Button(button_frame, text="Okay")
        self.okaybutton.grid(row = 0, column=1, sticky="E")
        self.okaybutton.bind("<Button>", self.okay_handler)

        cancelbutton = Button(button_frame, text="Cancel")
        cancelbutton.grid(row = 0, column = 2, sticky="W")
        cancelbutton.bind("<Button>", self.cancel_handler)
        self.fin = ''

        button_frame.grid(row=6)

        self.log("Welcome to Plone Installer for Windows.")
        self.log("This log can be found in the install.log file in the installer directory.")

        try:
            self.get_reg_vars()
        except:
            self.log("No previous installation config found.", display=False)

        if self.install_status == "enabling_wsl":
            self.install_wsl()

        self.log("This system has Windows build number " + str(self.build_number))

        if self.build_number < self.required_build:
            self.log("Windows 10 with Creator's Update (build 15063) required to install on WSL (recommended)")
            self.log("Will install Plone with buildout")
            default_pass_button.grid_forget() #default password is always used for buildout version
            self.auto_restart_checkbutton.grid_forget() #No restart necessary for buildout version
            window_height = 290
            self.fr1.config(height=window_height)
        else:
            self.log("Plone can be installed on WSL on this machine (recommended)")
            default_dir_button.grid_forget()
            window_height = 310
            self.fr1.config(height=window_height)

        self.log("Configure and select Okay.")

        #GUI Settings
        ws = self.gui.winfo_screenwidth()
        hs = self.gui.winfo_screenheight()
        x = (ws/2) - (window_width/2)
        y = (hs/2) - (window_height/2)
        self.gui.geometry('%dx%d+%d+%d' % (window_width, window_height, x, y))

        self.gui.mainloop()
        
    def okay_handler(self, event):
        self.okaybutton.configure(state="disabled")
        if self.install_status == "elevated":
            self.play_sound("begin.wav")
            self.set_reg_vars()
            self.check_connection()
            self.init_install()
        elif self.install_status == "enabling_wsl":
            self.restart_computer()
        elif self.install_status == "complete":
            self.kill_app()

    def cancel_handler(self, event):
        self.kill_app()

    def init_install(self):
        if self.build_number < self.required_build:
            self.install_plone_buildout()
        else:
            self.check_wsl()

    def check_connection(self):
        connection_trouble = 1
        attempts = 0
        self.log("Checking for internet connection")
        while connection_trouble == 1:
            connection_trouble = os.system("ping -n 1 plone.org") #successful ping with return 0
            attempts += 1
            if attempts == 1:
                if connection_trouble == 1:
                    self.log("First attempt at connecting has failed. Will keep trying for a minute, please check connection.")
                else:
                    break
            if attempts == 60:
                self.log("An internet connection has not been made.")
                self.log("Please reopen the installer to retry later. Thank you!")
                time.sleep(4)
                self.kill_app()
            time.sleep(2)
        self.log("Connection established.")
        return

    def install_plone_buildout(self):
        if self.default_directory.get():
            self.install_directory = "C:\\Program Files"
        else:
            self.install_directory = ''
            self.log("A dialog will appear. A \Plone directory will be added to the one you choose.")
            time.sleep(4)

            while self.install_directory == '': #make sure user selects a valid directory
                self.install_directory = filedialog.askdirectory()

        self.install_directory = self.install_directory.replace("/", "\\")
        self.log("Will install to "+self.install_directory+"\\Plone")
        SetValueEx(self.reg_key, "install_directory", 1, REG_SZ, self.install_directory)

        self.progress["value"] = 5 #Don't want them to worry while Chocolatey installs :)
        self.log("Installing Chocolatey package manager...")
        self.run_PS("install_choco.ps1", pipe=False)
        self.log("Chocolatey Installed")
        self.progress["value"] = 25
        self.run_PS("install_plone_buildout.ps1", pipe=False, hide=False)
        self.progress["value"] = 95
        self.log("Installation Complete")
        self.clean_up()
            
    def check_wsl(self):
        if self.install_status == "enabling_wsl":
            self.okaybutton.configure(state="disabled")
            self.log("Picking up where we left off. Installing Linux Subsystem...")
            self.check_connection()
            self.install_wsl()
        else:
            self.run_PS("check_wsl.ps1") #PS_status_handler will end up taking care of next steps

    def enable_wsl(self):
        ps_process = sp.Popen(["C:\\WINDOWS\\system32\\WindowsPowerShell\\v1.0\\powershell.exe", "-WindowStyle", "Hidden", "Enable-WindowsOptionalFeature -Online -NoRestart -FeatureName Microsoft-Windows-Subsystem-Linux"])
        ps_process.wait()
        self.progress["value"] = 15
        self.play_sound("attention.wav")
        self.gui.focus_force()
        if self.auto_restart.get():
            self.restart_computer()
        else:
            self.install_status = "enabling_wsl"
            self.okaybutton.configure(state="enabled")
            self.log("Please press Okay when you're ready to restart!")

    def install_wsl(self):
        self.run_PS("install_wsl.ps1", pipe=False, hide=False)
        self.install_status = QueryValueEx(self.reg_key, "install_status")[0]
        if self.install_status == "wsl_installed":
            self.install_plone_wsl()
        else:
            self.log("There was a problem enabling/installing WSL!")
            self.kill_app()

    def install_plone_wsl(self):
        self.progress["value"] = 35
        self.update_bash_script()
        self.run_PS("install_plone_wsl.ps1", pipe=False, hide=False) #Install Plone on the new instance of WSL
        self.log("Plone Installed Successfully")
        self.progress["value"] = 95
        self.clean_up()

    def update_bash_script(self):
        install_call = "sudo ./install.sh"

        if self.default_password.get():
            install_call += " --password=admin"

        install_call += " --target=/etc/Plone"

        install_call += " standalone"

        with io.open(self.base_path + "\\bash\\install_plone.sh", "a", newline='\n') as bash_script: #io.open allows explicit unix-style newline characters
            bash_script.write("\n"+install_call)
            bash_script.write("\necho Press any key and the Plone installer will clean up and finish.")
            bash_script.write("\nread -n 1 -s")
            bash_script.close()

    def set_reg_vars(self):
        SetValueEx(self.reg_key, "make_shortcut", 1, REG_SZ, str(self.make_shortcut.get()))
        SetValueEx(self.reg_key, "default_directory", 1, REG_SZ, str(self.default_directory.get()))
        SetValueEx(self.reg_key, "default_password", 1, REG_SZ, str(self.default_password.get()))
        SetValueEx(self.reg_key, "auto_restart", 1, REG_SZ, str(self.auto_restart.get()))

    def get_reg_vars(self):
        self.make_shortcut.set(int(QueryValueEx(self.reg_key, "make_shortcut")[0]))
        self.default_directory.set(int(QueryValueEx(self.reg_key, "default_directory")[0]))
        self.default_password.set(int(QueryValueEx(self.reg_key, "default_password")[0]))
        self.auto_restart.set(int(QueryValueEx(self.reg_key, "auto_restart")[0]))

    def run_PS(self,script_name, pipe=True, hide=True):
        script_path = self.base_path+"\\PS\\"+script_name

        if pipe and hide:
            self.log("Calling " + script_name + " in Microsoft PowerShell, please accept any prompts.")
            ps_process = sp.Popen(["C:\\WINDOWS\\system32\\WindowsPowerShell\\v1.0\\powershell.exe", "-ExecutionPolicy", "Unrestricted", "-WindowStyle", "Hidden", ". " + script_path], stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)

            status = "normal"
            while True:
                line = ps_process.stdout.readline().decode("utf-8").rstrip()
                if line != '':                    
                    if line[:2] == "**": #this is a log flag echoed out from the powershell process.
                        self.log(line[2:])
                    elif line[:2] == "*!": #this is an important status/command flag to the installer from the powershell process.
                        status = line[2:]
                        self.log(status)
                        break #we need to get out of this loop before we proceed with the message for control flow
                    else:
                        self.log(line, display=False)
                else:
                    break #No more lines to read from the PowerShell process.

            if status == "normal":
                return
            else:
                self.PS_status_handler(status)
        elif hide:
            ps_process = sp.Popen(["C:\\WINDOWS\\system32\\WindowsPowerShell\\v1.0\\powershell.exe", "-ExecutionPolicy", "Unrestricted", "-WindowStyle", "Hidden", ". " + script_path])
            ps_process.wait()
        else: #This will have to change if there's ever a reason for pipe=True & hide=False (doubtful)
            self.log("Please follow PowerShell prompts to continue. Calling " + script_name + " in Microsoft PowerShell.")
            ps_process = sp.Popen(["C:\\WINDOWS\\system32\\WindowsPowerShell\\v1.0\\powershell.exe", "-ExecutionPolicy", "Unrestricted", ". " + script_path])
            if script_name != "elevate.ps1": #quick fix for now, gui doesn't exist yet when elevate is called.
                self.gui.withdraw() #We'll close our window and focus on PowerShell
            ps_process.wait()
            if script_name != "elevate.ps1": #quick fix for now, gui doesn't exist yet when elevate is called.
                self.gui.deiconify()

    def PS_status_handler(self, status):
        if status == "Enabling WSL":
            self.progress["value"] = 5
            self.enable_wsl()
        elif status == "Installing WSL":
            self.log('Linux Subsystem is enabled')
            self.progress["value"] = 15
            self.install_wsl()
        elif status == "Installing Plone on WSL":
            self.install_plone_wsl()
        elif status == "Plone Installed Succesffully":
            self.progress["value"] = 95
            self.clean_up()

    def log(self, message, display=True):
        with open(self.log_path, "a") as log:
            log.write(message+"\n")
        if display:
            try:
                self.log_text.config(state="normal")
                self.log_text.insert(END, "> " + message + '\n')
                self.log_text.config(state="disabled")
                self.log_text.see(END)
                self.gui.update()
            except Exception as e:
                print("Tried to log before text object exists.")

    def restart_computer(self):
        self.log("Installation should continue after the machine restarts, thank you.")
        CloseKey(self.reg_key)
        time.sleep(15)
        ps_process = sp.Popen(["C:\\WINDOWS\\system32\\WindowsPowerShell\\v1.0\\powershell.exe", "-WindowStyle", "Hidden", "Restart-Computer"])

    def clean_up(self):
        self.log('Cleaning up.')
        self.progress["value"] = 100
        self.play_sound("complete.wav")
        self.log("Thank you! Press Finish to end the installer.")
        self.install_status = "complete"
        self.okaybutton.configure(state="enabled", text="Finish")

        if self.make_shortcut.get():
            self.create_shortcut()

        if self.build_number >= self.required_build:
            self.log("To start Plone manually later, use 'sudo -u plone_daemon /etc/Plone/zinstance/bin/plonectl console' in Bash.")
        else:
            self.log("To start Plone manually later, use '"+self.install_directory+"\\Plone\\bin\\instance fg' in PowerShell.")

        CloseKey(self.reg_key)
        DeleteKey(HKEY_CURRENT_USER, self.plone_key)

    def create_shortcut(self):
        if self.build_number >= self.required_build:
            self.run_PS("create_shortcut_wsl.ps1", pipe=False)
            self.log("You'll need to remember your UNIX/WSL password when you use the Plone shortcut.")
        else:
            self.run_PS("create_shortcut_buildout.ps1", pipe=False)
        
        self.log("Plone Desktop shortcut created.")

    def kill_app(self):
        sys.exit(0)

if __name__ == "__main__":
    try:
        app = WindowsPloneInstaller()
    except KeyboardInterrupt:
        raise SystemExit("Aborted by user request.")