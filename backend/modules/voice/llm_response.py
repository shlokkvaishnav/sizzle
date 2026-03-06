"""
llm_response.py - LLM-powered natural response generator.

Decides whether to use the local LLM for phrasing or fall back to
language-specific templates. Always returns speakable text and never raises.
"""

import logging

import httpx

from .voice_config import cfg

logger = logging.getLogger("petpooja.voice.llm_response")

SUPPORTED_LANGS = {"en", "hi", "gu", "mr", "kn"}

SYSTEM_PROMPT = (
    "You are Sizzle, the voice of an AI restaurant ordering assistant in India. "
    "Generate spoken response text that sounds like a polite live phone-ordering agent.\n\n"
    "Rules:\n"
    "1. Maximum 2 sentences and 25 words total.\n"
    "2. Match the customer's language exactly.\n"
    "3. Use only the order data provided. Do not invent facts.\n"
    "4. Sound warm and concise, like an order-taking agent, not a robot.\n"
    "5. For 5 or more items, summarize naturally instead of listing every item.\n"
    "6. Output only the spoken text, with no JSON or explanation."
)


class LLMResponseGenerator:
    """Singleton generator for spoken agent responses."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def should_use_llm(self, pipeline_result: dict) -> bool:
        """Use the LLM only when templates would sound limited."""
        if not cfg.LLM_ENABLED:
            return False

        items = pipeline_result.get("items", [])
        intent = pipeline_result.get("intent", "")

        if len(items) >= cfg.LLM_MIN_ITEMS_FOR_SUMMARY:
            return True
        if intent == "QUERY":
            return True
        return False

    async def generate(self, pipeline_result: dict, detected_language: str) -> str:
        """Call the local LLM and fall back to templates on failure."""
        try:
            user_prompt = self._build_user_prompt(pipeline_result, detected_language)

            async with httpx.AsyncClient(timeout=cfg.LLM_TIMEOUT_SEC) as client:
                resp = await client.post(
                    f"{cfg.LLM_BASE_URL}/api/generate",
                    json={
                        "model": cfg.LLM_MODEL,
                        "prompt": user_prompt,
                        "system": SYSTEM_PROMPT,
                        "stream": False,
                        "options": {
                            "temperature": cfg.LLM_TEMPERATURE,
                            "num_predict": cfg.LLM_MAX_TOKENS,
                        },
                    },
                )
                resp.raise_for_status()
                text = resp.json().get("response", "").strip().strip("\"'")
                if text:
                    return text
        except httpx.TimeoutException:
            logger.info("LLM timed out (%.1fs) - using template", cfg.LLM_TIMEOUT_SEC)
        except Exception as exc:
            logger.warning("LLM call failed: %s - using template", exc)

        return self._fallback_template(pipeline_result, detected_language)

    def _build_user_prompt(self, pipeline_result: dict, detected_language: str) -> str:
        """Construct a compact prompt from the pipeline result."""
        items = pipeline_result.get("items", [])
        intent = pipeline_result.get("intent", "UNCLEAR")
        upsells = pipeline_result.get("upsell_suggestions", [])
        disambiguation = pipeline_result.get("disambiguation", [])
        order = pipeline_result.get("order")

        if len(items) >= cfg.LLM_MIN_ITEMS_FOR_SUMMARY:
            situation = "complex_order_echo"
        elif upsells:
            situation = "upsell_suggestion"
        elif intent == "QUERY":
            situation = "query_response"
        elif len(disambiguation) >= 3:
            situation = "ambiguous_multi_option"
        else:
            situation = "standard_order_turn"

        item_summary = ", ".join(
            f"{item.get('quantity', 1)} {item.get('item_name', 'unknown')}"
            for item in items
        ) or "no items matched"

        extra = []
        if upsells:
            upsell_names = [u.get("name") or u.get("suggestion_text", "") for u in upsells]
            extra.append(f"upsells: {', '.join(upsell_names)}")
        if disambiguation:
            for entry in disambiguation:
                alts = [alt.get("item_name", "") for alt in entry.get("alternatives", [])]
                extra.append(f"ambiguous {entry.get('item_name', '')}: {', '.join(alts)}")
        if order and order.get("subtotal"):
            extra.append(f"subtotal: {order['subtotal']} rupees")

        extra_context = "; ".join(extra) if extra else "none"
        return (
            f"Situation: {situation}\n"
            f"Order data: {item_summary}\n"
            f"Customer language: {detected_language}\n"
            f"Context: {extra_context}\n"
            "Generate the spoken response:"
        )

    def _fallback_template(self, pipeline_result: dict, lang: str) -> str:
        """Template fallback that always returns a valid spoken response."""
        items = pipeline_result.get("items", [])
        intent = pipeline_result.get("intent", "UNCLEAR")
        order = pipeline_result.get("order")
        disambiguation = pipeline_result.get("disambiguation", [])
        stage_results = pipeline_result.get("stage_results", [])
        has_session_items = bool(pipeline_result.get("session_items"))

        for sr in stage_results:
            err = sr.get("error_type")
            if err == "no_speech_detected":
                return self._t_no_speech(lang, has_session_items)
            if err == "audio_too_short":
                return self._t_audio_short(lang)

        if intent == "DONE":
            if has_session_items:
                return self._t_done(lang)
            return self._t_done_empty(lang)

        if intent == "ORDER":
            if len(items) == 0:
                return self._t_no_match(lang)
            if len(items) >= cfg.LLM_MIN_ITEMS_FOR_SUMMARY:
                return self._t_order_many(lang, len(items))
            return self._t_order(lang, items)

        if intent == "CANCEL":
            if not items:
                if not has_session_items:
                    return self._t_cancel_all(lang)
                return self._t_cancel_clarify(lang)
            if len(items) == 1:
                return self._t_cancel(lang, items[0]["item_name"])
            return self._t_cancel(lang, ", ".join(item["item_name"] for item in items))

        if intent == "MODIFY":
            if items:
                item_name = items[0]["item_name"]
                mods = items[0].get("modifiers", {})
                modifier_str = ", ".join(mods.get("applied", [])) if mods.get("applied") else "as requested"
                return self._t_modify(lang, item_name, modifier_str)
            return self._t_modify(lang, "the item", "as requested")

        if intent == "CONFIRM":
            session_order = pipeline_result.get("session_order")
            confirm_order = session_order or order
            total = 0
            if confirm_order:
                total = confirm_order.get("total") or confirm_order.get("subtotal") or 0
            if not total and has_session_items:
                total = sum(
                    item.get("line_total", 0)
                    or (item.get("unit_price", 0) * item.get("quantity", 1))
                    for item in pipeline_result.get("session_items", [])
                )
            return self._t_confirm(lang, total)

        if disambiguation and len(disambiguation) <= 2:
            entry = disambiguation[0]
            alts = entry.get("alternatives", [])
            if alts:
                return self._t_disambiguation(
                    lang,
                    entry.get("item_name", "option one"),
                    alts[0].get("item_name", "option two"),
                )

        return self._t_no_speech(lang, has_session_items)

    @staticmethod
    def _t_order(lang: str, items: list) -> str:
        names = ", ".join(f"{item.get('quantity', 1)} {item.get('item_name', '')}" for item in items)
        templates = {
            "en": f"Sure, I've added {names}. Would you like anything else?",
            "hi": f"Theek hai, maine {names} add kar diya. Aur kuch chahiye?",
            "gu": f"ઠીક છે, મેં {names} ઉમેર્યા. બીજું કંઈ જોઈએ?",
            "mr": f"ठीक आहे, मी {names} जोडले. अजून काही हवे का?",
            "kn": f"ಸರಿ, ನಾನು {names} ಸೇರಿಸಿದ್ದೇನೆ. ಇನ್ನೇನಾದರೂ ಬೇಕೇ?",
        }
        return templates.get(lang, templates["en"])

    @staticmethod
    def _t_order_many(lang: str, count: int) -> str:
        templates = {
            "en": f"Sure, I've added {count} items to your order. Would you like anything else?",
            "hi": f"Theek hai, maine {count} items add kar diye hain. Aur kuch chahiye?",
            "gu": f"ઠીક છે, મેં {count} વસ્તુઓ ઉમેર્યાં છે. બીજું કંઈ જોઈએ?",
            "mr": f"ठीक आहे, मी {count} वस्तू जोडल्या आहेत. अजून काही हवे का?",
            "kn": f"ಸರಿ, ನಾನು {count} items ಸೇರಿಸಿದ್ದೇನೆ. ಇನ್ನೇನಾದರೂ ಬೇಕೇ?",
        }
        return templates.get(lang, templates["en"])

    @staticmethod
    def _t_cancel(lang: str, item_name: str) -> str:
        templates = {
            "en": f"Sure, I've removed {item_name}. Would you like anything else?",
            "hi": f"Theek hai, maine {item_name} hata diya. Aur kuch badalna hai?",
            "gu": f"ઠીક છે, મેં {item_name} દૂર કર્યું. બીજું કંઈ જોઈએ?",
            "mr": f"ठीक आहे, मी {item_name} काढले. अजून काही हवे का?",
            "kn": f"ಸರಿ, ನಾನು {item_name} ತೆಗೆದೆ. ಇನ್ನೇನಾದರೂ ಬೇಕೇ?",
        }
        return templates.get(lang, templates["en"])

    @staticmethod
    def _t_cancel_all(lang: str) -> str:
        templates = {
            "en": "Your order is cleared. Would you like to start again?",
            "hi": "Aapka order clear ho gaya. Naya order shuru karein?",
            "gu": "તમારો ઓર્ડર ક્લિયર થઈ ગયો. ફરીથી શરૂ કરવું છે?",
            "mr": "तुमचा ऑर्डर क्लिअर झाला. पुन्हा सुरू करायचं का?",
            "kn": "ನಿಮ್ಮ ಆರ್ಡರ್ ಕ್ಲಿಯರ್ ಆಗಿದೆ. ಮತ್ತೆ ಶುರು ಮಾಡಲಾ?",
        }
        return templates.get(lang, templates["en"])

    @staticmethod
    def _t_cancel_clarify(lang: str) -> str:
        templates = {
            "en": "Which item should I remove? Please say the item name.",
            "hi": "Kaunsa item hatana hai? Please item ka naam boliye.",
            "gu": "કયું item દૂર કરવું છે? કૃપા કરીને item નું નામ કહો.",
            "mr": "कोणते item काढायचे? कृपया item चे नाव सांगा.",
            "kn": "ಯಾವ item ತೆಗೆದುಹಾಕಬೇಕು? ದಯವಿಟ್ಟು item ಹೆಸರು ಹೇಳಿ.",
        }
        return templates.get(lang, templates["en"])

    @staticmethod
    def _t_modify(lang: str, item_name: str, modifier: str) -> str:
        templates = {
            "en": f"Sure, I've updated {item_name} to be {modifier}. Anything else?",
            "hi": f"Theek hai, maine {item_name} ko {modifier} kar diya. Aur kuch?",
            "gu": f"ઠીક છે, મેં {item_name} ને {modifier} કર્યું. બીજું કંઈ?",
            "mr": f"ठीक आहे, मी {item_name} ला {modifier} केले. अजून काही?",
            "kn": f"ಸರಿ, ನಾನು {item_name} ಅನ್ನು {modifier} ಮಾಡಿದ್ದೇನೆ. ಇನ್ನೇನಾದರೂ ಬೇಕೇ?",
        }
        return templates.get(lang, templates["en"])

    @staticmethod
    def _t_confirm(lang: str, total: float) -> str:
        total_str = str(int(total)) if total == int(total) else str(total)
        templates = {
            "en": f"Your order is confirmed. Total is {total_str} rupees, and I've sent it to the kitchen.",
            "hi": f"Aapka order confirm ho gaya. Total {total_str} rupees hai, aur maine kitchen ko bhej diya.",
            "gu": f"તમારો ઓર્ડર કન્ફર્મ થયો. કુલ {total_str} રૂપિયા છે અને મેં kitchen માં મોકલી દીધો.",
            "mr": f"तुमचा ऑर्डर confirm झाला. एकूण {total_str} रुपये आहेत आणि मी kitchen मध्ये पाठवला आहे.",
            "kn": f"ನಿಮ್ಮ order confirm ಆಗಿದೆ. ಒಟ್ಟು {total_str} rupees, ಮತ್ತು ನಾನು kitchen ಗೆ ಕಳಿಸಿದ್ದೇನೆ.",
        }
        return templates.get(lang, templates["en"])

    @staticmethod
    def _t_disambiguation(lang: str, opt_a: str, opt_b: str) -> str:
        templates = {
            "en": f"Did you mean {opt_a} or {opt_b}?",
            "hi": f"Aapko {opt_a} chahiye ya {opt_b}?",
            "gu": f"તમને {opt_a} જોઈએ છે કે {opt_b}?",
            "mr": f"तुम्हाला {opt_a} हवे आहे की {opt_b}?",
            "kn": f"ನಿಮಗೆ {opt_a} ಬೇಕೇ ಅಥವಾ {opt_b}?",
        }
        return templates.get(lang, templates["en"])

    @staticmethod
    def _t_no_speech(lang: str, has_session_items: bool = False) -> str:
        if has_session_items:
            templates = {
                "en": "I didn't hear anything. Would you like to add anything else or should I place the order?",
                "hi": "Mujhe kuch sunai nahi diya. Aur kuch add karna hai ya main order place kar doon?",
                "gu": "મને કંઈ સંભળાયું નહીં. બીજું કંઈ ઉમેરવું છે કે હું ઓર્ડર મૂકી દઉં?",
                "mr": "मला काही ऐकू आलं नाही. अजून काही जोडायचं आहे का, की मी ऑर्डर लावू?",
                "kn": "ನನಗೆ ಏನೂ ಕೇಳಿಸಲಿಲ್ಲ. ಇನ್ನೇನಾದರೂ ಸೇರಿಸಬೇಕೇ, ಇಲ್ಲವೇ ನಾನು order ಮಾಡಲೇ?",
            }
            return templates.get(lang, templates["en"])

        templates = {
            "en": "I didn't hear anything clearly. Please tell me your order once more.",
            "hi": "Mujhe kuch saaf sunai nahi diya. Kripya apna order phir se boliye.",
            "gu": "મને સાફ સંભળાયું નહીં. કૃપા કરીને તમારો ઓર્ડર ફરીથી કહો.",
            "mr": "मला स्पष्ट ऐकू आलं नाही. कृपया तुमचा ऑर्डर पुन्हा सांगा.",
            "kn": "ನನಗೆ ಸ್ಪಷ್ಟವಾಗಿ ಕೇಳಿಸಲಿಲ್ಲ. ದಯವಿಟ್ಟು ನಿಮ್ಮ order ಮತ್ತೆ ಹೇಳಿ.",
        }
        return templates.get(lang, templates["en"])

    @staticmethod
    def _t_audio_short(lang: str) -> str:
        templates = {
            "en": "That was too short. Please tell me your order a little more clearly.",
            "hi": "Woh bahut chhota tha. Kripya apna order thoda aur clearly boliye.",
            "gu": "એ બહુ ટૂંકો હતો. કૃપા કરીને તમારો ઓર્ડર થોડો વધુ સ્પષ્ટ કહો.",
            "mr": "ते खूप छोटं होतं. कृपया तुमचा ऑर्डर थोडा अधिक स्पष्ट सांगा.",
            "kn": "ಅದು ತುಂಬಾ ಚಿಕ್ಕದಾಗಿತ್ತು. ದಯವಿಟ್ಟು ನಿಮ್ಮ order ಸ್ವಲ್ಪ ಸ್ಪಷ್ಟವಾಗಿ ಹೇಳಿ.",
        }
        return templates.get(lang, templates["en"])

    @staticmethod
    def _t_done(lang: str) -> str:
        templates = {
            "en": "Would you like me to place the order now?",
            "hi": "Kya main order abhi place kar doon?",
            "gu": "હું હવે ઓર્ડર મૂકી દઉં?",
            "mr": "मी आता ऑर्डर लावू का?",
            "kn": "ನಾನು ಈಗ order ಮಾಡಲೇ?",
        }
        return templates.get(lang, templates["en"])

    @staticmethod
    def _t_done_empty(lang: str) -> str:
        templates = {
            "en": "I don't have any items yet. What would you like to order?",
            "hi": "Abhi mere paas koi item nahi hai. Aap kya order karna chahenge?",
            "gu": "હજુ મારી પાસે કોઈ item નથી. તમે શું ઓર્ડર કરશો?",
            "mr": "आत्तापर्यंत माझ्याकडे कोणतंही item नाही. तुम्हाला काय ऑर्डर करायचं आहे?",
            "kn": "ಇನ್ನೂ ನನ್ನ ಬಳಿ ಯಾವುದೇ item ಇಲ್ಲ. ನೀವು ಏನು order ಮಾಡುತ್ತೀರಿ?",
        }
        return templates.get(lang, templates["en"])

    @staticmethod
    def _t_no_match(lang: str) -> str:
        templates = {
            "en": "I couldn't find that on the menu. Could you please say it once more?",
            "hi": "Mujhe woh menu mein nahi mila. Kripya ek baar phir boliye.",
            "gu": "મને એ menu માં મળ્યું નહીં. કૃપા કરીને એક વાર ફરી કહો.",
            "mr": "मला ते menu मध्ये सापडलं नाही. कृपया एकदा पुन्हा सांगा.",
            "kn": "ನನಗೆ ಅದು menu ನಲ್ಲಿ ಸಿಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ.",
        }
        return templates.get(lang, templates["en"])

    @staticmethod
    def _t_out_of_stock(lang: str, item_name: str) -> str:
        templates = {
            "en": f"{item_name} is unavailable right now. Would you like something else instead?",
            "hi": f"{item_name} abhi available nahi hai. Kya aap kuch aur lena chahenge?",
            "gu": f"{item_name} હાલ ઉપલબ્ધ નથી. તેની બદલે બીજું કંઈ લેશો?",
            "mr": f"{item_name} सध्या उपलब्ध नाही. त्याऐवजी दुसरं काही घ्याल का?",
            "kn": f"{item_name} ಈಗ ಲಭ್ಯವಿಲ್ಲ. ಅದರ ಬದಲು ಇನ್ನೇನಾದರೂ ಬೇಕೇ?",
        }
        return templates.get(lang, templates["en"])

    async def get_response_text(self, pipeline_result: dict, detected_language: str) -> str:
        """Public entry point. Always returns speakable text."""
        lang = detected_language if detected_language in SUPPORTED_LANGS else "en"
        try:
            if self.should_use_llm(pipeline_result):
                return await self.generate(pipeline_result, lang)
            return self._fallback_template(pipeline_result, lang)
        except Exception as exc:
            logger.warning("Response text generation failed: %s", exc)
            return self._t_no_speech(lang, bool(pipeline_result.get("session_items")))


llm_generator = LLMResponseGenerator()
