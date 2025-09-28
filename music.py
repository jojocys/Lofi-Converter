"""
Simple audio processing module for Lofi Converter
Works without scipy or complex dependencies
"""
import os
from pydub import AudioSegment
from pydub.effects import speedup
import numpy as np

def msc_to_mp3_inf(wav_file):
    """
    Convert WAV file to MP3 format
    
    Args:
        wav_file: Path to WAV file
    
    Returns:
        Path to created MP3 file
    """
    try:
        # Load the WAV file
        audio = AudioSegment.from_wav(wav_file)
        
        # Create MP3 filename
        mp3_file = wav_file.replace('.wav', '.mp3')
        
        # Export as MP3 with good quality
        audio.export(mp3_file, format='mp3', bitrate="192k")
        
        return mp3_file
    except Exception as e:
        print(f"Error converting to MP3: {e}")
        # If conversion fails, return the original file
        return wav_file

def slowedreverb(input_file, output_file, room_size, damping, wet_level, dry_level, delay, slow_factor):
    """
    Apply lofi effects (slow + reverb) to audio file
    Using pydub for compatibility with Streamlit Cloud
    
    Args:
        input_file: Path to input audio file
        output_file: Path for output audio file
        room_size: Reverb room size (0.0 to 1.0)
        damping: Reverb damping (0.0 to 1.0)
        wet_level: Wet signal level (0.0 to 1.0)
        dry_level: Dry signal level (0.0 to 1.0)
        delay: Delay in milliseconds
        slow_factor: How much to slow down (0.0 to 0.3)
    """
    try:
        # Load the audio file
        audio = AudioSegment.from_wav(input_file)
        
        # Apply slow effect by changing frame rate
        if slow_factor > 0:
            # Calculate new frame rate (lower = slower)
            new_frame_rate = int(audio.frame_rate * (1 - slow_factor))
            
            # Change frame rate without changing pitch too much
            audio_slow = audio._spawn(audio.raw_data, overrides={
                "frame_rate": new_frame_rate
            })
            # Convert back to standard frame rate
            audio = audio_slow.set_frame_rate(audio.frame_rate)
        
        # Apply simple reverb effect using overlay
        if wet_level > 0 and delay > 0:
            # Create delayed version for reverb effect
            reverb = audio
            
            # Apply multiple delays for reverb simulation
            for i in range(3):
                delay_ms = delay * (i + 1)
                decay = room_size * (1 - damping) ** (i + 1)
                
                if decay > 0.01:  # Only add audible reverb
                    # Create delayed and attenuated version
                    delayed = AudioSegment.silent(duration=delay_ms) + reverb - (20 * (i + 1))
                    
                    # Mix with original
                    if len(delayed) > len(audio):
                        audio = audio.overlay(delayed[:len(audio)], position=0)
                    else:
                        audio = audio.overlay(delayed, position=0)
        
        # Adjust overall levels
        if dry_level < 1.0:
            audio = audio - int(20 * np.log10(max(dry_level, 0.01)))
        
        # Add some lofi character
        # Reduce high frequencies slightly for that warm lofi sound
        audio = audio.low_pass_filter(8000)
        
        # Add slight compression for consistency
        audio = audio.normalize()
        
        # Export the processed audio
        audio.export(output_file, format='wav')
        
        return output_file
        
    except Exception as e:
        print(f"Error processing audio: {e}")
        # If processing fails, just copy the original
        import shutil
        shutil.copy2(input_file, output_file)
        return output_file