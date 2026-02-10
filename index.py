from workers import Response, WorkerEntrypoint, fetch
import json

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        # 1. HANDLE CORS PREFLIGHT (The 'Handshake')
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
        
        if request.method == "OPTIONS":
            return Response("OK", headers=headers)

        try:
            body = await request.json()
            if "message" not in body: return Response("No Message", headers=headers)
            
            chat_id = str(body["message"]["chat"]["id"])
            user_text = body["message"].get("text", "")

            # --- 2. GET MEMORY ---
            history_key = f"chat_{chat_id}"
            old_data = await self.env.HISTORY.get(history_key)
            messages = json.loads(old_data) if old_data else []
            messages.append({"role": "user", "parts": [{"text": user_text}]})
            if len(messages) > 10: messages = messages[-10:]

            # --- 3. TALK TO AI ---
            api_key = getattr(self.env, "GOOGLE_API_KEY", "")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            
            system_instruction = "You are the VVHomePro Assistant. Goal: Help Ontario homeowners find vetted pros for Windows, Roofing, HVAC, etc. Rule: Once they give their Name/Phone, confirm we will call them. Always mention our 100% Workmanship Guarantee."

            payload = {
                "contents": messages,
                "system_instruction": {"parts": [{"text": system_instruction}]}
            }

            ai_res = await fetch(url, method="POST", body=json.dumps(payload))
            ai_data = await ai_res.json()
            bot_reply = ai_data['candidates'][0]['content']['parts'][0]['text']

            # --- 4. SAVE & NOTIFY TELEGRAM ---
            messages.append({"role": "model", "parts": [{"text": bot_reply}]})
            await self.env.HISTORY.put(history_key, json.dumps(messages))

            # Send alert to YOUR private chat so you know a web user is active
            tg_token = getattr(self.env, "TELEGRAM_TOKEN", "")
            my_id = getattr(self.env, "MY_CHAT_ID", "")
            if my_id:
                await fetch(f"https://api.telegram.org/bot{tg_token}/sendMessage",
                    method="POST", headers={"Content-Type":"application/json"},
                    body=json.dumps({"chat_id": my_id, "text": f"🌐 WEB LEAD: {user_text}"}))

            # --- 5. RETURN TO WEB PAGE ---
            return Response(bot_reply, headers=headers)

        except Exception as e:
            return Response(f"Error: {str(e)}", headers=headers)
