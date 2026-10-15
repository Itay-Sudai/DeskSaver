# DeskSaver

DeskSaver is a self-taught Python project I started to solve a problem I faced myself: having to reopen and reorganize all my applications whenever I wanted to switch between different activities or return to a previous workspace.

The project grew into a desktop application that lets users save their open applications as presets and restore them later. It supports multiple presets for different activities, such as studying, programming, or gaming, as well as an online client-server version that allows presets to be shared between connected computers.

## Features

- **Workspace presets:** Save and restore groups of open applications.
- **Multiple profiles:** Create presets for different activities and switch between them whenever needed.
- **Offline mode:** Save presets locally and load them whenever you want.
- **Online mode:** Upload presets to a server and access them from other connected computers.
- **User management:** Create user accounts and manage access to saved presets.
- **Access control:** Presets can be restricted to their owners, administrators, and users who have been granted permission.
- **Server administration:** The administrator can view server presets and access server logs.

## Getting Started

### Requirements

- Python
- The Python libraries used by the project (see the imports in the source files).
- OpenSSL and a certificate configuration for setting up the online version.

Install the required libraries before running the application.

## Offline Version

The offline version runs locally and does not require a server.

1. Download `main.py`, `Desk_GUI.py`, and `DeskSaver_Disk.py`.
2. Install the required Python dependencies.
3. Run `main.py`.
4. Create a preset and give it a name.
5. Save your current applications to the preset.
6. Load the preset whenever you want to restore that workspace.

You can create as many presets as you need.

## Online Version

The online version adds a client-server system for storing and accessing presets across multiple computers.

### Server Setup

1. Download `server2.py` and the required server configuration files.
2. Generate your own TLS certificate and private key using OpenSSL.
3. Configure the server's IP address, port, and certificate paths as needed.
4. Run `server2.py` on the computer that will host the server.

### Connecting a Client

1. Run `desksaver_gui_client2.py` on the client computer.
2. Create a user account.
3. Enter the server's IP address and port.
4. Connect to the server.

The first registered user is assigned administrator privileges. Administrators can view all stored presets and access server logs.

### Sharing Presets Between Computers

Presets can be uploaded from the offline application to the online server. By default, they are visible to their owner and administrators, as well as users who have been granted permission to access them.

You can then connect to the same server from another computer, download a saved preset, and load it using the offline application.

## Notes

DeskSaver started as a personal project and evolved as I explored new features and challenged myself to build more functionality. It was not originally designed as a production-ready application, so some setup or compatibility issues may occur.

Contributions, feedback, and suggestions are welcome.