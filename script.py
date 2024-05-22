import moviepy.editor as mp
import speech_recognition as sr 
import os 
from pydub import AudioSegment 
from pydub.silence import split_on_silence 
import queue    # For Python 2.x use 'import Queue as queue'
import threading, time, random
import vid2cleantxt
import whisper_timestamped as whisper
from pydub import AudioSegment
import json
from profanity_check import predict, predict_prob


def generate_audio_from_video(video_path):
  video = mp.VideoFileClip(video_path)
  
  audio_file = video.audio
  audio_file.write_audiofile("audio_file.wav")

  return "audio_file.wav"

def splice_audio_into_chunks(path):
  song = AudioSegment.from_wav(path)

  chunks = split_on_silence(song, 
    # must be silent for at least 0.5 seconds 
    # or 500 ms. adjust this value based on user 
    # requirement. if the speaker stays silent for  
    # longer, increase this value. else, decrease it. 
    min_silence_len = 1000, 

    # consider it silent if quieter than -16 dBFS 
    # adjust this per requirement 
    silence_thresh = -16,
    keep_silence=200
  ) 
  
  try: 
    os.mkdir('audio_chunks') 
  except(FileExistsError): 
    pass
  
  return chunks

def recognize_chunks(chunks):
  fh = open("recognized.txt", "w+")

  os.chdir("audio_chunks")

  i = 0
  
  for chunk in chunks:
    chunk_silent = AudioSegment.silent(duration = 10) 

    audio_chunk = chunk_silent + chunk + chunk_silent
    print("saving chunk{0}.wav".format(i)) 
    audio_chunk.export("./chunk{0}.wav".format(i), bitrate ='192k', format ="wav") 
    filename = 'chunk'+str(i)+'.wav'
  
    print("Processing chunk "+str(i)) 

    # get the name of the newly created chunk 
    # in the AUDIO_FILE variable for later use. 
    file = filename 

    # create a speech recognition object 
    r = sr.Recognizer() 

    # recognize the chunk 
    with sr.AudioFile(file) as source: 
        # remove this if it is not working 
        # correctly. 
        r.adjust_for_ambient_noise(source) 
        audio_listened = r.listen(source) 

    try: 
      # try converting it to text 
      rec = r.recognize_google(audio_listened) 
      # write the output to the file. 
      fh.write(rec+". ") 
    except sr.UnknownValueError: 
          print("Could not understand audio") 

    except sr.RequestError as e: 
        print("Could not request results. check your internet connection") 

    i += 1

    os.chdir('..')

if __name__ == '__main__': 
  video_path = "video.mp4"
  # text_output_dir, metadata_output_dir = vid2cleantxt.transcribe.transcribe_dir(
  #   input_dir="./",
  #   model_id="openai/whisper-base.en",
  #   chunk_length=30,
  # )

  model = whisper.load_model("base")
  audio = whisper.load_audio('video.mp4')

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

  start = 0
  audio_file = generate_audio_from_video(video_path)
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

  # TODO: COMBINE ALL COMBINED AUDIOS

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
  




  """"
  audio_file= "your_wav_file.wav"
  audio = AudioSegment.from_wav(audio_file)
  list_of_timestamps = [ 10, 20, 30, 40, 50 ,60, 70, 80, 90 ] #and so on in *seconds*

  start = ""
  for  idx,t in enumerate(list_of_timestamps):
      #break loop if at last element of list
      if idx == len(list_of_timestamps):
          break

      end = t * 1000 #pydub works in millisec
      print("split at [ {}:{}] ms".format(start, end))
      audio_chunk=audio[start:end]
      audio_chunk.export( "audio_chunk_{}.wav".format(end), format="wav")

      start = end * 1000 #pydub works in millisec

  #audio_file = generate_audio_from_video(video_path)
  #chunks = splice_audio_into_chunks(audio_file)
  #recognize_chunks(chunks)
  #silence_based_conversion(audio_file)
  """