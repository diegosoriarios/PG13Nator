import moviepy.editor as mp
import os 
from pydub import AudioSegment 
import whisper_timestamped as whisper
from pydub import AudioSegment
import json
from profanity_check import predict_prob
from moviepy.editor import VideoFileClip
import shutil
import argparse

def generate_audio_from_video(video_path):
  video = mp.VideoFileClip(video_path)
  
  audio_file = video.audio
  audio_file.write_audiofile("audio_file.wav")

  return "audio_file.wav"

def transcribe_video(video):
  model = whisper.load_model("base")
  audio = whisper.load_audio(video)

  result = whisper.transcribe(model, audio, language="en")
  with open('data.txt', 'w') as f:
    json.dump(result, f, ensure_ascii = False)

  sentences = result["segments"]
  list_of_timestamps = []
  for sentence in sentences:
    for words in sentence["words"]:
      word = words["text"]
      value = predict_prob([word])
      if value[0] >= .9:
         timestamp_start = words["start"]
         timestamp_end = words["end"]
         print(word + ":" + str(timestamp_start) + "-" + str(timestamp_end))
         list_of_timestamps.append({
            "start": timestamp_start,
            "end": timestamp_end
          })
  
  return list_of_timestamps

def splice_audio_into_chunks(video, list_of_timestamps):
  start = 0
  audio_file = generate_audio_from_video(video)
  audio = AudioSegment.from_wav(audio_file)
  try: 
    os.mkdir('audio_chunks') 
  except(FileExistsError): 
    pass
  os.chdir('audio_chunks')
  index = 1
  for timestamps in list_of_timestamps:
    end = timestamps['start'] * 1000

    audio_chunk=audio[start:end]
    audio_chunk.export(str(index) + "audio_chunk_{}.wav".format(end), format="wav")

    start = timestamps['end'] * 1000
    silence_duration = start - end
    silence = AudioSegment.silent(duration=silence_duration)
    silence.export("silence_" + str(index) + "audio_chunk_{}.wav".format(end), format="wav")
    index += 1
    pass
  #get last chunk
  last_chunk = list_of_timestamps[-1]['end'] * 1000
  end_of_file = audio.duration_seconds * 1000
  print(str(last_chunk))
  audio_chunk=audio[last_chunk:end_of_file]
  os.chdir('..')
  audio_chunk.export("last_audio_chunk.wav", format="wav")

def combine_chunks_with_silence():
  dir_list = os.listdir('audio_chunks')
  print(sorted(dir_list))
  try: 
    os.mkdir('combined_audio') 
  except(FileExistsError): 
    pass
  os.chdir('combined_audio')
  index = 1
  for file in sorted(dir_list):
    if "silence" in file:
      continue
    if "last_" in file:
      continue  
    sound1 = AudioSegment.from_file("../audio_chunks/" + file, format="wav")
    sound2 = AudioSegment.from_file("../audio_chunks/silence_" + file, format="wav")
    combined = sound1 + sound2
    combined.export("combined{}.wav".format(index), format="wav")
    index += 1
  
  os.chdir('..')

def combine_all_audio_chunks():
  dir_list = sorted(os.listdir('combined_audio'))
  os.chdir('combined_audio')
  print(dir_list)
  index = 1
  sound1 = AudioSegment.from_file(dir_list[0], format="wav")
  combined = None
  while index < len(dir_list):
    sound2 = AudioSegment.from_file(dir_list[index], format="wav")
    combined = sound1 + sound2
    sound1 = combined
    index += 1

  os.chdir('..')
  last_chunk = AudioSegment.from_file('last_audio_chunk.wav', format="wav")
  combined = combined + last_chunk
  combined.export("final_audio.wav", format="wav")

def remove_audio_from_video(video):
  videoclip = VideoFileClip(video)
  new_clip = videoclip.without_audio()
  new_clip.write_videofile("no_audio_video.mp4")

def add_new_audio_to_video():
  no_audio_clip = mp.VideoFileClip('no_audio_video.mp4')
  new_audio = mp.AudioFileClip('final_audio.wav')
  final = no_audio_clip.set_audio(new_audio)
  final.write_videofile("output.mp4")

def remove_temp_files():
  shutil.rmtree("audio_chunks")
  shutil.rmtree("combined_audio")
  os.remove("audio_file.wav")
  os.remove("final_audio.wav")
  os.remove("last_audio_chunk.wav")
  os.remove("no_audio_video.mp4")
  os.remove("data.txt")

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='video')
  parser.add_argument('--video', action="store", dest='video', default=None)
  args = parser.parse_args()
  video_path = args.video

  list_of_timestamps = transcribe_video(video_path)
  splice_audio_into_chunks(video_path, list_of_timestamps)
  combine_chunks_with_silence()
  combine_all_audio_chunks()
  remove_audio_from_video(video_path)
  add_new_audio_to_video()
  remove_temp_files()