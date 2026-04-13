import base64

from src.utils.globals import globals

try:
    from groq import Groq
except Exception:  # pragma: no cover
    Groq = None


VISION_MODEL_CANDIDATES = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    globals.vision_model,
    "llama-3.2-11b-vision-preview",
    "llama-3.2-90b-vision-preview",
]

def detect_crop_disease(image_bytes: bytes, user_prompt: str = "", session_id: str = "") -> str:
    """Analyze crop issue using Groq vision model (image + prompt)."""
    if not globals.groq_api_key:
        return "GROQ_API_KEY missing hai. .env me GROQ_API_KEY add karo."
    if Groq is None:
        return "Groq dependency missing hai. `uv sync` run karo."
    if not image_bytes:
        return "Image data empty mila. Dobara clear photo bhejo."
    try:
        print(f"[TOOL CALLED] session={session_id} tool=detect_crop_disease", flush=True)
        client = Groq(api_key=globals.groq_api_key)
        prompt = (
            "Tum agriculture disease advisor ho. Farmer ne crop image bheji hai.\n"
            "Image aur caption dono dekh kar Hinglish (Roman) me practical answer do.\n"
            "Format:\n"
            "1) Sambhavit bimari/issue\n"
            "2) Confidence (Low/Medium/High)\n"
            "3) Pehchan points (2-3)\n"
            "4) Turant steps (3-5)\n"
            "5) Spray/medicine (safe generic guidance)\n"
            "6) Kab expert ko dikhana hai\n"
            "Agar image unclear ho to clearly bolo aur better photo tips do.\n\n"
            f"Farmer symptoms/caption: {user_prompt.strip() or 'No caption provided'}"
        )

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        message_content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
        ]

        errors = []
        for model_name in dict.fromkeys(VISION_MODEL_CANDIDATES):
            try:
                print(
                    f"[MODEL TRY] session={session_id} tool=detect_crop_disease model={model_name}",
                    flush=True,
                )
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": message_content}],
                    temperature=0.2,
                )
                text = (response.choices[0].message.content or "").strip()
                if text:
                    print(
                        f"[MODEL OK] session={session_id} tool=detect_crop_disease model={model_name}",
                        flush=True,
                    )
                    return text
                errors.append(f"{model_name}: empty response")
            except Exception as model_error:
                errors.append(f"{model_name}: {model_error}")

        return (
            "Crop disease detection failed: koi Groq vision model response nahi de raha.\n"
            + "\n".join(errors)
            + "\nTip: .env me GROQ_VISION_MODEL set karke retry karo."
        )
    except Exception as e:
        return f"Crop disease detection error (Groq): {e}"
