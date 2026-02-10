from workers import Response, WorkerEntrypoint, fetch
import json
import re

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        if request.method == "OPTIONS":
            return Response("OK", headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST",
                "Access-Control-Allow-Headers": "Content-Type"
            })

        try:
            body = await request.json()
            if "message" not in body: return Response("OK")
            
            chat_id = str(body["message"]["chat"]["id"])
            user_text = body["message"].get("text", "")
            
            api_key = getattr(self.env, "GOOGLE_API_KEY", None)
            tg_token = getattr(self.env, "TELEGRAM_TOKEN", None)
            my_admin_id = str(getattr(self.env, "MY_CHAT_ID", None))

            # --- VVHomePro DIRECTORY CATEGORIES ---
            # As you add partners, the AI will use these to 'categorize' the lead
            categories = ["roofing", "hvac", "windows", "landscaping", "flooring", "plumbing", "electrical"]
            detected_category = "home improvement"
            for cat in categories:
                if cat in user_text.lower():
                    detected_category = cat

            # --- THE VVHomePro MATCHMAKER PROMPT ---
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            
            system_instruction = (
                f"You are the VVHomePro Matchmaker for Ontario. The user needs {detected_category} services. "
                "1. Acknowledge their specific location in Ontario. "
                "2. Emphasize that all VVHomePro partners are 'Vetted & Verified'. "
                "3. Explicitly mention our '100% Workmanship Guarantee'. "
                "4. You MUST collect: Name, Phone Number, and the best time for a specialist to call. "
                "Be premium, authoritative, and reassuring."
            )

            # --- AI CALL ---
            ai_res = await fetch(url, method="POST", body=json.dumps({"contents": [{"parts": [{"text": f"{system_instruction} User said: {user_text}"}]}]}))
            ai_data = await ai_res.json()
            
            try:
                bot_reply = ai_data['candidates'][0]['content']['parts'][0]['text']
            except:
                # PREMIUM BRANDED FALLBACK
                bot_reply = (
                    f"Thank you for contacting VVHomePro. We have vetted and verified specialists for {detected_category} "
                    "available in your area. All our partners are backed by our 100% Workmanship Guarantee. "
                    "May I have your name, phone number, and the most convenient time for our specialist to contact you?"
                )

            # --- DISPATCH LEAD TO ADMIN ---
            if len(user_text) > 5:
                alert_text = f"🏢 **VVHomePro NEW LEAD** 🏢\n\n**Category:** {detected_category.upper()}\n**Details:** {user_text}\n**Chat ID:** {chat_id}"
                await fetch(f"https://api.telegram.org/bot{tg_token}/sendMessage",
                    method="POST", headers={"Content-Type": "application/json"},
                    body=json.dumps({"chat_id": my_admin_id, "text": alert_text}))

            # --- SEND TO USER ---
            await fetch(f"https://api.telegram.org/bot{tg_token}/sendMessage",
                method="POST", headers={"Content-Type": "application/json"},
                body=json.dumps({"chat_id": chat_id, "text": bot_reply}))

            return Response("OK", status=200)

        except Exception as e:
            return Response("Error", status=200)
