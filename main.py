import os
import streamlit as st
import uuid

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.eleven_labs import ElevenLabsTools
from agno.tools.firecrawl import FirecrawlTools
from agno.utils.audio import write_audio_to_file
from agno.utils.log import logger



st.set_page_config(page_title="Article to podcast Agent")
st.title("end to end agent")

st.sidebar.header("API keys")

openai_api_key =st.sidebar.text_input("OpenAi API keys", type="password")
elevenlabs_api_key =st.sidebar.text_input("elevenlabs API keys", type="password")
firecrawl_api_key =st.sidebar.text_input("Firecrawl API keys", type="password")

keys_provided= all([openai_api_key, elevenlabs_api_key, firecrawl_api_key])

url= st.text_input("Enter the Url of the site", "")
generate_button = st.button("generate podcast", disabled=not keys_provided)

if not keys_provided:
  st.warning("please enter all the keys to proceed")

if generate_button:
  if url.strip()== "":
    st.warning("please eneter a blog/post/article url")
  else:
    os.environ["OPENAI_API_KEY"]= openai_api_key
    os.environ["ELEVENLABS_API_KEY"]= elevenlabs_api_key
    os.environ["FIRECRAWL_API_KEY"]= firecrawl_api_key

    with st.spinner("Processing... scraping blogs, summarising and generating podcast"):
      try:
        blog_to_podcast_agent= Agent(
          name="blogs to podcast Agent",
          model=OpenAIChat(id="gpt-4o"),
          tools=[
            ElevenLabsTools(
              voice_id="opjyhbtor76cutnqwgdtc",
              model_id="eleven_multilingual_v2",
              target_directory="audio_generation"
            ),
            FirecrawlTools(),
          ],
          description="You are An AI agent that can generate audio using the elevenlabs API",
          instructions=[
            instructions=[
    "You are an AI agent that converts blog posts into podcasts.",
    "Steps you MUST follow strictly:",
    "1. Use FirecrawlTools to scrape the full blog content from the URL.",
    "2. Summarize the blog in a conversational podcast tone.",
    "3. Ensure the summary is UNDER 1500 characters.",
    "4. You MUST call ElevenLabsTools to convert the summary into audio.",
    "5. Return ONLY the generated audio output."
          ],
          markdown= True,
          debug_mode= True
        )

        podcast= blog_to_podcast_agent.run(
          f"Convert the blog content to a podcast: {url}"
        )

        st.write(podcast)
        
        save_dir="audio_generations"
        os.makedirs(save_dir, exist_ok=True)

        if podcast.audio and len(podcast.audio)> 0:
          filename =f"{save_dir}/podcast_{uuid.uuid4()}.wav"
          write_audio_to_file(
            audio=podcast.audio[0].base64_audio,
            filename=filename
          )

          st.success("podcast generated successfully!")
          audio_bytes = open(filename, "rb").read()

          st.audio(audio_bytes, format="audio/wav")

          st.download_button(
            label="Download podcast",
            data= audio_bytes,
            file_name="generated_podcast.wav",
            mime="audio/wav"
          )

        else:
          st.error("No audio was generated. please try again")

      except Exception as e:
        st.error(f"An error occured :{e}")
        logger.error(f"streamlit app error:{e}")
          