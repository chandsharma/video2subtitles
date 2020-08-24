import io
import subprocess
from pydub.utils import mediainfo
import subprocess
import math
import datetime
import srt
import speech_recognition as sr
import os
#from google.cloud import storage
import json
from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
from google.cloud import speech_v1

os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="speechcaption-73406c9ba1ee.json"



def video_info(video_filepath):
    """ this function returns number of channels, bit rate, and sample rate of the video"""
    #print(video_filepath)
    video_data = mediainfo(video_filepath)
    #print(video_data)
    bit_rate = video_data["bit_rate"]
    sample_rate = video_data["sample_rate"]
    channels = video_data["channels"]
    #video_to_audio(video_filepath,"converted.wav",channels,bit_rate,sample_rate)
    return channels, bit_rate, sample_rate

def video_to_audio(video_filepath, audio_filename, video_channels, video_bit_rate, video_sample_rate):
    command = f"ffmpeg -i {video_filepath} -b:a {video_bit_rate} -ac {video_channels} -ar {video_sample_rate} -vn {audio_filename}"
    subprocess.call(command, shell=True)
    blob_name = f"audios/{audio_filename}"
    from pydub import AudioSegment
    sound = AudioSegment.from_file(audio_filename)
    sound.export(audio_filename, format="wav", bitrate="128k")
    #audio_to_text(audio_filename)
    #upload_blob(BUCKET_NAME, audio_filename, blob_name)
    #return blob_name
    return audio_filename


def long_running_recognize(storage_uri, channels, sample_rate):

    client = speech_v1.SpeechClient()

    config = {
        "language_code": "en-US",
        "sample_rate_hertz": int(sample_rate),
        "encoding": enums.RecognitionConfig.AudioEncoding.LINEAR16,
        "audio_channel_count": int(channels),
        "enable_word_time_offsets": True,
        "model": "video",
        "enable_automatic_punctuation":True
    }
    audio = {"uri": storage_uri}

    operation = client.long_running_recognize(config, audio)

    print(u"Waiting for operation to complete...")
    response = operation.result()
    return response

def subtitle_generation(speech_to_text_response, bin_size=3):
    """We define a bin of time period to display the words in sync with audio.
    Here, bin_size = 3 means each bin is of 3 secs.
    All the words in the interval of 3 secs in result will be grouped togather."""
    transcriptions = []
    index = 0

    for result in response.results:
        try:
            if result.alternatives[0].words[0].start_time.seconds:
                # bin start -> for first word of result
                start_sec = result.alternatives[0].words[0].start_time.seconds
                start_microsec = result.alternatives[0].words[0].start_time.nanos * 0.001
            else:
                # bin start -> For First word of response
                start_sec = 0
                start_microsec = 0
            end_sec = start_sec + bin_size # bin end sec

            # for last word of result
            last_word_end_sec = result.alternatives[0].words[-1].end_time.seconds
            last_word_end_microsec = result.alternatives[0].words[-1].end_time.nanos * 0.001

            # bin transcript
            transcript = result.alternatives[0].words[0].word

            index += 1 # subtitle index

            for i in range(len(result.alternatives[0].words) - 1):
                try:
                    word = result.alternatives[0].words[i + 1].word
                    word_start_sec = result.alternatives[0].words[i + 1].start_time.seconds
                    word_start_microsec = result.alternatives[0].words[i + 1].start_time.nanos * 0.001 # 0.001 to convert nana -> micro
                    word_end_sec = result.alternatives[0].words[i + 1].end_time.seconds
                    word_end_microsec = result.alternatives[0].words[i + 1].end_time.nanos * 0.001

                    if word_end_sec < end_sec:
                        transcript = transcript + " " + word
                    else:
                        previous_word_end_sec = result.alternatives[0].words[i].end_time.seconds
                        previous_word_end_microsec = result.alternatives[0].words[i].end_time.nanos * 0.001

                        # append bin transcript
                        transcriptions.append(srt.Subtitle(index, datetime.timedelta(0, start_sec, start_microsec), datetime.timedelta(0, previous_word_end_sec, previous_word_end_microsec), transcript))

                        # reset bin parameters
                        start_sec = word_start_sec
                        start_microsec = word_start_microsec
                        end_sec = start_sec + bin_size
                        transcript = result.alternatives[0].words[i + 1].word

                        index += 1
                except IndexError:
                    pass
            # append transcript of last transcript in bin
            transcriptions.append(srt.Subtitle(index, datetime.timedelta(0, start_sec, start_microsec), datetime.timedelta(0, last_word_end_sec, last_word_end_microsec), transcript))
            index += 1
        except IndexError:
            pass

    # turn transcription list into subtitles
    subtitles = srt.compose(transcriptions)
    return subtitles

def audio_to_text(audio_file):
    r = sr.Recognizer()
    #mic = sr.Microphone()
    mic = sr.AudioFile(audio_file)
    try:
        print("Calibrating to the Environment.... Starting few seconds may cut")
        with mic as source:
            r.adjust_for_ambient_noise(source)
        print("Now Convering....")
        #r.dynamic_energy_threshold = True
        #r.dynamic_energy_adjustment_damping = 0.15
        r.non_speaking_duration = 0.1
        r.pause_threshold = 0.1
        r.phrase_threshold = 0.1
        while True:
            with mic as source:
                with open("caption.txt", "w") as f:
                    while True:
                        audio = r.listen(source)
                        #print(audio)
                        #print("Single line Heard")
                        try:
                            # recognize speech using Google Speech Recognition
                            value = r.recognize_google(audio,language="en-IN")

                            # we need some special handling here to correctly print unicode characters to standard output
                            if str is bytes:  # this version of Python uses bytes for strings (Python 2)
                                print(u"{}".format(value).encode("utf-8"))
                                print("")
                                f.write(value)
                                f.write('\n')
                            else:  # this version of Python uses unicode for strings (Python 3+)
                                print("{}".format(value))
                                print("")
                                f.write(value)
                                f.write('\n')
                        except sr.UnknownValueError:
                            print("......")
                        except sr.RequestError as e:
                            print("Uh oh! Couldn't request results from Google Speech Recognition service; {0}".format(e))


    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    print('Enter the Video file path')
    path = input()
    c,b,s = video_info(path)
    response=long_running_recognize(path, c, s)
    subtitles= subtitle_generation(response)
    with open("subtitles.srt", "w") as f:
        f.write(subtitles)
