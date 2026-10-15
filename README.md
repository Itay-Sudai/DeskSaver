Started this project to solve a problem I was facing, then added more features as a challenge for myself.
Uploading the project here so it won't get lost.

This is aprogram that allows users to save their entire desktop workspace as a preset and restore it later. Users can create multiple presets for different activities, such as studying, programming, or gaming, and access their saved presets from other connected computers.

How to use:

There are two main programs to:
Offline version - Download - Desk_GUI.py , DeskSaver_Disk.py and main.py
Run main.py and a window will open up.
You will have the option to create a new preset, name it, save programs to it and load them back whenever you want.
You can create as many presents as you desire..

Online version - Download - server2.py - desksaver_gui_client2.py
I created a key and certificate with openssl, you can do the same.

Run server2.py and run desksaver_gui_client2.py
A screenless server will start running and a client panel will open up
Create a user, choose the correct IP addr and port that the server is running in and you will be connected.
The first User that is created will be an admin - Allowing to see all presets in the server as well as viewing server logs.
The Online version allows you to upload presets that you've saved via the offline version -
presets that are saved in the server are only visible to the user who uploaded them, the admin and users who got granted the ability to view them.
Now, you can log on to the server from a different machine, download a preset and use it with the offline version.

there are some python libraries that you will need to install in order to run the programs. View them in the code.

note: this is a personal - self taught project that I didn't account for others to use at first so problems may occur..
