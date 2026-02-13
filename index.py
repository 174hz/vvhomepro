from workers import Response, WorkerEntrypoint, fetch
import json

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        url = request.url
        # 1. THE CORS HANDSHAKE
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
        
        if request.method == "OPTIONS":
            return Response("OK", headers=headers)

        # --- 2. ROUTING LOGIC: FIX THE "ABOUT US" LINK ---
        # This tells the worker: If the URL has 'about', go get the page from GitHub.
        if "about" in url:
            github_about_url = "https://174hz.github.io/vvhomepro/about.html"
            try:
                res = await fetch(github_about_url)
                content = await res.text()
                return Response(content, headers={"Content-Type": "text/html", **headers})
            except Exception as e:
                return Response(f"Link Error: {str(e)}", status=404, headers=headers)

        # --- 3. AI BOT LOGIC ---
        if request.method == "POST":
            try:
                body = await request.json()
                
                # Support both Web (contents) and Telegram (message)
                if "contents" in body:
                    messages = body["contents"]
                    user_text = messages[-1]["parts"][0]["text"]
                    chat_id = "web_user" # Simplified for web
                elif "message" in body:
                    chat_id = str(body["message"]["chat"]["id"])
                    user_text = body["message"].get("text", "")
                    messages = [{"role": "user", "parts": [{"text": user_text}]}]
                else:
                    return Response("Invalid structure", headers=headers)

                # GET AI RESPONSE FROM GEMINI
                api_key = getattr(self.env, "GOOGLE_API_KEY", "")
                gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
                
                system_instruction = "You are the VV HOME PRO Assistant. Goal: Help Ontario homeowners find vetted pros. Mention our 100% Workmanship Guarantee. Use natural, helpful language."

                payload = {
                    "contents": messages,
                    "system_instruction": {"parts": [{"text": system_instruction}]}
                }

                ai_res = await fetch(gemini_url, method="POST", body=json.dumps(payload))
                ai_data = await ai_res.json()
                bot_reply = ai_data['candidates'][0]['content']['parts'][0]['text']

                # SEND TELEGRAM NOTIFICATION (Lead Alert)
                tg_token = getattr(self.env, "TELEGRAM_TOKEN", "")
                my_id = "YOUR_PERSONAL_TELEGRAM_ID" 
                if tg_token and my_id:
                    alert_text = f"🌐 NEW VV HOME PRO LEAD\nUser: {user_text}\nAI: {bot_reply}"
                    await fetch(f"https://api.telegram.org/bot{tg_token}/sendMessage",
                        method="POST", headers={"Content-Type":"application/json"},
                        body=json.dumps({"chat_id": my_id, "text": alert_text}))

                return Response(bot_reply, headers=headers)

            except Exception as e:
                return Response(f"Bot Error: {str(e)}", headers=headers)

        # DEFAULT RESPONSE
        return Response("VV HOME PRO Worker Active", headers=headers)
