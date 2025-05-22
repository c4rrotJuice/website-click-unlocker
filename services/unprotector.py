import aiohttp
import re
from urllib.parse import urlparse

# Blocks common JS-based blockers and anti-copy tricks
UNSAFE_JS_PATTERNS = [
    r'oncontextmenu\s*=\s*[\"\']?return\s+false[\"\']?',
    r'oncopy\s*=\s*[\"\']?return\s+false[\"\']?',
    r'onselectstart\s*=\s*[\"\']?return\s+false[\"\']?',
    r'on(contextmenu|copy|selectstart)\s*=\s*[\"\']?return\s+false[\"\']?',
    r'document\.on(?:copy|contextmenu|selectstart)\s*=\s*.*?;',
    r'document\.addEventListener\([\"\'](contextmenu|copy|selectstart)[\"\'],.*?\);',
    r'event\.preventDefault\(\);?',
    r'return\s+false;?'
]

BANNER_HTML = """
<div style="background:#111;color:#fff;padding:10px;text-align:center;font-size:14px">
✅ This page has been unlocked. You can now copy and cite content.
</div>
"""

CUSTOM_JS = CUSTOM_JS = """
<script>
document.addEventListener("DOMContentLoaded", function () {
    // --- Unlock right-click & selection ---
    document.oncontextmenu = null;
    document.onselectstart = null;
    document.oncopy = null;
    document.body.oncontextmenu = null;
    document.body.onselectstart = null;
    document.body.oncopy = null;

    const style = document.createElement('style');
    style.innerHTML = `
        * {
            user-select: text !important;
        }
        .copy-cite-btn {
            position: absolute;
            background: #222;
            color: #fff;
            padding: 5px 10px;
            font-size: 14px;
            border-radius: 5px;
            z-index: 9999;
            cursor: pointer;
            
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            
   
        }
        .citation-popup {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #fff;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.25);
            z-index: 10000;
            width: 90%;
            max-width: 500px;
        }
        .citation-popup h3 {
            margin-top: 0;
            font-size: 18px;
        }
        .citation-popup pre {
            background: #f0f0f0;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 14px;
        }
        .copy-popup-btn {
            background-color: #007bff;
            color: #fff;
            padding: 6px 10px;
            margin-top: 10px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        .blurred-bg {
            position: fixed;
            top: 0; left: 0;
            width: 100vw;
            height: 100vh;
            backdrop-filter: blur(6px);
            background: rgba(0,0,0,0.3);
            z-index: 9999;
        }
        .copied-toast {
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #333;
            color: #fff;
            padding: 10px 15px;
            border-radius: 6px;
            font-size: 14px;
            z-index: 10001;
            opacity: 0;
            transition: opacity 0.3s ease-in-out;
        }
        .copied-toast.show {
            opacity: 1;
        }
    `;
    document.head.appendChild(style);

    let selectedText = "";

    document.addEventListener("mouseup", function (event) {
        const selection = window.getSelection();
        const text = selection.toString().trim();
        if (text.length > 0) {
            selectedText = text;
            showCopyButton(event.pageX, event.pageY);
        }
    });

    function showCopyButton(x, y) {
        removeCopyButton();

        const btn = document.createElement("div");
        btn.className = "copy-cite-btn";
        btn.textContent = "📋 Copy + Cite";
        btn.style.top = `${y + 10}px`;
        btn.style.left = `${x + 10}px`;
        btn.onclick = () => {
            removeCopyButton();
            showCitationPopup(selectedText);
        };

        document.body.appendChild(btn);
    }

    function removeCopyButton() {
        const btn = document.querySelector(".copy-cite-btn");
        if (btn) btn.remove();
    }

    function showCitationPopup(text) {
        const sourceUrl = window.location.href;
        const pageTitle = document.title || "Untitled Page";
        const accessDate = new Date().toISOString().split("T")[0];

        const mlaCitation = `"${text}" — *${pageTitle}*. Accessed ${accessDate}. ${sourceUrl}`;
        const apaCitation = `${pageTitle}. (${accessDate}). Retrieved from ${sourceUrl}\n"${text}"`;

        const blur = document.createElement("div");
        blur.className = "blurred-bg";
        blur.onclick = () => {
            document.body.removeChild(blur);
            popup.remove();
        };

        const popup = document.createElement("div");
        popup.className = "citation-popup";

        popup.innerHTML = `
            <h3>Citations</h3>
            <strong>MLA:</strong>
            <pre id="mla-cite">${mlaCitation}</pre>
            <button class="copy-popup-btn" onclick="copyCitation('mla-cite')">Copy MLA</button>
            <br/><br/>
            <strong>APA:</strong>
            <pre id="apa-cite">${apaCitation}</pre>
            <button class="copy-popup-btn" onclick="copyCitation('apa-cite')">Copy APA</button>
        `;

        document.body.appendChild(blur);
        document.body.appendChild(popup);
    }

    window.copyCitation = async function (id) {
        const text = document.getElementById(id).innerText;
        try {
            await navigator.clipboard.writeText(text);
            showToast("Citation copied!");
        } catch (err) {
            alert("Copy failed. Please allow clipboard access or try again.");
        }

        // Close popup after short delay
        setTimeout(() => {
            document.querySelector(".citation-popup")?.remove();
            document.querySelector(".blurred-bg")?.remove();
        }, 1000);
    };

    function showToast(message) {
        const toast = document.createElement("div");
        toast.className = "copied-toast show";
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.remove("show");
            toast.remove();
        }, 2000);
    }

    // --- Prevent default blockers ---
    window.addEventListener("contextmenu", e => e.stopPropagation(), true);
    window.addEventListener("copy", e => e.stopPropagation(), true);
    window.addEventListener("selectstart", e => e.stopPropagation(), true);
});
</script>

"""

async def fetch_and_clean_page(url: str, unlock: bool = True) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/114.0.0.0 Safari/537.36"
        )
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            html = await response.text()


        if unlock:
            html = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
        for pattern in UNSAFE_JS_PATTERNS:
            html = re.sub(pattern, '', html, flags=re.IGNORECASE)

        inject = BANNER_HTML + CUSTOM_JS

        if '</body>' in html.lower():
            html = re.sub(r'</body>', inject + '</body>', html, flags=re.IGNORECASE)
        else:
            html += inject

    return html
    
# Remove all blocking <script> and inline blockers



async def run_ocr_on_url(url: str) -> str:
    if not url.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif')):
        return ("""
        <div style="position:fixed;top:20px;right:20px;padding:10px 15px;background:#ff4444;color:white;
        border-radius:6px;box-shadow:0 2px 6px rgba(0,0,0,0.2);z-index:9999;animation:fadeOut 5s forwards">
            OCR failed: The URL does not point to a supported image format.
        </div>
        <style>@keyframes fadeOut {
            0% {opacity:1;}
            80% {opacity:1;}
            100% {opacity:0;display:none;}
        }</style>
        """)

    api_key = "K89862932088957"
    payload = {
        'url': url,
        'isOverlayRequired': False,
        'apikey': api_key,
        'language': 'eng'
    }

    ocr_api = "https://api.ocr.space/parse/image"

    async with aiohttp.ClientSession() as session:
        async with session.post(ocr_api, data=payload) as resp:
            result = await resp.json()

    if result.get("IsErroredOnProcessing"):
        return ("""
        <div style="position:fixed;top:20px;right:20px;padding:10px 15px;background:#ff4444;color:white;
        border-radius:6px;box-shadow:0 2px 6px rgba(0,0,0,0.2);z-index:9999;animation:fadeOut 5s forwards">
            OCR failed: {result.get('ErrorMessage', 'Unknown error')}
        </div>
        <style>@keyframes fadeOut {
            0% {{opacity:1;}}
            80% {{opacity:1;}}
            100% {{opacity:0;display:none;}}
        }</style>
        """)

    parsed = result.get("ParsedResults", [{}])[0].get("ParsedText", "")
    parsed = parsed.replace('\n', '<br>')
    return f"<div><h3>OCR Extracted Text</h3><p>{parsed}</p></div>"


#async def fetch clena page


