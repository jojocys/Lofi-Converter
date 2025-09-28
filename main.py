import os
import streamlit as st
import music
import yt_dlp
import uuid
from typing import Optional, Tuple, Dict, Any
import logging
from contextlib import contextmanager
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
MAX_DURATION_SECONDS = 600
TEMP_DIR = "uploaded_files"
AUDIO_FORMAT = "bestaudio/best"
DEFAULT_SETTINGS = {
    "room_size": 0.75,
    "damping": 0.5,
    "wet_level": 0.08,
    "dry_level": 0.2,
    "delay": 2,
    "slow_factor": 0.08
}

class LofiConverter:
    """Main class for handling Lofi audio conversion"""
    
    def __init__(self):
        self.ensure_temp_dir()
    
    @staticmethod
    def ensure_temp_dir():
        """Ensure temporary directory exists"""
        Path(TEMP_DIR).mkdir(exist_ok=True)
    
    @contextmanager
    def temp_files_manager(self, *files):
        """Context manager for handling temporary files"""
        try:
            yield
        finally:
            for file in files:
                if file and os.path.exists(file):
                    try:
                        os.remove(file)
                        logger.info(f"Deleted temporary file: {file}")
                    except Exception as e:
                        logger.error(f"Error deleting file {file}: {e}")
    
    @st.cache_data(show_spinner=False, max_entries=5)
    def validate_youtube_url(_self, youtube_link: str) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        Validate if YouTube URL is downloadable and meets requirements
        
        Returns:
            Tuple of (is_valid, error_message, duration)
        """
        try:
            ydl_opts = {
                'format': 'bestaudio',
                'quiet': True,
                'noplaylist': True,
                'no_warnings': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(youtube_link, download=False)
                
                # Extract duration
                duration = info_dict.get('duration', 0)
                
                # Check if video is available
                if info_dict.get('is_live'):
                    return False, "Live streams are not supported", None
                
                if info_dict.get('private'):
                    return False, "Private videos are not accessible", None
                
                # Check duration
                if duration > MAX_DURATION_SECONDS:
                    minutes = duration // 60
                    return False, f"Video duration ({minutes:.1f} minutes) exceeds 10-minute limit", duration
                
                return True, None, duration
                
        except yt_dlp.utils.ExtractorError as e:
            error_msg = str(e)
            if "Video unavailable" in error_msg:
                return False, "Video is not available (may be private or region-locked)", None
            elif "age" in error_msg.lower():
                return False, "Age-restricted content cannot be downloaded", None
            else:
                return False, f"YouTube error: {error_msg[:100]}", None
        except Exception as e:
            logger.error(f"Validation error for {youtube_link}: {e}")
            return False, "Failed to validate YouTube URL. Please check the link.", None
    
    @st.cache_data(ttl=300, show_spinner=False)
    def download_youtube_audio(_self, youtube_link: str) -> Optional[Tuple[str, str, str, Dict[str, Any]]]:
        """
        Download YouTube audio and convert to appropriate format
        
        Returns:
            Tuple of (audio_file, mp3_file, song_name, metadata)
        """
        # Validate first
        is_valid, error_msg, duration = _self.validate_youtube_url(youtube_link)
        if not is_valid:
            st.error(error_msg)
            return None
        
        unique_id = str(uuid.uuid4())
        output_template = os.path.join(TEMP_DIR, f"{unique_id}.%(ext)s")
        
        try:
            ydl_opts = {
                'format': AUDIO_FORMAT,
                'outtmpl': output_template,
                'quiet': True,
                'noplaylist': True,
                'no_warnings': True,
                'prefer_ffmpeg': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '192',
                }]
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(youtube_link, download=True)
                audio_file = ydl.prepare_filename(info_dict).replace('.webm', '.wav').replace('.m4a', '.wav')
                
                # Extract metadata
                metadata = {
                    'title': info_dict.get('title', 'Unknown'),
                    'artist': info_dict.get('artist', info_dict.get('uploader', 'Unknown')),
                    'duration': duration,
                    'thumbnail': info_dict.get('thumbnail'),
                    'view_count': info_dict.get('view_count', 0)
                }
                
                # Convert to MP3 for preview
                mp3_file = music.msc_to_mp3_inf(audio_file)
                
                logger.info(f"Successfully downloaded: {metadata['title']}")
                return audio_file, mp3_file, metadata['title'], metadata
                
        except Exception as e:
            logger.error(f"Download error for {youtube_link}: {e}")
            st.error(f"Failed to download audio: {str(e)[:100]}")
            return None
    
    def process_audio(self, audio_file: str, settings: Dict[str, float]) -> Optional[str]:
        """
        Process audio with lofi effects
        
        Args:
            audio_file: Path to input audio file
            settings: Dictionary of effect parameters
            
        Returns:
            Path to processed audio file or None on error
        """
        try:
            output_file = os.path.splitext(audio_file)[0] + "_lofi.wav"
            
            music.slowedreverb(
                audio_file, 
                output_file,
                settings['room_size'],
                settings['damping'],
                settings['wet_level'],
                settings['dry_level'],
                settings['delay'],
                settings['slow_factor']
            )
            
            logger.info(f"Successfully processed audio with settings: {settings}")
            return output_file
            
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            st.error(f"Failed to process audio: {str(e)[:100]}")
            return None


def create_ui_components():
    """Create reusable UI components"""
    
    def render_header():
        """Render application header"""
        st.set_page_config(
            page_title="Lofi Converter",
            page_icon="🎵",
            layout="wide",
            initial_sidebar_state="collapsed"
        )
        
        # Custom CSS for better styling
        st.markdown("""
            <style>
            .main-header {
                text-align: center;
                padding: 1rem;
                background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                border-radius: 10px;
                color: white;
                margin-bottom: 2rem;
            }
            .stButton > button {
                background-color: #667eea;
                color: white;
                border-radius: 20px;
                padding: 0.5rem 2rem;
                border: none;
                transition: all 0.3s;
            }
            .stButton > button:hover {
                background-color: #764ba2;
                transform: translateY(-2px);
            }
            .info-card {
                background: #f0f2f6;
                padding: 1rem;
                border-radius: 10px;
                margin: 1rem 0;
            }
            .metric-card {
                background: white;
                padding: 0.8rem;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            </style>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="main-header"><h1>🎵 Lofi Converter</h1><p>Transform any song into a chill lofi version</p></div>', unsafe_allow_html=True)
        
        # Info columns
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info("🎧 Use headphones for best experience")
        with col2:
            st.info("⏱️ Max duration: 10 minutes")
        with col3:
            st.info("🎼 Supports YouTube & YouTube Music")
    
    def render_settings_panel() -> Dict[str, float]:
        """Render advanced settings panel"""
        with st.expander("⚙️ Advanced Settings", expanded=False):
            st.write("Fine-tune the lofi effect parameters:")
            
            # Preset buttons first
            st.subheader("🎨 Quick Presets")
            col1, col2, col3, col4 = st.columns(4)
            
            preset_selected = None
            if col1.button("🌙 Dreamy", use_container_width=True):
                preset_selected = {"room_size": 0.9, "damping": 0.3, "wet_level": 0.12, 
                                 "dry_level": 0.15, "delay": 5, "slow_factor": 0.12}
            if col2.button("☕ Chill", use_container_width=True):
                preset_selected = {"room_size": 0.6, "damping": 0.6, "wet_level": 0.06, 
                                 "dry_level": 0.25, "delay": 2, "slow_factor": 0.06}
            if col3.button("🌊 Ambient", use_container_width=True):
                preset_selected = {"room_size": 1.0, "damping": 0.2, "wet_level": 0.15, 
                                 "dry_level": 0.1, "delay": 8, "slow_factor": 0.15}
            if col4.button("🔄 Default", use_container_width=True):
                preset_selected = DEFAULT_SETTINGS
            
            if preset_selected:
                return preset_selected
            
            st.markdown("---")
            
            # Manual controls
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🏠 Reverb Settings")
                room_size = st.slider(
                    "Room Size",
                    min_value=0.1,
                    max_value=1.0,
                    value=DEFAULT_SETTINGS["room_size"],
                    step=0.05,
                    help="Larger values create a bigger space effect"
                )
                damping = st.slider(
                    "Damping",
                    min_value=0.1,
                    max_value=1.0,
                    value=DEFAULT_SETTINGS["damping"],
                    step=0.05,
                    help="Controls how quickly the reverb fades"
                )
                wet_level = st.slider(
                    "Wet Level",
                    min_value=0.0,
                    max_value=0.5,
                    value=DEFAULT_SETTINGS["wet_level"],
                    step=0.01,
                    help="Amount of reverb effect"
                )
            
            with col2:
                st.subheader("🎛️ Audio Settings")
                dry_level = st.slider(
                    "Dry Level",
                    min_value=0.0,
                    max_value=1.0,
                    value=DEFAULT_SETTINGS["dry_level"],
                    step=0.01,
                    help="Amount of original signal"
                )
                delay = st.slider(
                    "Delay (ms)",
                    min_value=0,
                    max_value=50,
                    value=DEFAULT_SETTINGS["delay"],
                    step=1,
                    help="Echo delay time"
                )
                slow_factor = st.slider(
                    "Slow Factor",
                    min_value=0.0,
                    max_value=0.3,
                    value=DEFAULT_SETTINGS["slow_factor"],
                    step=0.01,
                    help="How much to slow down the audio"
                )
            
            return {
                "room_size": room_size,
                "damping": damping,
                "wet_level": wet_level,
                "dry_level": dry_level,
                "delay": delay,
                "slow_factor": slow_factor
            }
    
    return render_header, render_settings_panel


def main():
    """Main application function"""
    # Initialize converter
    converter = LofiConverter()
    
    # Create UI components
    render_header, render_settings_panel = create_ui_components()
    
    # Render header
    render_header()
    
    # Session state initialization
    if 'processed_files' not in st.session_state:
        st.session_state.processed_files = []
    
    # Main input section
    youtube_link = st.text_input(
        "🔗 Enter YouTube URL:",
        placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        help="Paste any YouTube or YouTube Music link here"
    )
    
    if youtube_link:
        # Create placeholder for status messages
        status_placeholder = st.empty()
        
        try:
            # Download audio
            with st.spinner("🔄 Downloading audio from YouTube..."):
                download_result = converter.download_youtube_audio(youtube_link)
            
            if download_result:
                audio_file, mp3_base_file, song_name, metadata = download_result
                
                # Display song info
                st.success(f"✅ Successfully downloaded: **{song_name}**")
                
                # Display metadata in columns
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Artist", metadata.get('artist', 'Unknown'))
                with col2:
                    duration_min = metadata.get('duration', 0) / 60
                    st.metric("Duration", f"{duration_min:.1f} min")
                with col3:
                    views = metadata.get('view_count', 0)
                    st.metric("Views", f"{views:,}" if views else "N/A")
                
                # Audio players section
                st.markdown("---")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("🎵 Original Audio")
                    st.audio(mp3_base_file, format="audio/mp3")
                
                # Get user settings
                settings = render_settings_panel()
                
                # Process audio
                with st.spinner("🎛️ Applying lofi effects..."):
                    output_file = converter.process_audio(audio_file, settings)
                
                if output_file:
                    with col2:
                        st.subheader("🌙 Lofi Version")
                        lofi_mp3 = music.msc_to_mp3_inf(output_file)
                        st.audio(lofi_mp3, format="audio/mp3")
                    
                    # Download section
                    st.markdown("---")
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col2:
                        with open(lofi_mp3, 'rb') as f:
                            st.download_button(
                                label="⬇️ Download Lofi MP3",
                                data=f.read(),
                                file_name=f"{song_name}_lofi.mp3",
                                mime="audio/mp3",
                                use_container_width=True
                            )
                    
                    # Add to history
                    st.session_state.processed_files.append(song_name)
                    
                    # Clean up with context manager
                    with converter.temp_files_manager(audio_file, output_file, mp3_base_file, lofi_mp3):
                        pass
        
        except Exception as e:
            logger.error(f"Main function error: {e}")
            st.error(f"❌ An unexpected error occurred: {str(e)[:200]}")
            st.info("💡 Try refreshing the page and trying again")
    
    # Show processing history
    if st.session_state.processed_files:
        with st.sidebar:
            st.subheader("📜 Recent Conversions")
            for i, file in enumerate(reversed(st.session_state.processed_files[-10:]), 1):
                st.text(f"{i}. {file[:40]}...")
    
    # Instructions section at the bottom
    with st.expander("📖 How to Use", expanded=False):
        st.markdown("""
        1. **Copy a YouTube URL** - Find any song on YouTube or YouTube Music
        2. **Paste the URL** - Enter it in the text box above
        3. **Adjust Settings** (Optional) - Use presets or customize the effect parameters
        4. **Download** - Click the download button to save your lofi version
        
        **Tips:**
        - Songs under 10 minutes work best
        - Try different presets to find your preferred lofi style
        - The 'Dreamy' preset adds more reverb for a spacious feel
        - The 'Chill' preset is subtle and maintains clarity
        - The 'Ambient' preset creates an atmospheric, ethereal sound
        """)


if __name__ == "__main__":
    main()