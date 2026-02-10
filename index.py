from workers import Response, WorkerEntrypoint, fetch
import json

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        try:
            body = await request.json()
            if "message" not in body: return Response("OK")
            
            chat_id = str(body["message"]["chat"]["id"])
            user_text = body["message"].get("text", "")

            # --- 1. ACCESS MEMORY (The KV Binding) ---
            history_key = f"chat_{chat_id}"
            # This line looks into your 'HISTORY' binding we just set up
            old_data = await self.env.HISTORY.get(history_key)
            messages = json.loads(old_data) if old_data else []
            
            # --- 2. RECORD THE NEW MESSAGE ---
            messages.append({"role": "user", "parts": [{"text": user_text}]})
            
            # Keep history to 10 messages so it stays fast
            if len(messages) > 10: messages = messages[-10:]

            # --- 3. THE BRAIN (Gemini 1.5 Flash) ---
            api_key = getattr(self.env, "GOOGLE_API_KEY", "")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            
            system_instruction = (
                "You are the VVHomePro Assistant. "
                "Goal: Help Ontario homeowners find vetted pros for Windows, Roofing, HVAC, etc. "
                "Rule: Once they give their Name/Phone, confirm we will call them. "
                "Always mention our 100% Workmanship Guarantee. "
                "Context: You have access to the conversation history. Use it to be helpful."
            )

            payload = {
                "contents": messages,
                "system_instruction": {"parts": [{"text": system_instruction}]}
            }

            ai_res = await fetch(url, method="POST", body=json.dumps(payload))
            ai_data = await ai_res.json()
            bot_reply = ai_data['candidates'][0]['content']['parts'][0]['text']

            # --- 4. SAVE REPLY TO MEMORY ---
            messages.append({"role": "model", "parts": [{"text": bot_reply}]})
            await self.env.HISTORY.put(history_key, json.dumps(messages))

            # --- 5. SEND TO TELEGRAM ---
            tg_token = getattr(self.env, "TELEGRAM_TOKEN", "")
            await fetch(f"https://api.telegram.org/bot{tg_token}/sendMessage",
                method="POST", headers={"Content-Type":"application/json"},
                body=json.dumps({"chat_id": chat_id, "text": bot_reply}))

            return Response("OK")
        except:
            # Silent fail to prevent bot crashing
            return Response("OK")
