from .. import core, VERSION
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from asyncio import run, sleep, create_task, wait_for, TimeoutError
import uvicorn
import sys
import aiohttp
import tempfile
import os
from pathlib import Path


app = FastAPI()
manager = core.wrapper.InstanceManager()
config = core.config.Config()


@app.get("/")
async def root(request: Request):
    return {
        "message": "Welcome to the https://github.com/nichind/pybalt api, you can use it just like you would use any normal cobalt instance, the response would be always from the fastest instance to answer to the request",
        "version": VERSION,
        "instance_count": len(manager.all_instances),
    }


async def check_file_size(url, timeout=2):
    """
    Quickly check if a file has non-zero size by starting to download it.
    
    Args:
        url: URL to check
        timeout: Maximum time to spend checking in seconds
    
    Returns:
        Tuple of (is_valid, instance_url) where:
        - is_valid: True if file has non-zero size, False otherwise
        - instance_url: The hostname of the instance that provided the file
    """
    try:
        # Extract instance hostname from URL
        instance_url = url.split('/')[2] if '://' in url else None
        
        # Create a temporary file for the download
        temp_file = Path(tempfile.gettempdir()) / f"pybalt_check_{os.urandom(4).hex()}"
        
        async with aiohttp.ClientSession() as session:
            # Get the headers first to check if the server accepts range requests
            head_resp = await wait_for(session.head(url), timeout=timeout/2)
            
            # Try to download just the first few bytes
            async with session.get(url, headers={"Range": "bytes=0-1024"}, timeout=timeout) as resp:
                if resp.status == 206:  # Partial content (range request worked)
                    chunk = await resp.content.read(1024)
                    if len(chunk) > 64:
                        return True, instance_url
                else:  # Range request not supported, read a small amount of data
                    chunk = await resp.content.read(1024)
                    if len(chunk) > 64:
                        return True, instance_url
                        
                # If we got here, the file is empty or too small
                return False, instance_url
                
    except (TimeoutError, aiohttp.ClientError, Exception) as e:
        # If there's any error, assume there's an issue with the file
        return False, instance_url


@app.post("/")
async def post(request: Request):
    data = await request.json()
    url = data.get("url", None)
    ignored_instances = data.get("ignoredInstances", [])
    
    if url is None:
        return {"error": "URL not provided"}
    
    # Create a copy of data without the URL for passing to first_tunnel
    request_params = data.copy()
    if "url" in request_params:
        del request_params["url"]
    if "ignoredInstances" in request_params:
        del request_params["ignoredInstances"]
    
    # Set maximum retries to avoid excessive delay
    max_retries = 3
    retries = 0
    
    while retries < max_retries:
        # Try to get a response from the first available instance
        response = await manager.first_tunnel(url, ignored_instances=ignored_instances, **request_params)
        
        # If not a tunnel response or reached max retries, return whatever we got
        if response.get("status") != "tunnel" or retries >= max_retries - 1:
            return JSONResponse(response)
        
        # For tunnel responses, quickly check if the file has content
        download_url = response.get("url")
        if download_url:
            is_valid, instance_url = await check_file_size(download_url)
            
            if is_valid:
                # File looks good, return the response
                return JSONResponse(response)
            elif instance_url and instance_url not in ignored_instances:
                # File is empty, add the instance to ignored list and retry
                ignored_instances.append(instance_url)
                retries += 1
                continue
        
        # If we couldn't check the file or no URL was provided, return the response
        return JSONResponse(response)
    
    # If we exhausted retries, return the last response
    return JSONResponse(response)


@app.get("/ui", response_class=HTMLResponse)
async def webui():
    """Serve the web UI for pybalt api."""
    return HTML_TEMPLATE


@app.on_event("startup")
async def startup_event():
    """Start background tasks when the API starts."""
    create_task(update_instances())


async def update_instances():
    """Periodically update the stored_instances list with current instances."""
    while True:
        try:
            await manager.get_instances()
        except Exception as e:
            print(f"Error updating instances: {e}")

        # Get instance list update period from config
        update_period = config.get_as_number("update_period", 60, "api")

        await sleep(update_period)


def run_api(port=None, **kwargs):
    """Run the FastAPI application on the specified port or from config."""
    # Use provided port, or get it from kwargs, or from config, or default to 8000
    if port is None:
        port = config.get_as_number("port", 8009, "api")

    # Run the API server
    uvicorn.run(app, host="0.0.0.0", port=port)


HTML_TEMPLATE = (
    """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>pybalt downloader</title>
    <style>
        :root {
            --bg-color: #121212;
            --card-color: #1e1e1e;
            --text-color: #f5f5f5;
            --accent-color: #3a86ff;
            --error-color: #ff4c4c;
            --success-color: #4caf50;
            --warning-color: #ff9800;
            --shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 0 1px 3px rgba(0, 0, 0, 0.08);
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 2rem;
            line-height: 1.6;
        }
        
        .container {
            width: 100%;
            max-width: 600px;
            background-color: var(--card-color);
            border-radius: 10px;
            padding: 2rem;
            box-shadow: var(--shadow);
            transition: all 0.3s ease;
        }
        
        h1 {
            margin-bottom: 1.5rem;
            text-align: center;
            font-weight: 500;
        }
        
        .input-group {
            display: flex;
            gap: 10px;
            margin-bottom: 1.5rem;
        }
        
        input {
            flex: 1;
            padding: 0.8rem 1rem;
            border: none;
            border-radius: 5px;
            background-color: rgba(255, 255, 255, 0.1);
            color: var(--text-color);
            font-size: 1rem;
            outline: none;
            transition: all 0.2s ease;
        }
        
        input:focus {
            background-color: rgba(255, 255, 255, 0.15);
            box-shadow: 0 0 0 2px rgba(58, 134, 255, 0.5);
        }
        
        button {
            padding: 0.8rem 1.5rem;
            border: none;
            border-radius: 5px;
            background-color: var(--accent-color);
            color: white;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.2s ease;
            font-weight: 500;
        }
        
        button:hover {
            background-color: #2a75ff;
            transform: translateY(-2px);
        }
        
        button:active {
            transform: translateY(0);
        }
        
        .response {
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 5px;
            padding: 1rem;
            white-space: pre-wrap;
            word-break: break-word;
            max-height: 300px;
            overflow-y: auto;
            display: none;
        }
        
        .response.error {
            border-left: 4px solid var(--error-color);
        }
        
        .response.success {
            border-left: 4px solid var(--success-color);
        }
        
        .loader {
            display: none;
            width: 1.5rem;
            height: 1.5rem;
            border: 3px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top-color: var(--text-color);
            animation: spin 1s ease-in-out infinite;
            margin: 0 auto;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .footer {
            margin-top: 1.5rem;
            text-align: center;
            font-size: 0.9rem;
            opacity: 0.7;
        }
        
        .footer a {
            color: var(--accent-color);
            text-decoration: none;
        }
        
        /* Action buttons styles */
        .action-buttons {
            display: none;
            gap: 1.5rem;
            justify-content: center;
            margin: 1.5rem 0;
        }
        
        .action-button {
            display: flex;
            flex-direction: column;
            align-items: center;
            background: none;
            border: none;
            color: var(--text-color);
            cursor: pointer;
            padding: 0.5rem;
            border-radius: 8px;
            transition: all 0.2s ease;
        }
        
        .action-button:hover {
            background-color: rgba(255, 255, 255, 0.1);
            transform: translateY(-2px);
        }
        
        .action-button svg {
            width: 2rem;
            height: 2rem;
            margin-bottom: 0.5rem;
        }
        
        .action-button span {
            font-size: 0.9rem;
        }
        
        .success-notification {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background-color: var(--success-color);
            color: white;
            padding: 0.8rem 1.5rem;
            border-radius: 5px;
            box-shadow: var(--shadow);
            opacity: 0;
            transform: translateY(20px);
            transition: opacity 0.3s, transform 0.3s;
        }
        
        .instance-count {
            display: inline-flex;
            align-items: center;
            margin-left: 1rem;
            background-color: rgba(255, 255, 255, 0.1);
            padding: 0.25rem 0.5rem;
            border-radius: 12px;
            font-size: 0.8rem;
        }
        
        .instance-count-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--accent-color);
            margin-right: 0.5rem;
            display: inline-block;
        }
        
        .instance-count.loading .instance-count-dot {
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 0.3; }
            50% { opacity: 1; }
            100% { opacity: 0.3; }
        }
        
        /* Warning Modal Styles */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(0, 0, 0, 0.7);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        
        .modal {
            background-color: var(--card-color);
            border-radius: 10px;
            padding: 2rem;
            max-width: 600px;
            width: 90%;
            box-shadow: var(--shadow);
        }
        
        .modal-header {
            display: flex;
            align-items: center;
            margin-bottom: 1rem;
            color: var(--warning-color);
        }
        
        .modal-header svg {
            width: 24px;
            height: 24px;
            margin-right: 10px;
        }
        
        .modal-content {
            margin-bottom: 1.5rem;
        }
        
        .modal-actions {
            display: flex;
            justify-content: flex-end;
        }
        
        .modal-button {
            padding: 0.7rem 1.2rem;
            border: none;
            border-radius: 5px;
            background-color: var(--warning-color);
            color: white;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .modal-button:hover {
            opacity: 0.9;
        }
        
        /* Ignored instances styles */
        .ignored-instances {
            margin-top: 1.5rem;
            padding: 1rem;
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 5px;
            display: none;
        }
        
        .ignored-instances h3 {
            margin-top: 0;
            margin-bottom: 0.5rem;
            font-size: 1rem;
            font-weight: 500;
        }
        
        .ignored-list {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        
        .ignored-item {
            display: flex;
            align-items: center;
            background-color: rgba(255, 255, 255, 0.1);
            padding: 0.3rem 0.6rem;
            border-radius: 4px;
            font-size: 0.85rem;
        }
        
        .ignored-item button {
            background: none;
            border: none;
            color: var(--error-color);
            cursor: pointer;
            padding: 0;
            margin-left: 0.5rem;
            font-size: 1rem;
            display: flex;
            align-items: center;
        }
        
        .ignored-item button:hover {
            transform: none;
            background: none;
        }
        
        /* Settings panel styles */
        .settings-toggle {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 1rem;
            gap: 0.5rem;
            cursor: pointer;
            user-select: none;
            color: rgba(255, 255, 255, 0.7);
            transition: all 0.2s ease;
        }
        
        .settings-toggle:hover {
            color: var(--text-color);
        }

        .settings-toggle svg {
            width: 18px;
            height: 18px;
            transition: transform 0.3s ease;
        }
        
        .settings-toggle.active svg {
            transform: rotate(180deg);
        }
        
        .settings-panel {
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            display: none;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .settings-group {
            margin-bottom: 1.5rem;
        }
        
        .settings-group:last-child {
            margin-bottom: 0;
        }
        
        .settings-group h3 {
            margin-bottom: 0.8rem;
            font-size: 1rem;
            font-weight: 500;
            color: var(--accent-color);
        }
        
        .settings-row {
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 1rem;
        }
        
        .settings-row:last-child {
            margin-bottom: 0;
        }
        
        .setting-item {
            flex: 1;
            min-width: 200px;
        }
        
        .setting-item label {
            display: block;
            margin-bottom: 0.3rem;
            font-size: 0.9rem;
            opacity: 0.8;
        }
        
        .setting-item select {
            width: 100%;
            padding: 0.6rem 0.8rem;
            border: none;
            border-radius: 4px;
            background-color: rgba(255, 255, 255, 0.1);
            color: var(--text-color);
            font-size: 0.9rem;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 0.8rem center;
            background-size: 1rem;
            outline: none;
        }
        
        .setting-item input[type="text"] {
            width: 100%;
            padding: 0.6rem 0.8rem;
            border: none;
            border-radius: 4px;
            background-color: rgba(255, 255, 255, 0.1);
            color: var(--text-color);
            font-size: 0.9rem;
            outline: none;
        }
        
        .setting-item input[type="checkbox"] {
            margin-right: 0.5rem;
            width: auto;
            height: auto;
        }
        
        .checkbox-label {
            display: flex;
            align-items: center;
            cursor: pointer;
        }
        
        .settings-actions {
            display: flex;
            justify-content: space-between;
            margin-top: 1rem;
        }
        
        .settings-button {
            padding: 0.5rem 1rem;
            font-size: 0.9rem;
            background-color: rgba(255, 255, 255, 0.1);
        }
        
        .settings-button:hover {
            background-color: rgba(255, 255, 255, 0.2);
        }
        
        .settings-button.save {
            background-color: var(--accent-color);
        }
        
        .settings-button.save:hover {
            background-color: #2a75ff;
        }
        
        .settings-button.reset {
            background-color: var(--error-color);
        }
        
        .settings-button.reset:hover {
            background-color: #e33e3e;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>cobalt downloader</h1>
        <div class="input-group">
            <input 
                type="text" 
                id="url-input" 
                placeholder="Enter URL (YouTube, Twitter, Instagram, etc.)"
                autocomplete="off"
            >
            <button id="download-btn">Download</button>
        </div>
        
        <!-- Settings Toggle -->
        <div class="settings-toggle" id="settings-toggle">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
            <span>Advanced Settings</span>
        </div>
        
        <!-- Settings Panel -->
        <div class="settings-panel" id="settings-panel">
            <div class="settings-group">
                <h3>Video Settings</h3>
                <div class="settings-row">
                    <div class="setting-item">
                        <label for="video-quality">Video Quality</label>
                        <select id="video-quality">
                            <option value="">Auto (Default)</option>
                            <option value="144">144p</option>
                            <option value="240">240p</option>
                            <option value="360">360p</option>
                            <option value="480">480p</option>
                            <option value="720">720p</option>
                            <option value="1080">1080p</option>
                            <option value="1440">1440p</option>
                            <option value="2160">2160p (4K)</option>
                            <option value="4320">4320p (8K)</option>
                            <option value="max">Maximum</option>
                        </select>
                    </div>
                    <div class="setting-item">
                        <label for="download-mode">Download Mode</label>
                        <select id="download-mode">
                            <option value="">Auto (Default)</option>
                            <option value="audio">Audio Only</option>
                            <option value="mute">Video Without Audio</option>
                        </select>
                    </div>
                </div>
            </div>
            
            <div class="settings-group">
                <h3>Audio Settings</h3>
                <div class="settings-row">
                    <div class="setting-item">
                        <label for="audio-format">Audio Format</label>
                        <select id="audio-format">
                            <option value="">Best (Default)</option>
                            <option value="mp3">MP3</option>
                            <option value="ogg">OGG</option>
                            <option value="wav">WAV</option>
                            <option value="opus">Opus</option>
                        </select>
                    </div>
                    <div class="setting-item">
                        <label for="audio-bitrate">Audio Bitrate</label>
                        <select id="audio-bitrate">
                            <option value="">Auto (Default)</option>
                            <option value="320">320 kbps</option>
                            <option value="256">256 kbps</option>
                            <option value="128">128 kbps</option>
                            <option value="96">96 kbps</option>
                            <option value="64">64 kbps</option>
                            <option value="8">8 kbps</option>
                        </select>
                    </div>
                </div>
            </div>
            
            <div class="settings-group">
                <h3>YouTube Specific</h3>
                <div class="settings-row">
                    <div class="setting-item">
                        <label for="youtube-video-codec">Video Codec</label>
                        <select id="youtube-video-codec">
                            <option value="">Default (h264)</option>
                            <option value="h264">H.264</option>
                            <option value="av1">AV1</option>
                            <option value="vp9">VP9</option>
                        </select>
                    </div>
                    <div class="setting-item">
                        <label for="youtube-dub-lang">Dubbed Language</label>
                        <input type="text" id="youtube-dub-lang" placeholder="e.g. en, fr, de (optional)">
                    </div>
                </div>
                <div class="settings-row">
                    <div class="setting-item">
                        <label class="checkbox-label">
                            <input type="checkbox" id="youtube-hls">
                            <span>Use HLS</span>
                        </label>
                    </div>
                </div>
            </div>
            
            <div class="settings-group">
                <h3>TikTok & Twitter Settings</h3>
                <div class="settings-row">
                    <div class="setting-item">
                        <label class="checkbox-label">
                            <input type="checkbox" id="tiktok-full-audio">
                            <span>TikTok Full Audio</span>
                        </label>
                    </div>
                    <div class="setting-item">
                        <label class="checkbox-label">
                            <input type="checkbox" id="tiktok-h265">
                            <span>TikTok H.265</span>
                        </label>
                    </div>
                </div>
                <div class="settings-row">
                    <div class="setting-item">
                        <label class="checkbox-label">
                            <input type="checkbox" id="twitter-gif">
                            <span>Twitter Download as GIF</span>
                        </label>
                    </div>
                </div>
            </div>
            
            <div class="settings-group">
                <h3>General Options</h3>
                <div class="settings-row">
                    <div class="setting-item">
                        <label for="filename-style">Filename Style</label>
                        <select id="filename-style">
                            <option value="">Default</option>
                            <option value="classic">Classic</option>
                            <option value="pretty">Pretty</option>
                            <option value="basic">Basic</option>
                            <option value="nerdy">Nerdy</option>
                        </select>
                    </div>
                </div>
                <div class="settings-row">
                    <div class="setting-item">
                        <label class="checkbox-label">
                            <input type="checkbox" id="always-proxy">
                            <span>Always Use Proxy</span>
                        </label>
                    </div>
                    <div class="setting-item">
                        <label class="checkbox-label">
                            <input type="checkbox" id="disable-metadata">
                            <span>Disable Metadata</span>
                        </label>
                    </div>
                </div>
            </div>
            
            <div class="settings-actions">
                <button class="settings-button reset" id="reset-settings">Reset to Defaults</button>
                <button class="settings-button save" id="save-settings">Save Settings</button>
            </div>
        </div>
        
        <div class="loader" id="loader"></div>
        <div class="action-buttons" id="action-buttons">
            <button class="action-button" id="download-url-btn">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                <span>Download</span>
            </button>
            <button class="action-button" id="copy-url-btn">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
                <span>Copy Link</span>
            </button>
            <button class="action-button" id="ignore-instance-btn">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line>
                </svg>
                <span>Ignore Instance</span>
            </button>
        </div>
        <div class="response" id="response"></div>
        
        <!-- Ignored Instances Section -->
        <div class="ignored-instances" id="ignored-instances">
            <h3>Ignored Instances:</h3>
            <div class="ignored-list" id="ignored-list"></div>
        </div>
    </div>
    
    <!-- Warning Modal -->
    <div class="modal-overlay" id="warning-modal">
        <div class="modal">
            <div class="modal-header">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                    <line x1="12" y1="9" x2="12" y2="13"></line>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                </svg>
                <h2>Security Warning</h2>
            </div>
            <div class="modal-content">
                <p>Be aware that this service uses a bunch of random cobalt instances hosted all across the world. The pybalt/cobalt devs have nothing to do with code changes inside cobalt-instances on their side.</p>
                <p>Some instances can answer with some kind of malware. Do not run executable files or files with strange extensions that you download from here.</p>
                <p>Be safe and have fun downloading!</p>
            </div>
            <div class="modal-actions">
                <button class="modal-button" id="warning-acknowledge">I understand, proceed</button>
            </div>
        </div>
    </div>
    
    <div class="footer">
        Powered by <a href="https://github.com/nichind/pybalt" target="_blank">pybalt</a> • Version """
    + VERSION
    + """
        <div class="instance-count loading" id="instance-count">
            <span class="instance-count-dot"></span>
            <span id="instance-count-text">Loading instances...</span>
        </div>
    </div>
    <div class="success-notification" id="copy-notification">
        Link copied to clipboard!
    </div>
    <div class="success-notification" id="ignore-notification">
        Instance added to ignore list!
    </div>
    <div class="success-notification" id="settings-notification">
        Settings saved!
    </div>

    <script>
        let currentResponseUrl = null;
        let currentRespondingInstance = null;
        let ignoredInstances = [];
        
        // Default settings values
        const defaultSettings = {
            videoQuality: "",
            audioFormat: "",
            audioBitrate: "",
            filenameStyle: "",
            downloadMode: "",
            youtubeVideoCodec: "",
            youtubeDubLang: "",
            alwaysProxy: false,
            disableMetadata: false,
            tiktokFullAudio: false,
            tiktokH265: false,
            twitterGif: false,
            youtubeHLS: false
        };
        
        // Current settings
        let currentSettings = {...defaultSettings};
        
        // Load ignored instances and settings from local storage
        document.addEventListener('DOMContentLoaded', () => {
            try {
                const saved = localStorage.getItem('ignoredInstances');
                if (saved) {
                    ignoredInstances = JSON.parse(saved);
                    updateIgnoredInstancesUI();
                }
                
                // Load saved settings
                const savedSettings = localStorage.getItem('cobaltSettings');
                if (savedSettings) {
                    currentSettings = {...defaultSettings, ...JSON.parse(savedSettings)};
                    applySettingsToUI();
                }
            } catch (error) {
                console.error('Failed to load saved data:', error);
            }
            
            // Initialize settings toggle
            document.getElementById('settings-toggle').addEventListener('click', function() {
                const panel = document.getElementById('settings-panel');
                const isVisible = panel.style.display === 'block';
                
                panel.style.display = isVisible ? 'none' : 'block';
                this.classList.toggle('active', !isVisible);
            });
            
            // Initialize settings buttons
            document.getElementById('save-settings').addEventListener('click', saveSettings);
            document.getElementById('reset-settings').addEventListener('click', resetSettings);
        });
        
        // Function to save settings
        function saveSettings() {
            // Gather settings from UI
            currentSettings = {
                videoQuality: document.getElementById('video-quality').value,
                audioFormat: document.getElementById('audio-format').value,
                audioBitrate: document.getElementById('audio-bitrate').value,
                filenameStyle: document.getElementById('filename-style').value,
                downloadMode: document.getElementById('download-mode').value,
                youtubeVideoCodec: document.getElementById('youtube-video-codec').value,
                youtubeDubLang: document.getElementById('youtube-dub-lang').value,
                alwaysProxy: document.getElementById('always-proxy').checked,
                disableMetadata: document.getElementById('disable-metadata').checked,
                tiktokFullAudio: document.getElementById('tiktok-full-audio').checked,
                tiktokH265: document.getElementById('tiktok-h265').checked,
                twitterGif: document.getElementById('twitter-gif').checked,
                youtubeHLS: document.getElementById('youtube-hls').checked
            };
            
            // Save to localStorage
            localStorage.setItem('cobaltSettings', JSON.stringify(currentSettings));
            
            // Show notification
            const notification = document.getElementById('settings-notification');
            notification.style.opacity = '1';
            notification.style.transform = 'translateY(0)';
            
            setTimeout(() => {
                notification.style.opacity = '0';
                notification.style.transform = 'translateY(20px)';
            }, 2000);
        }
        
        // Function to reset settings to defaults
        function resetSettings() {
            currentSettings = {...defaultSettings};
            applySettingsToUI();
            localStorage.removeItem('cobaltSettings');
        }
        
        // Function to apply current settings to UI elements
        function applySettingsToUI() {
            document.getElementById('video-quality').value = currentSettings.videoQuality;
            document.getElementById('audio-format').value = currentSettings.audioFormat;
            document.getElementById('audio-bitrate').value = currentSettings.audioBitrate;
            document.getElementById('filename-style').value = currentSettings.filenameStyle;
            document.getElementById('download-mode').value = currentSettings.downloadMode;
            document.getElementById('youtube-video-codec').value = currentSettings.youtubeVideoCodec;
            document.getElementById('youtube-dub-lang').value = currentSettings.youtubeDubLang;
            document.getElementById('always-proxy').checked = currentSettings.alwaysProxy;
            document.getElementById('disable-metadata').checked = currentSettings.disableMetadata;
            document.getElementById('tiktok-full-audio').checked = currentSettings.tiktokFullAudio;
            document.getElementById('tiktok-h265').checked = currentSettings.tiktokH265;
            document.getElementById('twitter-gif').checked = currentSettings.twitterGif;
            document.getElementById('youtube-hls').checked = currentSettings.youtubeHLS;
        }
        
        // Function to update the ignored instances UI
        function updateIgnoredInstancesUI() {
            const container = document.getElementById('ignored-instances');
            const list = document.getElementById('ignored-list');
            
            // Clear the list
            list.innerHTML = '';
            
            // If we have ignored instances, show the container
            if (ignoredInstances.length > 0) {
                container.style.display = 'block';
                
                // Add each ignored instance to the list
                ignoredInstances.forEach(instance => {
                    const item = document.createElement('div');
                    item.className = 'ignored-item';
                    
                    const text = document.createTextNode(instance);
                    item.appendChild(text);
                    
                    const removeBtn = document.createElement('button');
                    removeBtn.innerHTML = '×';
                    removeBtn.title = 'Remove from ignore list';
                    removeBtn.onclick = () => removeIgnoredInstance(instance);
                    
                    item.appendChild(removeBtn);
                    list.appendChild(item);
                });
            } else {
                container.style.display = 'none';
            }
        }
        
        // Function to add an instance to the ignored list
        function addIgnoredInstance(instance) {
            if (instance && !ignoredInstances.includes(instance)) {
                ignoredInstances.push(instance);
                localStorage.setItem('ignoredInstances', JSON.stringify(ignoredInstances));
                updateIgnoredInstancesUI();
                
                // Show notification
                const notification = document.getElementById('ignore-notification');
                notification.style.opacity = '1';
                notification.style.transform = 'translateY(0)';
                
                setTimeout(() => {
                    notification.style.opacity = '0';
                    notification.style.transform = 'translateY(20px)';
                }, 2000);
            }
        }
        
        // Function to remove an instance from the ignored list
        function removeIgnoredInstance(instance) {
            ignoredInstances = ignoredInstances.filter(item => item !== instance);
            localStorage.setItem('ignoredInstances', JSON.stringify(ignoredInstances));
            updateIgnoredInstancesUI();
        }
        
        // Fetch instance count on page load
        document.addEventListener('DOMContentLoaded', async () => {
            try {
                const response = await fetch('/');
                const data = await response.json();
                
                const instanceCountEl = document.getElementById('instance-count');
                const instanceCountTextEl = document.getElementById('instance-count-text');
                
                if (data.instance_count !== undefined) {
                    instanceCountEl.classList.remove('loading');
                    instanceCountTextEl.textContent = `${data.instance_count} instances available`;
                } else {
                    instanceCountTextEl.textContent = 'Unable to load instance count';
                }
            } catch (error) {
                console.error('Failed to fetch instance count:', error);
                document.getElementById('instance-count-text').textContent = 'Unable to load instance count';
            }
        });
        
        document.getElementById('download-btn').addEventListener('click', async () => {
            // Check if warning has been acknowledged
            if (!localStorage.getItem('warning_acknowledged')) {
                document.getElementById('warning-modal').style.display = 'flex';
                return;
            }
            
            // Proceed with download if warning was acknowledged
            await performDownload();
        });
        
        // Warning acknowledgment
        document.getElementById('warning-acknowledge').addEventListener('click', async () => {
            localStorage.setItem('warning_acknowledged', 'true');
            document.getElementById('warning-modal').style.display = 'none';
            await performDownload();
        });
        
        async function performDownload() {
            const urlInput = document.getElementById('url-input');
            const loader = document.getElementById('loader');
            const responseElement = document.getElementById('response');
            const actionButtons = document.getElementById('action-buttons');
            const url = urlInput.value.trim();
            
            // Reset current values
            currentResponseUrl = null;
            currentRespondingInstance = null;
            actionButtons.style.display = 'none';
            
            if (!url) {
                showResponse('Please enter a URL', true);
                return;
            }
            
            // Show loader, hide previous response
            loader.style.display = 'block';
            responseElement.style.display = 'none';
            
            try {
                const response = await fetch('/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ 
                        url,
                        ignoredInstances: ignoredInstances 
                        ,
                        // Add settings from localStorage if they exist
                        ...(currentSettings.videoQuality ? { videoQuality: currentSettings.videoQuality } : {}),
                        ...(currentSettings.audioFormat ? { audioFormat: currentSettings.audioFormat } : {}),
                        ...(currentSettings.audioBitrate ? { audioBitrate: currentSettings.audioBitrate } : {}),
                        ...(currentSettings.filenameStyle ? { filenameStyle: currentSettings.filenameStyle } : {}),
                        ...(currentSettings.downloadMode ? { downloadMode: currentSettings.downloadMode } : {}),
                        ...(currentSettings.youtubeVideoCodec ? { youtubeVideoCodec: currentSettings.youtubeVideoCodec } : {}),
                        ...(currentSettings.youtubeDubLang ? { youtubeDubLang: currentSettings.youtubeDubLang } : {}),
                        ...(currentSettings.alwaysProxy ? { alwaysProxy: true } : {}),
                        ...(currentSettings.disableMetadata ? { disableMetadata: true } : {}),
                        ...(currentSettings.tiktokFullAudio ? { tiktokFullAudio: true } : {}),
                        ...(currentSettings.tiktokH265 ? { tiktokH265: true } : {}),
                        ...(currentSettings.twitterGif ? { twitterGif: true } : {}),
                        ...(currentSettings.youtubeHLS ? { youtubeHLS: true } : {})
                    })
                });
                
                const data = await response.json();
                
                // Hide loader
                loader.style.display = 'none';
                
                // Show response
                if (data.error || data.status === 'error') {
                    showResponse(JSON.stringify(data, null, 2), true);
                } else {
                    showResponse(JSON.stringify(data, null, 2), false);
                    
                    // Check if response contains a URL
                    if (data.url) {
                        currentResponseUrl = data.url;
                        
                        // Store responding instance if available
                        if (data.instance_info && data.instance_info.url) {
                            currentRespondingInstance = data.instance_info.url;
                        }
                        
                        actionButtons.style.display = 'flex';
                    }
                }
            } catch (error) {
                loader.style.display = 'none';
                showResponse(`Error: ${error.message}`, true);
            }
        }
        
        function showResponse(text, isError) {
            const responseElement = document.getElementById('response');
            responseElement.textContent = text;
            responseElement.className = isError ? 'response error' : 'response success';
            responseElement.style.display = 'block';
        }
        
        // Download URL button
        document.getElementById('download-url-btn').addEventListener('click', () => {
            if (currentResponseUrl) {
                window.open(currentResponseUrl, '_blank');
            }
        });
        
        // Copy URL button
        document.getElementById('copy-url-btn').addEventListener('click', async () => {
            if (currentResponseUrl) {
                try {
                    await navigator.clipboard.writeText(currentResponseUrl);
                    const notification = document.getElementById('copy-notification');
                    notification.style.opacity = '1';
                    notification.style.transform = 'translateY(0)';
                    
                    setTimeout(() => {
                        notification.style.opacity = '0';
                        notification.style.transform = 'translateY(20px)';
                    }, 2000);
                } catch (err) {
                    console.error('Failed to copy URL: ', err);
                }
            }
        });
        
        // Ignore Instance button
        document.getElementById('ignore-instance-btn').addEventListener('click', () => {
            if (currentRespondingInstance) {
                addIgnoredInstance(currentRespondingInstance);
            }
        });
        
        // Allow pressing Enter to submit
        document.getElementById('url-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                document.getElementById('download-btn').click();
            }
        });
    </script>
</body>
</html>
"""
)

# Main entry point for running the API directly
if __name__ == "__main__":
    # Check if port is provided as command line argument
    port = None
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}")
            sys.exit(1)
    
    print(f"Starting pybalt API server on port {port or config.get_as_number('port', 8009, 'api')}")
    run_api(port=port)
