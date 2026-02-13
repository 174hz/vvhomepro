from workers import Response, WorkerEntrypoint, fetch
import json

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        url = request.url.lower()
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
        
        if request.method == "OPTIONS":
            return Response("OK", headers=headers)

        # 1. FAIL-SAFE ROUTING FOR ABOUT PAGE
        if "about" in url:
            try:
                # Direct fetch from your GitHub Pages
                github_res = await fetch("https://174hz.github.io/vvhomepro/about.html")
                content = await github_res.text()
                return Response(content, headers={"Content-Type": "text/html", **headers})
            except:
                return Response("About page currently unavailable.", status=404, headers=headers)

        # 2. AI BOT PROCESSING
        if request.method == "POST":
            try:
                body = await request.json()
                
                # Handle Web Chat Structure
                if "contents" in body:
                    messages = body["contents"]
                    user_text = messages[-1]["parts"][0]["text"]
                else:
                    return Response("Invalid Request Format", headers=headers)

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

                # TELEGRAM NOTIFICATION (Lead Alert)
                tg_token = getattr(self.env, "TELEGRAM_TOKEN", "")
                my_id = "YOUR_PERSONAL_TELEGRAM_ID" 
                if tg_token and my_id:
                    alert = f"🌐 NEW VV HOME PRO LEAD\nUser: {user_text}\nAI: {bot_reply}"
                    await fetch(f"https://api.telegram.org/bot{tg_token}/sendMessage",
                        method="POST", headers={"Content-Type":"application/json"},
                        body=json.dumps({"chat_id": my_id, "text": alert}))

                return Response(bot_reply, headers=headers)

            except Exception as e:
                return Response(f"Worker Error: {str(e)}", headers=headers)

        return Response("VV HOME PRO Worker Active", headers=headers)
