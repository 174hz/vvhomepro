from workers import Response, WorkerEntrypoint, fetch
import json

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        # --- 1. THE BULLETPROOF HANDSHAKE (CORS) ---
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }

        # If the browser is just checking the connection, say "Yes" immediately
        if request.method == "OPTIONS":
            return Response("OK", headers=headers)

        try:
            body = await request.json()
            if "message" not in body:
                return Response("Ready", headers=headers)
            
            chat_id = str(body["message"]["chat"]["id"])
            user_text = body["message"].get("text", "")

            # --- 2. MEMORY LOGIC ---
            history_key = f"chat_{chat_id}"
            old_data = await self.env.HISTORY.get(history_key)
            messages = json.loads(old_data) if old_data else []
            messages.append({"role": "user", "parts": [{"text": user_text}]})
            if len(messages) > 10: messages = messages[-10:]

            # --- 3. CALL GEMINI ---
            api_key = getattr(self.env, "GOOGLE_API_KEY", "")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            
            system_instruction = (
                "You are the VVHomePro Assistant. "
                "Help Ontario homeowners find vetted pros for Windows, Roofing, HVAC, etc. "
                "Mention our 100% Workmanship Guarantee. "
                "Keep responses professional and helpful."
            )

            payload = {
                "contents": messages,
                "system_instruction": {"parts": [{"text": system_instruction}]}
            }

            ai_res = await fetch(url, method="POST", body=json.dumps(payload))
            ai_data = await ai_res.json()
            bot_reply = ai_data['candidates'][0]['content']['parts'][0]['text']

            # --- 4. SAVE MEMORY ---
            messages.append({"role": "model", "parts": [{"text": bot_reply}]})
            await self.env.HISTORY.put(history_key, json.dumps(messages))

            # --- 5. RETURN RESPONSE TO WEB ---
            return Response(bot_reply, headers=headers)

        except Exception as e:
            # If something fails, send the error message so we can see it
            return Response(f"Internal Error: {str(e)}", headers=headers)
