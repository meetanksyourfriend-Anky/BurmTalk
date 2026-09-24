from flask import Flask, render_template_string, request, jsonify
import urllib.request
import urllib.parse
import json
import base64
import socket
import asyncio
import edge_tts
import tempfile
import os
import sys
import re

# Windows Fix: Prevents asyncio from crashing when generating audio on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Safety timeout to prevent the server from getting permanently stuck
socket.setdefaulttimeout(4.0)

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Dear Leona - Translator</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <link href="https://fonts.googleapis.com/css2?family=Dancing+Script:wght@700&family=Padauk:wght@400;700&family=Noto+Sans+Myanmar:wght@400;700&display=swap" rel="stylesheet">
    
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 0; margin: 0; background: #f4f6f8; color: #333; }
        .header { background: linear-gradient(135deg, #007bff, #0056b3); color: white; padding: 15px 20px; text-align: center; font-size: 22px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.15); letter-spacing: 0.5px; }
        .container { max-width: 500px; margin: 20px auto; padding: 0 15px; }
        .tabs { display: flex; margin-bottom: 20px; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .tab-btn { flex: 1; padding: 12px; border: none; background: #fff; color: #555; font-size: 16px; font-weight: 600; cursor: pointer; transition: 0.2s; }
        .tab-btn.active { background: #e9ecef; color: #007bff; border-bottom: 3px solid #007bff; }
        .tab-content { display: none; animation: fadeIn 0.3s; }
        .tab-content.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        input[type="text"] { width: 100%; padding: 12px; margin: 10px 0 15px; box-sizing: border-box; font-size: 16px; border: 1px solid #ddd; border-radius: 6px; }
        button.primary-btn { background: #007bff; color: white; border: none; padding: 14px 20px; border-radius: 6px; cursor: pointer; width: 100%; font-size: 16px; font-weight: bold; transition: 0.2s; }
        button.primary-btn:hover { background: #0056b3; }
        button.primary-btn:disabled { background: #a5cbf5; cursor: not-allowed; }
        .output { background: #f8f9fa; padding: 15px; margin-top: 20px; border-radius: 8px; display: none; border: 1px solid #e9ecef;}
        audio { width: 100%; margin-top: 10px; height: 40px; display: none; }
        #loading { display: none; text-align: center; margin-top: 20px; font-style: italic; color: #666; }
        .error { color: #dc3545; margin-top: 15px; font-weight: bold; text-align: center; display: none;}
        .burmese-text { font-family: 'Padauk', 'Noto Sans Myanmar', sans-serif; font-size: 28px; color: #111; margin: 10px 0; line-height: 1.5; }
        .phonetics-text { color: #0056b3; font-size: 18px; margin-bottom: 15px; font-weight: 500; }
        .save-btn { background: #ffc107; color: #333; border: none; padding: 10px 15px; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; margin-top: 15px; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 15px; }
        .save-btn:hover { background: #e0a800; }
        .saved-item { background: white; border: 1px solid #ddd; padding: 15px; border-radius: 8px; margin-bottom: 15px; position: relative; }
        .saved-english { font-weight: bold; font-size: 16px; color: #555; margin-bottom: 5px;}
        .delete-btn { position: absolute; top: 10px; right: 10px; background: #dc3545; color: white; border: none; border-radius: 4px; padding: 5px 10px; font-size: 12px; cursor: pointer; }
        .empty-state { text-align: center; color: #777; padding: 30px 10px; font-style: italic; }
        .footer-signature { font-family: 'Dancing Script', cursive; color: #dc3545; font-size: 32px; text-align: center; margin-top: 30px; margin-bottom: 30px; text-shadow: 1px 1px 2px rgba(0,0,0,0.05); }
    </style>
</head>
<body>
    <div class="header">Dear Leona</div>
    <div class="container">
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('translator')" id="tabBtn-translator">📡 Live Translator</button>
            <button class="tab-btn" onclick="switchTab('phrasebook')" id="tabBtn-phrasebook">⭐ Phrasebook</button>
        </div>

        <div id="tab-translator" class="tab-content active">
            <div class="card">
                <form id="translator-form">
                    <label>What do you want to say?</label>
                    <input type="text" id="english_text" placeholder="e.g., Where is the taxi?" autocomplete="off" required>
                    <button type="submit" id="submit-btn" class="primary-btn">Translate</button>
                </form>

                <div id="loading">Translating and generating audio... Please wait.</div>
                <div id="error-msg" class="error"></div>

                <div class="output" id="output-section">
                    <div class="burmese-text" id="burmese-text"></div>
                    <div class="phonetics-text" id="phonetics-text"></div>
                    <audio id="audio-player" controls></audio>
                    <button class="save-btn" id="save-btn" onclick="saveCurrentTranslation()">⭐ Save to Offline Phrasebook</button>
                </div>
            </div>
        </div>

        <div id="tab-phrasebook" class="tab-content">
            <div id="phrasebook-list"></div>
        </div>
        
        <div class="footer-signature">With love Anky</div>
    </div>

    <script>
        let currentTranslationData = null; 

        function switchTab(tabId) {
            document.getElementById('tabBtn-translator').classList.remove('active');
            document.getElementById('tabBtn-phrasebook').classList.remove('active');
            document.getElementById('tabBtn-' + tabId).classList.add('active');
            
            document.getElementById('tab-translator').classList.remove('active');
            document.getElementById('tab-phrasebook').classList.remove('active');
            document.getElementById('tab-' + tabId).classList.add('active');

            if(tabId === 'phrasebook') renderPhrasebook();
        }

        document.getElementById('translator-form').addEventListener('submit', async function(e) {
            e.preventDefault(); 
            
            const text = document.getElementById('english_text').value.trim();
            const btn = document.getElementById('submit-btn');
            const loading = document.getElementById('loading');
            const output = document.getElementById('output-section');
            const errorMsg = document.getElementById('error-msg');
            const burmeseText = document.getElementById('burmese-text');
            const phoneticsText = document.getElementById('phonetics-text');
            const audioPlayer = document.getElementById('audio-player');
            const saveBtn = document.getElementById('save-btn');

            if (!text) return;

            btn.disabled = true;
            loading.style.display = 'block';
            output.style.display = 'none';
            errorMsg.style.display = 'none';
            audioPlayer.style.display = 'none';
            saveBtn.innerHTML = "⭐ Save to Offline Phrasebook";
            saveBtn.disabled = false;

            try {
                const controller = new AbortController();
                // Extended timeout to allow Render time to wake up without failing
                const timeoutId = setTimeout(() => controller.abort(), 60000); 

                const response = await fetch('/translate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: text }),
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                const data = await response.json();

                if (response.ok) {
                    burmeseText.innerText = data.translation;
                    phoneticsText.innerText = data.phonetics ? "🗣️ " + data.phonetics : "";
                    
                    if (data.audio_base64) {
                        audioPlayer.src = "data:audio/mp3;base64," + data.audio_base64;
                        audioPlayer.style.display = 'block'; 
                        audioPlayer.play().catch(e => console.log("Autoplay blocked."));
                    }
                    
                    currentTranslationData = {
                        id: Date.now().toString(),
                        english: text,
                        burmese: data.translation,
                        phonetics: data.phonetics,
                        audio: data.audio_base64
                    };
                    output.style.display = 'block';
                } else {
                    errorMsg.innerText = "Translation failed. Servers are too busy.";
                    errorMsg.style.display = 'block';
                }
            } catch (err) {
                errorMsg.innerText = "Connection error. The server is waking up, try again in a few seconds!";
                errorMsg.style.display = 'block';
            } finally {
                btn.disabled = false;
                loading.style.display = 'none';
            }
        });

        function saveCurrentTranslation() {
            if (!currentTranslationData) return;
            let savedItems = JSON.parse(localStorage.getItem('burmTalkSaved') || '[]');
            savedItems.unshift(currentTranslationData);
            localStorage.setItem('burmTalkSaved', JSON.stringify(savedItems));
            
            const saveBtn = document.getElementById('save-btn');
            saveBtn.innerHTML = "✅ Saved to Phrasebook!";
            saveBtn.disabled = true;
        }

        function renderPhrasebook() {
            const listContainer = document.getElementById('phrasebook-list');
            let savedItems = JSON.parse(localStorage.getItem('burmTalkSaved') || '[]');
            
            listContainer.innerHTML = ''; 
            if (savedItems.length === 0) {
                listContainer.innerHTML = '<div class="empty-state">Your phrasebook is empty.<br>Translate some phrases and click "Save" to add them here!</div>';
                return;
            }

            savedItems.forEach(item => {
                const card = document.createElement('div');
                card.className = 'saved-item';
                let audioHtml = item.audio ? `<audio controls src="data:audio/mp3;base64,${item.audio}" style="width: 100%; margin-top: 10px;"></audio>` : '';
                let phoneticsHtml = item.phonetics ? `<div class="phonetics-text">🗣️ ${item.phonetics}</div>` : '';

                card.innerHTML = `
                    <button class="delete-btn" onclick="deletePhrase('${item.id}')">Delete</button>
                    <div class="saved-english">${item.english}</div>
                    <div class="burmese-text" style="font-size: 22px;">${item.burmese}</div>
                    ${phoneticsHtml}
                    ${audioHtml}
                `;
                listContainer.appendChild(card);
            });
        }

        function deletePhrase(id) {
            let savedItems = JSON.parse(localStorage.getItem('burmTalkSaved') || '[]');
            savedItems = savedItems.filter(item => item.id !== id);
            localStorage.setItem('burmTalkSaved', JSON.stringify(savedItems));
            renderPhrasebook();
        }
        
        renderPhrasebook();
    </script>
</body>
</html>
"""

def direct_translate(text):
    print(f"--> [1/3] Translating text: '{text}'")
    clean_text = text.strip().lower().replace("?", "").replace("!", "").replace(".", "")
    safety_net = {
        "hello": "မင်္ဂလာပါ", 
        "thank you": "ကျေးဇူးတင်ပါတယ်",
        "thanks": "ကျေးဇူးတင်ပါတယ်",
        "goodbye": "သွားပါဦးမယ်",
        "bye": "သွားပါဦးမယ်"
    }

    if clean_text in safety_net: return safety_net[clean_text]

    # THE VIP FIX: MyMemory restricts free cloud servers, but gives 50,000 words/day 
    # to ANY valid email address. This completely bypasses the IP block!
    email_bypass = "leona.gift.app@gmail.com"
    
    engines = [
        ("MyMemory VIP", f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text)}&langpair=en|my&de={email_bypass}"),
        ("Google Chrome Ext", f"https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=en&tl=my&q={urllib.parse.quote(text)}"),
        ("Lingva Core", f"https://lingva.thedesk.top/api/v1/en/my/{urllib.parse.quote(text)}")
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    for name, url in engines:
        try:
            print(f"--> Trying {name}...")
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5.0) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                if "mymemory" in url:
                    if data.get('responseStatus') == 200: 
                        return data['responseData']['translatedText']
                elif "clients5" in url:
                    if isinstance(data, list) and len(data) > 0:
                        if isinstance(data[0], str): return "".join(data)
                        elif isinstance(data[0], list): return "".join([s[0] for s in data[0] if s[0]])
                elif "lingva" in url:
                    if "text" in data: return data["text"]
        except Exception as e:
            print(f"--> {name} failed: {e}")
            
    raise Exception("All translation engines blocked.")

def smooth_phonetics(raw_text):
    if not raw_text: return ""
    text = raw_text.lower()
    spaced_text = re.sub(r'(barsar|hcakar|ko|sai|nyuu|nay|par|mhar|lell|bhaal|lout|mingalar)', r' \1 ', text)
    mapping = [
        ("ngarr", "ngar"), ("nhaith", "hnit"), ("hkuk", "ku ga"), ("kuk", "ku ga"),
        ("de ", "dee "), ("myanmar", "myan-mar"), ("barsar", "bar-thar"),
        ("hcakar", "sa-garr"), ("mingalar", "min-ga-la"), ("bh", "b"), ("mh", "m"),
        ("dh", "d"), ("gh", "g"), ("jh", "z"), ("hc", "s"), ("rr", "r"),
        ("ll", "l"), ("aou", "ou"), ("hk", "k"), ("ky", "ky"), ("kr", "ky")
    ]
    for old, new in mapping: spaced_text = spaced_text.replace(old, new)
    return re.sub(r'\s+', ' ', spaced_text).strip().capitalize()

def get_phonetics(burmese_text):
    print(f"--> [2/3] Generating phonetics...")
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=my&tl=my&dt=t&dt=rm&q={urllib.parse.quote(burmese_text)}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5.0) as response:
            data = json.loads(response.read().decode('utf-8'))
            def extract_latin(obj):
                if isinstance(obj, str):
                    has_letters = any(c.isalpha() for c in obj)
                    has_burmese = any('\u1000' <= c <= '\u109f' for c in obj)
                    if has_letters and not has_burmese and obj.lower().strip() not in ["my", "en"]:
                        return obj.strip().capitalize()
                elif isinstance(obj, list):
                    for item in obj:
                        res = extract_latin(item)
                        if res: return res
                return None
            
            if data and isinstance(data, list) and len(data) > 0:
                phonetics = extract_latin(data[0])
                if phonetics: return smooth_phonetics(phonetics)
    except Exception as e:
        print(f"--> Phonetics failed: {e}")
    return ""

def generate_neural_audio(text):
    print(f"--> [3/3] Generating neural audio...")
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    temp_path = temp_file.name
    temp_file.close() 
    
    try:
        async def _generate():
            communicate = edge_tts.Communicate(text, "my-MM-NilarNeural")
            await communicate.save(temp_path)
            
        # Bulletproof execution for Linux servers (like Render)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_generate())
        finally:
            loop.close()
            
        with open(temp_path, "rb") as f: data = f.read()
        return base64.b64encode(data).decode('utf-8')
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)

@app.route("/", methods=["GET"]) 
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/translate", methods=["POST"])
def translate():
    try:
        data = request.get_json()
        text = data.get("text", "")
        if not text.strip(): return jsonify({"error": "No text provided"}), 400

        try:
            translation = direct_translate(text)
        except Exception:
            return jsonify({"error": "Translation service failed."}), 500
            
        phonetics = get_phonetics(translation)
        
        audio_base64 = ""
        try:
            audio_base64 = generate_neural_audio(translation)
        except Exception:
            pass # Fails gracefully so the text still appears
            
        return jsonify({
            "translation": translation,
            "phonetics": phonetics,
            "audio_base64": audio_base64
        })
        
    except Exception as e:
        return jsonify({"error": "An unexpected server error occurred."}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True, debug=True)
