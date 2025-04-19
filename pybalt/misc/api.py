from .. import core, VERSION
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from asyncio import run, sleep, create_task
import uvicorn


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


@app.post("/")
async def post(request: Request):
    data = await request.json()
    url = data.get("url", None)
    if url is None:
        return {"error": "URL not provided"}
    del data["url"]
    return JSONResponse(await manager.first_tunnel(url, **data))


@app.get("/ui", response_class=HTMLResponse)
async def webui():
    """Serve the web UI for pybalt."""
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


HTML_TEMPLATE = """<!DOCTYPE html>
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
        </div>
        <div class="response" id="response"></div>
    </div>
    <div class="footer">
        Powered by <a href="https://github.com/nichind/pybalt" target="_blank">pybalt</a> • Version """ + VERSION + """
        <div class="instance-count loading" id="instance-count">
            <span class="instance-count-dot"></span>
            <span id="instance-count-text">Loading instances...</span>
        </div>
    </div>
    <div class="success-notification" id="copy-notification">
        Link copied to clipboard!
    </div>

    <script>
        let currentResponseUrl = null;
        
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
            const urlInput = document.getElementById('url-input');
            const loader = document.getElementById('loader');
            const responseElement = document.getElementById('response');
            const actionButtons = document.getElementById('action-buttons');
            const url = urlInput.value.trim();
            
            // Reset current URL
            currentResponseUrl = null;
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
                    body: JSON.stringify({ url })
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
                        actionButtons.style.display = 'flex';
                    }
                }
            } catch (error) {
                loader.style.display = 'none';
                showResponse(`Error: ${error.message}`, true);
            }
        });
        
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
