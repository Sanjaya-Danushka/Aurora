#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import json
import os
from threading import Thread

class ArchPkgManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Arch Linux Package Manager")
        self.root.geometry("800x600")
        
        # Set theme
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame with grid layout
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky='nsew')
        
        # Configure grid weights for main window
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Search frame
        search_frame = ttk.Frame(main_frame)
        search_frame.grid(row=0, column=0, columnspan=2, sticky='ew', pady=5)
        search_frame.columnconfigure(1, weight=1)
        
        # Search widgets
        ttk.Label(search_frame, text="Search:").grid(row=0, column=0, padx=(0, 5), sticky='w')
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=50)
        self.search_entry.grid(row=0, column=1, sticky='ew', padx=(0, 5))
        self.search_entry.bind('<Return>', lambda e: self.search_packages())
        
        search_btn = ttk.Button(search_frame, text="Search", command=self.search_packages)
        search_btn.grid(row=0, column=2, padx=5)
        
        # Package list frame
        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=1, column=0, columnspan=2, sticky='nsew', pady=5)
        
        # Package list
        self.tree = ttk.Treeview(tree_frame, columns=('Name', 'Version', 'Description'), show='headings')
        
        # Configure tags for different package sources
        self.tree.tag_configure('official', background='#f0f0f0')
        self.tree.tag_configure('aur', background='#f9f9ff')
        
        # Configure columns
        self.tree.heading('Name', text='Package Name', command=lambda: self.sort_column('Name', False))
        self.tree.heading('Version', text='Version', command=lambda: self.sort_column('Version', False))
        self.tree.heading('Description', text='Description')
        
        self.tree.column('Name', width=200, anchor='w')
        self.tree.column('Version', width=100, anchor='center')
        self.tree.column('Description', width=400, anchor='w')
        
        # Add scrollbars
        y_scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        x_scroll = ttk.Scrollbar(main_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        
        # Grid layout for tree and scrollbars
        self.tree.grid(row=0, column=0, sticky='nsew')
        y_scroll.grid(row=0, column=1, sticky='ns')
        x_scroll.grid(row=2, column=0, columnspan=2, sticky='ew')
        
        # Configure grid weights
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Action buttons frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=3, column=0, columnspan=2, sticky='ew', pady=5)
        
        # Action buttons
        self.install_btn = ttk.Button(btn_frame, text="Install Selected", command=self.install_package)
        self.install_btn.pack(side=tk.LEFT, padx=5)
        
        self.remove_btn = ttk.Button(btn_frame, text="Remove Selected", command=self.remove_package)
        self.remove_btn.pack(side=tk.LEFT, padx=5)
        
        refresh_btn = ttk.Button(btn_frame, text="Refresh Package List", command=self.update_package_list)
        refresh_btn.pack(side=tk.RIGHT, padx=5)
        
        # Console output
        console_frame = ttk.Frame(main_frame)
        console_frame.grid(row=4, column=0, columnspan=2, sticky='nsew', pady=5)
        
        self.console = scrolledtext.ScrolledText(console_frame, height=10, state='disabled')
        self.console.pack(fill=tk.BOTH, expand=True)
        
        # Configure weights for console frame
        console_frame.columnconfigure(0, weight=1)
        console_frame.rowconfigure(0, weight=1)
        
        # Initial package list update
        self.update_package_list()
    
    def log(self, message):
        """Add message to console"""
        self.console.config(state='normal')
        self.console.insert(tk.END, message + '\n')
        self.console.see(tk.END)
        self.console.config(state='disabled')
    
    def run_command(self, command, sudo=False):
        """Run a shell command and return the output"""
        try:
            if sudo:
                # Use pkexec for GUI password prompt
                command = ["pkexec", "--disable-internal-agent"] + command
                
            self.log(f"Running: {' '.join(command)}")
            
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Stream output in real-time
            output = []
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    self.log(line.strip())
                    output.append(line)
            
            # Check for errors
            _, stderr = process.communicate()
            if stderr and process.returncode != 0:
                self.log(f"Error: {stderr}")
                return None
                
            return ''.join(output)
            
        except Exception as e:
            self.log(f"Error running command: {str(e)}")
            return None
    
    def search_packages(self, event=None):
        """Search for packages in both official repos and AUR"""
        query = self.search_var.get().strip()
        if not query:
            return
            
        self.log(f"Searching for: {query}")
        
        # Clear current items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        def search_thread():
            try:
                # Search in official repos
                try:
                    result = self.run_command(["pacman", "-Ss", query])
                    if result:
                        self.parse_pacman_search(result)
                except Exception as e:
                    self.root.after(0, lambda: self.log(f"Error searching official repos: {str(e)}"))
                
                # Search in AUR using AUR RPC
                try:
                    import urllib.request
                    import json
                    
                    # First try AUR RPC
                    url = f"https://aur.archlinux.org/rpc/?v=5&type=search&arg={urllib.parse.quote(query)}"
                    with urllib.request.urlopen(url) as response:
                        data = json.loads(response.read().decode())
                        
                    if data.get('resultcount', 0) > 0:
                        self.root.after(0, lambda: self.parse_aur_rpc_results(data['results']))
                    
                    # Also try yay if available
                    try:
                        result = self.run_command(["yay", "-Ss", query])
                        if result and 'error: target not found' not in result:
                            self.root.after(0, lambda: self.parse_aur_search(result))
                    except (FileNotFoundError, subprocess.CalledProcessError):
                        pass
                        
                except Exception as e:
                    self.root.after(0, lambda: self.log(f"Error searching AUR: {str(e)}"))
                    
            except Exception as e:
                self.root.after(0, lambda: self.log(f"Search error: {str(e)}"))
        
        # Start search in a separate thread
        Thread(target=search_thread, daemon=True).start()
    
    def parse_pacman_search(self, output):
        """Parse pacman search results"""
        current_pkg = {}
        for line in output.split('\n'):
            if line.startswith('core/') or line.startswith('extra/') or line.startswith('community/'):
                if current_pkg:
                    self.tree.insert('', 'end', values=(
                        current_pkg.get('name', ''),
                        current_pkg.get('version', ''),
                        current_pkg.get('desc', '')
                    ))
                
                parts = line.split()
                current_pkg = {
                    'name': parts[0].split('/')[-1],
                    'version': parts[1] if len(parts) > 1 else '',
                    'desc': ' '.join(parts[2:]) if len(parts) > 2 else ''
                }
            elif line.strip() and ':' not in line:
                current_pkg['desc'] = line.strip()
        
        if current_pkg:
            self.tree.insert('', 'end', values=(
                current_pkg.get('name', ''),
                current_pkg.get('version', ''),
                current_pkg.get('desc', '')
            ))
    
    def parse_aur_search(self, output):
        """Parse yay -Ss output for AUR packages"""
        current_pkg = {}
        for line in output.split('\n'):
            if line.startswith('aur/'):
                if current_pkg:
                    self.tree.insert('', 'end', values=(
                        current_pkg.get('name', ''),
                        current_pkg.get('version', ''),
                        current_pkg.get('desc', '')
                    ), tags=('aur',))
                
                parts = line.split()
                current_pkg = {
                    'name': parts[0].split('/')[-1],
                    'version': parts[1] if len(parts) > 1 else '',
                    'desc': ' '.join(parts[2:]) if len(parts) > 2 else ''
                }
            elif line.strip() and ':' not in line:
                current_pkg['desc'] = line.strip()
        
        if current_pkg:
            self.tree.insert('', 'end', values=(
                current_pkg.get('name', ''),
                current_pkg.get('version', ''),
                current_pkg.get('desc', '')
            ), tags=('aur',))
    
    def parse_aur_rpc_results(self, packages):
        """Parse AUR RPC search results"""
        for pkg in packages:
            name = pkg.get('Name', '')
            version = pkg.get('Version', '')
            desc = pkg.get('Description', '')
            votes = pkg.get('NumVotes', 0)
            popularity = pkg.get('Popularity', 0)
            
            # Add votes and popularity to description
            desc = f"{desc} (Votes: {votes}, Popularity: {popularity:.2f})"
            
            # Insert into tree with AUR tag for styling
            self.tree.insert('', 'end', values=(
                name,
                version,
                desc
            ), tags=('aur',))
    
    def sort_column(self, col, reverse):
        """Sort tree contents when a column header is clicked"""
        # Get all items and their values
        items = [(self.tree.set(item, col), item) for item in self.tree.get_children('')]
        
        # Sort the items
        items.sort(reverse=reverse)
        
        # Rearrange items in sorted positions
        for index, (val, item) in enumerate(items):
            self.tree.move(item, '', index)
        
        # Reverse sort next time
        self.tree.heading(col, command=lambda: self.sort_column(col, not reverse))
        
        # Update the view to ensure everything is visible
        self.tree.update()

    def __init__(self, root):
        self.root = root
        self.root.title("Arch Linux Package Manager")
        self.root.geometry("800x600")
        
        # Set theme
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        # Track if an update is in progress
        self.updating = False
        
        self.setup_ui()

    def update_package_list(self):
        """Update the package list from repositories"""
        # Prevent multiple simultaneous updates
        if self.updating:
            self.log("Update already in progress...")
            return
            
        self.updating = True
        self.log("Updating package lists...")
        
        def update():
            try:
                # Create a temporary script to update both repos in one go
                update_script = """#!/bin/bash
                # Update official repos
                echo "Updating official repositories..."
                pacman -Syy
                
                # Update AUR if yay is installed
                if command -v yay &> /dev/null; then
                    echo "Updating AUR repositories..."
                    # Run yay as non-root user
                    sudo -u $SUDO_USER yay -Sy --noconfirm
                fi
                echo "Package lists updated successfully"
                """
                
                # Save script to a temporary file
                import tempfile
                import os
                
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                    f.write(update_script)
                    script_path = f.name
                
                # Make the script executable
                os.chmod(script_path, 0o755)
                
                # Run the script with a single pkexec call
                result = self.run_command([script_path], sudo=True)
                
                # Clean up the temporary script
                try:
                    os.unlink(script_path)
                except:
                    pass
                
                if result:
                    self.log(result.strip())
                
            except Exception as e:
                self.log(f"Error updating package lists: {str(e)}")
            finally:
                self.updating = False
                # Refresh the UI if needed
                self.root.after(100, self.refresh_ui)
        
        # Run in a separate thread to keep the UI responsive
        Thread(target=update, daemon=True).start()
    
    def refresh_ui(self):
        """Refresh UI elements after updates"""
        # Clear and refresh the package list
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.log("Package lists refreshed")
    
    def install_package(self):
        """Install the selected package"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a package to install")
            return
        
        pkg_name = self.tree.item(selected[0])['values'][0]
        if not pkg_name:
            return
        
        # Check if the package is from AUR (has 'aur' tag)
        is_aur = 'aur' in self.tree.item(selected[0], 'tags') if self.tree.item(selected[0], 'tags') else False
        
        if messagebox.askyesno("Confirm Install", f"Install {pkg_name}?"):
            self.log(f"Installing {pkg_name}...")
            
            def install():
                try:
                    if is_aur:
                        # For AUR packages, use yay
                        cmd = ["yay", "-S", "--noconfirm", pkg_name]
                        self.log(f"Installing AUR package: {pkg_name}")
                    else:
                        # For official packages, use pacman
                        cmd = ["pacman", "-S", "--noconfirm", pkg_name]
                        self.log(f"Installing official package: {pkg_name}")
                    
                    result = self.run_command(cmd, sudo=True)
                    if result is None:
                        self.log(f"Failed to install {pkg_name}")
                        if is_aur:
                            self.log("Note: Make sure yay is installed for AUR packages")
                    else:
                        self.log(f"Successfully installed {pkg_name}")
                        self.update_package_list()
                        
                except Exception as e:
                    self.log(f"Error during installation: {str(e)}")
            
            Thread(target=install, daemon=True).start()
    
    def remove_package(self):
        """Remove the selected package"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a package to remove")
            return
        
        pkg_name = self.tree.item(selected[0])['values'][0]
        if not pkg_name:
            return
        
        if messagebox.askyesno("Confirm Removal", f"Remove {pkg_name}?"):
            self.log(f"Removing {pkg_name}...")
            
            def remove():
                try:
                    # First try to remove with pacman
                    result = self.run_command(["pacman", "-R", "--noconfirm", pkg_name], sudo=True)
                    if result is None:
                        # If that fails, try with yay (for AUR packages)
                        result = self.run_command(["yay", "-R", "--noconfirm", pkg_name], sudo=True)
                        if result is None:
                            self.log(f"Failed to remove {pkg_name}")
                            self.log("Package might not be installed or you may need to remove dependencies manually")
                            return
                    
                    self.log(f"Successfully removed {pkg_name}")
                    self.update_package_list()
                except Exception as e:
                    self.log(f"Error during removal: {str(e)}")
            
            Thread(target=remove, daemon=True).start()

def main():
    # Check if running as root
    if os.geteuid() == 0:
        messagebox.showerror("Error", "Do not run this application as root.")
        return
    
    root = tk.Tk()
    app = ArchPkgManager(root)
    
    # Center the window
    window_width = 800
    window_height = 600
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (window_width // 2)
    y = (screen_height // 2) - (window_height // 2)
    root.geometry(f'{window_width}x{window_height}+{x}+{y}')
    
    root.mainloop()

if __name__ == "__main__":
    main()
