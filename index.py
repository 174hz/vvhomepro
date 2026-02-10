from workers import Response, WorkerEntrypoint, fetch
import json

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        try:
            body = await request.json()
            msg = body.get("message", {})
            chat_id = str(msg.get("chat", {}).get("id", ""))
            user_text = msg.get("text", "")

            # 1. RETRIEVE HISTORY
            # We look up the chat_id in our 'HISTORY' binding
            history_key = f"chat_{chat_id}"
            raw_history = await self.env.HISTORY.get(history_key)
            history = json.loads(raw_history) if raw_history else []

            # 2. ADD NEW MESSAGE TO HISTORY
            history.append({"role": "user", "parts": [{"text": user_text}]})
            
            # Keep only last 10 messages so it stays fast
            if len(history) > 10: history = history[-10:]

            # 3. CALL GEMINI WITH FULL CONTEXT
            api_key = getattr(self.env, "GOOGLE_API_KEY", "")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            
            system_prompt = "You are the VVHomePro Assistant. Identify service and location in Ontario. Confirm our 100% Guarantee. Collect Name, Phone, and Time."
            
            payload = {
                "contents": history,
                "system_instruction": {"parts": [{"text": system_prompt}]}
            }

            ai_res = await fetch(url, method="POST", body=json.dumps(payload))
            ai_data = await ai_res.json()
            bot_reply = ai_data['candidates'][0]['content']['parts'][0]['text']

            # 4. SAVE UPDATED HISTORY
            history.append({"role": "model", "parts": [{"text": bot_reply}]})
            await self.env.HISTORY.put(history_key, json.dumps(history))

            # 5. SEND TO TELEGRAM
            tg_token = getattr(self.env, "TELEGRAM_TOKEN", "")
            await fetch(f"https://api.telegram.org/bot{tg_token}/sendMessage",
                method="POST", headers={"Content-Type":"application/json"},
                body=json.dumps({"chat_id": chat_id, "text": bot_reply}))

            return Response("OK")
        except Exception as e:
            return Response("OK")
