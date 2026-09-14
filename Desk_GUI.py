from Desksaver_Disk import *


class DeskMainGUI(ctk.CTk):
    """Main Menu GUI"""
    def __init__(self):
        super().__init__()
        self.title("DeskSaver")
        self.geometry(WINDOW_SIZE)
        self.my_desk = Desktop()

        ctk.CTkLabel(self, text="DeskSaver").pack(pady=10)
        ctk.set_appearance_mode("light")

        
        ctk.CTkButton(self, text="View Presets", command=self.open_view_presets_window).pack(pady=5)
        ctk.CTkButton(self, text="Add Preset", command=self.open_set_preset_window).pack(pady=5)
        ctk.CTkButton(self, text="Quit", command=self.destroy).pack(pady=5)
    

    def open_set_preset_window(self):
        
        self.withdraw()
        popup = PresetWindow(self)


    def open_view_presets_window(self):

        self.withdraw()
        popup = ViewPresets(self)
    

class PresetWindow(ctk.CTkToplevel):
    """Creates new preset window"""
    def __init__(self, master):
        super().__init__()
        self.master = master
        self.title("New Preset")
        self.geometry(WINDOW_SIZE)
        self.my_desk = Desktop()

        print("Entered")
        

        self.preset_entry = ctk.CTkEntry(self, placeholder_text="Preset name")
        self.preset_entry.pack(pady=20)


        self.submit = ctk.CTkButton(self, text="Submit", command=self.on_submit)
        self.submit.pack(pady=20)

        ctk.CTkButton(self, text="Go Back", command=self.close_popup).pack(pady=25)


    def close_popup(self):
        self.destroy()             # Close popup
        self.master.deiconify()    # Show main window again

    def on_submit(self):
        if self.my_desk.new_preset(self.preset_entry.get()):
            self.close_popup()

class ViewPresets(ctk.CTkToplevel):
    """Creates new preset window"""
    def __init__(self, master):
        super().__init__()
        self.master = master
        self.title("My Presets")
        self.geometry(WINDOW_SIZE)
        self.my_desk = Desktop()

        print("[View Presets] entered")
        

        presets = self.my_desk.choose_preset()
        for preset in presets:
            print(preset)
            ctk.CTkButton(self, text=preset, command=lambda p=preset: self.open_preset(p)).pack(pady=5)

        ctk.CTkButton(self, text="Go Back", command=self.close_popup).pack(pady=25)


    def close_popup(self):
        self.destroy()             # Close popup
        self.master.deiconify()    # Show main window again   


    def open_preset(self, preset):
        self.withdraw()
        popup = PresetOptions(self, preset)


class PresetOptions(ctk.CTkToplevel):
    """Shows commands for preset"""
    def __init__(self, master, preset):
        super().__init__()
        self.master = master
        self.title(preset)
        self.geometry(WINDOW_SIZE)
        self.my_desk = Desktop("snapshots", preset)

        print(f"[PresertOptions] - entered - {preset}")

        ctk.CTkButton(self, text="Capture", command=self.my_desk.capture).pack(pady=5)
        ctk.CTkButton(self, text="Save", command=self.my_desk.save).pack(pady=5)
        ctk.CTkButton(self, text="Load", command=self.my_desk.load).pack(pady=5)

        ctk.CTkButton(self, text="Go Back", command=self.close_popup).pack(pady=55)
        
    def close_popup(self):
        self.destroy()           # Close popup
        self.master.deiconify()    # Show main window again  
