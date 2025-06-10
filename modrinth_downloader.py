import os
import requests
from urllib.parse import urlparse
import json
import customtkinter as ctk
import threading

# --- CONFIG ---
API_BASE = "https://api.modrinth.com/v2/project/"

# --- HELPERS ---
def get_project_slug(url):
    """Extracts the project slug from a Modrinth project URL."""
    parsed = urlparse(url)
    parts = parsed.path.strip('/').split('/')
    if len(parts) >= 2 and parts[0] == 'mod':
        return parts[1]
    elif len(parts) >= 1:
        return parts[-1]
    return None

def download_file(url, dest):
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(dest, 'wb') as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

def save_text(text, dest):
    with open(dest, 'w', encoding='utf-8') as f:
        f.write(text)

def run_downloader(link, pat, log_callback):
    try:
        slug = get_project_slug(link)
        if not slug:
            log_callback("Could not extract project slug from URL.")
            return
        headers = {"Authorization": pat} if pat else {}
        resp = requests.get(API_BASE + slug, headers=headers)
        if resp.status_code != 200:
            log_callback(f"Failed to fetch project info: {resp.status_code}")
            return
        data = resp.json()
        name = data['title']
        safe_name = name.replace(' ', '_').replace('/', '_')
        downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        save_dir = os.path.join(downloads_dir, safe_name)
        os.makedirs(save_dir, exist_ok=True)
        if data.get('icon_url'):
            log_callback("Downloading icon...")
            download_file(data['icon_url'], os.path.join(save_dir, 'icon.png'))
        summary = data.get('summary', '')
        log_callback("Saving summary...")
        save_text(summary, os.path.join(save_dir, 'summary.txt'))
        links = []
        for key in ['issues_url', 'source_url', 'wiki_url', 'discord_url', 'donation_urls', 'external_url']:
            val = data.get(key)
            if isinstance(val, str) and val:
                links.append(f"{key}: {val}")
            elif isinstance(val, list):
                for v in val:
                    if isinstance(v, dict) and 'url' in v:
                        links.append(f"{key}: {v['url']}")
                    elif isinstance(v, str):
                        links.append(f"{key}: {v}")
        if 'slug' in data:
            links.append(f"project_page: https://modrinth.com/project/{data['slug']}")
        save_text('\n'.join(links), os.path.join(save_dir, 'links.txt'))
        log_callback("Fetching releases...")
        releases = requests.get(API_BASE + f"{slug}/version", headers=headers).json()
        mc_versions = set()
        for rel in releases:
            for v in rel.get('game_versions', []):
                mc_versions.add(v)
        save_text('\n'.join(sorted(mc_versions)), os.path.join(save_dir, 'versions.txt'))
        software = set()
        for rel in releases:
            for loader in rel.get('loaders', []):
                software.add(loader)
        save_text('\n'.join(sorted(software)), os.path.join(save_dir, 'software.txt'))
        gallery = data.get('gallery', [])
        if gallery:
            img_dir = os.path.join(save_dir, 'gallery')
            os.makedirs(img_dir, exist_ok=True)
            for i, img in enumerate(gallery):
                url = img.get('featured_url') or img.get('url')
                if url:
                    log_callback(f"Downloading gallery image {i+1}...")
                    ext = os.path.splitext(urlparse(url).path)[1] or '.png'
                    download_file(url, os.path.join(img_dir, f'image_{i+1}{ext}'))
        rel_dir = os.path.join(save_dir, 'releases')
        os.makedirs(rel_dir, exist_ok=True)
        for rel in releases:
            files = rel.get('files', [])
            for file in files:
                url = file.get('url')
                fname = file.get('filename')
                if url and fname:
                    log_callback(f"Downloading release file: {fname}")
                    download_file(url, os.path.join(rel_dir, fname))
        log_callback(f"All done! Files saved in: {save_dir}")
    except Exception as e:
        log_callback(f"Error: {e}")

def start_download(link, pat, log_callback):
    threading.Thread(target=run_downloader, args=(link, pat, log_callback), daemon=True).start()

def gui():
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("green")
    root = ctk.CTk()
    root.title("Modrinth Downloader")
    root.geometry("500x380")

    tabview = ctk.CTkTabview(root)
    tabview.pack(fill="both", expand=True, padx=10, pady=10)
    tab1 = tabview.add("Download")
    tab2 = tabview.add("Logs")

    # Download tab
    pat_var = ctk.StringVar()
    ctk.CTkLabel(tab1, text="Modrinth API Key (PAT):").pack(pady=(10, 0))
    pat_entry = ctk.CTkEntry(tab1, textvariable=pat_var, width=350, placeholder_text="Paste your Modrinth PAT here", show="*")
    pat_entry.pack(pady=(0, 10))

    link_var = ctk.StringVar()
    ctk.CTkLabel(tab1, text="Project Link:").pack(pady=(10, 0))
    link_entry = ctk.CTkEntry(tab1, textvariable=link_var, width=350, placeholder_text="Paste Modrinth project link here")
    link_entry.pack(pady=(0, 10))

    logbox = ctk.CTkTextbox(tab2, width=450, height=220)
    logbox.pack(padx=10, pady=10)

    def log_callback(msg):
        logbox.insert("end", msg + "\n")
        logbox.see("end")

    def on_download():
        link = link_var.get().strip()
        pat = pat_var.get().strip()
        if not link:
            log_callback("Please enter a Modrinth project link.")
            return
        if not pat:
            log_callback("Please enter your Modrinth API key (PAT).")
            return
        tabview.set("Logs")  # Switch to the Logs tab automatically
        log_callback(f"Starting download for: {link}")
        start_download(link, pat, log_callback)

    btn = ctk.CTkButton(tab1, text="Download", command=on_download)
    btn.pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    gui()