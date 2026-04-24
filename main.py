import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import replicate

# Logging mínimo
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuración desde variables de entorno (Render las inyecta)
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
REPLICATE_API_TOKEN = os.environ["REPLICATE_API_TOKEN"]
RENDER_EXTERNAL_URL = os.environ["RENDER_EXTERNAL_URL"]  # Render la da automáticamente
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

# Modelo de Stable Video Diffusion (igual al bot original)
MODEL_ID = "stability-ai/stable-video-diffusion:3f0457e461e01e9f9c949b85059e1e8333b0bb3e6cfbd94e2ae41b3f24b32b7c"

# Flask para recibir webhooks
app_flask = Flask(__name__)

# Handlers del bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *VixAI Video Maker*\n"
        "Crea videos a partir de texto con IA.\n\n"
        "Comandos:\n"
        "/generate <descripción> – Genera un video\n"
        "/help – Muestra esta ayuda",
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Envía /generate seguido de tu idea.\n"
        "Ejemplo: `/generate un gato volando sobre un río de lava`\n"
        "El video tardará unos segundos en procesarse."
    )

async def generate_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_prompt = " ".join(context.args)
    if not user_prompt:
        await update.message.reply_text("❌ Debes escribir un prompt después de /generate.")
        return

    status_msg = await update.message.reply_text("⏳ Generando video... Esto puede tardar 15-30 segundos.")
    try:
        output = replicate.run(
            MODEL_ID,
            input={
                "prompt": user_prompt,
                "num_frames": 25,
                "fps": 8,
                "negative_prompt": "text, watermark, blurry, distorted",
                "num_inference_steps": 25,
            }
        )
        video_url = output[0] if isinstance(output, list) else output
        await update.message.reply_video(video=video_url, caption=f"🎥 *{user_prompt}*", parse_mode="Markdown")
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Error en generación: {e}")
        await status_msg.edit_text("⚠️ Error al generar el video. Intenta de nuevo.")

# Crear la aplicación de Telegram
ptb_app = Application.builder().token(TELEGRAM_TOKEN).build()
ptb_app.add_handler(CommandHandler("start", start))
ptb_app.add_handler(CommandHandler("help", help_command))
ptb_app.add_handler(CommandHandler("generate", generate_video))

# Ruta para el webhook
@app_flask.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), ptb_app.bot)
    ptb_app.update_queue.put_nowait(update)
    return "ok", 200

@app_flask.route("/")
def index():
    return "VixAI Bot is running", 200

async def main():
    # Inicializar la aplicación PTB
    await ptb_app.initialize()
    # Configurar el webhook de Telegram
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
    await ptb_app.bot.set_webhook(url=webhook_url)
    logger.info(f"Webhook configurado: {webhook_url}")
    # Iniciar la app de Flask en el puerto que Render asigna
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
