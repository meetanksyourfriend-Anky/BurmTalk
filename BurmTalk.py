from flask import Flask, render_template_string, request, jsonify
import base64
import os
import sys
import tempfile
import subprocess
import urllib.parse

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Dear Leona - Translator</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Dancing+Script:wght@700&family=Padauk:wght@400;700&family=Noto+Sans+Myanmar:wght@400;700&display=swap" rel="stylesheet">

    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 0; margin: 0; background: #f4f6f8; color: #333; }
        .header { background: #007bff; color: white; padding: 15px 20px; text-align: center; font-size: 22px; font-weight: bold; }
        .container { max-width: 500px; margin: 20px auto; padding: 0 15px; }
        .tabs { display: flex; margin-bottom: 20px; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .tab-btn { flex: 1; padding: 12px; border: none; background: #fff; color: #555; font-size: 16px; font-weight: 600; cursor: pointer; }
        .tab-btn.active { background: #e9ecef; color: #007bff; border-bottom: 3px solid #007bff; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        input[type="text"] { width: 100%; padding: 12px; margin: 10px 0 15px; box-sizing: border-box; font-size: 16px; border: 1px solid #ddd; border-radius: 6px; }
        button.primary-btn { background: #007bff; color: white; border: none; padding: 14px 20px; border-radius: 6px; cursor: pointer; width: 100%; font-size: 16px; font-weight: bold; }
        button.primary-btn:disabled { background: #a5cbf5; cursor: not-allowed; }
        .output { background: #f8f9fa; padding: 15px; margin-top: 20px; border-radius: 8px; display: none; border: 1px solid #e9ecef;}
        audio { width: 100%; margin-top: 10px; height: 40px; display: none; }
        #loading { display: none; text-align: center; margin-top: 20px; font-style: italic; color: #666; }
        .error { color: #dc3545; margin-top: 15px; font-weight: bold; text-align: center; display: none;}
        .burmese-text { font-family: 'Padauk', 'Noto Sans Myanmar', sans-serif; font-size: 28px; color: #111; margin: 10px 0; }
        .phonetics-text { color: #0056b3; font-size: 18px; margin-bottom: 15px; font-weight: 500; }
        .save-btn { background: #ffc107; color: #333; border: none; padding: 10px 15px; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; margin-top: 15px; font-size: 15px; }
        .saved-item { background: white; border: 1px solid #ddd; padding: 15px; border-radius: 8px; margin-bottom: 15px; position: relative; }
        .saved-english { font-weight: bold; font-size: 16px; color: #555; margin-bottom: 5px;}
        .delete-btn { position: absolute; top: 10px; right: 10px; background: #dc3545; color: white; border: none; border-radius: 4px; padding: 5px 10px; font-size: 12px; cursor: pointer; }
        .empty-state { text-align: center; color: #777; padding: 30px 10px; font-style: italic; }
        .footer-signature { font-family: 'Dancing Script', cursive; color: #dc3545; font-size: 32px; text-align: center; margin: 30px 0; text-shadow: 1px 1px 2px rgba(0,0,0,0.05); }
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
                <div id="loading">Translating directly from your device...</div>
                <div id="error-msg" class="error"></div>
                <div class="output" id="output-section">
                    <div class="burmese-text" id="burmese-text"></div>
                    <div class="phonetics-text" id="phonetics-text"></div>
                    <audio id="audio-player" controls></audio>
                    <button class="save-btn" id="save-btn" onclick="saveCurrentTranslation()">⭐ Save to Phrasebook</button>
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
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById('tabBtn-' + tabId).classList.add('active');
            document.getElementById('tab-' + tabId).classList.add('active');
            if(tabId === 'phrasebook') renderPhrasebook();
        }

        // Custom Phonetic Smoother 
        function smoothPhonetics(rawText) {
            if (!rawText) return "";
            let text = rawText.toLowerCase();
            text = text.replace(/(barsar|hcakar|ko|sai|nyuu|nay|par|mhar|lell|bhaal|lout|mingalar)/g, ' $1 ');
            const mapping = [
                ["ngarr", "ngar"], ["nhaith", "hnit"], ["hkuk", "ku ga"], ["kuk", "ku ga"],
                ["de ", "dee "], ["myanmar", "myan-mar"], ["barsar", "bar-thar"],
                ["hcakar", "sa-garr"], ["mingalar", "min-ga-la"], ["bh", "b"],
                ["mh", "m"], ["dh", "d"], ["gh", "g"], ["jh", "z"], ["hc", "s"],
                ["rr", "r"], ["ll", "l"], ["aou", "ou"], ["hk", "k"], ["ky", "ky"], ["kr", "ky"]
            ];
            mapping.forEach(([old, replaceVal]) => { text = text.split(old).join(replaceVal); });
            text = text.replace(/\s+/g, ' ').trim();
            return text.charAt(0).toUpperCase() + text.slice(1);
        }

        function extractLatin(obj) {
            if (typeof obj === 'string') {
                const str = obj.trim();
                // Extract only if it has english letters, NO burmese letters, and isn't a language code
                if (/[a-zA-Z]/.test(str) && !/[\u1000-\u109F]/.test(str) && !['my','en'].includes(str.toLowerCase())) {
                    return str;
                }
            } else if (Array.isArray(obj)) {
                for (let item of obj) {
                    let res = extractLatin(item);
                    if (res) return res;
                }
            }
            return null;
        }

        document.getElementById('translator-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            const text = document.getElementById('english_text').value.trim();
            const btn = document.getElementById('submit-btn');
            const loading = document.getElementById('loading');
            const output = document.getElementById('output-section');
            const errorMsg = document.getElementById('error-msg');
            const audioPlayer = document.getElementById('audio-player');
            const saveBtn = document.getElementById('save-btn');

            if (!text) return;
            btn.disabled = true; loading.style.display = 'block'; output.style.display = 'none'; errorMsg.style.display = 'none';
            audioPlayer.style.display = 'none'; audioPlayer.src = "";
            saveBtn.innerHTML = "⭐ Save to Phrasebook"; saveBtn.disabled = false;

            let finalBurmese = "";
            let finalPhonetics = "";
            
            const cleanText = text.toLowerCase().replace(/[.?!]/g, '').trim();
            const safetyNet = { "hello": ["မင်္ဂလာပါ", "Min-ga-la-ba"], "thank you": ["ကျေးဇူးတင်ပါတယ်", "Kye-zu tin bar de"], "thanks": ["ကျေးဇူးတင်ပါတယ်", "Kye-zu tin bar de"], "goodbye": ["သွားပါဦးမယ်", "Thwa bar ou me"], "bye": ["သွားပါဦးမယ်", "Thwa bar ou me"] };

            try {
                if (safetyNet[cleanText]) {
                    finalBurmese = safetyNet[cleanText][0];
                    finalPhonetics = safetyNet[cleanText][1];
                } else {
                    // Fetch 1: Translate English to Burmese
                    const url1 = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=my&dt=t&q=${encodeURIComponent(text)}`;
                    const res1 = await fetch(url1);
                    const data1 = await res1.json();
                    
                    if (data1 && data1[0]) {
                        finalBurmese = data1[0][0][0];
                        
                        // Fetch 2: Isolate the phonetics by requesting the romanization of the Burmese text
                        const url2 = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=my&tl=my&dt=rm&q=${encodeURIComponent(finalBurmese)}`;
                        const res2 = await fetch(url2);
                        const data2 = await res2.json();
                        
                        const rawPhonetics = extractLatin(data2[0]);
                        finalPhonetics = smoothPhonetics(rawPhonetics);
                    } else {
                        throw new Error("Translation data missing");
                    }
                }

                document.getElementById('burmese-text').innerText = finalBurmese;
                document.getElementById('phonetics-text').innerText = finalPhonetics ? "🗣️ " + finalPhonetics : "";
                output.style.display = 'block';

                // Fetch 3: Generate Neural Audio safely via Render
                const audioRes = await fetch('/generate_audio', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: finalBurmese })
                });
                
                let audioBase64 = null;
                if (audioRes.ok) {
                    const audioData = await audioRes.json();
                    if (audioData.audio_base64) {
                        audioBase64 = audioData.audio_base64;
                        audioPlayer.src = "data:audio/mp3;base64," + audioBase64;
                        audioPlayer.style.display = 'block';
                        audioPlayer.play().catch(e => console.log("Autoplay blocked."));
                    }
                }

                currentTranslationData = {
                    id: Date.now().toString(),
                    english: text, burmese: finalBurmese, phonetics: finalPhonetics, audio: audioBase64
                };

            } catch (err) {
                errorMsg.innerText = "Check your internet connection.";
                errorMsg.style.display = 'block';
            } finally {
                btn.disabled = false; loading.style.display = 'none';
            }
        });

        function saveCurrentTranslation() {
            if (!currentTranslationData) return;
            let savedItems = JSON.parse(localStorage.getItem('burmTalkSaved') || '[]');
            savedItems.unshift(currentTranslationData);
            localStorage.setItem('burmTalkSaved', JSON.stringify(savedItems));
            const saveBtn = document.getElementById('save-btn');
            saveBtn.innerHTML = "✅ Saved!";
            saveBtn.disabled = true;
        }

        function renderPhrasebook() {
            const listContainer = document.getElementById('phrasebook-list');
            let savedItems = JSON.parse(localStorage.getItem('burmTalkSaved') || '[]');
            listContainer.innerHTML = '';
            if (savedItems.length === 0) {
                listContainer.innerHTML = '<div class="empty-state">Your phrasebook is empty.</div>'; return;
            }
            savedItems.forEach(item => {
                const card = document.createElement('div');
                card.className = 'saved-item';
                let audioHtml = item.audio ? `<audio controls src="data:audio/mp3;base64,${item.audio}" style="display:block;"></audio>` : '';
                let phoneticsHtml = item.phonetics ? `<div class="phonetics-text">🗣️ ${item.phonetics}</div>` : '';
                card.innerHTML = `
                    <button class="delete-btn" onclick="deletePhrase('${item.id}')">Delete</button>
                    <div class="saved-english">${item.english}</div>
                    <div class="burmese-text">${item.burmese}</div>
                    ${phoneticsHtml} ${audioHtml}
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

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/generate_audio", methods=["POST"])
def generate_audio():
    data = request.get_json()
    text = data.get("text", "")
    if not text.strip():
        return jsonify({"error": "No text"}), 400

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    temp_path = temp_file.name
    temp_file.close()

    try:
        # Thread-safe execution perfectly suited for Render's environment
        subprocess.run(
            [sys.executable, "-m", "edge_tts", "--voice", "my-MM-NilarNeural", "--text", text, "--write-media", temp_path], 
            check=True
        )
        
        with open(temp_path, "rb") as f:
            audio_bytes = f.read()
            
        return jsonify({"audio_base64": base64.b64encode(audio_bytes).decode('utf-8')})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)
