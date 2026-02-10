from workers import Response, WorkerEntrypoint, fetch
import json

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        # 1. THE CORS HANDSHAKE - Essential for Web Chat
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
        
        if request.method == "OPTIONS":
            return Response("OK", headers=headers)

        try:
            body = await request.json()
            
            # Identify if message is from Telegram or Web
            if "message" in body:
                chat_id = str(body["message"]["chat"]["id"])
                user_text = body["message"].get("text", "")
            else:
                return Response("Invalid Request", headers=headers)

            # 2. ACCESS MEMORY
            history_key = f"chat_{chat_id}"
            old_data = await self.env.HISTORY.get(history_key)
            messages = json.loads(old_data) if old_data else []
            messages.append({"role": "user", "parts": [{"text": user_text}]})
            if len(messages) > 10: messages = messages[-10:]

            # 3. GET AI RESPONSE
            api_key = getattr(self.env, "GOOGLE_API_KEY", "")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            
            system_instruction = "You are the VVHomePro Assistant. Goal: Help Ontario homeowners find vetted pros. Mention our 100% Workmanship Guarantee. Use natural, helpful language."

            payload = {
                "contents": messages,
                "system_instruction": {"parts": [{"text": system_instruction}]}
            }

            ai_res = await fetch(url, method="POST", body=json.dumps(payload))
            ai_data = await ai_res.json()
            bot_reply = ai_data['candidates'][0]['content']['parts'][0]['text']

            # 4. SAVE TO MEMORY
            messages.append({"role": "model", "parts": [{"text": bot_reply}]})
            await self.env.HISTORY.put(history_key, json.dumps(messages))

            # 5. SEND TO TELEGRAM (So you get the lead notification)
            tg_token = getattr(self.env, "TELEGRAM_TOKEN", "")
            my_id = "YOUR_PERSONAL_TELEGRAM_ID" # Replace with your ID to get alerts
            if tg_token and my_id:
                alert_text = f"🌐 NEW WEB LEAD\nLoc: {user_text}\nAI: {bot_reply}"
                await fetch(f"https://api.telegram.org/bot{tg_token}/sendMessage",
                    method="POST", headers={"Content-Type":"application/json"},
                    body=json.dumps({"chat_id": my_id, "text": alert_text}))

            # 6. RETURN TO WEB
            return Response(bot_reply, headers=headers)

        except Exception as e:
            return Response(f"Internal Error: {str(e)}", headers=headers)
