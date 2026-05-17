import os
import streamlit as st
import uuid

from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools.eleven_labs import ElevenLabsTools
from agno.tools.firecrawl import FirecrawlTools
from agno.utils.audio import write_audio_to_file
from agno.utils.log import logger



st.set_page_config(page_title="Article to podcast Agent")
st.title("end to end agent")

st.sidebar.header("API keys")

groq_api_key = st.sidebar.text_input("Groq API keys", type="password")
elevenlabs_api_key = st.sidebar.text_input("elevenlabs API keys", type="password")
firecrawl_api_key = st.sidebar.text_input("Firecrawl API keys", type="password")

# Default ElevenLabs voice ID fallback for free-tier-compatible voices
selected_eleven_voice_id = "JBFqnCBsd6RMkjVDRZzb"

if elevenlabs_api_key:
    try:
        voice_client = ElevenLabsTools(
            api_key=elevenlabs_api_key,
            target_directory="audio_generations",
            enable_get_voices=False,
            enable_generate_sound_effect=False,
            enable_text_to_speech=False,
        )
        voice_response = voice_client.eleven_labs_client.voices.search(
            voice_type="non-community",
            page_size=50,
        )
        available_voices = getattr(voice_response, "voices", None) or []

        if not available_voices:
            voice_response = voice_client.eleven_labs_client.voices.get_all(show_legacy=False)
            available_voices = getattr(voice_response, "voices", None) or []

        personal_voices = [voice for voice in available_voices if getattr(voice, "is_owner", False)]
        voice_list = personal_voices or available_voices

        if voice_list:
            voice_options = {
                f"{voice.name or voice.voice_id} ({voice.category or 'unknown'})": voice.voice_id
                for voice in voice_list
            }
            selected_label = st.sidebar.selectbox(
                "Choose ElevenLabs voice",
                options=list(voice_options.keys()),
                index=0,
            )
            selected_eleven_voice_id = voice_options[selected_label]
        else:
            st.sidebar.warning(
                "No compatible ElevenLabs voices were found. Please add a personal voice in your ElevenLabs account."
            )
    except Exception as e:
        st.sidebar.warning(f"Unable to fetch ElevenLabs voices: {e}")

keys_provided = all([groq_api_key, elevenlabs_api_key, firecrawl_api_key])

url = st.text_input("Enter the Url of the site", "")
generate_button = st.button("generate podcast", disabled=not keys_provided)

if not keys_provided:
  st.warning("please enter all the keys to proceed")

if generate_button:
  if url.strip()== "":
    st.warning("please eneter a blog/post/article url")
  else:
    os.makedirs("audio_generations", exist_ok=True)

    os.environ["GROQ_API_KEY"]= groq_api_key
    os.environ["ELEVENLABS_API_KEY"]= elevenlabs_api_key
    os.environ["FIRECRAWL_API_KEY"]= firecrawl_api_key

    with st.spinner("Processing... scraping blogs, summarising and generating podcast"):
      try:
        # Step 1: Scrape manually and truncate
        from firecrawl import FirecrawlApp
        firecrawl = FirecrawlApp(api_key=firecrawl_api_key)
        scraped = firecrawl.scrape(url)
        raw_text = scraped.markdown or scraped.content or str(scraped)
                
                # Truncate to first 2000 characters only
        truncated_text = raw_text[:2000]
        blog_to_podcast_agent= Agent(
          name="blogs to podcast Agent",
          model=Groq(id="llama-3.3-70b-versatile"),
          tools=[
            ElevenLabsTools(
              api_key=elevenlabs_api_key,
              voice_id=selected_eleven_voice_id,
              model_id="eleven_multilingual_v2",
              target_directory="audio_generations",
            ),
          ],
          description="You are An AI agent that can generate audio using the elevenlabs API",
          instructions=[
            "You are an AI agent that converts blog posts into podcasts.",
            "Steps you MUST follow strictly:",
            "1. Read the blog content provided.",
            "2. Generate a longer conversational podcast script of around 700-900 characters.",
            "3. Use ONLY plain text - no markdown, asterisks, formatting, or special characters.",
            "4. Call the text_to_speech tool with this plain text summary as the prompt parameter.",
            "5. Pass the summary text DIRECTLY to text_to_speech using prompt='Your summary here'.",
            "6. Do NOT use any other tools - only text_to_speech.",
            "7. Return only the audio output, not the text summary.",
          ],
          markdown= True,
          debug_mode= False,
        )

        podcast= blog_to_podcast_agent.run(
          f"Convert the blog content to a podcast: {truncated_text}"
        )

        save_dir="audio_generations"
        os.makedirs(save_dir, exist_ok=True)

        if podcast.audio and len(podcast.audio)> 0:
          filename =f"{save_dir}/podcast_{uuid.uuid4()}.mp3"
        import glob
        audio_files = glob.glob("audio_generations/*.mp3") + glob.glob("audio_generations/*.wav")

        if audio_files:
          latest_file = max(audio_files, key=os.path.getctime)  # get most recent file
          st.success("Podcast generated successfully!")
          audio_bytes = open(latest_file, "rb").read()
          st.audio(audio_bytes, format="audio/mp3")
          st.download_button(
            label="Download Podcast",
            data=audio_bytes,
            file_name="generated_podcast.mp3",
            mime="audio/mp3"
        )
        else:
          st.error("No audio was generated. Please try again.")

      except Exception as e:
        error_str = str(e)
        if "401" in error_str or "unusual_activity" in error_str or "Free Tier" in error_str:
          st.error("ElevenLabs API Error: Your free tier account has been blocked for unusual activity.")
          st.info("Solutions:\n" +
                  "1. Try using a different network (not VPN/proxy)\n" +
                  "2. Upgrade to a paid ElevenLabs plan\n" +
                  "3. Create a new ElevenLabs account with a different email\n" +
                  "4. Wait 24 hours and try again\n" +
                  f"\nOriginal error: {e}")
        elif "400" in error_str or "tool_use_failed" in error_str:
          st.error("Groq API Error: Failed to call text_to_speech function correctly.")
          st.info("This usually means the function parameters are malformed. Please try again.")
          logger.error(f"Groq function call error:{e}")
        else:
          st.error(f"An error occurred: {e}")
        logger.error(f"streamlit app error:{e}")
           